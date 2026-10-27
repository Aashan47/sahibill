"""Checks 1 (billing period and proration), 3 (slab, protected, lifeline) and 9 (A-1 arithmetic).

Rule texts and worked examples: 09-RULES-TEST-CASES.md sections 1, 3 and 9.
"""
from __future__ import annotations

from sahibill import tariff as T
from sahibill.rules.core import (CBD, OK, PROBLEM, BillFacts, Finding, days_in_month, money, month_index,
                                 parse_date, round_half_up)

CL_PERIOD = "Tariff T&C definition 1 (billing month of 31 days or less; prorate beyond the calendar month); CSM 6.1.1.1"
CL_STATUS = "Tariff T&C Part-II A-1 definitions (lifeline, protected)"
CL_ARITH = "NEPRA decision 11-02-2026 Annex-C (S.R.O. 279(I)/2026); FCA Aug 2026 decision; S.R.O. 1501(I)/2026"

RATES_FROM = "2026-03"   # first billing month certainly under the rationalised table (U10: Feb 2026 unclear)


def _hist_units(f: BillFacts):
    return [h.get("units") for h in (f.history or [])]


def eligible_status(f: BillFacts, current_units: int):
    """Expected status for a month with `current_units`. Returns (status | None, detail dict, missing list).

    None means cannot be determined (the detail says why, with both readings where they differ).
    """
    if f.tou:
        return "tou", {}, []
    hist = _hist_units(f)
    missing = []
    # Lifeline: single phase, load up to 1 kW, max of last 12 months and current <= 100.
    could_be_lifeline = (f.sanctioned_load_kw is not None and f.sanctioned_load_kw <= T.LIFELINE_MAX_LOAD_KW
                         and current_units <= T.LIFELINE_LIMIT
                         and all(u is not None and u <= T.LIFELINE_LIMIT for u in hist[:12]))
    if could_be_lifeline:
        if f.phase is None:
            return None, {}, ["phase of the connection"]
        if f.phase == 1:
            if len(hist) < 12:
                return None, {}, ["12 months of billing history (lifeline)"]
            return "lifeline", {"max_units": max(hist[:12] + [current_units])}, []
    # Protected: Non-ToU, <= 200 consistently for the past 6 months. No protected row above 200 units.
    if current_units > T.PROTECTED_LIMIT:
        return "unprotected", {"reason": "current month above 200 units"}, []
    if len(hist) < 6 or any(u is None for u in hist[:6]):
        return None, {}, ["6 months of billing history (protected)"]
    excl = all(u <= T.PROTECTED_LIMIT for u in hist[:6])                   # t-1 .. t-6
    incl = all(u <= T.PROTECTED_LIMIT for u in [current_units] + hist[:5])  # t .. t-5
    if excl != incl:
        return None, {"excluding_current": "protected" if excl else "unprotected",
                      "including_current": "protected" if incl else "unprotected"}, \
            ["whether 'the past 6 months' includes the current month (readings differ)"]
    return ("protected" if excl else "unprotected"), {}, missing


def rate_for(status: str, units: int) -> float:
    table = {"lifeline": T.LIFELINE, "protected": T.PROTECTED, "unprotected": T.UNPROTECTED}[status]
    return T.slab_row(table, units)[1][2]


def expected_variable(status: str, units: int) -> float:
    if status == "protected":
        if units <= 100:
            return money(units * T.PROTECTED[0][2])
        return money(100 * T.PROTECTED[0][2] + (units - 100) * T.PROTECTED[1][2])
    return money(units * rate_for(status, units))


