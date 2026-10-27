"""Checks 2 (snapshot), 5 (defective-meter average billing) and 6 (late retrieval charges).

Rule texts and cases: 09-RULES-TEST-CASES.md sections 2, 5 and 6.
"""
from __future__ import annotations

import math

from sahibill import tariff as T
from sahibill.rules.core import (CBD, OK, PROBLEM, BillFacts, Finding, add_months, is_month_only, month_index,
                                 parse_date)

CL_SNAP = "CSM 6.1.3 and 6.1.3.1 (snapshot printed, time-stamped, geo-tagged); CSM 6.4.1 (snapshot of present reading)"
# Absences read from a photo are asked before they are alleged (the reader may have missed them)
ASK_SNAPSHOT = "confirmation that no meter-reading photo is printed on the bill"
ASK_STAMP = "confirmation that no time stamp is printed with the meter-reading photo"
ASK_MCO = "confirmation that the old meter's final-reading photo is not printed"
CL_PRORATA = "CSM 6.1.1.1 (pro-rata billing; units over the period carried forward to the next billing cycle)"
CL_AVG ="CSM 4.3.1(b) and 4.3.2(b) (higher of same month last year or 11-month average, max 2 months); CSM 6.1.5 (provisional: lower)"
CL_RET = "CSM 4.3.2(d) (display wash: no debit unless retrieved within 3 months of replacement; 6 via manufacturer)"


def check_snapshot(f: BillFacts) -> list[Finding]:
    out = []
    if f.snapshot_present is False:
        if not f.absence_confirmed:
            return [Finding("2", CBD, clause=CL_SNAP, missing=[ASK_SNAPSHOT])]
        return [Finding("2", PROBLEM, "snapshot_missing_or_mismatch", CL_SNAP, note="no meter-reading snapshot printed")]
    if f.mco and f.mco_final_snapshot_present is False:
        out.append(Finding("2", CBD, clause=CL_SNAP, missing=[ASK_MCO]) if not f.absence_confirmed else
                   Finding("2", PROBLEM, "snapshot_missing_or_mismatch", CL_SNAP,
                           note="meter changed but the old meter's final-reading snapshot is not printed"))
    if f.snapshot:
        if f.present_reading is None:
            out.append(Finding("2", CBD, clause=CL_SNAP, missing=["billed present reading"]))
        else:
            mf = f.mf if f.mf is not None else (1.0 if f.phase == 1 else None)
            for reg, snap in f.snapshot.items():
                billed = f.present_reading.get(reg)
                if snap is None:
                    out.append(Finding("2", CBD, clause=CL_SNAP, missing=[f"legible snapshot reading ({reg})"]))
                elif billed is None:
                    out.append(Finding("2", CBD, clause=CL_SNAP, missing=[f"billed present reading ({reg})"]))
                elif billed == snap:
                    out.append(Finding("2", OK, clause=CL_SNAP, numbers={"register": reg, "excess_units": 0}))
                elif f.pro_rata_reading and billed < snap and mf is not None and f.carried_forward_units is not None \
                        and (snap - billed) * mf == f.carried_forward_units:
                    out.append(Finding("2", OK, clause=CL_SNAP + "; " + CL_PRORATA, note=(
                        "present reading billed pro-rata; the snapshot's recorded reading is higher by exactly the "
                        "units carried forward to the next bill"),
                        numbers={"register": reg, "snapshot": snap, "billed": billed,
                                 "carried_forward": f.carried_forward_units}))
                elif f.pro_rata_reading and billed < snap and f.carried_forward_units is None:
                    out.append(Finding("2", CBD, clause=CL_SNAP + "; " + CL_PRORATA,
                                       numbers={"register": reg, "snapshot": snap, "billed": billed},
                                       missing=["units carried forward (pro-rata reading)"]))
                else:
                    nums = {"register": reg, "snapshot": snap, "billed": billed,
                            "direction": "billed above snapshot" if billed > snap else "billed below snapshot"}
                    if mf is not None:
                        nums["excess_units"] = (billed - snap) * mf
                    else:
                        nums["excess_units"] = "cannot be determined: multiplying factor not printed"
                    out.append(Finding("2", PROBLEM, "snapshot_missing_or_mismatch", CL_SNAP, nums))
    if f.snapshot_stamp_present is False and not f.absence_confirmed:
        out.append(Finding("2", CBD, clause=CL_SNAP, missing=[ASK_STAMP]))
    elif f.snapshot_stamp_present is False or (f.snapshot_stamp_date is None and f.snapshot_geotag is False):
        out.append(Finding("2", PROBLEM, "snapshot_missing_or_mismatch", CL_SNAP,
                           note="snapshot shows no time stamp (CSM 6.1.3.1: time stamp and geo-tag shall be printed)"))
    elif f.pro_rata_reading and f.snapshot_stamp_date and f.reading_date and f.snapshot_stamp_date > f.reading_date:
        pass   # a pro-rata bill: the recorded reading (and its photo) comes after the reading date it is billed to
    elif f.snapshot_stamp_date and f.reading_date and f.snapshot_stamp_date != f.reading_date:
        out.append(Finding("2", PROBLEM, "snapshot_missing_or_mismatch", CL_SNAP,
                           {"stamp_date": f.snapshot_stamp_date, "reading_date": f.reading_date},
                           note="snapshot not taken on the reading date (derived from CSM 6.4.1 definitions)"))
    return out or [Finding("2", CBD, clause=CL_SNAP, missing=["snapshot"])]


