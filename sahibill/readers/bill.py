"""Read a bill photo with Muse Spark Open, then map what was read into the rules engine's input.

The model only transcribes. Every field comes back as {"value", "text"} where "text" is the characters
as printed, so two readers can be compared on both. Numbers used by the rules are parsed here, in code.
"""
from __future__ import annotations

import re
from pathlib import Path

from sahibill.readers.llm import chat, image_part, parse_json
from sahibill.rules.core import BillFacts

FIELDS = {
    "billing_month": "Billing month, as YYYY-MM",
    "reading_date": "Reading date (present reading), as YYYY-MM-DD",
    "prev_reading_date": "Previous reading date, as YYYY-MM-DD, only if printed",
    "issue_date": "Issue date, as YYYY-MM-DD",
    "due_date": "Due date, as YYYY-MM-DD",
    "tariff": "Tariff code exactly as printed",
    "sanctioned_load_kw": "Sanctioned load in kW, a number",
    "status": "Consumer category as printed (for example lifeline, protected, unprotected); on some bills this is under CATEGORY while STATUS shows the meter status",
    "prev_reading": "Previous meter reading, a number",
    "present_reading": "Present meter reading, a number",
    "units": "Units billed this month, a number",
    "carried_forward": "Units carried forward that are included in present minus previous reading, only if printed",
    "pro_rata": "true if the bill says the present reading is pro-rata (for example 'Pro-Rata based Present Reading instead of Recorded'), else false",
    "outstanding_units": "Outstanding units carried to the next bill (for example 'Outstanding units: 3'), only if printed",
    "snapshot_state": "The meter-reading snapshot box: 'readable', 'unreadable' (present but cannot be read) or 'blank' (no picture or digits printed)",
    "snapshot_reading": "The digits shown inside the meter-reading snapshot picture, a number; null if blank or unreadable",
    "snapshot_stamp": "The time stamp printed on or under the snapshot picture, exactly as far as it can be read (write ? for unreadable characters); null only if there is no stamp",
    "snapshot_stamp_printed": "Is a time stamp printed with the snapshot picture? 'yes', 'no' (clearly none printed) or 'cannot tell'",
    "variable": "Energy or variable charges in Rs (also printed as 'Cost of Electricity'), only if printed as its own line",
    "fixed": "Fixed charges in Rs, only if printed",
    "min_charge": "Minimum charges in Rs, only if printed",
    "fca": "Fuel charges or fuel price adjustment (FCA or FPA) line in Rs, before tax, only if printed as its own charge line",
    "fc_surcharge": "F.C surcharge in Rs, only if printed",
    "qta": "Quarterly adjustment (QTA, Qtr. Tariff Adjustment) in Rs, only if printed",
    "gst": "GST (general sales tax) on the electricity charges in Rs, only if printed",
    "gst_on_fpa": "GST on FPA in Rs, only if printed",
    "total_electricity_charges": "Total electricity charges before subsidy in Rs, only if printed",
    "subsidies": "Subsidies in Rs, only if printed",
    "net_electricity_charges": "Net electricity charges in Rs, only if printed",
    "taxes": "Taxes in Rs as one total, only if printed",
    "current_bill": "Current bill in Rs, only if printed",
    "total_fpa": "Total FPA in Rs as printed (may include tax), only if printed",
    "payable_within": "Amount payable within due date in Rs",
}