def check_status(f: BillFacts) -> list[Finding]:
    if f.units is None:
        return [Finding("3", CBD, clause=CL_STATUS, missing=["units"])]
    exp, detail, missing = eligible_status(f, f.units)
    if exp is None:
        return [Finding("3", CBD, clause=CL_STATUS, missing=missing, numbers=detail)]
    if exp == "tou":
        return [Finding("3", OK, clause=CL_STATUS, note="ToU: protected and lifeline do not apply")]
    billed = f.status_billed
    if billed is None and f.rate_billed is not None:
        billed = next((s for s in ("lifeline", "protected", "unprotected")
                       if abs(rate_for(s, f.units) - f.rate_billed) < 0.005), None)
    if billed is None:
        return [Finding("3", CBD, clause=CL_STATUS, missing=["status or rate applied on the bill"],
                        numbers={"expected_status": exp})]
    if billed == exp:
        return [Finding("3", OK, clause=CL_STATUS, numbers={"status": exp, **detail})]
    rank = {"lifeline": 0, "protected": 1, "unprotected": 2}
    if rank[billed] > rank[exp]:
        return [Finding("3", PROBLEM, "protected_status_wrongly_removed", CL_STATUS,
                        {"expected_status": exp, "billed_status": billed, **detail})]
    return [Finding("3", OK, clause=CL_STATUS, numbers={"expected_status": exp, "billed_status": billed},
                    note="billed in a lower-priced category than the rule gives")]


def check_period(f: BillFacts) -> list[Finding]:
    rd, pd = parse_date(f.reading_date), parse_date(f.prev_reading_date)
    missing = [n for n, v in (("reading date", rd), ("previous reading date (not a required bill field)", pd),
                              ("units", f.units), ("billing month", f.billing_month)) if v is None]
    if missing:
        return [Finding("1", CBD, clause=CL_PERIOD, missing=missing)]
    period = (rd - pd).days
    dim = days_in_month(f.billing_month)
    if period <= dim:
        return [Finding("1", OK, clause=CL_PERIOD, numbers={"period_days": period, "days_in_month": dim})]
    prorated = int(round_half_up(f.units * dim / period))
    carry = f.units - prorated
    nums = {"period_days": period, "days_in_month": dim, "prorated_units": prorated, "carry_forward": carry}
    exp_status, _, miss = eligible_status(f, prorated)
    if exp_status is None:
        return [Finding("1", CBD, clause=CL_PERIOD, numbers=nums, missing=miss)]
    if exp_status == "tou":
        return [Finding("1", OK, clause=CL_PERIOD, numbers=nums, note="ToU: no slabs")]
    if f.rate_billed is None:
        return [Finding("1", CBD, clause=CL_PERIOD, numbers=nums, missing=["rate applied on the bill"])]
    exp_rate = rate_for(exp_status, prorated)
    nums.update(expected_status=exp_status, expected_rate=exp_rate, billed_rate=f.rate_billed)
    if abs(exp_rate - f.rate_billed) < 0.005:
        note = "" if f.carry_forward_shown in (None, True) else "carry-forward units not shown (CSM 6.1.1.2)"
        return [Finding("1", OK, clause=CL_PERIOD, numbers=nums, note=note)]
    return [Finding("1", PROBLEM, "slab_not_prorated_long_period", CL_PERIOD, nums)]


