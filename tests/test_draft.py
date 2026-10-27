from sahibill.complaint.draft import accept_polished, numbers_in, template
from sahibill.complaint.requests import build_requests
from sahibill.rules import BillFacts, run_all
from sahibill.verdict import verdict


def _case():
    f = BillFacts(phase=1, sanctioned_load_kw=1, detection=dict(units=600, months=3, reasons="tampering"))
    fs = run_all(f)
    return verdict(fs), build_requests(fs)


def test_template_lists_each_problem_with_its_numbers():
    v, ns = _case()
    t = template(v, ns, "2026-10")
    assert "Detection bill units" in t["en"] and "438" in t["en"] and "600" in t["en"]
    assert t["problem_count"] == sum(c["status"] == "problem_found" for c in v["cards"])
    assert "[your reference number]" in t["en"]          # personal details stay placeholders
    assert "CSM 10.3.1(g)" in t["en"]


def test_polished_letter_rejected_if_it_adds_a_number():
    v, ns = _case()
    t = template(v, ns, "2026-10")["en"]
    assert accept_polished(t, "Dear Sir, the detection bill of 600 units exceeds 438 units.")
    assert not accept_polished(t, "Dear Sir, the detection bill of 650 units exceeds 438 units.")


def test_numbers_in_normalises_separators():
    assert numbers_in("Rs 13,927.70 and 438") == {"13927.7", "438"}