PROMPT = """You are reading a photo of a Pakistani household electricity bill. Transcribe; do not calculate,
correct or guess anything. The photo may be rotated, skewed, blurred or partly covered.

Return only one JSON object with these keys:
- "fields": an object with one entry per key below. Each entry is {"value": ..., "text": "..."} where
  "text" is the exact characters printed on the bill for that item and "value" is the same item in the
  format asked. If an item is not printed or cannot be read with confidence, use {"value": null, "text": null}.
- "history": a list, most recent month first, of {"month": "as printed", "units": number or null,
  "mode": "any code printed in that row, else empty"} for the billing history table.
- "supplementary": a list of any supplementary or detection charge lines, each
  {"kind": "detection | retrieval | skipped_mf | other", "text": "the whole line exactly", "units": number or null,
  "amount": "the rupee amount on that line, a number, or null",
  "months": number or null, "period_from": "YYYY-MM or null", "period_to": "YYYY-MM or null",
  "load_kw": number or null, "event_date": "YYYY-MM-DD or null (meter change date or date raised)"}.
- "fpa_line": the printed fuel adjustment note, if any (often a sentence like "units consumed in <month> ... FPA @ <rate> per unit"):
  {"reference_month": "the month whose units it is charged on, as printed", "units": number or null,
  "rate": "Rs per unit, a number, or null", "amount": "the rupee amount on that line, a number, or null"}, or null.
- "bill_calculation": the per-unit rate lines printed in a bill calculation box, if any (for example "13.0100 X 77"),
  as a list of {"rate": number, "units": number}, or an empty list.
- "orientation": the rotation in degrees needed to make the bill upright (0, 90, 180 or 270).

Keys for "fields":
""" + "\n".join(f"- {k}: {v}" for k, v in FIELDS.items())


def _upright(image: Path, clockwise: int) -> Path:
    """Turn the photo clockwise by the reported amount, cached by content."""
    import hashlib
    from PIL import Image
    from sahibill.readers.llm import CACHE
    h = hashlib.sha256(image.read_bytes()).hexdigest()[:20]
    out = CACHE / "upright" / f"{h}_cw{clockwise}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(image).convert("RGB").rotate(-clockwise, expand=True, fillcolor=(118, 108, 92)).save(out)
    return out


def read_bill(image: str | Path, reasoning_effort: str | None = None, tag: str = "", reread_rotated: bool = True) -> dict:
    """Read once; if the model reports the page rotated by 90, 180 or 270 degrees, turn it upright in
    code and read it again. The upright reading is used; the first reading's cost is kept in the record."""
    first = _read_once(Path(image), reasoning_effort, tag)
    o = first.get("orientation")
    try:
        o = int(round(float(o))) % 360
    except (TypeError, ValueError):
        o = 0
    if not reread_rotated or o not in (90, 180, 270):
        return first
    second = _read_once(_upright(Path(image), o), reasoning_effort, tag + ":upright")
    second["_first_pass"] = {"orientation": o, "_call": first["_call"],
                             "fields_read": sum(1 for v in (first.get("fields") or {}).values() if (v or {}).get("value") is not None)}
    return second


def _read_once(image: Path, reasoning_effort: str | None, tag: str) -> dict:
    messages = [{"role": "user", "content": [{"type": "text", "text": PROMPT}, image_part(image)]}]
    r = chat(messages, reasoning_effort=reasoning_effort, tag=tag)
    try:
        data = parse_json(r["content"])
    except Exception as e:   # noqa: BLE001
        data = {"error": f"unparseable output: {e}", "raw": r["content"][:2000]}
    data["_call"] = {k: r.get(k) for k in ("usage", "usd", "cached", "latency_s", "provider", "model", "reasoning_effort")}
    return data


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTHS_UR = {m: i for i, m in enumerate(["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر",
                                         "اکتوبر", "نومبر", "دسمبر"], 1)}


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    m = _NUM.search(str(v))
    if not m:
        return None
    s = m.group(0).replace(",", "")
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def month_key(text: str | None) -> str | None:
    """'Sep-26' or '2026-09' or 'September 2026' -> '2026-09'."""
    if not text:
        return None
    t = str(text).strip().lower()
    m = re.match(r"(\d{4})-(\d{1,2})", t)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    for name, i in MONTHS_UR.items():          # Urdu month names, either side of the year: "26-مئی", "مئی-26"
        if name in t:
            y = re.search(r"\d{2,4}", t)
            if y:
                yy = int(y.group(0))
                return f"{yy + 2000 if yy < 100 else yy:04d}-{i:02d}"
    m = re.match(r"([a-z]{3})[a-z]*[\s\-/']*(\d{2,4})", t)
    if m and m.group(1) in MONTHS:
        y = int(m.group(2))
        y = y + 2000 if y < 100 else y
        return f"{y:04d}-{MONTHS[m.group(1)]:02d}"
    return None


