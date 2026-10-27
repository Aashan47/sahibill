"""Checks 4 (detection bill: 4A formula, 4B months, 4C history), 7 (skipped-charge recovery) and
8 (accumulated units). Rule texts and cases: 09-RULES-TEST-CASES.md sections 4, 7 and 8.
"""
from __future__ import annotations

import math

from sahibill import tariff as T
from sahibill.rules.core import CBD, OK, PROBLEM, BillFacts, Finding, money, month_index

CL_DET_F = "CSM 9.1.3, 9.2.3(b): units = Load x Load Factor x 730 x Months, less units already charged; Annexure V"
CL_DET_P = "CSM 9.2.3(b): order of priority, billing history first"
CL_DET_M = "CSM 9.2.3(c)(i): 3 billing cycles for A-1, A-2, A-3, up to 6 with CEO approval; CSM 9.1.3: 6 months registered, 12 unregistered"
CL_DET_D = "CSM 9.2.5: detection bill shows reasons, units, amount, period, taxes"
CL_DET_H = "CSM 9.2.3(b)(i)-(ii): previous and future consumption; NEPRA decisions on history"
CL_SKIP = "CSM 7.5.5: skipped charges raised within one year, for at most 6 months retrospectively"
CL_ACC = "CSM 6.4.2: accumulated readings billed as segregated monthly bills; CSM 10.3.1(h)"

SHORTFALL_D = 0   # D3: no threshold in any source (U20); fixed in the pre-registration


def check_detection(f: BillFacts) -> list[Finding]:
    d = f.detection
    if not d:
        return []
    out = []
    months = d.get("months")
    if months is None:
        out.append(Finding("4A", PROBLEM, "detection_procedure_not_followed", CL_DET_D,
                           note="The detection bill does not state the period it covers."))
    if d.get("reasons") is None:
        out.append(Finding("4B", PROBLEM, "detection_procedure_not_followed", CL_DET_D,
                           note="The detection bill does not state its reasons."))

    # 4A formula
    loads = [x for x in (d.get("connected_load_kw", f.connected_load_kw), f.sanctioned_load_kw) if x is not None]
    if months is not None and d.get("units") is not None:
        if not loads:
            out.append(Finding("4A", CBD, clause=CL_DET_F, missing=["load"]))
        else:
            load = max(loads)
            phase = f.phase or (3 if load >= 5 else None)
            already = d.get("already_charged", 0) or 0
            bound = lambda lf: load * lf * T.HOURS_PER_MONTH * months - already
            billed = d["units"]
            if phase is not None:
                mx = bound(T.LOAD_FACTOR[phase])
                nums = {"load_kw": load, "load_factor": T.LOAD_FACTOR[phase], "months": months,
                        "already_charged": already, "max_units": round(mx, 2), "billed_units": billed}
                if billed <= mx + 1e-9:
                    out.append(Finding("4A", OK, clause=CL_DET_F, numbers=nums))
                else:
                    nums["excess_units"] = round(billed - mx, 2)
                    out.append(Finding("4A", PROBLEM, "detection_units_formula_error", CL_DET_F, nums))
            else:
                lo, hi = bound(T.LOAD_FACTOR[1]), bound(T.LOAD_FACTOR[3])
                nums = {"load_kw": load, "months": months, "bound_20pct": round(lo, 2), "bound_25pct": round(hi, 2),
                        "billed_units": billed}
                if billed > hi:
                    nums["excess_over_25pct"] = round(billed - hi, 2)
                    out.append(Finding("4A", PROBLEM, "detection_units_formula_error", CL_DET_F, nums))
                elif billed <= lo:
                    out.append(Finding("4A", OK, clause=CL_DET_F, numbers=nums))
                else:
                    out.append(Finding("4A", CBD, clause=CL_DET_F, numbers=nums, missing=["phase of the connection"]))
    # 4A priority: load basis used while a credible history exists
    if d.get("basis") == "load" and d.get("history_credible") and not d.get("history_not_credible_reason"):
        out.append(Finding("4A", PROBLEM, "detection_procedure_not_followed", CL_DET_P,
                           note="Charged on load although a usable billing history exists; the manual puts history first."))

    # 4B months limit
    if months is not None:
        reason, registered = d.get("reasons"), d.get("registered", True)
        cat = d.get("category", "A-1")
        if reason == "direct_theft":
            limit = 6 if registered else 12
            st = OK if months <= limit else PROBLEM
            out.append(Finding("4B", st, "detection_load_or_period_exceeds_limits" if st == PROBLEM else None,
                               CL_DET_M, {"months": months, "limit": limit}))
        else:
            general = cat in ("A-1", "A-2", "A-3")
            base = 3 if general else 6
            approval = d.get("approval")
            if months <= base:
                st = OK
            elif months > 6:
                st = PROBLEM
            elif reason is None:
                st = CBD
            elif approval is True:
                st = OK
            elif approval is False:
                st = PROBLEM
            else:
                st = CBD
            missing = []
            if st == CBD:
                missing = ["detection reasons (direct theft or tampering)"] if reason is None else \
                          ["CEO or committee approval (never printed on a bill)"]
            out.append(Finding("4B", st, "detection_load_or_period_exceeds_limits" if st == PROBLEM else None,
                               CL_DET_M, {"months": months, "base_limit": base}, missing))

    # 4C history test (any-arm rule, D3)
    period = d.get("period_units")
    arms = {}
    for arm, key in (("previous_year", "previous_year_units"), ("future", "future_units")):
        comp = d.get(key)
        if period and comp and None not in comp and None not in period:
            k = min(len(comp), len(period))   # compare the months both lists cover (spec 4.6, FESCO_0146)
            arms[arm] = sum(comp[:k]) - sum(period[:k])
    if period is not None or d.get("previous_year_units") or d.get("future_units"):
        if not arms:
            out.append(Finding("4C", CBD, clause=CL_DET_H, missing=["consumption of the comparison months"]))
        elif any(v > SHORTFALL_D for v in arms.values()):
            out.append(Finding("4C", OK, clause=CL_DET_H, numbers={"shortfall_by_arm": arms}))
        else:
            out.append(Finding("4C", PROBLEM, "detection_not_justified_by_history", CL_DET_H,
                               {"shortfall_by_arm": arms}))
    return out


