

def test_stamp_dates_from_real_bills():
    from sahibill.readers.bill import stamp_date
    assert stamp_date("25-04-2026 16:55") == "2026-04-25"
    assert stamp_date("25.05.2026 16:55:26") == "2026-05-25"
    assert stamp_date("?? 07:45:30") is None          # stamp present, date not legible


def test_bill_calculation_gives_the_rate_when_no_category_is_printed():
    from sahibill.readers.bill import to_facts
    r = {"fields": {"units": {"value": 177}}, "bill_calculation": [{"rate": 13.01, "units": 77},
                                                                     {"rate": 10.54, "units": 100}, {"rate": 300, "units": 2}]}
    assert to_facts(r).rate_billed == 13.01


def test_urdu_month_names():
    from sahibill.readers.bill import month_key
    assert month_key("26-مئی") == "2026-05" and month_key("جولائی-26") == "2026-07"


def test_unread_stamp_is_not_evidence_of_no_stamp():
    from sahibill.readers.bill import to_facts
    r = {"fields": {"snapshot_state": {"value": "unreadable"}, "snapshot_stamp": {"value": None}}}
    assert to_facts(r).snapshot_stamp_present is None
