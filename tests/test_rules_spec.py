"""Synthetic cases from 09-RULES-TEST-CASES.md, by ID. Expected values are the spec's hand arithmetic."""
import pytest

from sahibill.rules import BillFacts, CBD, OK, PROBLEM
from sahibill.rules.charges import check_accumulated, check_detection, check_skipped
from sahibill.rules.consumption import check_arithmetic, check_period, check_status
from sahibill.rules.dates import check_due_date
from sahibill.rules.meter import check_average, check_retrieval, check_snapshot


def H(units, start="2026-09", n=None):
    """History most recent first, months counting back from `start`."""
    y, m = map(int, start.split("-"))
    out = []
    for u in units:
        out.append({"month": f"{y:04d}-{m:02d}", "units": u, "mode": ""})
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def one(findings, check=None):
    fs = [f for f in findings if check is None or f.check == check]
    assert len(fs) == 1, fs
    return fs[0]


LIFE = dict(phase=1, sanctioned_load_kw=1, history=H([40] * 12))
PROT = dict(phase=1, sanctioned_load_kw=2, history=H([150] * 12))
UNPR = dict(phase=1, sanctioned_load_kw=2, history=H([350] * 12))


# 1 Billing period and proration
@pytest.mark.parametrize("cid,kw,status,nums", [
    ("BP-01", dict(**LIFE, billing_month="2026-11", reading_date="2026-11-10", prev_reading_date="2026-10-08", units=54, rate_billed=7.74), PROBLEM, {"prorated_units": 49, "carry_forward": 5}),
    ("BP-02", dict(**LIFE, billing_month="2026-11", reading_date="2026-11-10", prev_reading_date="2026-10-08", units=109, rate_billed=28.91), PROBLEM, {"prorated_units": 99, "carry_forward": 10}),
    ("BP-03", dict(**PROT, billing_month="2026-11", reading_date="2026-11-10", prev_reading_date="2026-10-08", units=208, rate_billed=33.10), PROBLEM, {"prorated_units": 189, "carry_forward": 19}),
    ("BP-04", dict(**UNPR, billing_month="2026-11", reading_date="2026-11-10", prev_reading_date="2026-10-08", units=309, rate_billed=36.46), PROBLEM, {"prorated_units": 281, "carry_forward": 28}),
    ("BP-05", dict(**UNPR, billing_month="2026-07", reading_date="2026-07-31", prev_reading_date="2026-06-30", units=205, rate_billed=33.10), OK, {}),
    ("BP-06", dict(**UNPR, billing_month="2026-11", reading_date="2026-11-30", prev_reading_date="2026-10-30", units=310, rate_billed=36.46), PROBLEM, {"prorated_units": 300, "carry_forward": 10}),
    ("BP-07", dict(**UNPR, billing_month="2026-08", reading_date="2026-08-31", prev_reading_date="2026-07-30", units=320, rate_billed=36.46, carry_forward_shown=False), OK, {"prorated_units": 310}),
    ("BP-08", dict(phase=1, sanctioned_load_kw=2, history=H([150] * 12, "2027-01"), billing_month="2027-02", reading_date="2027-02-28", prev_reading_date="2027-01-30", units=202, rate_billed=33.10), PROBLEM, {"prorated_units": 195, "carry_forward": 7}),
    ("BP-09", dict(**UNPR, billing_month="2026-11", reading_date="2026-11-30", prev_reading_date="2026-10-31", units=210, rate_billed=33.10), OK, {}),
    ("BP-10", dict(**UNPR, billing_month="2026-11", reading_date="2026-11-30", units=210, rate_billed=33.10), CBD, {}),
])
def test_period(cid, kw, status, nums):
    f = one(check_period(BillFacts(**kw)))
    assert f.status == status, (cid, f)
    for k, v in nums.items():
        assert f.numbers[k] == v, (cid, k, f.numbers)


