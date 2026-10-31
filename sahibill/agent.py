"""The case agent: Muse Spark Open works a household's report to a finish, using SahiBill's own code as tools.

It looks at what is still open, asks the household only the questions SahiBill's rules raised (one at a time,
in their language), re-runs the checks with each answer, and when a problem stands, prepares the complaint with
the dates the Consumer Service Manual sets. Code decides every number: the tools compute them, every step's
title is written by code, and the model's own words (a reason for a question, the closing summary) are kept
only if every number in them came from a tool. The agent runs in short segments: it stops when it needs the
household and continues when they answer.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
import threading
import time

from sahibill import report
from sahibill.complaint.draft import ESCALATION, TIMELINES, numbers_in
from sahibill.readers.llm import BudgetExceeded, chat

MAX_CALLS = 10             # model calls per segment; a segment ends at a question, the finish, or this cap
MAX_QUESTIONS = 3          # questions per case; what stays open is named in the summary
FIGURE_FIELDS = {"units": "units", "sanctioned load": "sanctioned_load_kw"}   # misread figures the household can correct
PKT = dt.timezone(dt.timedelta(hours=5))

PLAN_KINDS = ["look", "ask", "check", "letter", "finish"]
TOOLS = [
    {"type": "function", "function": {
        "name": "make_plan",
        "description": "State your plan before acting: 3 to 6 short steps in the order you will take them. The "
                       "household sees it as a checklist that ticks as the steps happen.",
        "parameters": {"type": "object", "properties": {"steps": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": PLAN_KINDS},
            "text": {"type": "string", "description": "a few words, in the household's language, no numbers"}},
            "required": ["kind", "text"]}}}, "required": ["steps"]}}},
    {"type": "function", "function": {
        "name": "list_open_items",
        "description": "Every bill in the report: its verdict, the problems found (with clause), and the items "
                       "still open, each with who can supply it: the household (answerable now), the utility "
                       "(goes in the complaint), a clearer photo, or a SahiBill limit.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "ask_household",
        "description": "Ask the household one open item marked 'household'. The case pauses until they answer; "
                       "the answer is then applied and the checks re-run.",
        "parameters": {"type": "object", "properties": {
            "item_id": {"type": "string", "description": "an item_id from list_open_items with who = household"},
            "reason": {"type": "string", "description": "one short sentence, in the household's language, on why "
                                                        "this answer matters; no numbers"}},
            "required": ["item_id", "reason"]}}},
    {"type": "function", "function": {
        "name": "recheck",
        "description": "Re-run SahiBill's checks on one bill with every answer given so far; returns its verdict, "
                       "problems and remaining open items.",
        "parameters": {"type": "object", "properties": {"bill_id": {"type": "string"}}, "required": ["bill_id"]}}},
    {"type": "function", "function": {
        "name": "explain_rule",
        "description": "The rule behind one check on one bill: what it found, the numbers it used, and the clause.",
        "parameters": {"type": "object", "properties": {"bill_id": {"type": "string"}, "check": {"type": "string"}},
                       "required": ["bill_id", "check"]}}},
    {"type": "function", "function": {
        "name": "prepare_complaint",
        "description": "For a bill with problems found: the complaint's problems, the records to request from the "
                       "utility, and the dates the manual sets (settle by, then where to escalate), counted from today.",
        "parameters": {"type": "object", "properties": {"bill_id": {"type": "string"}}, "required": ["bill_id"]}}},
    {"type": "function", "function": {
        "name": "finish",
        "description": "End the case with a short summary for the household, in their language: what was checked, "
                       "what their answers changed, and what to do next. Use only numbers that tools returned.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]

SYSTEM = """You are SahiBill's case agent. A household in Pakistan uploaded electricity bills; SahiBill's code
checked them against NEPRA's Consumer Service Manual. Your job is to take the case as far as it can go, using
the tools, then finish.

How to work:
0. First call make_plan with your plan for this case.
1. Then list_open_items.
2. If an item can be answered by the household, ask it with ask_household, one item at a time, the item most
   likely to change a verdict first. Never ask about anything that is not an open item.
3. After each answer, recheck that bill and look at what changed.
4. For every bill with a problem found, call prepare_complaint.
5. When nothing is left that the household can answer, call finish.

