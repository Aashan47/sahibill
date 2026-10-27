"""Two independent Meta models read the same bill; a field is accepted only where they agree.

Spark Open (hosted open weights) and Glimmer (self-hosted open weights) transcribe independently with the
same prompt. A field is accepted when both give the same value (numbers compared after removing
separators, dates and months compared normalised) and it is not held by the consistency layer. Anything
else is held: the rules see it as missing, and the user is asked for a clearer photo.
"""
from __future__ import annotations

from sahibill.readers import consistency
from sahibill.readers.bill import month_key, num

NUMERIC = {"sanctioned_load_kw", "prev_reading", "present_reading", "units", "carried_forward", "snapshot_reading",
           "variable", "fixed", "min_charge", "fca", "qta", "gst", "payable_within", "outstanding_units", "fc_surcharge",
           "gst_on_fpa", "total_electricity_charges", "subsidies", "net_electricity_charges", "taxes", "current_bill",
           "total_fpa"}


def _norm(k, v):
    if v is None:
        return None
    if k in NUMERIC:
        n = num(v)
        return None if n is None else round(float(n), 2)
    if k == "billing_month":
        return month_key(str(v))
    return str(v).strip().lower()[:32]


def combine(a: dict, b: dict) -> dict:
    """Merge two readings into one with only agreed fields; record every disagreement."""
    fa, fb = a.get("fields") or {}, b.get("fields") or {}
    fields, disagreements = {}, {}
    for k in set(fa) | set(fb):
        ea, eb = (e if isinstance(e, dict) else {} for e in (fa.get(k), fb.get(k)))   # off-schema entry: unread
        va, vb = ea.get("value"), eb.get("value")
        na, nb = _norm(k, va), _norm(k, vb)
        if na is not None and na == nb:
            fields[k] = fa[k]
        else:
            fields[k] = {"value": None, "text": None, "held": "readers disagree" if (na or nb) is not None else "unread"}
            if (na or nb) is not None:
                disagreements[k] = {"spark": va, "glimmer": vb}
    ha = {month_key(h.get("month")): num(h.get("units")) for h in a.get("history") or []}
    hb = {month_key(h.get("month")): num(h.get("units")) for h in b.get("history") or []}
    history = [{"month": m, "units": ha[m], "mode": ""} for m in ha if m and m in hb and ha[m] == hb[m] and ha[m] is not None]
    merged = {"fields": fields, "history": history, "supplementary": a.get("supplementary") or [],
              "agreement": {"disagreements": disagreements, "history_agreed": len(history),
                            "history_spark": len(ha), "history_glimmer": len(hb)}}
    return consistency.apply(merged)