# 2 Snapshot
@pytest.mark.parametrize("cid,kw,status,excess", [
    ("SN-01", dict(phase=1, snapshot={"total": 12345}, present_reading={"total": 12345}, snapshot_stamp_date="2026-10-05", reading_date="2026-10-05", snapshot_geotag=True), OK, 0),
    ("SN-02", dict(phase=1, mf=1, snapshot={"total": 12345}, present_reading={"total": 12545}), PROBLEM, 200),
    ("SN-03", dict(tou=True, mf=80, snapshot={"offpeak": 8759, "peak": 1976}, present_reading={"offpeak": 9995, "peak": 1976}), PROBLEM, 98880),
    ("SN-04", dict(snapshot_present=False), PROBLEM, None),
    ("SN-05", dict(phase=1, snapshot={"total": 12345}, present_reading={"total": 12345}, snapshot_stamp_date=None, snapshot_geotag=False), PROBLEM, None),
    ("SN-06", dict(phase=1, snapshot={"total": None}, present_reading={"total": 12345}), CBD, None),
    ("SN-07", dict(phase=1, snapshot={"total": 12345}, present_reading={"total": 12345}, snapshot_stamp_date="2026-10-02", reading_date="2026-10-05"), PROBLEM, None),
    ("SN-08", dict(phase=1, mf=1, snapshot={"total": 12400}, present_reading={"total": 12345}), PROBLEM, -55),
    ("SN-09", dict(mco=True, mco_final_snapshot_present=False), PROBLEM, None),
])
def test_snapshot(cid, kw, status, excess):
    fs = check_snapshot(BillFacts(**kw))
    worst = PROBLEM if any(f.status == PROBLEM for f in fs) else (CBD if any(f.status == CBD for f in fs) else OK)
    assert worst == status, (cid, fs)
    if excess is not None:
        got = [f.numbers.get("excess_units") for f in fs if "excess_units" in f.numbers]
        assert excess in got, (cid, got)


# 3 Status
@pytest.mark.parametrize("cid,kw,status", [
    ("ST-01", dict(phase=1, sanctioned_load_kw=1, history=H([95] + [60] * 11), units=80, rate_billed=7.74), OK),
    ("ST-02", dict(phase=1, sanctioned_load_kw=1, history=H([95] + [60] * 11), units=80, status_billed="protected"), PROBLEM),
    ("ST-03", dict(phase=1, sanctioned_load_kw=1.5, history=H([90] * 12), units=80, status_billed="protected"), OK),
    ("ST-04", dict(phase=1, sanctioned_load_kw=1, history=H([101] + [60] * 11), units=80, status_billed="protected"), OK),
    ("ST-05", dict(phase=3, sanctioned_load_kw=1, history=H([60] * 12), units=80, status_billed="protected"), OK),
    ("ST-06", dict(phase=1, sanctioned_load_kw=2, history=H([180, 150, 200, 190, 170, 160]), units=150, status_billed="unprotected"), PROBLEM),
    ("ST-07", dict(phase=1, sanctioned_load_kw=2, history=H([180, 201, 200, 190, 170, 160]), units=150, status_billed="unprotected"), OK),
    ("ST-08", dict(phase=1, sanctioned_load_kw=2, history=H([180, 150, 200, 190, 170, 250]), units=150, status_billed="unprotected"), CBD),
    ("ST-09", dict(phase=1, sanctioned_load_kw=2, history=H([180] * 6), units=205, status_billed="unprotected"), OK),
    ("ST-10", dict(phase=1, sanctioned_load_kw=2, history=H([150] * 3), units=150, status_billed="unprotected"), CBD),
    ("ST-11", dict(tou=True, units=150), OK),
])
def test_status(cid, kw, status):
    assert one(check_status(BillFacts(**kw))).status == status, cid


# 4A formula and priority
@pytest.mark.parametrize("cid,kw,det,status,num", [
    ("DF-01", dict(phase=1, sanctioned_load_kw=1), dict(units=438, months=3, connected_load_kw=1, reasons="tampering"), OK, ("max_units", 438)),
    ("DF-02", dict(phase=1, sanctioned_load_kw=1), dict(units=439, months=3, connected_load_kw=1, reasons="tampering"), PROBLEM, ("excess_units", 1)),
    ("DF-03", dict(phase=1, sanctioned_load_kw=4), dict(units=1752, months=3, reasons="tampering"), OK, ("max_units", 1752)),
    ("DF-04", dict(phase=3, sanctioned_load_kw=2), dict(units=1600, months=3, connected_load_kw=3.5, already_charged=400, reasons="tampering"), PROBLEM, ("excess_units", 83.75)),
    ("DF-05", dict(sanctioned_load_kw=2), dict(units=1000, months=3, reasons="tampering"), CBD, ("bound_25pct", 1095)),
    ("DF-06", dict(sanctioned_load_kw=2), dict(units=1200, months=3, reasons="tampering"), PROBLEM, ("excess_over_25pct", 105)),
    ("DF-07", dict(), dict(units=1200, months=3, reasons="tampering"), CBD, None),
])
def test_detection_formula(cid, kw, det, status, num):
    f = one([x for x in check_detection(BillFacts(detection=det, **kw)) if x.check == "4A"])
    assert f.status == status, (cid, f)
    if num:
        assert f.numbers[num[0]] == pytest.approx(num[1]), (cid, f.numbers)


