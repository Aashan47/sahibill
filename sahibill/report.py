"""Reports: several bill photos of one household, read in the background and checked together.

A report keeps only what is needed to recompute it: the photos' hashes, their status, the user's answers
and corrections. Readings live in the readings store (one file per photo hash), so a photo is read once and
every later view, answer or correction re-runs the checks from it without a model call.

Household rules (10-PRODUCT-DESIGN.md): bills are ordered by billing month; for consecutive months the
earlier bill's reading date fills a missing previous reading date, and the earlier present reading must
equal the later previous reading (a chain note, not a NEPRA violation). Photos of the same billing month are
merged field by field: kept where they agree, held where they differ.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sahibill.pipeline import analyze_reading
from sahibill.readers.agree import NUMERIC, _norm
from sahibill.readers.bill import FIELDS, month_key, num, read_bill
from sahibill.readers import quality
from sahibill.rules.consumption import ASK_MISREAD
from sahibill.readers.llm import CACHE, BudgetExceeded

READINGS = CACHE / "readings"
REPORTS = CACHE / "reports"
UPLOADS = CACHE / "uploads"
LLM_CACHE = CACHE / "llm"
SAMPLES = Path(__file__).resolve().parents[1] / "web" / "static" / "samples"
SAMPLE_READINGS = SAMPLES / "readings"      # committed: synthetic bills, no personal details
PROTECTED_LINE = 200
MAX_PHOTOS = 12
PAUSED = {"en": "Checking new photos is paused on this server for now. Your photo is saved; try again later, or open a sample bill.",
          "ur": "اس سرور پر نئی تصاویر کی جانچ ابھی رکی ہوئی ہے۔ آپ کی تصویر محفوظ ہے؛ بعد میں دوبارہ کوشش کریں، یا نمونے کا بل کھولیں۔"}


UNREADABLE = {"en": "This photo could not be read. Please take it again, flat and in daylight.",
              "ur": "یہ تصویر پڑھی نہیں جا سکی۔ براہ کرم بل سیدھا رکھ کر، دن کی روشنی میں دوبارہ تصویر لیں۔"}


class RetakeNeeded(Exception):
    """The photo is too blurred to read reliably (readers/quality.py); ask for a retake before any model call."""

_lock = threading.RLock()
_reports: dict[str, dict] = {}
_pool = ThreadPoolExecutor(max_workers=3)


# ---------- readings store ----------

def photo_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stored_reading(sha: str) -> dict | None:
    """A saved reading for this photo: fixtures first (fixture mode), then samples, then the readings store."""
    fixtures = os.environ.get("SAHIBILL_FIXTURES")
    places = ([Path(fixtures) / f"{sha[:24]}.json"] if fixtures else []) + \
             [SAMPLE_READINGS / f"{sha[:24]}.json", READINGS / f"{sha}.json"]
    for p in places:
        if p.exists():
            return json.loads(p.read_text())
    return None


def get_reading(sha: str, path: Path) -> tuple[dict, bool]:
    """The photo's reading and whether it was read just now: saved if it exists, else one paid read
    (budget-capped) that is then saved. In fixture mode a photo without a saved reading fails; no model is called."""
    saved = stored_reading(sha)
    if saved is not None:
        return saved, False
    try:
        gate = quality.check(path)
    except Exception:   # noqa: BLE001  (not decodable as an image: the reader reports it)
        gate = {"ok": True}
    if not gate["ok"]:
        raise RetakeNeeded(gate.get("sharpness"))
    if os.environ.get("SAHIBILL_FIXTURES"):
        raise LookupError("No saved reading for this photo (fixture mode).")
    raw = read_bill(path, reasoning_effort="low", tag="app")
    READINGS.mkdir(parents=True, exist_ok=True)
    (READINGS / f"{sha}.json").write_text(json.dumps(raw, ensure_ascii=False))
    return raw, True


def _cost(raw: dict) -> float:
    calls = [raw.get("_call") or {}, ((raw.get("_first_pass") or {}).get("_call")) or {}]
    return round(sum(c.get("usd") or 0 for c in calls if c and not c.get("cached")), 5)


# ---------- report state ----------

def _path(rid: str) -> Path:
    return REPORTS / f"{rid}.json"


def _save(state: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    _path(state["id"]).write_text(json.dumps(state, ensure_ascii=False))


def _state(rid: str) -> dict | None:
    if not re.fullmatch(r"[0-9a-f]{12,32}", rid or ""):      # ids go into file paths: accept only our own form
        return None
    with _lock:
        if rid not in _reports and _path(rid).exists():
            _reports[rid] = json.loads(_path(rid).read_text())
        return _reports.get(rid)


def create(photos: list[tuple[str, bytes]], household: bool = True, background: bool = True) -> str:
    """photos: [(file name, bytes)]. Saves each photo and starts reading it; returns the report id."""
    if not 1 <= len(photos) <= MAX_PHOTOS:
        raise ValueError(f"Send 1 to {MAX_PHOTOS} photos.")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    # 122 random bits: a report's link is the only key to its photos
    state = {"id": uuid.uuid4().hex, "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "household": household,
             "photos": [], "answers": {}, "overrides": {}}
    for i, (name, data) in enumerate(photos, 1):
        sha = photo_sha(data)
        suffix = ".png" if data[:4] == b"\x89PNG" else ".jpg"
        path = UPLOADS / f"{sha[:24]}{suffix}"
        if not path.exists():
            path.write_bytes(data)
        else:
            os.utime(path)        # in use again: restart its retention clock
        state["photos"].append({"id": f"b{i}", "name": Path(name or f"photo-{i}").name, "sha": sha,
                                "file": path.name, "status": "queued", "error": None, "cost_usd": 0.0})
    with _lock:
        _reports[state["id"]] = state
        _save(state)
    for p in state["photos"]:
        if background:
            _pool.submit(_read_photo, state["id"], p["id"])
        else:
            _read_photo(state["id"], p["id"])
    return state["id"]


def sweep(days: float) -> int:
    """Delete reports, uploaded photos, their readings and cached model answers older than `days`. Returns the count."""
    cutoff = time.time() - days * 86400
    n = 0
    with _lock:
        keep = set()      # photos and readings a surviving report still points at
        for f in REPORTS.glob("*.json") if REPORTS.is_dir() else []:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                n += 1
                continue
            try:
                keep |= {x for p in json.loads(f.read_text()).get("photos", []) for x in (p["file"], f"{p['sha']}.json")}
            except (ValueError, KeyError, TypeError):
                pass
        for d in (UPLOADS, READINGS, LLM_CACHE):
            for f in d.glob("*") if d.is_dir() else []:
                if f.is_file() and f.name not in keep and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
                    n += 1
        for rid in [r for r in _reports if not _path(r).exists()]:
            del _reports[rid]
    return n


def create_sample(background: bool = True) -> str:
    photos = [(p.name, p.read_bytes()) for p in sorted(SAMPLES.glob("*.jpg"))]
    return create(photos, household=False, background=background)   # separate synthetic households


def _read_photo(rid: str, pid: str) -> None:
    state = _state(rid)
    photo = next(p for p in state["photos"] if p["id"] == pid)
    with _lock:
        photo["status"] = "reading"
        _save(state)
    try:
        raw, fresh = get_reading(photo["sha"], UPLOADS / photo["file"])
        if raw.get("error"):
            raise ValueError("unreadable")
        status, error, cost = "done", None, _cost(raw) if fresh else 0.0   # a saved reading costs nothing now
    except RetakeNeeded:
        status, error, cost = "failed", quality.RETAKE, 0.0
        photo["retake"] = True
    except LookupError as e:
        status, error, cost = "failed", {"en": str(e), "ur": None}, 0.0
    except BudgetExceeded:
        status, error, cost = "failed", PAUSED, 0.0
    except Exception:   # noqa: BLE001  (a network failure or an unreadable photo)
        status, error, cost = "failed", UNREADABLE, 0.0
    with _lock:
        photo.update(status=status, error=error["en"] if error else None, error_ur=error["ur"] if error else None, cost_usd=cost)
        _save(state)


# ---------- household ----------

def _fields(raw: dict) -> dict:
    return {k: (v.get("value") if isinstance(v, dict) else None) for k, v in (raw.get("fields") or {}).items()}


def merge(raws: list[dict]) -> dict:
    """Photos of the same bill month: a field is kept where every photo that read it agrees, held where they differ."""
    if len(raws) == 1:
        return raws[0]
    out = copy.deepcopy(raws[0])
    keys = set().union(*[(r.get("fields") or {}).keys() for r in raws])
    fields, disagreements = {}, {}
    for k in keys:
        entries = [e for r in raws if isinstance(e := (r.get("fields") or {}).get(k), dict) and e.get("value") is not None]
        normed = {_norm(k, e["value"]) for e in entries} - {None}
        if not entries:
            fields[k] = (out.get("fields") or {}).get(k) or {"value": None, "text": None}
        elif len(normed) <= 1:
            fields[k] = entries[0]
        else:
            fields[k] = {"value": None, "text": None, "held": "the photos of this bill show different values"}
            disagreements[k] = [e["value"] for e in entries]
    out["fields"] = fields
    hist: dict[str, dict] = {}
    conflict = set()
    for r in raws:
        for h in r.get("history") or []:
            m = month_key(h.get("month"))
            if not m:
                continue
            if m in hist and num(hist[m]["units"]) != num(h.get("units")):
                conflict.add(m)
            hist.setdefault(m, {"month": m, "units": h.get("units"), "mode": h.get("mode") or ""})
    out["history"] = [h for m, h in sorted(hist.items(), reverse=True) if m not in conflict]
    lines = [r.get("fpa_line") for r in raws if isinstance(r.get("fpa_line"), dict)]
    if len({json.dumps({k: str(v) for k, v in sorted(x.items())}) for x in lines}) > 1:
        out["fpa_line"] = None
    out["photo_agreement"] = {"photos": len(raws), "disagreements": disagreements}
    return out


def _whole(x):
    n = num(x)
    return int(n) if isinstance(n, float) and n.is_integer() else n


def _prev_month(m: str) -> str:
    y, mo = map(int, m.split("-"))
    return f"{y - (mo == 1):04d}-{12 if mo == 1 else mo - 1:02d}"


def _answer_raw(raw: dict, answers: dict) -> dict:
    """A user who says the item IS on the bill overrides the reader's 'absent': the photo just did not show it."""
    raw = copy.deepcopy(raw)
    f = raw.setdefault("fields", {})
    if answers.get("snapshot") is False:
        f["snapshot_state"] = {"value": "unreadable", "text": None, "answered": True}
    if answers.get("stamp") is False:
        f["snapshot_stamp_printed"] = {"value": "yes", "text": None, "answered": True}
    return raw


