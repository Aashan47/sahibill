"""Two false alarms found by the fresh E3 run of 29 October 2026 (results/E3.md), as regression tests."""
from sahibill.complaint.requests import build_requests
from sahibill.rules import run_all
from sahibill.rules.consumption import check_period, rate_for
from sahibill.rules.core import CBD, OK, PROBLEM, BillFacts
from sahibill.rules.meter import ASK_STAMP_DATE, check_snapshot

HIST = [{"month": f"2026-{m:02d}", "units": 150, "mode": ""} for m in range(9, 0, -1)]


def long_period(**kw):
    base = dict(billing_month="2026-10", reading_date="2026-10-12", prev_reading_date="2026-09-04",  # 38 days
                units=114, status_billed="protected", rate_billed=13.01, history=HIST, phase=1, sanctioned_load_kw=3.0)
    return BillFacts(**{**base, **kw})


def test_bill_that_already_prorated_is_not_prorated_again():
    # syn0029: 140 units recorded over 38 days, 114 billed (140 x 31 / 38), 26 carried forward.
    [f] = check_period(long_period(units_carried_forward=26))
    assert f.status == OK and f.numbers["prorated_units"] == 114


def test_pro_rata_present_reading_with_outstanding_units_is_not_prorated_again():
    # The IESCO way of printing the same thing: a pro-rata present reading and outstanding units.
    [f] = check_period(long_period(pro_rata_reading=True, carried_forward_units=26))
    assert f.status == OK


def test_long_period_billed_in_full_is_still_a_problem():
    # 210 units over 38 days billed in full at the unprotected rate; prorated, 171 units stay protected.
    [f] = check_period(long_period(units=210, rate_billed=rate_for("unprotected", 210), status_billed="unprotected"))
    assert f.status == PROBLEM and f.violation == "slab_not_prorated_long_period"


def snap(stamp, snapshot=56411):
    return BillFacts(billing_month="2026-10", reading_date="2026-10-14", prev_reading_date="2026-09-15", phase=1,
                     snapshot_present=True, snapshot={"total": snapshot}, present_reading={"total": 56411},
                     snapshot_stamp_present=True, snapshot_stamp_date=stamp)


def test_stamp_read_before_the_period_on_this_periods_photo_is_asked_not_alleged():
    # syn0030: the stamp 2026-10-14 was read as 2025-10-14, and the photo shows the billed reading.
    out = check_snapshot(snap("2025-10-14"))
    assert not [f for f in out if f.status == PROBLEM]
    assert any(f.status == CBD and ASK_STAMP_DATE in f.missing for f in out)
    assert build_requests(out)          # routed to the household, never left without a next step


def test_old_photo_with_an_old_reading_is_still_a_problem():
    out = check_snapshot(snap("2025-10-14", snapshot=55000))
    assert any(f.status == PROBLEM for f in out)


def test_stamp_a_few_days_off_inside_the_period_is_still_a_problem():
    # spec SN-07: the digits match, but the photo was not taken on the reading date.
    out = check_snapshot(snap("2026-10-11"))
    assert any(f.status == PROBLEM and f.numbers.get("stamp_date") == "2026-10-11" for f in out)


def test_clean_bill_of_e3_fresh_raises_nothing_through_all_rules():
    assert not [f for f in run_all(long_period(units_carried_forward=26)) if f.violation == "slab_not_prorated_long_period"]


# Second fresh set (seed 20261031): two clean bills were accused on one misread digit each.
from sahibill.rules.consumption import ASK_MISREAD, check_arithmetic, expected_variable  # noqa: E402


def arith(**kw):
    base = dict(billing_month="2026-10", units=150, status_billed="unprotected", sanctioned_load_kw=2.0, phase=1,
                history=HIST)
    f = BillFacts(**{**base, **kw})
    return f


def line(out, name):
    return [x for x in out if x.numbers.get("line") == name]


def test_load_misread_by_one_digit_is_asked_not_alleged():
    # syn0000: load 2.0 kW read as 2.6; the bill's fixed charge is right for 2.0 kW.
    right = check_arithmetic(arith(fixed_billed=0.0))
    fixed = line(right, "fixed")[0].numbers["expected"]
    out = check_arithmetic(arith(sanctioned_load_kw=2.6, fixed_billed=fixed))
    [f] = line(out, "fixed")
    assert f.status == CBD and ASK_MISREAD in f.missing and f.numbers["adds_up_if"] == 2.0
    assert build_requests(out)


def test_history_units_misread_by_one_digit_is_asked_not_alleged():
    # syn0030: August's 528 units read as 526; the fuel adjustment on the bill is right for 528.
    from sahibill import tariff as T
    rate = T.FCA_BY_REFERENCE_MONTH["2026-08"]
    hist = [{"month": "2026-08", "units": 526, "mode": ""}] + HIST
    out = check_arithmetic(arith(history=hist, fpa_billed=round(528 * rate, 2)))
    [f] = line(out, "fpa")
    assert f.status == CBD and f.numbers["adds_up_if"] == 528


def test_overcharge_no_single_digit_explains_is_still_alleged():
    # The generator's seeded error: the energy charge inflated by 12%.
    out = check_arithmetic(arith(variable_billed=round(expected_variable("unprotected", 150) * 1.12, 2)))
    [f] = line(out, "variable")
    assert f.status == PROBLEM and f.violation == "tariff_arithmetic_error"


def test_retrieval_change_date_is_taken_from_the_printed_words():
    # E3 third set, syn0031: the reader put the retrieval date in event_date; the line itself states both.
    from sahibill.readers.bill import to_facts
    read = {"fields": {"billing_month": {"value": "2026-10"}}, "supplementary": [{
        "kind": "retrieval", "event_date": "2026-07-26",
        "text": "RETRIEVAL | 631 units | meter changed 2026-03-14 | display wash meter replaced; data retrieved in-house on 2026-07-26"}]}
    f = to_facts(read)
    assert f.retrieval["replaced"] == "2026-03-14" and f.retrieval["retrieved"] == "2026-07-26"
