"""The generator's answer key must agree with the rules on a perfect reading of every bill."""
import pytest

from sahibill.readers import consistency
from sahibill.readers.bill import to_facts
from sahibill.rules import run_all, violations
from sahibill.synth.generate import plan
from sahibill.synth.model import make_bill
from sahibill.synth.oracle import oracle_read


@pytest.mark.parametrize("seed", [20261026, 7, 99])
def test_answer_key_matches_rules_on_perfect_reading(seed):
    problems = []
    for i, ds in enumerate(plan(60, seed)):
        _, t = make_bill(seed * 1000 + i, f"o{i}", ds)
        read = consistency.apply(oracle_read(t))
        held = read["consistency"]["held"]
        raised = violations(run_all(to_facts(read, confirmed_absent=True)))   # the answer key is ground truth
        expected = {d["violation"] for d in t["defects"] if d["determinable_from_bill"]}
        if held or raised != expected:
            problems.append((i, ds, t.get("dropped"), sorted(expected), sorted(raised), held))
    assert not problems, problems[:5]


def test_clean_bills_in_both_halves():
    clean = [i for i, ds in enumerate(plan(50, 20261026)) if not ds]
    assert any(i % 2 == 0 for i in clean) and any(i % 2 == 1 for i in clean)