def check_arithmetic(f: BillFacts) -> list[Finding]:
    if f.billing_month is None:
        return [Finding("9", CBD, clause=CL_ARITH, missing=["billing month"])]
    if month_index(f.billing_month) < month_index(RATES_FROM):
        return [Finding("9", CBD, clause=CL_ARITH, missing=["rate table for this billing month"])]
    out = []
    if f.tou:
        if None in (f.peak_units, f.offpeak_units, f.sanctioned_load_kw):
            return [Finding("9", CBD, clause=CL_ARITH, missing=["peak/off-peak units or load"])]
        exp_var = money(f.peak_units * 46.85 + f.offpeak_units * 34.53)
        basis = max(0.5 * f.sanctioned_load_kw, f.mdi_kw or 0)
        exp_fixed = money(basis * 675)
        status_name, units = "tou", f.peak_units + f.offpeak_units
    else:
        if not f.units:
            return [Finding("9", CBD, clause=CL_ARITH, missing=["units (zero units has no slab row)"])]
        status_name, _, miss = eligible_status(f, f.units)
        if f.status_billed in ("lifeline", "protected", "unprotected"):
            status_name = f.status_billed          # arithmetic is checked on the category the bill used
        if status_name is None:
            return [Finding("9", CBD, clause=CL_ARITH, missing=miss)]
        units = f.units
        exp_var = expected_variable(status_name, units)
        table = {"lifeline": T.LIFELINE, "protected": T.PROTECTED, "unprotected": T.UNPROTECTED}[status_name]
        fx_rate = T.slab_row(table, units)[1][1]
        exp_fixed = money(fx_rate * (f.sanctioned_load_kw or 0)) if f.sanctioned_load_kw is not None else None
    lines = [("variable", exp_var, f.variable_billed), ("fixed", exp_fixed, f.fixed_billed)]
    # FCA: billed two months later on the reference month's units (lifeline exempt). The bill's own note, where
    # printed, names the month, its units and the rate; each is checked against the history and NEPRA's decision.
    y, m = map(int, f.billing_month.split("-"))
    ref_month = f"{y - (m <= 2):04d}-{(m - 3) % 12 + 1:02d}"
    hist_units = next((h.get("units") for h in (f.history or []) if h.get("month") == ref_month), None)
    nepra_rate = T.FCA_BY_REFERENCE_MONTH.get(ref_month)
    if f.fpa_ref_month is not None:
        lines.append(("fpa_month", ref_month, f.fpa_ref_month))
    if f.fpa_ref_units is not None and hist_units is not None:
        lines.append(("fpa_units", hist_units, f.fpa_ref_units))
    if f.fpa_rate is not None:
        if nepra_rate is None:
            out.append(Finding("9", CBD, clause=CL_ARITH, missing=[f"NEPRA's FCA rate for {ref_month}"]))
        else:
            lines.append(("fpa_rate", nepra_rate, f.fpa_rate))
    if f.fpa_billed is not None:
        if status_name == "lifeline":
            lines.append(("fpa", 0.0, f.fpa_billed))
        elif nepra_rate is None:
            out.append(Finding("9", CBD, clause=CL_ARITH, missing=[f"NEPRA's FCA rate for {ref_month}"]))
        elif hist_units is None:
            out.append(Finding("9", CBD, clause=CL_ARITH, missing=[f"units of {ref_month} in the history"]))
        else:
            lines.append(("fpa", money(hist_units * nepra_rate), f.fpa_billed))
    if f.qta_billed is not None:
        q = T.QTA_BY_BILLING_MONTH.get(f.billing_month)
        if status_name == "lifeline":
            lines.append(("qta", 0.0, f.qta_billed))
        elif q is None:
            out.append(Finding("9", CBD, clause=CL_ARITH, missing=[f"QTA rate for billing month {f.billing_month}"]))
        else:
            lines.append(("qta", money(units * q), f.qta_billed))
    for name, exp, billed in lines:
        if billed is None or exp is None:
            continue
        if name in ("fpa_month", "fpa_units", "fpa_rate"):
            same = billed == exp if name != "fpa_rate" else abs(billed - exp) < 0.00005
            out.append(Finding("9", OK, clause=CL_ARITH, numbers={"line": name, "expected": exp, "billed": billed}) if same
                       else Finding("9", PROBLEM, "tariff_arithmetic_error", CL_ARITH,
                                    {"line": name, "expected": exp, "billed": billed}))
            continue
        diff = money(billed - exp)
        if abs(diff) <= 0.01:
            out.append(Finding("9", OK, clause=CL_ARITH, numbers={"line": name, "expected": exp, "billed": billed}))
        else:
            out.append(Finding("9", PROBLEM, "tariff_arithmetic_error", CL_ARITH,
                               {"line": name, "expected": exp, "billed": billed, "difference": diff}))
    return out or [Finding("9", CBD, clause=CL_ARITH, missing=["billed charge lines"])]