def _inclusive_months(a: str, b: str) -> int:
    return month_index(b) - month_index(a) + 1


def check_skipped(f: BillFacts) -> list[Finding]:
    s = f.skipped
    if not s:
        return []
    out = []
    missing_details = [k for k in ("reason", "amount") if not s.get(k)]
    if not s.get("period_from") and not s.get("months"):
        missing_details.append("period of charging")
    if missing_details:
        out.append(Finding("7", PROBLEM, "skipped_charges_beyond_recovery_limit", CL_SKIP,
                           note="supplementary bill lacks: " + ", ".join(missing_details)))
    pf, pt, raised, checking = s.get("period_from"), s.get("period_to"), s.get("raised"), s.get("checking")
    if not (pf and pt) and s.get("months"):
        n = int(s["months"])          # only the month count is printed: T1 still applies
        if n > T.SKIPPED_MAX_MONTHS:
            out.append(Finding("7", PROBLEM, "skipped_charges_beyond_recovery_limit", CL_SKIP, {"months_charged": n}))
        elif not out:
            out.append(Finding("7", CBD, clause=CL_SKIP, numbers={"months_charged": n}, missing=["period of charging"]))
        return out
    if not (pf and pt):
        if not out:
            out.append(Finding("7", CBD, clause=CL_SKIP, missing=["period of charging"]))
        return out
    n = _inclusive_months(pf, pt)
    nums = {"months_charged": n}
    if n > T.SKIPPED_MAX_MONTHS:
        out.append(Finding("7", PROBLEM, "skipped_charges_beyond_recovery_limit", CL_SKIP, dict(nums)))
    if checking:
        earliest_ok = month_index(checking) - T.SKIPPED_MAX_MONTHS
        within_window = month_index(pf) >= earliest_ok and month_index(pt) <= month_index(checking)
        nums.update(checking=checking)
        if raised:
            lag = month_index(raised) - month_index(checking)
            nums["months_raised_after_checking"] = lag
            if lag > T.SKIPPED_RAISE_WITHIN_MONTHS:
                out.append(Finding("7", PROBLEM, "skipped_charges_beyond_recovery_limit", CL_SKIP, dict(nums),
                                   note="Raised more than one year after the discrepancy was checked."))
        if not within_window and n <= T.SKIPPED_MAX_MONTHS:
            out.append(Finding("7", PROBLEM, "skipped_charges_beyond_recovery_limit", CL_SKIP, dict(nums),
                               note="The months charged fall outside the 6 months before checking."))
    elif raised:
        back = month_index(raised) - month_index(pf)
        nums["earliest_month_before_bill"] = back
        if back > T.SKIPPED_MAX_MONTHS + T.SKIPPED_RAISE_WITHIN_MONTHS:
            out.append(Finding("7", PROBLEM, "skipped_charges_beyond_recovery_limit", CL_SKIP, dict(nums)))
        elif not any(x.status == PROBLEM for x in out):
            out.append(Finding("7", CBD, clause=CL_SKIP, numbers=dict(nums), missing=["date of checking"]))
    if not out:
        out.append(Finding("7", OK, clause=CL_SKIP, numbers=nums))
    return out


def check_accumulated(f: BillFacts) -> list[Finding]:
    a = f.accumulated
    if not a:
        return []
    lump, months = a.get("lump_units"), a.get("months_covered")
    if a.get("segregated_shown"):
        return [Finding("8", OK, clause=CL_ACC, note="segregated monthly bills shown")]
    if months is None or months < 2:
        if a.get("admitted"):
            return [Finding("8", PROBLEM, "accumulated_units_charged_at_once", CL_ACC,
                            note="accumulation admitted; months not stated, so segregated figures cannot be determined")]
        if months == 1:
            return [Finding("8", OK, clause=CL_ACC, note="not accumulated")]
        return [Finding("8", CBD, clause=CL_ACC, missing=["number of months the units cover"])]
    if lump is None:
        if a.get("admitted"):
            return [Finding("8", PROBLEM, "accumulated_units_charged_at_once", CL_ACC,
                            note="accumulation admitted; units not stated, so segregated figures cannot be determined")]
        return [Finding("8", CBD, clause=CL_ACC, missing=["units charged at once"])]
    per = lump / months
    nums = {"lump_units": lump, "months": months, "units_per_month": round(per, 2)}
    rates = [r for r in T.UNPROTECTED]
    if per != int(per) and any(math.floor(per) <= row[0] < math.ceil(per) for row in rates[:-1]):
        nums["slab_per_month"] = "cannot be determined: split straddles a slab boundary"
    elif a.get("status", "unprotected") == "unprotected":
        per_rate = T.slab_row(T.UNPROTECTED, per)[1][2]
        lump_rate = T.slab_row(T.UNPROTECTED, lump)[1][2]
        seg = money(months * per * per_rate)
        lumped = money(lump * lump_rate)
        nums.update(segregated_variable=seg, lumped_variable=lumped, difference=money(lumped - seg))
    return [Finding("8", PROBLEM, "accumulated_units_charged_at_once", CL_ACC, nums)]
