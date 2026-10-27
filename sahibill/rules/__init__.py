"""The rules engine: every check, run on one bill's facts. No model decides any number here."""
from __future__ import annotations

from sahibill.rules.charges import check_accumulated, check_detection, check_skipped
from sahibill.rules.consumption import check_arithmetic, check_period, check_status
from sahibill.rules.core import CBD, OK, PROBLEM, BillFacts, Finding
from sahibill.rules.dates import check_due_date
from sahibill.rules.meter import check_average, check_retrieval, check_snapshot

CHECKS = [check_period, check_snapshot, check_status, check_detection, check_average, check_retrieval,
          check_skipped, check_accumulated, check_arithmetic, check_due_date]


def run_all(f: BillFacts) -> list[Finding]:
    out: list[Finding] = []
    for check in CHECKS:
        out.extend(check(f))
    return out


def violations(findings: list[Finding]) -> set[str]:
    return {x.violation for x in findings if x.status == PROBLEM and x.violation}


__all__ = ["BillFacts", "Finding", "run_all", "violations", "PROBLEM", "OK", "CBD"]
