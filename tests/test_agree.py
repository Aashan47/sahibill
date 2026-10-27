from sahibill.readers.agree import combine


def R(**fields):
    return {"fields": {k: {"value": v, "text": str(v)} for k, v in fields.items()},
            "history": [{"month": "Sep-26", "units": 120}, {"month": "Aug-26", "units": 130}]}


def test_agreement_accepts_same_values_in_different_formats():
    m = combine(R(units="239", variable="13,927.72", billing_month="2026-10"),
                R(units=239, variable=13927.72, billing_month="Oct-26"))
    assert m["fields"]["units"]["value"] == "239"
    assert m["fields"]["billing_month"]["value"] == "2026-10"
    assert not m["agreement"]["disagreements"]


def test_disagreement_is_held_and_recorded():
    m = combine(R(units=196), R(units=198))
    assert m["fields"]["units"]["value"] is None
    assert m["agreement"]["disagreements"]["units"] == {"spark": 196, "glimmer": 198}


def test_history_keeps_only_agreed_months():
    a = R(units=1); b = R(units=1)
    b["history"][1]["units"] = 131
    assert [h["month"] for h in combine(a, b)["history"]] == ["2026-09"]


def test_off_schema_entry_is_unread():
    b = R(units=239)
    b["fields"]["snapshot_state"] = "readable"          # a bare value with no {"value", "text"} wrapper
    m = combine(R(units=239, snapshot_state="readable"), b)
    assert m["fields"]["units"]["value"] == 239
    assert m["fields"]["snapshot_state"]["value"] is None