def test_df08_priority_and_df09_no_period():
    fs = check_detection(BillFacts(sanctioned_load_kw=1, phase=1, detection=dict(units=300, months=3, basis="load", history_credible=True, reasons="tampering")))
    assert any(f.check == "4A" and f.status == PROBLEM and f.violation == "detection_procedure_not_followed" for f in fs)
    fs = check_detection(BillFacts(sanctioned_load_kw=1, phase=1, detection=dict(units=300, reasons="tampering")))
    assert any(f.status == PROBLEM and "does not state the period" in f.note for f in fs)


# 4B months
@pytest.mark.parametrize("cid,det,status", [
    ("DM-01", dict(months=3, reasons="tampering"), OK),
    ("DM-02", dict(months=4, reasons="tampering"), CBD),
    ("DM-03", dict(months=4, reasons="tampering", approval=False), PROBLEM),
    ("DM-04", dict(months=7, reasons="tampering"), PROBLEM),
    ("DM-05", dict(months=6, reasons="direct_theft"), OK),
    ("DM-06", dict(months=7, reasons="direct_theft"), PROBLEM),
    ("DM-07", dict(months=12, reasons="direct_theft", registered=False), OK),
    ("DM-08", dict(months=5), CBD),
])
def test_detection_months(cid, det, status):
    fs = [x for x in check_detection(BillFacts(detection=det)) if x.check == "4B" and "reasons" not in x.note]
    assert one(fs).status == status, cid


def test_dm08_also_flags_missing_reasons():
    fs = check_detection(BillFacts(detection=dict(months=5)))
    assert any(f.status == PROBLEM and "does not state its reasons" in f.note for f in fs)


# 4C history
@pytest.mark.parametrize("cid,det,status", [
    ("DH-01", dict(period_units=[150, 160, 170], previous_year_units=[250, 260, 270]), OK),
    ("DH-02", dict(period_units=[300, 300, 300], previous_year_units=[280, 290, 300]), PROBLEM),
    ("DH-03", dict(period_units=[300, 300, 300], previous_year_units=[300, 300, 300]), PROBLEM),
    ("DH-04", dict(period_units=[300, 300, 300]), CBD),
])
def test_detection_history(cid, det, status):
    assert one([x for x in check_detection(BillFacts(detection=det)) if x.check == "4C"]).status == status, cid


# 5 Average billing
ELEVEN = [200, 220, 240, 260, 280, 300, 320, 340, 360, 380, 400]
@pytest.mark.parametrize("cid,avg,status", [
    ("AV-01", dict(billed_units=350, same_month_last_year=350, last_eleven=ELEVEN), OK),
    ("AV-02", dict(billed_units=420, same_month_last_year=350, last_eleven=ELEVEN), PROBLEM),
    ("AV-03", dict(billed_units=300, same_month_last_year=350, last_eleven=ELEVEN), PROBLEM),
    ("AV-04", dict(consecutive_months=2), OK),
    ("AV-05", dict(consecutive_months=3), PROBLEM),
    ("AV-06a", dict(billed_units=300, same_month_last_year=300, last_eleven=[300] * 10 + [301]), OK),
    ("AV-06b", dict(billed_units=301, same_month_last_year=300, last_eleven=[300] * 10 + [301]), OK),
    ("AV-07", dict(billed_units=300, last_eleven=ELEVEN), CBD),
    ("AV-08", dict(billed_units=350, same_month_last_year=350, last_eleven=[300] * 11, provisional=True), PROBLEM),
])
def test_average(cid, avg, status):
    assert one(check_average(BillFacts(average=avg))).status == status, cid