def _analyze(raw: dict, answers: dict, overrides: dict) -> dict:
    raw = _answer_raw(raw, answers)
    out = analyze_reading(raw, overrides=overrides)
    pending = [q for q in out["questions"] if q["id"] not in answers]
    asked = [q for q in out["questions"] if q["id"] in answers]
    if asked and not pending and all(answers[q["id"]] for q in asked):
        out = analyze_reading(raw, confirmed_absent=True, overrides=overrides)
    out["questions"] = [q for q in out["questions"] if q["id"] not in answers]
    return out


def _bill_stamp(out: dict) -> str:
    c = out["verdict"]["counts"]
    if c["problem"]:
        return "problem_found"
    if out["questions"] or not c["looks_right"]:
        return "cannot_be_determined"
    return "looks_right"


def _value(raw: dict, overrides: dict, key: str):
    return overrides[key] if key in overrides else _fields(raw).get(key)


def view(rid: str) -> dict | None:
    """The report as the API returns it, recomputed from stored readings (no model call)."""
    state = _state(rid)
    if state is None:
        return None
    with _lock:
        state = copy.deepcopy(state)
    pending_bills, groups = [], {}
    for p in state["photos"]:
        raw = stored_reading(p["sha"]) if p["status"] == "done" else None
        if raw is None:
            pending_bills.append({"id": p["id"], "photo_name": p["name"], "photos": [p["name"]],
                                  "photo_urls": [f"/api/reports/{rid}/photos/{p['id']}"], "status": p["status"],
                                  "error": p["error"], "error_ur": p.get("error_ur"), "retake": bool(p.get("retake")),
                                  "billing_month": None, "cost_usd": p["cost_usd"]})
            continue
        m = month_key(_fields(raw).get("billing_month"))
        key = m if (state["household"] and m) else p["id"]
        groups.setdefault(key, []).append((p, raw))
    bills = []
    for key, members in groups.items():
        first = members[0][0]
        merged = merge([r for _, r in members])
        bills.append({"id": first["id"], "raw": merged, "photos": [p for p, _ in members]})
    bills.sort(key=lambda b: (month_key(_fields(b["raw"]).get("billing_month")) or "9999", b["id"]))

    chain = []
    if state["household"]:
        for a, b in zip(bills, bills[1:]):
            ma, mb = (month_key(_fields(x["raw"]).get("billing_month")) for x in (a, b))
            if not (ma and mb) or _prev_month(mb) != ma:
                continue
            oa, ob = state["overrides"].get(a["id"], {}), state["overrides"].get(b["id"], {})
            if not _value(b["raw"], ob, "prev_reading_date") and _value(a["raw"], oa, "reading_date"):
                b["raw"] = copy.deepcopy(b["raw"])
                b["raw"].setdefault("fields", {})["prev_reading_date"] = {
                    "value": _value(a["raw"], oa, "reading_date"), "text": None, "from_previous_bill": a["id"]}
            pres, prev = num(_value(a["raw"], oa, "present_reading")), num(_value(b["raw"], ob, "prev_reading"))
            if pres is not None and prev is not None:
                ok = pres == prev
                chain.append({"from": ma, "to": mb, "ok": ok,
                              "note": (f"{mb} starts from {ma}'s present reading ({int(pres)})." if ok else
                                       f"{ma} ended at {int(pres)} but {mb} starts from {int(prev)}."),
                              "note_ur": (f"{mb} کی ریڈنگ {ma} کی موجودہ ریڈنگ ({int(pres)}) سے شروع ہوتی ہے۔" if ok else
                                          f"{ma} کی ریڈنگ {int(pres)} پر ختم ہوئی مگر {mb} {int(prev)} سے شروع ہوتا ہے۔")})

    out_bills = []
    for b in bills:
        answers, overrides = state["answers"].get(b["id"], {}), state["overrides"].get(b["id"], {})
        a = _analyze(b["raw"], answers, overrides)
        prev_fill = (b["raw"].get("fields") or {}).get("prev_reading_date") or {}
        reading = a["reading"]
        if prev_fill.get("from_previous_bill"):
            for r in reading:
                if r["key"] == "prev_reading_date":
                    r["from_previous_bill"] = True
        out_bills.append({
            "id": b["id"], "photo_name": b["photos"][0]["name"], "photos": [p["name"] for p in b["photos"]],
            "photo_urls": [f"/api/reports/{rid}/photos/{p['id']}" for p in b["photos"]],
            "status": "done", "error": None, "billing_month": a["billing_month"], "stamp": _bill_stamp(a),
            "headline": {"en": a["verdict"]["headline"], "ur": a["verdict"]["headline_ur"]},
            "counts": a["verdict"]["counts"], "reading": reading, "cards": a["verdict"]["cards"],
            "questions": a["questions"], "answers": answers, "next_steps": a["next_steps"],
            "complaint": a["complaint"], "history": a["history"],
            "photo_agreement": b["raw"].get("photo_agreement"),
            # charge lines that add up if one digit of a read figure is changed (asked, never alleged)
            "misreads": [{k: f["numbers"].get(k) for k in ("line", "figure", "read_as", "adds_up_if")}
                         for f in a["findings"] if ASK_MISREAD in (f.get("missing") or [])],
            "cost_usd": round(sum(p["cost_usd"] for p in b["photos"]), 5)})

    statuses = [p["status"] for p in state["photos"]]
    status = "reading" if any(s in ("queued", "reading") for s in statuses) else (
        "partial" if "failed" in statuses else "done")
    months = [{"month": b["billing_month"], "units": _whole(next((r["value"] for r in b["reading"] if r["key"] == "units"), None)),
               "status": b["stamp"], "bill_id": b["id"]} for b in out_bills]
    latest = next((b for b in reversed(out_bills) if b["history"]), None)
    history = sorted(({"month": month_key(h.get("month")), "units": _whole(h.get("units")), "mode": h.get("mode") or ""}
                      for h in (latest["history"] if latest else []) if month_key(h.get("month"))),
                     key=lambda h: h["month"])
    return {"id": rid, "created": state["created"], "status": status, "household_mode": state["household"],
            "headline": _headline(out_bills, status), "bills": out_bills + pending_bills,
            "household": {"months": months, "chain": chain, "history": history, "protected_line": PROTECTED_LINE},
            "cost_usd": round(sum(p["cost_usd"] for p in state["photos"]), 5)}