Ask at most three questions in a case, the ones most likely to change a verdict (start with the bill whose
verdict is still open, and with yes-or-no questions about what the photo did not show). Whatever stays open,
say in the summary who can supply it.

Rules: SahiBill's code decides every number and every verdict. Never state a number, date, rate or clause that a
tool did not return. Never say a bill is wrong unless a tool says problem found. Items for the utility go in the
complaint; do not ask the household for them. Write every reason and the summary in {language}, in plain short
sentences{script}. Plain text only: no markdown, no headings, no asterisks, no dashes. Refer to bills by their
month, never by bill_id. Keep the summary under 90 words."""

LANG = {"en": ("English", ""), "ur": ("Urdu", ", in Urdu script only")}


# ---------- state ----------

def _get(rid: str) -> dict | None:
    state = report._state(rid)
    if state is None:
        return None
    with report._lock:
        return copy.deepcopy(state.get("agent"))


def _put(rid: str, agent: dict) -> None:
    state = report._state(rid)
    with report._lock:
        state["agent"] = agent
        report._save(state)


def public(agent: dict | None) -> dict:
    """What the page sees: the trace, the open question, the summary. Never the model transcript."""
    if not agent:
        return {"status": "idle", "trace": [], "ask": None, "summary": None}
    out = {k: agent.get(k) for k in ("status", "trace", "ask", "summary", "language", "cost_usd", "plan", "grounding",
                                     "stats", "started", "model")}
    if out["ask"]:
        out["ask"] = {k: v for k, v in out["ask"].items() if k != "call_id"}
    return out


# ---------- tools (pure code) ----------

def _bills(rid: str) -> list[dict]:
    v = report.view(rid) or {}
    return [b for b in v.get("bills", []) if b.get("status") == "done"]


def _items(b: dict) -> list[dict]:
    out = []
    for q in b.get("questions") or []:
        out.append({"item_id": f"{b['id']}:confirm:{q['id']}", "who": "household", "kind": "confirm",
                    "text": q["en"], "text_ur": q["ur"]})
    reading = {r["key"]: r for r in b.get("reading") or []}
    snap_card = next((c for c in b.get("cards") or [] if str(c.get("check")) == "2"), None)
    if (snap_card and snap_card.get("status") == "cannot_be_determined" and not b.get("questions")
            and (reading.get("snapshot_state") or {}).get("value") != "blank"
            and not (reading.get("snapshot_reading") or {}).get("corrected")):
        # the meter photo is printed but unreadable: SAM 3 cuts it out and the household reads the digits
        out.append({"item_id": f"{b['id']}:meter:snapshot_reading", "who": "household", "kind": "meter",
                    "text": "SAM 3 cut out the meter photo printed on your bill. What number does it show?",
                    "text_ur": "SAM 3 نے بل پر چھپی میٹر کی تصویر الگ کر دی ہے۔ اس میں کون سا نمبر نظر آتا ہے؟"})
    steps = b.get("next_steps") or {}
    for s in steps.get("user") or []:
        if "10B" in (s.get("checks") or []):
            out.append({"item_id": f"{b['id']}:date:delivery_date", "who": "household", "kind": "date",
                        "text": s["en"], "text_ur": s["ur"]})
    for m in b.get("misreads") or []:
        field = FIGURE_FIELDS.get(m.get("figure"))
        if field:
            out.append({"item_id": f"{b['id']}:figure:{field}", "who": "household", "kind": "figure",
                        "field": field, "read_as": m["read_as"], "adds_up_if": m["adds_up_if"],
                        "text": f"Please check the {m['figure']} printed on the bill.",
                        "text_ur": "براہ کرم بل پر چھپا یہ نمبر دیکھیں۔"})
    for who in ("utility", "retake", "limit"):
        for s in steps.get(who) or []:
            out.append({"who": who, "text": s["en"], **({"clause": s["clause"]} if s.get("clause") else {})})
    seen, uniq = set(), []
    for it in out:                                   # one item per id (a question can come from two checks)
        k = it.get("item_id") or it["text"]
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq


def _bill_summary(b: dict) -> dict:
    return {"bill_id": b["id"], "month": b.get("billing_month"), "verdict": b.get("stamp"),
            "counts": b.get("counts"),
            "problems": [{"check": c.get("check"), "title": c.get("title"), "found": " ".join(c.get("lines") or []),
                          "clauses": c.get("clauses")} for c in b.get("cards") or [] if c.get("status") == "problem_found"],
            "open_items": _items(b)}


def meter_found(rid: str, bill_id: str) -> bool | None:
    """Run SAM 3 on the bill's photos for the printed meter photo. None when the service is unavailable."""
    from sahibill.vision import meter as m
    b = _bill(rid, bill_id) or {}
    for url in b.get("photo_urls") or []:
        path = report.photo_file(rid, url.rsplit("/", 1)[-1])
        if path is None:
            continue
        try:
            if m.locate(path.read_bytes()):
                return True
        except Exception:   # noqa: BLE001  (SAM 3 on Modal unavailable)
            return None
    return False


