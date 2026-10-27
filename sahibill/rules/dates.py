"""Check 10: due date. CSM 6.5 (within 15 days of issue; clear 7 days from delivery); CSM 6.4.1
(holiday moves the due date); tariff General Condition 2 (delivered at least seven days before).
Cases: 09-RULES-TEST-CASES.md section 10.
"""
from __future__ import annotations

from datetime import timedelta

from sahibill import tariff as T
from sahibill.rules.core import CBD, OK, PROBLEM, BillFacts, Finding, parse_date

CL_DUE = "CSM 6.5: due date within 15 days of issue; consumer has clear 7 days from delivery; CSM 6.4.1 holiday rule"


def check_due_date(f: BillFacts) -> list[Finding]:
    issue, due = parse_date(f.issue_date), parse_date(f.due_date)
    if issue is None or due is None:
        miss = ["issue date"] if issue is None else ["due date"]
        return [Finding("10A", CBD, clause=CL_DUE, missing=miss), Finding("10B", CBD, clause=CL_DUE, missing=miss)]
    out = []
    span = (due - issue).days
    if span <= T.DUE_DATE_MAX_DAYS:
        out.append(Finding("10A", OK, clause=CL_DUE, numbers={"issue_to_due_days": span}))
    elif f.holidays is None:
        out.append(Finding("10A", CBD, clause=CL_DUE, numbers={"issue_to_due_days": span},
                           missing=["public holiday calendar (a holiday moves the due date)"]))
    else:
        gap = [(issue + timedelta(days=k)).isoformat() for k in range(T.DUE_DATE_MAX_DAYS, span)]
        moved = all(d in f.holidays for d in gap)
        out.append(Finding("10A", OK if moved else PROBLEM, None if moved else "due_date_too_short", CL_DUE,
                           {"issue_to_due_days": span},
                           note="" if moved else "later than 15 days after issue: favourable to the consumer, procedural"))
    delivery = parse_date(f.delivery_date)
    if delivery is None:
        if span <= 6:
            out.append(Finding("10B", PROBLEM, "due_date_too_short", CL_DUE, {"issue_to_due_days": span},
                               note="under seven days even with delivery on the issue day"))
        else:
            out.append(Finding("10B", CBD, clause=CL_DUE, numbers={"issue_to_due_days": span},
                               missing=["delivery date (not printed on bills)"]))
    else:
        counting_due = (due - delivery).days          # T&C: "at least seven days before the due date"
        strictly_between = counting_due - 1           # a "clear days" reading excluding both ends
        nums = {"delivery_to_due_days": counting_due}
        if strictly_between >= 7:
            out.append(Finding("10B", OK, clause=CL_DUE, numbers=nums))
        elif counting_due < 7:
            out.append(Finding("10B", PROBLEM, "due_date_too_short", CL_DUE, nums))
        else:
            out.append(Finding("10B", CBD, clause=CL_DUE, numbers=nums,
                               missing=["meaning of 'clear seven days' (readings differ)"]))
    return out
