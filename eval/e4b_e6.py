"""Score E4b (rules engine on facts read from page images) and E6 (reading and attribution) against the labels.

python eval/e4b_e6.py --labels <dir> --reads <dir> --pdfs <dir> --e4a results/e4a.json --out results/e4b-e6.json
Scoring is fixed in PREREGISTRATION.md (amendment of 22 October 2026). The output holds stems, codes and
counts only (NEPRA documents are not redistributed).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path

from sahibill.readers.bill import month_key, num
from sahibill.rules import BillFacts, CBD, PROBLEM, run_all

from e4a import ENGINE_VIOLATIONS, FIELDS

DATE_FIELDS = {"billing_month", "detection_period_from", "detection_period_to"}


def norm_value(field: str, v):
    """A comparable form of a labelled or read value; None when the value is not a number or a month."""
    if v is None:
        return None
    if isinstance(v, dict):
        parts = sorted((month_key(str(k)) or str(k), norm_value(field, x)) for k, x in v.items())
        return tuple(parts) if parts and all(x is not None for _, x in parts) else None
    if field in DATE_FIELDS:
        return month_key(str(v))
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).strip()
    if re.fullmatch(r"[\d,]+(\.\d+)?", s):
        return round(float(num(s)), 2)
    return None


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()


def page_texts(pdf: Path) -> dict[int, str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    return {i: _text(t) for i, t in enumerate(out.split("\f"), 1)}


def quote_check(fact: dict, pages: dict[int, str], scan: bool = False) -> str:
    """'pass', 'fail' or 'unverifiable' (no text layer on that page). The quote must be on the stated page
    (longest common run at least 80% of the quote) and a number's digits must appear in the quote."""
    page = pages.get(fact.get("page") if isinstance(fact.get("page"), int) else -1, "")
    if scan or len(page) < 40:          # no usable text layer (the label records which decisions are scans)
        return "unverifiable"
    q = _text(fact.get("quote"))
    if not q:
        return "fail"
    m = SequenceMatcher(None, q, page, autojunk=False).find_longest_match(0, len(q), 0, len(page))
    if m.size < 0.8 * len(q):
        return "fail"
    v = norm_value(fact.get("field", ""), fact.get("value"))
    if isinstance(v, float) and fact.get("field") not in DATE_FIELDS:
        digits = re.sub(r"\D", "", (fact.get("quote") or ""))
        whole = str(int(v)) if v == int(v) else str(v).replace(".", "")
        if whole not in digits:
            return "fail"
    return "pass"


def same_sentence(a: str, b: str) -> bool:
    x, y = _text(a), _text(b)
    if not x or not y:
        return False
    m = SequenceMatcher(None, x, y, autojunk=False).find_longest_match(0, len(x), 0, len(y))
    return m.size >= 0.6 * min(len(x), len(y))


def e6(label: dict, read: dict, pages: dict[int, str], use_quote_check: bool, scan: bool) -> dict:
    """Values: a labelled number or month is read right when a read fact has the same field and value.
    Speakers are judged sentence by sentence: a read fact of that field and value whose quote is the
    labelled fact's sentence must name the labelled speaker. Restatements the label does not record are
    not judged."""
    facts = [f for f in read.get("facts") or [] if isinstance(f, dict)]
    if use_quote_check:
        facts = [f for f in facts if quote_check(f, pages, scan) != "fail"]
    labelled = right = 0
    wrong = []
    for lf in label.get("facts") or []:
        v = norm_value(lf["field"], lf.get("value"))
        if v is None:
            continue
        labelled += 1
        hits = [f for f in facts if f.get("field") == lf["field"] and norm_value(lf["field"], f.get("value")) == v]
        right += bool(hits)
        for f in hits:
            if same_sentence(f.get("quote"), lf.get("quote")) and f.get("speaker") != lf.get("speaker"):
                wrong.append([lf["field"], str(v), lf.get("speaker"), f.get("speaker")])
                break
    return {"labelled": labelled, "read_right": right, "wrong_speaker": len(wrong), "wrong_speaker_items": wrong}