def _headline(bills: list[dict], status: str) -> dict:
    done = len(bills)
    problems = sum(b["counts"]["problem"] for b in bills)
    questions = sum(len(b["questions"]) for b in bills)
    if not done and status != "reading":      # every photo failed: nothing is being read any more
        return {"en": "No bill could be read yet. See what to do below.",
                "ur": "ابھی کوئی بل پڑھا نہیں جا سکا۔ نیچے دیکھیں کہ کیا کرنا ہے۔", "stamp": "cannot_be_determined"}
    if not done:
        return {"en": "Reading your bills.", "ur": "آپ کے بل پڑھے جا رہے ہیں۔", "stamp": "cannot_be_determined"}
    nb_en = f"{done} bill{'s' if done != 1 else ''}"
    if problems:
        found_ur = "1 مسئلہ ملا" if problems == 1 else f"{problems} مسائل ملے"
        return {"en": f"{problems} problem{'s' if problems != 1 else ''} found across {nb_en}.",
                "ur": f"{done} بلوں میں {found_ur}۔" if done != 1 else f"اس بل میں {found_ur}۔",
                "stamp": "problem_found"}
    if questions:
        return {"en": f"No problem found yet. {questions} question{'s' if questions != 1 else ''} for you before we can say more.",
                "ur": f"ابھی تک کوئی مسئلہ نہیں ملا۔ مزید بتانے سے پہلے آپ سے {questions} سوال۔",
                "stamp": "cannot_be_determined"}
    if all(b["stamp"] == "looks_right" for b in bills) and status == "done":
        return {"en": "No problem found in what this bill shows." if done == 1 else
                      f"No problem found in what these {done} bills show.",
                "ur": "ان بلوں میں دکھائی گئی معلومات میں کوئی مسئلہ نہیں ملا۔" if done != 1 else
                      "اس بل میں دکھائی گئی معلومات میں کوئی مسئلہ نہیں ملا۔",
                "stamp": "looks_right"}
    return {"en": f"No problem found in what we could check on {nb_en}. Some checks need more information.",
            "ur": "جتنا جانچا جا سکا اس میں کوئی مسئلہ نہیں ملا۔ کچھ جانچوں کے لیے مزید معلومات درکار ہیں۔",
            "stamp": "cannot_be_determined"}