# 6 Late retrieval
@pytest.mark.parametrize("cid,r,status,flag", [
    ("RT-01", dict(defect="display_wash", replaced="2026-03-14", retrieved="2026-05-20", debit="2026-06-05", branch="in_house"), OK, False),
    ("RT-02", dict(defect="display_wash", replaced="2026-03-14", retrieved="2026-06-14", branch="in_house"), OK, None),
    ("RT-03", dict(defect="display_wash", replaced="2026-03-14", retrieved="2026-06-15", branch="in_house"), PROBLEM, True),
    ("RT-04", dict(defect="display_wash", replaced="2026-03-14", debit="2026-09-05", branch="manufacturer"), OK, True),
    ("RT-05", dict(defect="display_wash", replaced="2026-03-14", debit="2026-09-20", branch="manufacturer"), PROBLEM, True),
    ("RT-06", dict(defect="display_wash", replaced="2026-03", retrieved="2026-05", branch="in_house"), OK, None),
    ("RT-07", dict(defect="display_wash", replaced="2026-03", retrieved="2026-06", branch="in_house"), CBD, None),
    ("RT-08", dict(defect="display_wash", replaced="2026-03", retrieved="2026-07", branch="in_house"), PROBLEM, True),
    ("RT-09", dict(defect="display_wash", replaced="2026-03", debit="2026-10"), CBD, True),
    ("RT-10", dict(defect="burnt", replaced="2026-03", debit="2026-10"), CBD, True),
])
def test_retrieval(cid, r, status, flag):
    f = one(check_retrieval(BillFacts(retrieval=r)))
    assert f.status == status, (cid, f)
    assert f.numbers.get("nepra_practice_flag") == flag, (cid, f.numbers)


# 7 Skipped charges
BASE7 = dict(reason="multiplying factor", amount=1000)
@pytest.mark.parametrize("cid,s,status", [
    ("SK-01", dict(BASE7, period_from="2026-04", period_to="2026-09", checking="2026-10", raised="2026-10"), OK),
    ("SK-02", dict(BASE7, period_from="2026-03", period_to="2026-09", checking="2026-10", raised="2026-10"), PROBLEM),
    ("SK-03", dict(BASE7, period_from="2025-10", period_to="2026-03", checking="2026-04", raised="2026-10"), OK),
    ("SK-04", dict(BASE7, period_from="2025-10", period_to="2026-03", checking="2026-04", raised="2027-05"), PROBLEM),
    ("SK-05", dict(BASE7, period_from="2025-10", period_to="2026-03", checking="2026-04", raised="2027-04"), OK),
    ("SK-06", dict(BASE7, period_from="2025-01", period_to="2025-06", raised="2027-01"), PROBLEM),
    ("SK-07", dict(BASE7, period_from="2026-01", period_to="2026-06", raised="2026-10"), CBD),
    ("SK-08", dict(reason="multiplying factor", amount=1000), PROBLEM),
])
def test_skipped(cid, s, status):
    fs = check_skipped(BillFacts(skipped=s))
    worst = PROBLEM if any(f.status == PROBLEM for f in fs) else (CBD if any(f.status == CBD for f in fs) else OK)
    assert worst == status, (cid, fs)


# 8 Accumulated units
@pytest.mark.parametrize("cid,a,status,nums", [
    ("AC-01", dict(lump_units=450, months_covered=3), PROBLEM, {"segregated_variable": 13009.50, "lumped_variable": 17527.50, "difference": 4518.00}),
    ("AC-02", dict(lump_units=450, months_covered=3, segregated_shown=True), OK, {}),
    ("AC-03", dict(lump_units=450, months_covered=1), OK, {}),
    ("AC-04", dict(lump_units=2000), CBD, {}),
    ("AC-05", dict(lump_units=401, months_covered=2), PROBLEM, {"units_per_month": 200.5}),
    ("AC-06", dict(lump_units=800, months_covered=4), PROBLEM, {"units_per_month": 200}),
])
def test_accumulated(cid, a, status, nums):
    f = one(check_accumulated(BillFacts(accumulated=a)))
    assert f.status == status, (cid, f)
    for k, v in nums.items():
        assert f.numbers[k] == v, (cid, k, f.numbers)


def test_ac05_slab_cannot_be_determined():
    f = one(check_accumulated(BillFacts(accumulated=dict(lump_units=401, months_covered=2))))
    assert "straddles" in str(f.numbers["slab_per_month"])