def check_average(f: BillFacts) -> list[Finding]:
    a = f.average
    if not a:
        return []
    out = []
    consecutive = a.get("consecutive_months")
    if consecutive is not None:
        if consecutive > T.AVERAGE_MAX_MONTHS:
            out.append(Finding("5", PROBLEM, "average_billing_beyond_limit", CL_AVG,
                               {"consecutive_average_months": consecutive, "limit": T.AVERAGE_MAX_MONTHS}))
        else:
            out.append(Finding("5", OK, clause=CL_AVG, numbers={"consecutive_average_months": consecutive}))
    billed, same, eleven = a.get("billed_units"), a.get("same_month_last_year"), a.get("last_eleven")
    if billed is None:
        return out
    missing = []
    if same is None:
        missing.append("same month of the previous year")
    if not eleven or len(eleven) < 11 or any(u is None for u in eleven):
        missing.append("units of the last eleven months")
    if missing:
        return out + [Finding("5", CBD, clause=CL_AVG, missing=missing)]
    avg = sum(eleven) / 11
    rule = min(same, avg) if a.get("provisional") else max(same, avg)
    lo, hi = math.floor(rule), math.ceil(rule)     # rounding UNVERIFIED: floor and ceiling both accepted
    nums = {"rule_value": round(rule, 2), "eleven_month_average": round(avg, 2), "same_month_last_year": same,
            "billed": billed, "basis": "lower (provisional, CSM 6.1.5)" if a.get("provisional") else "higher"}
    if lo <= billed <= hi:
        out.append(Finding("5", OK, clause=CL_AVG, numbers=nums))
    else:
        nums["difference"] = round(billed - rule, 2)
        nums["direction"] = "above rule value" if billed > hi else "below rule value"
        out.append(Finding("5", PROBLEM, "average_billing_wrong_basis", CL_AVG, nums))
    return out


def _months_between(a: str, b: str) -> int:
    return month_index(b) - month_index(a)


def _within(start: str, end: str, months: int):
    """True, False or None (cannot tell at month resolution). Inclusive of the end date (U24)."""
    if is_month_only(start) or is_month_only(end):
        k = _months_between(start[:7], end[:7])
        if k <= months - 1:
            return True
        if k >= months + 1:
            return False
        return None
    return parse_date(end) <= add_months(parse_date(start), months)


def check_retrieval(f: BillFacts) -> list[Finding]:
    r = f.retrieval
    if not r:
        return []
    replaced, retrieved, debit, branch = r.get("replaced"), r.get("retrieved"), r.get("debit"), r.get("branch")
    flag = None
    if replaced and debit:
        w = _within(replaced, debit, 3)
        flag = None if w is None else (not w)
    if replaced and retrieved and flag is None:
        w = _within(replaced, retrieved, 3)
        if w is False:
            flag = True
    if r.get("defect") not in (None, "display_wash"):
        return [Finding("6", CBD, clause=CL_RET, missing=["a display-wash defect (4.3.2(d) does not cover this defect)"],
                        numbers={"nepra_practice_flag": flag})]
    if not replaced:
        return [Finding("6", CBD, clause=CL_RET, missing=["meter replacement date"])]

    def in_house():
        if retrieved:
            return _within(replaced, retrieved, 3)
        if debit and _within(replaced, debit, 3) is True:
            return True        # retrieval cannot follow the debit
        return None

    def manufacturer():
        point = debit or retrieved
        return _within(replaced, point, 6) if point else None

    if branch == "in_house":
        res = in_house()
    elif branch == "manufacturer":
        res = manufacturer()
    else:
        a, b = in_house(), manufacturer()
        res = a if a == b else (True if a is True and b is None else None)
    nums = {"nepra_practice_flag": flag}
    if res is True:
        return [Finding("6", OK, clause=CL_RET, numbers=nums)]
    if res is False:
        return [Finding("6", PROBLEM, "retrieval_charge_beyond_time_limit", CL_RET, nums)]
    missing = []
    if not retrieved:
        missing.append("retrieval date (not printed on bills)")
    if branch is None:
        missing.append("whether the meter was sent to the manufacturer")
    if not missing:
        missing.append("day of replacement and retrieval (month-level dates exactly at the limit)")
    return [Finding("6", CBD, clause=CL_RET, numbers=nums, missing=missing)]