# ---------- user input ----------

def answer(rid: str, bill_id: str, question: str, absent: bool) -> dict | None:
    if question not in ("snapshot", "stamp", "mco"):
        raise ValueError("Unknown question.")
    state = _state(rid)
    if state is None:
        return None
    with _lock:
        state["answers"].setdefault(bill_id, {})[question] = bool(absent)
        _save(state)
    return view(rid)


USER_FIELDS = {"delivery_date"}      # facts only the household knows; never read from the photo


def correct(rid: str, bill_id: str, field: str, value) -> dict | None:
    if field not in FIELDS and field not in USER_FIELDS:
        raise ValueError("Unknown field.")
    if field == "delivery_date" and value not in (None, ""):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
            raise ValueError("Enter the date as YYYY-MM-DD.")
    if field in NUMERIC and value not in (None, ""):
        parsed = num(value)
        if parsed is None:
            raise ValueError("Enter a number.")
        value = parsed
    state = _state(rid)
    if state is None:
        return None
    with _lock:
        ov = state["overrides"].setdefault(bill_id, {})
        ov[field] = None if value == "" else value
        if field == "snapshot_reading" and value not in (None, ""):
            ov["snapshot_state"] = "readable"        # the person read the meter photo for us
        _save(state)
    return view(rid)


def photo_file(rid: str, pid: str) -> Path | None:
    state = _state(rid)
    p = next((p for p in (state or {}).get("photos", []) if p["id"] == pid), None)
    return UPLOADS / p["file"] if p and (UPLOADS / p["file"]).exists() else None