# 9 Arithmetic
OCT_H = H([280, 300, 290] + [250] * 9)   # Sep, Aug (300), Jul ...
@pytest.mark.parametrize("cid,kw,status,exp", [
    ("TA-01", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=2, units=250, history=OCT_H, status_billed="unprotected", variable_billed=8275.00, fixed_billed=700.00, fpa_billed=332.58, qta_billed=129.85), OK, None),
    ("TA-02", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=2, units=250, history=OCT_H, status_billed="unprotected", variable_billed=9115.00), PROBLEM, 840.00),
    ("TA-03", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=1, units=150, history=H([150] * 12), status_billed="protected", variable_billed=1704.50, fixed_billed=300.00), OK, None),
    ("TA-04", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=1, units=100, history=H([250] * 12), status_billed="unprotected", variable_billed=2244.00, fixed_billed=275.00), OK, None),
    ("TA-05", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=1, units=101, history=H([250] * 12), status_billed="unprotected", variable_billed=2919.91, fixed_billed=300.00), OK, None),
    ("TA-06", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=1, units=80, history=H([60] * 12), status_billed="lifeline", variable_billed=619.20), OK, None),
    ("TA-07", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=1, units=50, history=H([40] * 12), status_billed="lifeline", variable_billed=197.50), OK, None),
    ("TA-08", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=1, units=50, history=H([40] * 12), status_billed="lifeline", fpa_billed=55.43), PROBLEM, None),
    ("TA-09", dict(billing_month="2026-10", phase=1, sanctioned_load_kw=1.5, units=350, history=H([350] * 12), status_billed="unprotected", variable_billed=12761.00, fixed_billed=600.00), OK, None),
    ("TA-10", dict(billing_month="2026-10", tou=True, peak_units=100, offpeak_units=400, sanctioned_load_kw=6, mdi_kw=4, variable_billed=18497.00, fixed_billed=2700.00), OK, None),
    ("TA-11", dict(billing_month="2026-12", phase=1, sanctioned_load_kw=2, units=250, history=H([250] * 12, "2026-11"), status_billed="unprotected", qta_billed=129.85), CBD, None),
    ("TA-12", dict(billing_month="2026-11", phase=1, sanctioned_load_kw=2, units=250, history=H([250] * 12, "2026-10"), status_billed="unprotected", fpa_billed=300.0), CBD, None),
    ("TA-13", dict(billing_month="2026-01", phase=1, sanctioned_load_kw=2, units=250, history=H([250] * 12, "2025-12")), CBD, None),
])
def test_arithmetic(cid, kw, status, exp):
    fs = check_arithmetic(BillFacts(**kw))
    worst = PROBLEM if any(f.status == PROBLEM for f in fs) else (CBD if any(f.status == CBD for f in fs) else OK)
    assert worst == status, (cid, fs)
    if exp is not None:
        assert any(f.numbers.get("difference") == exp for f in fs), (cid, fs)


# 10 Due date
@pytest.mark.parametrize("cid,kw,a,b", [
    ("DD-01", dict(issue_date="2026-10-05", due_date="2026-10-20"), OK, CBD),
    ("DD-02", dict(issue_date="2026-10-05", due_date="2026-10-21", holidays=set()), PROBLEM, CBD),
    ("DD-03", dict(issue_date="2026-10-05", due_date="2026-10-21", holidays={"2026-10-20"}), OK, CBD),
    ("DD-04", dict(issue_date="2026-10-05", due_date="2026-10-21"), CBD, CBD),
    ("DD-05", dict(issue_date="2026-10-05", due_date="2026-10-11"), OK, PROBLEM),
    ("DD-06", dict(issue_date="2026-10-05", due_date="2026-10-20", delivery_date="2026-10-08"), OK, OK),
    ("DD-07", dict(issue_date="2026-10-05", due_date="2026-10-20", delivery_date="2026-10-13"), OK, CBD),
    ("DD-08", dict(due_date="2026-10-20"), CBD, CBD),
])
def test_due_date(cid, kw, a, b):
    fs = check_due_date(BillFacts(**kw))
    assert one(fs, "10A").status == a, (cid, fs)
    assert one(fs, "10B").status == b, (cid, fs)


def test_accumulated_units_not_stated():
    """Found in stage 3 (IESCO_0330 as read): months given, units missing; the check crashed."""
    assert one(check_accumulated(BillFacts(accumulated=dict(months_covered=25, admitted=True)))).status == PROBLEM
    assert one(check_accumulated(BillFacts(accumulated=dict(months_covered=25)))).status == CBD


