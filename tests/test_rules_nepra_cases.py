"""Real NEPRA complaint decisions (09-RULES-TEST-CASES.md, label cases), facts as recorded in the labels.

Where the written rule and NEPRA's ruling disagree, the test asserts NEPRA's finding and is marked
xfail(strict=True): the disagreement stays visible, and if the engine ever starts agreeing the test fails
and must be reviewed. A disagreement is a finding, not an error.
"""
import pytest

from sahibill.rules import BillFacts, CBD, OK, PROBLEM
from sahibill.rules.charges import check_accumulated, check_detection, check_skipped
from sahibill.rules.consumption import check_period, check_status
from sahibill.rules.dates import check_due_date
from sahibill.rules.meter import check_average, check_retrieval, check_snapshot


def status_of(findings, check=None):
    fs = [f for f in findings if check is None or f.check == check]
    if any(f.status == PROBLEM for f in fs):
        return PROBLEM
    if any(f.status == CBD for f in fs):
        return CBD
    return OK


def disagree(reason):
    return pytest.mark.xfail(strict=True, reason="disagrees with NEPRA: " + reason)


# Agreements -----------------------------------------------------------------------------------------

def test_kelectric_0389_period_and_status():
    f = BillFacts(billing_month="2024-07", reading_date="2024-07-11", prev_reading_date="2024-06-10",
                  units=205, status_billed="unprotected")
    assert status_of(check_period(f)) == OK
    assert status_of(check_status(f)) == OK


@pytest.mark.parametrize("stem,kw,excess", [
    ("LESCO_0783", dict(snapshot={"offpeak": 11144, "peak": 173}, present_reading={"offpeak": 75506, "peak": 1119}), None),
    ("LESCO_0892", dict(tou=True, mf=80, snapshot={"offpeak": 8759, "peak": 1976}, present_reading={"offpeak": 9995, "peak": 1976}), 98880),
    ("LESCO_0847", dict(tou=True, mf=40, snapshot={"offpeak": 10144, "peak": 2215}, present_reading={"offpeak": 15122, "peak": 2215}), 199120),
])
def test_snapshot_cases(stem, kw, excess):
    fs = check_snapshot(BillFacts(**kw))
    assert status_of(fs) == PROBLEM, stem
    if excess:
        assert excess in [f.numbers.get("excess_units") for f in fs], stem


def test_gepco_0237_detection_finding_and_months():
    f = BillFacts(phase=1, detection=dict(units=1220, months=6, connected_load_kw=1.4, already_charged=956,
                                          reasons="direct_theft"))
    fs = check_detection(f)
    assert status_of(fs, "4A") == PROBLEM
    assert status_of(fs, "4B") == OK


def test_lesco_0845_priority():
    f = BillFacts(detection=dict(units=1592, months=3, connected_load_kw=4.218, basis="load",
                                 history_credible=True, reasons="direct_theft"))
    assert any(x.violation == "detection_procedure_not_followed" for x in check_detection(f))


def test_kelectric_0470_months_and_formula():
    f = BillFacts(sanctioned_load_kw=12, detection=dict(units=15150, months=6, connected_load_kw=3.609,
                                                        reasons="tampering", category="A-2", approval=False))
    fs = check_detection(f)
    assert status_of(fs, "4B") == PROBLEM
    assert status_of(fs, "4A") == PROBLEM


def test_lesco_0734_history():
    f = BillFacts(detection=dict(months=3, reasons="tampering", period_units=[269, 149, 66],
                                 previous_year_units=[243, 165, 36], future_units=[50, 50, 0]))
    assert status_of(check_detection(f), "4C") == PROBLEM


def test_fesco_0146_history_any_arm():
    f = BillFacts(detection=dict(months=6, reasons="tampering",
                                 period_units=[184, 100, 54, 259, 70, 107],
                                 previous_year_units=[184, 29, 87, 103, 70, 79],
                                 future_units=[539, 277, 459]))
    assert status_of(check_detection(f), "4C") == OK


def test_fesco_0089_average_two_months():
    sept = dict(billed_units=5142, same_month_last_year=5142,
                last_eleven=[1816, 170, 944, 82, 378, 546, 58, 0, 1057, 0, 0])
    octo = dict(billed_units=1549, same_month_last_year=1816,
                last_eleven=[170, 944, 82, 378, 546, 58, 0, 1057, 0, 0, 5142])
    assert status_of(check_average(BillFacts(average=sept))) == OK
    fs = check_average(BillFacts(average=octo))
    assert status_of(fs) == PROBLEM and fs[0].numbers["direction"] == "below rule value"