def _bill(rid: str, bill_id: str) -> dict | None:
    return next((b for b in _bills(rid) if b["id"] == bill_id), None)


def tool_list(rid: str) -> dict:
    return {"bills": [_bill_summary(b) for b in _bills(rid)]}


def tool_recheck(rid: str, bill_id: str) -> dict:
    b = _bill(rid, bill_id)
    return _bill_summary(b) if b else {"error": f"no bill {bill_id}"}


def tool_explain(rid: str, bill_id: str, check: str) -> dict:
    b = _bill(rid, bill_id)
    card = next((c for c in (b or {}).get("cards") or [] if str(c.get("check")) == str(check)
                 or (c.get("title") or "").lower() == str(check).lower()), None)
    if not card:
        return {"error": f"no check {check} on bill {bill_id}"}
    return {"check": card.get("check"), "title": card.get("title"), "status": card.get("status"),
            "found": card.get("lines"), "clauses": card.get("clauses")}


def tool_complaint(rid: str, bill_id: str, today: dt.date | None = None) -> dict:
    b = _bill(rid, bill_id)
    if not b:
        return {"error": f"no bill {bill_id}"}
    problems = [c for c in b.get("cards") or [] if c.get("status") == "problem_found"]
    if not problems:
        return {"bill_id": bill_id, "problems": [], "note": "no problem found on this bill, so no complaint is needed"}
    today = today or dt.datetime.now(PKT).date()
    detection = any("etection" in (c.get("title") or "") or str(c.get("check", "")).startswith("4") for c in problems)
    days = 15 if detection else 7
    rule = TIMELINES[1] if detection else TIMELINES[0]
    settle_by = today + dt.timedelta(days=days)
    return {"bill_id": bill_id, "month": b.get("billing_month"),
            "problems": [{"title": c.get("title"), "found": " ".join(c.get("lines") or []), "clauses": c.get("clauses")}
                         for c in problems],
            "records_to_request": [s["en"] for s in (b.get("next_steps") or {}).get("utility") or []],
            "complaint_date": today.isoformat(), "settle_within_days": days, "settle_by": settle_by.isoformat(),
            "settle_rule": f"{rule[0]} ({rule[2]})",
            "if_not_settled": f"{ESCALATION[0]} ({ESCALATION[2]})",
            "letter": "ready in English and Urdu on this report"}


# ---------- trace (titles written by code, in both languages) ----------

MONTHS_EN = "January February March April May June July August September October November December".split()
MONTHS_UR = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"]
STATUS = {"problem_found": ("problem found", "مسئلہ ملا"), "looks_right": ("looks right", "درست لگتا ہے"),
          "cannot_be_determined": ("can't tell yet", "ابھی نہیں کہہ سکتے")}


def _month(b: dict | None, lang: str = "en") -> str:
    ym = (b or {}).get("billing_month") or ""
    if not re.fullmatch(r"\d{4}-\d{2}", ym):
        return ym
    y, m = int(ym[:4]), int(ym[5:])
    return f"{(MONTHS_UR if lang == 'ur' else MONTHS_EN)[m - 1]} {y}"


