"""Photo in, verdict out: read (Spark Open, cached), hold inconsistent fields, run the rules, route gaps.

`analyze_reading` does everything after the read and never calls a model, so answers to questions and
corrections re-run the checks for free from a stored reading.
"""
from __future__ import annotations

import copy
from pathlib import Path

from sahibill.complaint.draft import template
from sahibill.complaint.requests import ROUTES, build_requests
from sahibill.readers import consistency
from sahibill.readers.bill import FIELDS, read_bill, to_facts
from sahibill.rules import run_all
from sahibill.rules.core import CBD
from sahibill.rules.meter import ASK_MCO, ASK_SNAPSHOT, ASK_STAMP
from sahibill.verdict import verdict

QUESTIONS = {"snapshot": ASK_SNAPSHOT, "stamp": ASK_STAMP, "mco": ASK_MCO}


def _question_text(missing: str) -> dict:
    for pattern, req in ROUTES:
        if pattern in missing:
            return {"en": req.en, "ur": req.ur}
    return {"en": missing, "ur": missing}


def questions(findings) -> list[dict]:
    """The yes/no questions a photo reading leaves for the user (absences, asked before they are alleged)."""
    out = []
    for qid, msg in QUESTIONS.items():
        if any(f.status == CBD and msg in f.missing for f in findings):
            out.append({"id": qid, **_question_text(msg)})
    return out


def apply_overrides(raw: dict, overrides: dict | None) -> dict:
    """A copy of the reading with the user's corrections in place of what was read."""
    if not overrides:
        return raw
    out = copy.deepcopy(raw)
    fields = out.setdefault("fields", {})
    for k, v in overrides.items():
        fields[k] = {"value": v, "text": None if v is None else str(v), "corrected": True}
    return out


def analyze_reading(raw: dict, phase: int | None = None, confirmed_absent: bool = False,
                    overrides: dict | None = None) -> dict:
    """Everything after the read, from a stored reading; no model call."""
    raw = apply_overrides(raw, overrides)
    checked = consistency.apply(raw)
    facts = to_facts(checked, phase=phase, confirmed_absent=confirmed_absent)
    findings = run_all(facts)
    reading = []
    for k, label in FIELDS.items():
        v = (checked.get("fields") or {}).get(k) or {}
        reading.append({"key": k, "label": label.split(",")[0].split(" (")[0], "value": v.get("value"),
                        "text": v.get("text"), "held": v.get("held"), "corrected": bool(v.get("corrected"))})
    v = verdict(findings)
    steps = build_requests(findings)
    return {
        "ok": True,
        "reading": reading,
        "history": checked.get("history") or [],
        "supplementary": checked.get("supplementary") or [],
        "consistency": checked.get("consistency"),
        "billing_month": facts.billing_month,
        "verdict": v,
        "questions": questions(findings),
        "next_steps": steps,
        "complaint": template(v, steps, facts.billing_month),
        "findings": [f.to_dict() for f in findings],
    }


def analyze(image: str | Path, phase: int | None = None, confirmed_absent: bool = False) -> dict:
    raw = read_bill(image, reasoning_effort="low", tag="app")
    if raw.get("error"):
        return {"ok": False, "error": "The bill could not be read. Please take the photo again, flat and in daylight."}
    out = analyze_reading(raw, phase=phase, confirmed_absent=confirmed_absent)
    calls = [raw.get("_call") or {}, ((raw.get("_first_pass") or {}).get("_call")) or {}]
    out.update(rotated=(raw.get("_first_pass") or {}).get("orientation"),
               cost_usd=round(sum(c.get("usd", 0) for c in calls if c and not c.get("cached")), 5),
               models={"reader": "Muse Spark Open (meta-models/muse-spark-open), open weights, via Nebius Token Factory"})
    return out