@pytest.mark.parametrize("stem,months", [("LESCO_1040", 6), ("LESCO_1053", 5)])
def test_average_too_long(stem, months):
    assert status_of(check_average(BillFacts(average=dict(consecutive_months=months)))) == PROBLEM, stem


def test_lesco_0883_retrieval():
    f = BillFacts(retrieval=dict(defect="display_wash", replaced="2023-03", retrieved="2024-01", debit="2024-02"))
    assert status_of(check_retrieval(f)) == PROBLEM


@pytest.mark.parametrize("stem,s", [
    ("FESCO_0138", dict(reason="MF-1 instead of MF-40", amount=1, period_from="2023-05", period_to="2024-10", raised="2024-11")),
    ("GEPCO_0235", dict(reason="units refunded then debited back", amount=24852, period_from="2023-12", period_to="2024-04", raised="2026-01")),
    ("PESCO_1443", dict(reason="MF 01 instead of 20", amount=1, period_from="2022-10", period_to="2024-06", checking="2024-08", raised="2025-08")),
])
def test_skipped_cases(stem, s):
    assert status_of(check_skipped(BillFacts(skipped=s))) == PROBLEM, stem


@pytest.mark.parametrize("stem,a", [
    ("LESCO_1032a", dict(lump_units=2316, months_covered=4)),
    ("LESCO_1032b", dict(lump_units=1027, months_covered=3)),
    ("LESCO_1203", dict(lump_units=5386, admitted=True)),
    ("MEPCO_1266", dict(lump_units=305, months_covered=3)),
])
def test_accumulated_cases(stem, a):
    assert status_of(check_accumulated(BillFacts(accumulated=a))) == PROBLEM, stem


# Disagreements (asserting NEPRA's finding; expected to fail) ---------------------------------------

@disagree("protected status for a connection about three months old; the rule needs six months of history")
def test_mepco_1266_protected_status():
    f = BillFacts(phase=1, sanctioned_load_kw=1, units=101, status_billed="unprotected",
                  history=[{"month": "2023-08", "units": 102, "mode": ""}, {"month": "2023-07", "units": 102, "mode": ""}])
    assert status_of(check_status(f)) == PROBLEM


@disagree("NEPRA rounds the monthly figure to 204 and orders 268 units; the formula gives 270.4")
def test_gepco_0237_number():
    f = BillFacts(phase=1, detection=dict(units=1220, months=6, connected_load_kw=1.4, already_charged=956,
                                          reasons="direct_theft"))
    a = [x for x in check_detection(f) if x.check == "4A"][0]
    assert a.numbers["max_units"] == 268


@disagree("six detection months on A-1 with nothing recorded on approval; NEPRA treats the missing record as a breach")
def test_kelectric_0427_months():
    f = BillFacts(detection=dict(months=6, reasons="tampering", category="A-1"))
    assert status_of(check_detection(f), "4B") == PROBLEM


@disagree("disputed months 23 to 43 percent below the year before; NEPRA called it no significant variation")
def test_kelectric_0394_history():
    f = BillFacts(detection=dict(months=2, reasons="tampering", period_units=[2104, 2067],
                                 previous_year_units=[4127, 3222], future_units=[1777, 2324]))
    assert status_of(check_detection(f), "4C") == PROBLEM


@pytest.mark.parametrize("stem,r", [
    ("LESCO_1062", dict(defect="display_wash", replaced="2024-07", debit="2025-02")),
    ("LESCO_0991", dict(defect="display_wash", replaced="2023-09", debit="2025-07")),
])
@disagree("the clause keys on the retrieval date, which the decision does not give; NEPRA measured the debit")
def test_retrieval_without_retrieval_date(stem, r):
    assert status_of(check_retrieval(BillFacts(retrieval=r))) == PROBLEM, stem


@disagree("seven months billed as one; CSM 6.4.2 requires segregation, NEPRA found no violation")
def test_lesco_1056_accumulated():
    assert status_of(check_accumulated(BillFacts(tou=True, accumulated=dict(lump_units=2180, months_covered=7)))) == OK


@disagree("issue to due date is 8 days, within the 15-day ceiling; NEPRA compared reading-to-due gaps across DISCOs")
def test_iesco_0316_due_date():
    assert status_of(check_due_date(BillFacts(issue_date="2024-02-20", due_date="2024-02-28"))) == PROBLEM
