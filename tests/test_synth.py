import json

from sahibill import tariff as T
from sahibill.synth.generate import family, plan
from sahibill.synth.model import DEFECTS, energy_charge, make_bill


def test_unprotected_whole_units_at_slab_rate():
    var, rate, fixed, _ = energy_charge("unprotected", 382, 2)
    assert rate == 36.46 and var == round(382 * 36.46, 2) and fixed == 800


def test_protected_one_previous_slab():
    var, rate, fixed, _ = energy_charge("protected", 150, 1)
    assert var == round(100 * 10.54 + 50 * 13.01, 2) and fixed == 300


def test_lifeline_no_slab_benefit_no_fixed():
    var, rate, fixed, _ = energy_charge("lifeline", 80, 1)
    assert var == round(80 * 7.74, 2) and fixed == 0


def test_clean_bill_is_self_consistent():
    for seed in range(40):
        b, t = make_bill(seed, f"t{seed}", [])
        assert t["defects"] == []
        assert b.present_reading - b.prev_reading == t["measured_units"]
        assert b.snapshot_reading == b.present_reading
        assert b.units + b.carried_forward == t["measured_units"]
        if t["reading_days"] > t["days_in_month"]:
            assert b.carried_forward > 0


def test_every_defect_is_recorded_with_its_violation():
    for i, d in enumerate(DEFECTS):
        b, t = make_bill(1000 + i, f"d{i}", [d])
        assert [x["defect"] for x in t["defects"]] == [d]
        assert t["defects"][0]["violation"] == DEFECTS[d]


def test_detection_formula_defect_exceeds_cap():
    b, t = make_bill(5, "x", ["detection_formula_exceeded"])
    s = b.supplementary[0]
    cap = s["load_kw"] * T.LOAD_FACTOR[b.phase] * T.HOURS_PER_MONTH * s["months"]
    assert s["units"] > cap


def test_plan_never_pairs_a_family():
    for ds in plan(300, 3):
        assert len({family(d) for d in ds}) == len(ds)


def test_no_identifying_strings():
    b, _ = make_bill(9, "y", [])
    assert b.consumer.startswith("SAMPLE CONSUMER") and b.reference_no.startswith("SYN ")