# Pro-rata present reading (CSM 6.1.1.1), as on IESCO bills: photo a day after the reading date, the
# recorded reading higher than the billed one by exactly the units carried forward.
PRO = dict(phase=1, snapshot_present=True, snapshot_stamp_present=True, reading_date="2026-04-24",
           snapshot_stamp_date="2026-04-25", present_reading={"total": 2917}, pro_rata_reading=True)


def test_pro_rata_snapshot_matches_carried_forward():
    assert one(check_snapshot(BillFacts(**PRO, snapshot={"total": 2920}, carried_forward_units=3))).status == OK


def test_pro_rata_snapshot_gap_not_explained():
    f = one(check_snapshot(BillFacts(**PRO, snapshot={"total": 2930}, carried_forward_units=3)))
    assert f.status == PROBLEM and f.numbers["excess_units"] == -13


def test_pro_rata_billed_above_snapshot_is_still_a_problem():
    assert one(check_snapshot(BillFacts(**PRO, snapshot={"total": 2910}, carried_forward_units=3))).status == PROBLEM


def test_pro_rata_carried_units_not_printed():
    assert one(check_snapshot(BillFacts(**PRO, snapshot={"total": 2920}))).status == CBD


def test_without_pro_rata_a_late_stamp_is_still_a_problem():
    kw = {**PRO, "pro_rata_reading": None}
    fs = check_snapshot(BillFacts(**kw, snapshot={"total": 2917}))
    assert any(f.status == PROBLEM and "reading date" in f.note for f in fs)


def test_pro_rata_stamp_before_reading_date_is_a_problem():
    kw = {**PRO, "snapshot_stamp_date": "2026-04-22"}
    fs = check_snapshot(BillFacts(**kw, snapshot={"total": 2917}))
    assert any(f.status == PROBLEM for f in fs)


# FPA note printed on the bill (month, units, rate), checked against the history and NEPRA's rate.
def _fpa(monkeypatch, **kw):
    from sahibill import tariff as T
    monkeypatch.setitem(T.FCA_BY_REFERENCE_MONTH, "2026-07", 2.0581)     # test value, not a verified rate
    base = dict(billing_month="2026-09", units=162, status_billed="protected", sanctioned_load_kw=2,
                history=[{"month": "2026-08", "units": 108, "mode": ""}, {"month": "2026-07", "units": 118, "mode": ""}])
    return {x.numbers["line"]: x for x in check_arithmetic(BillFacts(**{**base, **kw})) if "line" in x.numbers}


def test_fpa_note_matches(monkeypatch):
    got = _fpa(monkeypatch, fpa_ref_month="2026-07", fpa_ref_units=118, fpa_rate=2.0581)
    assert [got[k].status for k in ("fpa_month", "fpa_units", "fpa_rate")] == [OK, OK, OK]


def test_fpa_note_wrong_units_month_and_rate(monkeypatch):
    got = _fpa(monkeypatch, fpa_ref_month="2026-08", fpa_ref_units=128, fpa_rate=2.1)
    assert [got[k].status for k in ("fpa_month", "fpa_units", "fpa_rate")] == [PROBLEM, PROBLEM, PROBLEM]


def test_fpa_rate_unknown_is_not_judged():
    fs = check_arithmetic(BillFacts(billing_month="2026-03", units=63, status_billed="protected", fpa_rate=0.9))
    assert any(f.status == CBD and "FCA rate for 2026-01" in f.missing[0] for f in fs)


# Absences read from a photo are asked, not alleged, until the user confirms them.
def test_missing_snapshot_from_a_photo_is_a_question():
    from sahibill.complaint.requests import build_requests
    fs = check_snapshot(BillFacts(snapshot_present=False, absence_confirmed=False))
    assert one(fs).status == CBD
    assert build_requests(fs)["user"][0]["en"].startswith("We could not see a meter-reading photo")


def test_missing_snapshot_confirmed_is_a_problem():
    assert one(check_snapshot(BillFacts(snapshot_present=False, absence_confirmed=True))).status == PROBLEM


def test_missing_stamp_from_a_photo_is_a_question():
    fs = check_snapshot(BillFacts(snapshot_present=True, snapshot={"total": 10}, present_reading={"total": 10},
                                  snapshot_stamp_present=False, absence_confirmed=False))
    assert any(f.status == CBD and "time stamp" in f.missing[0] for f in fs)
    assert not any(f.status == PROBLEM for f in fs)