def facts_of(read: dict) -> BillFacts:
    raw = read.get("bill_facts") or {}
    return BillFacts(**{k: v for k, v in raw.items() if k in FIELDS and v is not None})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--reads", type=Path, required=True)
    ap.add_argument("--pdfs", type=Path, required=True)
    ap.add_argument("--e4a", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    e4a = {r["stem"]: r for r in json.loads(a.e4a.read_text())["rows"]}
    rows = []
    for rp in sorted(a.reads.glob("*.json")):
        stem, read = rp.stem, json.loads(rp.read_text())
        label = json.loads((a.labels / f"{stem}.json").read_text())
        pages = page_texts(next(a.pdfs.rglob(f"{stem}.pdf")))
        scan = not label.get("text_layer_usable", True)
        checks = [quote_check(f, pages, scan) for f in read.get("facts") or [] if isinstance(f, dict)]
        row = {"stem": stem, "error": read.get("error"), "facts_read": len(checks),
               "quote_check": {k: checks.count(k) for k in ("pass", "fail", "unverifiable")},
               "e6": e6(label, read, pages, False, scan), "e6_quote_checked": e6(label, read, pages, True, scan)}
        try:
            findings = run_all(facts_of(read))
            raised = {f.violation for f in findings if f.status == PROBLEM and f.violation}
            missing = sorted({m for f in findings if f.status == CBD for m in f.missing})
        except Exception as e:   # noqa: BLE001  (a read the engine cannot take counts as no finding)
            raised, missing, row["engine_error"] = set(), [], repr(e)[:200]
        src = json.dumps(read.get("bill_sources") or {})
        ref = e4a.get(stem, {})
        row.update(engine=sorted(raised), missing=missing, leaky="nepra_finding" in src or "ordered_correction" in src,
                   e4a_set=ref.get("set"), e4a_match=ref.get("match"), e4a_leaky=ref.get("leaky"))
        if ref.get("set") == "scored":
            target = set(ref["nepra"]) & ENGINE_VIOLATIONS
            row["match"] = bool(raised & target)
            row["gap"] = ("both" if row["match"] and ref["match"] else "reading" if ref["match"] else
                          "reading_added" if row["match"] else "rules")
        rows.append(row)
    sc = [r for r in rows if "match" in r]
    strict = [r for r in sc if not r["leaky"]]

    def tot(key, sub):
        return sum(r[key][sub] for r in rows)

    summary = {
        "decisions_read": len(rows), "unparseable": sum(1 for r in rows if r["error"]),
        "e4b_scored": len(sc), "e4b_matched": sum(r["match"] for r in sc),
        "e4b_strict": len(strict), "e4b_strict_matched": sum(r["match"] for r in strict),
        "e4a_matched_same_decisions": sum(bool(r["e4a_match"]) for r in sc),
        "gaps": {g: sum(r["gap"] == g for r in sc) for g in ("both", "reading", "rules", "reading_added")},
        "e6_labelled_values": tot("e6", "labelled"), "e6_read_right": tot("e6", "read_right"),
        "e6_decisions_with_wrong_speaker": sum(r["e6"]["wrong_speaker"] > 0 for r in rows),
        "e6_quote_checked_read_right": tot("e6_quote_checked", "read_right"),
        "e6_quote_checked_decisions_with_wrong_speaker": sum(r["e6_quote_checked"]["wrong_speaker"] > 0 for r in rows),
        "quote_check": {k: sum(r["quote_check"][k] for r in rows) for k in ("pass", "fail", "unverifiable")},
    }
    if sc:
        summary["e4b_match_rate"] = round(summary["e4b_matched"] / len(sc), 3)
    if strict:
        summary["e4b_strict_match_rate"] = round(summary["e4b_strict_matched"] / len(strict), 3)
    if summary["e6_labelled_values"]:
        summary["e6_value_accuracy"] = round(summary["e6_read_right"] / summary["e6_labelled_values"], 3)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
