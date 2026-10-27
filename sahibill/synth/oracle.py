"""A perfect reading of a synthetic bill, built from its ground truth: what a flawless reader would return.

Used to check the generator's answer key against the rules, with no model involved.
"""
from __future__ import annotations

from sahibill.synth.render import supplementary_text


def oracle_read(truth: dict) -> dict:
    p = truth["printed"]
    keys = ["billing_month", "reading_date", "prev_reading_date", "issue_date", "due_date", "tariff",
            "sanctioned_load_kw", "status", "prev_reading", "present_reading", "units", "variable", "fixed", "gst",
            "payable_within"]
    fields = {k: {"value": p.get(k), "text": str(p.get(k))} for k in keys}
    for k in ("carried_forward", "min_charge", "fca", "qta"):
        fields[k] = {"value": p[k] or None, "text": str(p[k]) if p[k] else None}
    snap, stamp = p["snapshot_reading"], p["snapshot_stamp"]
    fields["snapshot_state"] = {"value": "readable" if snap is not None else "blank", "text": None}
    fields["snapshot_reading"] = {"value": snap, "text": str(snap)}
    fields["snapshot_stamp"] = {"value": stamp, "text": stamp}
    fields["snapshot_stamp_printed"] = {"value": "yes" if stamp else "no", "text": None}
    supp = []
    for s in p["supplementary"]:
        supp.append({**{k: s.get(k) for k in ("kind", "units", "amount", "months", "period_from", "period_to", "load_kw", "event_date")},
                     "text": supplementary_text(s)})
    return {"fields": fields, "history": [{"month": h["month"], "units": h["units"], "mode": h["mode"]} for h in p["history"]],
            "supplementary": supp, "orientation": 0}
