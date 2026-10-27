"""Hold any read field that breaks an identity every genuine bill satisfies. Free: no model call.

Identities used (each is a property of a correctly printed bill, not of the rules being checked):
1. present reading - previous reading = units billed + units carried forward (multiplying factor 1);
2. reading, issue and due dates fall in the billing month or the month before it, and in order;
3. the charge lines add up to the amount payable within the due date (within Rs 1, for rounding).
A held field is treated as unread: the rules see it as missing and the user is asked for a clearer photo.
The rates themselves are never used here, so a wrongly charged bill is still caught by the rules.
"""
from __future__ import annotations

from datetime import date

from sahibill.readers.bill import month_key, num

MONEY = ["variable", "fixed", "min_charge", "fca", "fc_surcharge", "qta", "gst", "gst_on_fpa"]
SUMMARY = ["total_electricity_charges", "subsidies", "net_electricity_charges", "taxes", "current_bill", "total_fpa"]


def _d(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def check(read: dict) -> dict:
    """Returns {"held": {field: reason}, "passed": [identity names]}."""
    f = {k: (v or {}).get("value") for k, v in (read.get("fields") or {}).items()}
    held, passed = {}, []
    prev, pres, units = num(f.get("prev_reading")), num(f.get("present_reading")), num(f.get("units"))
    carried = num(f.get("carried_forward")) or 0
    if None not in (prev, pres, units):
        if pres - prev == units + carried:
            passed.append("readings")
        else:
            for k in ("prev_reading", "present_reading", "units"):
                held[k] = f"present - previous ({pres} - {prev}) does not equal units {units} + carried {carried}"
    bm = month_key(f.get("billing_month"))
    dates = {k: _d(f.get(k)) for k in ("reading_date", "issue_date", "due_date")}
    if bm:
        y, m = map(int, bm.split("-"))
        allowed = {(y, m), (y - (m == 1), 12 if m == 1 else m - 1)}
        bad = [k for k, d in dates.items() if d and (d.year, d.month) not in allowed and k != "due_date"]
        order = [dates[k] for k in ("reading_date", "issue_date", "due_date") if dates[k]]
        if bad or order != sorted(order):
            for k in [*bad, *(["reading_date", "issue_date", "due_date"] if order != sorted(order) else [])]:
                held[k] = f"date not consistent with billing month {bm} or out of order"
            held["billing_month"] = "dates on the bill disagree with the billing month"
        elif any(dates.values()):
            passed.append("dates")
    # Dates must come after the most recent month printed in the billing history.
    hist_months = [month_key(h.get("month")) for h in read.get("history") or []]
    hist_months = [h for h in hist_months if h]
    if hist_months:
        latest = max(hist_months)
        for k, d in dates.items():
            if d and f"{d.year:04d}-{d.month:02d}" <= latest and k not in held:
                held[k] = f"date {d} is not after the latest history month {latest}"
    lines = [num(f.get(k)) for k in MONEY]
    payable = num(f.get("payable_within"))
    supp = read.get("supplementary") or []
    supp_amounts = [num(x.get("amount")) for x in supp]
    if payable is not None and num(f.get("variable")) is not None and None not in supp_amounts:
        total = sum(x for x in lines if x is not None) + sum(supp_amounts)
        if abs(total - payable) <= 1.0:
            passed.append("charges")
        else:
            for k in MONEY + ["payable_within"]:
                if num(f.get(k)) is not None:
                    held[k] = f"charge lines add to {total:.2f}, payable within due date is {payable}"
    # Bills that print totals only: total - subsidies = net; net + taxes = current bill; current + FPA = payable.
    t, sub, net, tax, cur, fpa = (num(f.get(k)) for k in SUMMARY)
    sums = [(t is not None and sub is not None and net is not None, lambda: t - sub - net),
            # net + taxes is the current bill (IESCO from Jul 2026) or the grand total with FPA inside (IESCO Jun 2026)
            (net is not None and tax is not None and (cur is not None or payable is not None),
             lambda: min(abs(net + tax - x) for x in (cur, payable) if x is not None)),
            (cur is not None and fpa is not None and payable is not None, lambda: cur + fpa - payable)]
    tested = [abs(diff()) <= 1.0 for ok, diff in sums if ok]
    if tested and all(tested):
        passed.append("summary")
    elif tested:
        for k in SUMMARY + ["payable_within"]:
            if num(f.get(k)) is not None:
                held[k] = "the bill's totals (charges, subsidy, taxes, FPA, payable) do not add up"
    return {"held": held, "passed": passed}


def apply(read: dict) -> dict:
    """A copy of the reading with held fields blanked, plus the consistency report."""
    rep = check(read)
    out = dict(read)
    out["fields"] = {k: ({"value": None, "text": None, "held": rep["held"][k]} if k in rep["held"] else v)
                     for k, v in (read.get("fields") or {}).items()}
    out["consistency"] = rep
    return out
