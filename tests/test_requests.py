import re
from pathlib import Path

import pytest

from sahibill.complaint.requests import build_requests, route
from sahibill.rules import BillFacts, run_all

ENGINE = Path(__file__).resolve().parents[1] / "sahibill" / "rules"


def engine_missing_messages():
    msgs = set()
    for p in ENGINE.glob("*.py"):
        src = p.read_text()
        for block in re.findall(r"missing=\[([^\]]*)\]|missing\.append\(([^)]*)\)|\[\"([^\"]+)\"\]", src):
            for part in block:
                msgs.update(re.findall(r'f?"([^"]+)"', part) if part.startswith(("\"", "f\"")) else [part] if part else [])
    return {m for m in msgs if " " in m or m in ("units", "load", "snapshot")}


@pytest.mark.parametrize("msg", sorted(engine_missing_messages()))
def test_every_engine_message_has_a_route(msg):
    route(msg.replace("{f.billing_month}", "2026-10").replace("{reg}", "total"))


def test_requests_grouped_by_audience_and_deduplicated():
    f = BillFacts(detection=dict(months=5, reasons="tampering"),
                  retrieval=dict(defect="display_wash", replaced="2026-03", debit="2026-10"))
    req = build_requests(run_all(f))
    utility = [r["en"] for r in req.get("utility", [])]
    assert any("CEO or committee approval" in t for t in utility)
    assert any("retrieval report" in t for t in utility)
    assert len(utility) == len(set(utility))
    assert all("ur" in r and r["ur"] for rs in req.values() for r in rs)


def test_limits_never_reach_the_utility():
    f = BillFacts(billing_month="2026-01", units=250, status_billed="unprotected")
    req = build_requests(run_all(f))
    assert all("SahiBill" not in r["en"] for r in req.get("utility", []))