def _label(item: dict, bill: dict | None) -> tuple[str, str]:
    """A short name for what was asked, in both languages, for the trace."""
    me, mu = _month(bill), _month(bill, "ur")
    key = item["item_id"].split(":")[2]
    return {
        ("confirm", "snapshot"): (f"whether the {me} bill has a meter-reading photo", f"کیا {mu} کے بل پر میٹر ریڈنگ کی تصویر ہے"),
        ("confirm", "stamp"): (f"whether the {me} meter photo has a date and time", f"کیا {mu} کی میٹر تصویر پر تاریخ اور وقت ہے"),
        ("confirm", "mco"): (f"whether the {me} bill shows the old meter's final reading", f"کیا {mu} کے بل پر پرانے میٹر کی آخری ریڈنگ ہے"),
        ("date", "delivery_date"): (f"when the {me} bill reached you", f"{mu} کا بل آپ کو کب ملا"),
        ("meter", "snapshot_reading"): (f"the number on the {me} meter photo, cut out by SAM 3", f"{mu} کی میٹر تصویر کا نمبر، جو SAM 3 نے الگ کی"),
    }.get((item["kind"], key), (f"the {item.get('field', key)} on the {me} bill", f"{mu} کے بل کا ایک نمبر"))


def _step(kind: str, en: str, ur: str, **extra) -> dict:
    return {"kind": kind, "en": en, "ur": ur, **extra}


def _trace_for(name: str, args: dict, result: dict) -> dict | None:
    if name == "list_open_items":
        bills = result.get("bills", [])
        mine = sum(1 for b in bills for i in b["open_items"] if i["who"] == "household")
        probs = sum(len(b["problems"]) for b in bills)
        return _step("look", f"Looked at {len(bills)} bills: {probs} problems found, {mine} things only you can tell us.",
                     f"{len(bills)} بل دیکھے: {probs} مسائل ملے، {mine} باتیں جو صرف آپ بتا سکتے ہیں۔")
    if name == "recheck" and "verdict" in result:
        c = result.get("counts") or {}
        bill = {"billing_month": result.get("month")}
        return _step("check", f"Re-ran the checks on {_month(bill)}: {c.get('problem', 0)} problems, "
                              f"{c.get('cannot_be_determined', 0)} still open, {c.get('looks_right', 0)} look right.",
                     f"{_month(bill, 'ur')} کی جانچ دوبارہ کی: {c.get('problem', 0)} مسائل، "
                     f"{c.get('cannot_be_determined', 0)} ابھی کھلے، {c.get('looks_right', 0)} درست۔")
    if name == "explain_rule" and "title" in result:
        return _step("rule", f"Looked up the rule: {result['title']} ({'; '.join(result.get('clauses') or [])}).",
                     f"قاعدہ دیکھا: {result['title']}۔")
    if name == "prepare_complaint" and result.get("problems"):
        bill = {"billing_month": result.get("month")}
        return _step("letter", f"Prepared the complaint for {_month(bill)}: the utility must settle it within "
                               f"{result['settle_within_days']} days, by {result['settle_by']}. If not, escalate.",
                     f"{_month(bill, 'ur')} کی شکایت تیار کی: کمپنی کو {result['settle_within_days']} دن میں، "
                     f"{result['settle_by']} تک حل کرنا ہے۔ ورنہ آگے شکایت کریں۔", settle_by=result["settle_by"])
    return None


# ---------- the loop ----------

def _allowed(agent: dict) -> set[str]:
    return numbers_in(json.dumps([m.get("content") for m in agent["messages"] if m.get("role") == "tool"], ensure_ascii=False))


FOREIGN = re.compile(r"[\u0900-\u097F\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")   # Devanagari, CJK, Hangul