def stamp_date(text: str | None) -> str | None:
    """'25-04-2026 16:55', '25.05.2026', '2026-04-25' -> '2026-04-25'; None when no full date can be read."""
    if not text:
        return None
    m = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", str(text))
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"(\d{1,2})[-./](\d{1,2})[-./](\d{4})", str(text))
        if not m:
            return None
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else None


def to_facts(read: dict, phase: int | None = None, confirmed_absent: bool = False) -> BillFacts:
    """Map a reading into BillFacts. Phase is not a required bill field; pass it if known. An absence the
    photo reading reports (no meter photo, no stamp) is only alleged once the user has confirmed it."""
    f = {k: (v or {}).get("value") for k, v in (read.get("fields") or {}).items()}
    units = num(f.get("units"))
    status = (f.get("status") or "").strip().lower() or None
    status = next((s for s in ("lifeline", "unprotected", "protected") if status and s in status), None)
    variable = num(f.get("variable"))
    rate = None
    if units and variable is not None and status in ("lifeline", "unprotected"):
        rate = round(variable / units, 2)            # single-rate categories: rate = charge / units
    elif units and variable is not None and status == "protected":
        rate = 10.54 if units <= 100 else 13.01      # headline row; arithmetic check uses the full charge
    calc = [num((c or {}).get("rate")) for c in read.get("bill_calculation") or [] if isinstance(c, dict)]
    calc = [c for c in calc if c and c < 100]        # per-unit rates only (fixed charges are Rs per kW, in the hundreds)
    if rate is None and calc:
        rate = max(calc)                             # the headline (highest) slab rate the bill applied
    snap = num(f.get("snapshot_reading"))
    stamp = f.get("snapshot_stamp")
    state = (f.get("snapshot_state") or "").lower()
    hist = []
    for h in read.get("history") or []:
        mk = month_key(h.get("month"))
        if mk:
            hist.append({"month": mk, "units": num(h.get("units")), "mode": (h.get("mode") or "").strip()})
    present = num(f.get("present_reading"))
    fl = read.get("fpa_line") if isinstance(read.get("fpa_line"), dict) else {}
    pro = f.get("pro_rata")
    pro = pro if isinstance(pro, bool) else (str(pro).strip().lower() == "true" if pro is not None else None)
    bm = month_key(f.get("billing_month"))
    detection = retrieval = skipped = average = accumulated = None
    for line in read.get("supplementary") or []:
        kind = (line.get("kind") or "").lower()
        if kind == "detection":
            detection = {"units": num(line.get("units")), "months": num(line.get("months")),
                         "connected_load_kw": num(line.get("load_kw"))}
            pf, pt = line.get("period_from"), line.get("period_to")
            if pf and pt and hist:
                by = {h["month"]: h["units"] for h in hist}
                months = []
                y, m = map(int, pf.split("-")[:2])
                while f"{y:04d}-{m:02d}" <= pt[:7]:
                    months.append(f"{y:04d}-{m:02d}")
                    m += 1
                    y, m = (y + 1, 1) if m == 13 else (y, m)
                period = [by.get(k) for k in months]
                prev = [by.get(f"{int(k[:4]) - 1:04d}{k[4:]}") for k in months]
                after, (ay, am) = [], map(int, pt.split("-")[:2])
                for _ in months:                     # the same number of months right after the period
                    am += 1
                    ay, am = (ay + 1, 1) if am == 13 else (ay, am)
                    after.append(by.get(f"{ay:04d}-{am:02d}"))
                if None not in period:
                    detection["period_units"] = period
                    if None not in prev:
                        detection["previous_year_units"] = prev
                    if None not in after:
                        detection["future_units"] = after
            text = (line.get("text") or "").lower()
            detection["reasons"] = "direct_theft" if ("hook" in text or "direct" in text) else (
                "tampering" if any(w in text for w in ("tamper", "slow", "phase", "bypass")) else None)
            if "no ceo approval" in text or "approval not" in text or "without approval" in text:
                detection["approval"] = False
            elif "approval" in text and any(w in text for w in ("obtained", "granted", "approved")):
                detection["approval"] = True
            detection = {k: v for k, v in detection.items() if v is not None}
        elif kind == "retrieval":
            text = (line.get("text") or "").lower()
            got = re.search(r"retrieved[^0-9]*(\d{4}-\d{2}-\d{2})", text)
            retrieval = {"replaced": line.get("event_date"), "debit": bm,
                         "retrieved": got.group(1) if got else None,
                         "branch": "in_house" if "in-house" in text or "in house" in text else (
                             "manufacturer" if "manufacturer" in text else None),
                         "defect": "display_wash" if "display" in text or "wash" in text else None}
            retrieval = {k: v for k, v in retrieval.items() if v is not None}
        elif kind == "skipped_mf":
            skipped = {"reason": line.get("text") or "multiplying factor", "amount": num(line.get("amount")),
                       "months": num(line.get("months")), "raised": bm,
                       "period_from": line.get("period_from"), "period_to": line.get("period_to")}
            skipped = {k: v for k, v in skipped.items() if v is not None}
    if hist:
        run = 0
        for h in hist:                      # most recent first
            if h.get("mode", "").upper() in ("AVG", "AV", "DF", "DEF"):
                run += 1
            else:
                break
        if run:
            average = {"consecutive_months": run}
        zeros = 0
        for h in hist:
            if (h.get("units") == 0) or h.get("mode", "").upper() in ("NR", "N/R"):
                zeros += 1
            else:
                break
        if zeros and units:
            accumulated = {"lump_units": units, "months_covered": zeros + 1, "segregated_shown": False}
    return BillFacts(
        detection=detection, retrieval=retrieval, skipped=skipped, average=average, accumulated=accumulated,
        billing_month=month_key(f.get("billing_month")), phase=phase,
        sanctioned_load_kw=num(f.get("sanctioned_load_kw")),
        reading_date=f.get("reading_date"), prev_reading_date=f.get("prev_reading_date"),
        issue_date=f.get("issue_date"), due_date=f.get("due_date"),
        units=units,
        carry_forward_shown=bool(num(f.get("carried_forward"))) if f.get("carried_forward") is not None else None,
        snapshot_present=False if state == "blank" else (True if state in ("readable", "unreadable") else None),
        snapshot={"total": snap} if state == "readable" and snap is not None else ({"total": None} if state == "unreadable" else None),
        # an unread stamp is unknown, never "no stamp": only text the model actually read counts as evidence
        snapshot_stamp_present=True if stamp else (
            False if str(f.get("snapshot_stamp_printed") or "").strip().lower() == "no" else None),
        present_reading={"total": present} if present is not None else None,
        snapshot_stamp_date=stamp_date(stamp), snapshot_geotag=None,
        history=hist or None, status_billed=status, rate_billed=rate,
        variable_billed=variable, fixed_billed=num(f.get("fixed")),
        fpa_billed=num(f.get("fca")), qta_billed=num(f.get("qta")),
        absence_confirmed=confirmed_absent,
        delivery_date=f.get("delivery_date"),      # given by the household (it is not printed on bills)
        pro_rata_reading=pro, carried_forward_units=num(f.get("outstanding_units")),
        fpa_ref_month=month_key(fl.get("reference_month")), fpa_ref_units=num(fl.get("units")), fpa_rate=num(fl.get("rate")),
    )