def _tidy(text: str) -> str:
    """House style for the model's words: no markdown, no em or en dashes between words, no internal ids."""
    text = re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[*-]\s+", "• ", text, flags=re.M)
    text = re.sub(r"\s*[\u2014\u2013]\s*", ", ", text)
    text = re.sub(r"\s*\(b\d+\)|\bbill_id\b|\bb\d+\b", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _clean(text: str, agent: dict) -> str | None:
    """The model's words, kept only if every number came from a tool and the script fits the language."""
    text = _tidy(text or "")
    if not text or FOREIGN.search(text):
        return None
    if not numbers_in(text) <= _allowed(agent):
        return None
    if agent["language"] == "ur" and re.search(r"[A-Za-z]{4,}", re.sub(r"NEPRA|SahiBill|IESCO|CSM", "", text)):
        return None
    return text


def _grounding(text: str, agent: dict) -> dict:
    """Each number the model wrote, and whether a tool returned it (the summary is shown only if all did)."""
    allowed = _allowed(agent)
    nums = sorted(numbers_in(_tidy(text)), key=lambda n: _tidy(text).find(n))
    bad = [n for n in nums if n not in allowed]
    # a refused number is never shown, even marked as refused; only how many there were
    return {"numbers": [{"n": n, "ok": True} for n in nums if n in allowed], "ok": not bad, "refused": len(bad)}


def _args_label(args: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in args.items() if k in ("bill_id", "check", "item_id"))


def _fallback_summary(rid: str, agent: dict) -> dict:
    bills = _bills(rid)
    probs = sum(b["counts"]["problem"] for b in bills)
    answered = sum(1 for s in agent["trace"] if s["kind"] == "answer")
    letter = next((s for s in reversed(agent["trace"]) if s["kind"] == "letter"), None)
    en = f"Checked {len(bills)} bills. {answered} of your answers were used. "
    ur = f"{len(bills)} بل جانچے۔ آپ کے {answered} جواب استعمال ہوئے۔ "
    if probs:
        en += f"{probs} problems found; the complaint is ready below."
        ur += f"{probs} مسائل ملے؛ شکایت نیچے تیار ہے۔"
        if letter:
            en += f" The utility must settle it by {letter['settle_by']}."
            ur += f" کمپنی کو {letter['settle_by']} تک حل کرنا ہے۔"
    else:
        en += "No problem found in what could be checked."
        ur += "جتنا جانچا جا سکا اس میں کوئی مسئلہ نہیں ملا۔"
    return {"en": en, "ur": ur, "source": "code"}


def _apply_reply(rid: str, ask: dict, value) -> str:
    bill_id, kind, key = ask["item_id"].split(":", 2)
    if kind == "confirm":
        absent = value == "absent"
        report.answer(rid, bill_id, key, absent)
        return "absent" if absent else "present"
    if kind == "date":
        report.correct(rid, bill_id, "delivery_date", str(value))
        return str(value)
    if kind in ("figure", "meter"):
        if not re.fullmatch(r"\d+(\.\d+)?", str(value).strip()):
            raise ValueError("Enter a number.")
        report.correct(rid, bill_id, key, str(value).strip())
        return str(value).strip()
    raise ValueError("Unknown question.")


def _run(rid: str) -> None:
    agent = _get(rid)
    try:
        calls = 0
        while calls < MAX_CALLS:
            calls += 1
            t0 = time.time()
            r = chat(agent["messages"], reasoning_effort="low", max_tokens=900, tools=TOOLS, tag="agent")
            agent["cost_usd"] = round(agent.get("cost_usd", 0) + (0 if r.get("cached") else r.get("usd", 0)), 6)
            u = r.get("usage") or {}
            reasoning = u.get("reasoning_tokens") or (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
            st = agent.setdefault("stats", {"calls": 0, "tokens_in": 0, "tokens_out": 0, "reasoning_tokens": 0})
            st["calls"] += 1
            st["tokens_in"] += u.get("prompt_tokens") or 0
            st["tokens_out"] += u.get("completion_tokens") or 0
            st["reasoning_tokens"] += reasoning
            tcs = r.get("tool_calls") or []
            note = _clean(r.get("content"), agent) if tcs else None
            agent["trace"].append(_step("think", "", "", reasoning_tokens=reasoning,
                                        seconds=round(r.get("latency_s") or (time.time() - t0), 1),
                                        note=note, tools=[c["name"] for c in tcs], replayed=bool(r.get("cached"))))
            agent["messages"].append({"role": "assistant", "content": r.get("content") or "",
                                      **({"tool_calls": [{"id": c["id"], "type": "function", "function":
                                                          {"name": c["name"], "arguments": c["arguments"]}} for c in tcs]}
                                         if tcs else {})})
            if not tcs:                      # the model spoke without a tool: treat its words as the finish
                agent["summary"] = ({"text": t, "source": "muse-spark-open"} if (t := _clean(r.get("content"), agent))
                                    else _fallback_summary(rid, agent))
                agent["grounding"] = _grounding(r.get("content") or "", agent)
                agent["status"] = "done"
                break
            stop = False
            for c in tcs:
                try:
                    args = json.loads(c["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                result: dict
                if c["name"] == "make_plan":
                    items = []
                    for it in (args.get("steps") or [])[:6]:
                        text = _clean(str(it.get("text") or ""), agent) if isinstance(it, dict) else None
                        if text and it.get("kind") in PLAN_KINDS:
                            items.append({"kind": it["kind"], "text": text})
                    agent["plan"] = items
                    result = {"ok": True, "steps": len(items)}
                elif c["name"] == "list_open_items":
                    result = tool_list(rid)
                elif c["name"] == "recheck":
                    result = tool_recheck(rid, str(args.get("bill_id")))
                elif c["name"] == "explain_rule":
                    result = tool_explain(rid, str(args.get("bill_id")), str(args.get("check")))
                elif c["name"] == "prepare_complaint":
                    result = tool_complaint(rid, str(args.get("bill_id")))
                elif c["name"] == "ask_household" and stop:
                    result = {"error": "one question at a time; this one was not asked"}
                elif c["name"] == "ask_household" and sum(st["kind"] == "ask" for st in agent["trace"]) >= MAX_QUESTIONS:
                    result = {"error": f"the household has been asked {MAX_QUESTIONS} questions; call finish"}
                elif c["name"] == "ask_household":
                    item = next((i for b in _bills(rid) for i in _items(b)
                                 if i.get("item_id") == args.get("item_id") and i["who"] == "household"
                                 and i["item_id"] not in agent.get("skipped", [])), None)
                    found = None
                    if item is not None and item["kind"] == "meter":
                        # SAM 3 must find the meter photo before the household is asked to read it
                        bid = item["item_id"].split(":")[0]
                        found = meter_found(rid, bid)
                        bm = _bill(rid, bid)
                        agent["trace"].append(_step(
                            "look",
                            f"SAM 3 found the meter photo on the {_month(bm)} bill and cut it out." if found else
                            f"SAM 3 could not find the meter photo on the {_month(bm)} bill.",
                            f"SAM 3 نے {_month(bm, 'ur')} کے بل پر میٹر کی تصویر ڈھونڈ کر الگ کر دی۔" if found else
                            f"SAM 3 کو {_month(bm, 'ur')} کے بل پر میٹر کی تصویر نہیں ملی۔",
                            tool="sam3_find_meter", args=f"bill_id={bid}"))
                    if item is None:
                        result = {"error": "not an open household item; call list_open_items"}
                    elif item["kind"] == "meter" and not found:
                        result = {"error": "SAM 3 found no meter photo on this bill's photos, so the household cannot "
                                           "be asked to read it; choose another item or finish"}
                    else:
                        reason = _clean(args.get("reason"), agent)
                        bill = _bill(rid, item["item_id"].split(":")[0])
                        agent["ask"] = {**item, "reason": reason, "call_id": c["id"], "month": _month(bill),
                                        "month_ur": _month(bill, "ur")}
                        en, ur = _label(item, bill)
                        agent["trace"].append(_step("ask", f"Asked you {en}.", f"آپ سے پوچھا: {ur}؟"))
                        agent["status"] = "waiting"
                        stop = True
                        continue      # its tool result is written when the household answers
                elif c["name"] == "finish":
                    text = _clean(args.get("summary"), agent)
                    agent["summary"] = {"text": text, "source": "muse-spark-open"} if text else _fallback_summary(rid, agent)
                    agent["grounding"] = _grounding(args.get("summary") or "", agent)
                    agent["status"] = "done"
                    result = {"ok": True}
                    stop = True
                else:
                    result = {"error": f"unknown tool {c['name']}"}
                agent["messages"].append({"role": "tool", "tool_call_id": c["id"],
                                          "content": json.dumps(result, ensure_ascii=False)})
                step = _trace_for(c["name"], args, result)
                if step:
                    agent["trace"].append({**step, "tool": c["name"], "args": _args_label(args)})
            _put(rid, agent)
            if stop:
                break
        else:
            agent["status"] = "done"
            agent["summary"] = _fallback_summary(rid, agent)
    except BudgetExceeded:
        agent["status"] = "paused"
        agent["trace"].append(_step("paused", report.PAUSED["en"], report.PAUSED["ur"]))
    except Exception as e:   # a provider failure ends the segment; the page offers to try again
        agent["status"] = "failed"
        agent["error"] = repr(e)[:200]
    _put(rid, agent)


def start(rid: str, language: str, background: bool = True) -> dict | None:
    if report._state(rid) is None:
        return None
    current = _get(rid)
    if current and current.get("status") in ("running", "waiting"):
        return public(current)
    lang = "ur" if language == "ur" else "en"
    name, script = LANG[lang]
    agent = {"status": "running", "language": lang, "trace": [], "ask": None, "summary": None, "cost_usd": 0.0,
             "plan": [], "grounding": None, "started": time.time(), "model": "Muse Spark Open (Meta, open weights)",
             "messages": [{"role": "system", "content": SYSTEM.format(language=name, script=script)},
                          {"role": "user", "content": "Please work my case."}]}
    _put(rid, agent)
    return _go(rid, background)


def reply(rid: str, value, background: bool = True) -> dict | None:
    if report._state(rid) is None:
        return None
    agent = _get(rid)
    if not agent or agent.get("status") != "waiting" or not agent.get("ask"):
        raise ValueError("SahiBill is not waiting for an answer.")
    ask = agent["ask"]
    if value == "unsure":
        # the household does not know: nothing is applied, the item stays open and is not asked again
        agent.setdefault("skipped", []).append(ask["item_id"])
        agent["trace"].append(_step("answer", "You were not sure, so this stays open.", "آپ کو یقین نہیں تھا، اس لیے یہ کھلا رہے گا۔"))
        agent["messages"].append({"role": "tool", "tool_call_id": ask["call_id"],
                                  "content": json.dumps({"item_id": ask["item_id"], "household_answer": "not sure",
                                                         "applied": False, "note": "do not ask this again"})})
        agent["ask"] = None
        agent["status"] = "running"
        _put(rid, agent)
        return _go(rid, background)
    if ask["kind"] == "confirm" and value not in ("present", "absent"):
        raise ValueError("Answer present or absent.")
    if ask["kind"] == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value or "")):
        raise ValueError("Enter the date as YYYY-MM-DD.")
    bill_id = ask["item_id"].split(":")[0]
    before = {c.get("check"): c.get("status") for c in (_bill(rid, bill_id) or {}).get("cards") or []}
    applied = _apply_reply(rid, ask, value)
    shown = {"present": ("Yes, it is on the bill", "جی، بل پر موجود ہے"), "absent": ("No, it is not on the bill", "نہیں، بل پر نہیں ہے")}
    en, ur = shown.get(applied, (applied, applied))
    agent["trace"].append(_step("answer", f"You answered: {en}.", f"آپ کا جواب: {ur}۔"))
    # Every answer is applied and the bill re-checked by code, whatever the model plans next.
    after = _bill(rid, bill_id) or {}
    changed = [c for c in after.get("cards") or [] if before.get(c.get("check")) != c.get("status")]
    month = {"billing_month": after.get("billing_month")}
    if changed:
        agent["trace"].append(_step(
            "check", f"Re-ran the checks on {_month(month)} with your answer.",
            f"آپ کے جواب کے ساتھ {_month(month, 'ur')} کی جانچ دوبارہ کی۔",
            tool="recheck", args=f"bill_id={bill_id}",
            changes=[{"title": c["title"], "title_ur": c.get("title_ur") or c["title"], "status": c["status"]} for c in changed]))
    else:
        agent["trace"].append(_step("check", f"Re-ran the checks on {_month(month)} with your answer: no verdict changed yet.",
                                    f"آپ کے جواب کے ساتھ {_month(month, 'ur')} کی جانچ دوبارہ کی: ابھی کوئی فیصلہ نہیں بدلا۔",
                                    tool="recheck", args=f"bill_id={bill_id}"))
    agent["messages"].append({"role": "tool", "tool_call_id": ask["call_id"],
                              "content": json.dumps({"item_id": ask["item_id"], "household_answer": applied, "applied": True,
                                                     "rechecked": _bill_summary(after) if after else None,
                                                     "changed": [{"check": c.get("title"), "now": c.get("status")} for c in changed]},
                                                    ensure_ascii=False)})
    agent["ask"] = None
    agent["status"] = "running"
    _put(rid, agent)
    return _go(rid, background)


def _go(rid: str, background: bool) -> dict:
    if background:
        threading.Thread(target=_run, args=(rid,), daemon=True).start()
    else:
        _run(rid)
    return public(_get(rid))


def state(rid: str) -> dict | None:
    if report._state(rid) is None:
        return None
    return public(_get(rid))
