"""The case agent, with a scripted stand-in for Muse Spark Open (no model call)."""
import json

import pytest
from fastapi.testclient import TestClient

from sahibill import agent, report
from sahibill.readers.llm import BudgetExceeded


def call(name, **args):
    return {"content": "", "usd": 0.001, "cached": False,
            "tool_calls": [{"id": f"c{abs(hash((name, json.dumps(args)))) % 10**6}", "name": name, "arguments": json.dumps(args)}]}


@pytest.fixture
def rid(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "REPORTS", tmp_path / "reports")
    report._reports.clear()
    return report.create_sample(background=False)


def script(monkeypatch, steps):
    seen = []

    def fake(messages, **kw):
        seen.append(messages)
        step = steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step(messages) if callable(step) else step
    monkeypatch.setattr(agent, "chat", fake)
    return seen


def test_case_runs_to_a_question_then_to_the_complaint(rid, monkeypatch):
    script(monkeypatch, [
        call("list_open_items"),
        call("ask_household", item_id="b2:date:delivery_date", reason="It decides whether you had enough time to pay."),
        call("recheck", bill_id="b2"),
        call("prepare_complaint", bill_id="b2"),
        lambda m: call("finish", summary="Your complaint is ready. The utility must settle it by "
                       + json.loads(m[-1]["content"])["settle_by"] + "."),
    ])
    st = agent.start(rid, "en", background=False)
    assert st["status"] == "waiting" and st["ask"]["kind"] == "date"
    assert [s["kind"] for s in st["trace"] if s["kind"] != "think"] == ["look", "ask"]
    st = agent.reply(rid, "2026-10-20", background=False)
    assert st["status"] == "done"
    assert [s["kind"] for s in st["trace"] if s["kind"] != "think"] == ["look", "ask", "answer", "check", "check", "letter"]
    assert st["grounding"]["ok"] and st["stats"]["calls"] == 5
    assert st["summary"]["source"] == "muse-spark-open" and "settle it by" in st["summary"]["text"]
    bill = next(b for b in report.view(rid)["bills"] if b["id"] == "b2")
    assert any(r["key"] == "delivery_date" and r["value"] == "2026-10-20" for r in bill["reading"]) or \
        report._state(rid)["overrides"]["b2"]["delivery_date"] == "2026-10-20"


def test_a_number_no_tool_returned_is_never_shown(rid, monkeypatch):
    script(monkeypatch, [call("list_open_items"), call("finish", summary="You were overcharged Rs 999.")])
    st = agent.start(rid, "en", background=False)
    assert st["status"] == "done" and st["summary"]["source"] == "code" and "999" not in json.dumps(st)


def test_the_household_is_asked_only_open_items(rid, monkeypatch):
    script(monkeypatch, [call("ask_household", item_id="b2:confirm:snapshot", reason="x"),
                                call("finish", summary="Done.")])
    st = agent.start(rid, "en", background=False)
    assert st["status"] == "done" and st["ask"] is None
    tool_results = [m["content"] for m in agent._get(rid)["messages"] if m["role"] == "tool"]
    assert "not an open household item" in tool_results[0]


def test_questions_are_capped(rid, monkeypatch):
    steps = []
    for b in ("b1", "b2", "b3", "b4"):
        steps.append(call("ask_household", item_id=f"{b}:date:delivery_date", reason="It decides the time to pay."))
    steps.append(call("finish", summary="Done."))
    script(monkeypatch, steps)
    st = agent.start(rid, "en", background=False)
    for _ in range(3):
        st = agent.reply(rid, "2026-10-20", background=False)
    assert sum(s["kind"] == "ask" for s in st["trace"]) == 3 and st["status"] == "done"


def test_spent_budget_pauses_the_case(rid, monkeypatch):
    script(monkeypatch, [BudgetExceeded("spent")])
    st = agent.start(rid, "ur", background=False)
    assert st["status"] == "paused" and st["trace"][-1]["ur"] == report.PAUSED["ur"]


def test_reply_needs_a_waiting_question(rid):
    with pytest.raises(ValueError):
        agent.reply(rid, "present", background=False)


def test_api_routes(rid, monkeypatch):
    from web import app as webapp
    monkeypatch.setenv("SAHIBILL_NO_LIMITS", "1")
    script(monkeypatch, [call("list_open_items"), call("finish", summary="Done.")])
    monkeypatch.setattr(agent, "_go", lambda r, background: (agent._run(r), agent.public(agent._get(r)))[1])
    c = TestClient(webapp.app)
    assert c.get(f"/api/reports/{rid}/agent").json()["status"] == "idle"
    assert c.post(f"/api/reports/{rid}/agent", json={"language": "en"}).json()["status"] == "done"
    assert c.post(f"/api/reports/{rid}/agent/reply", json={"value": "x"}).status_code == 400
    assert "messages" not in c.get(f"/api/reports/{rid}/agent").json()


def test_house_style_and_scripts_are_enforced(rid, monkeypatch):
    script(monkeypatch, [call("list_open_items"), call("finish", summary="**Done** — all checked (b6).\n* meter photo 清晰")])
    st = agent.start(rid, "en", background=False)
    assert st["summary"]["source"] == "code"          # a foreign script rejects the model's words outright
    agent_state = agent._get(rid)
    assert agent._tidy("**Done** — all checked (b6).\n* one") == "Done, all checked.\n• one"
    assert agent_state["status"] == "done"


def test_plan_is_the_models_and_numbers_are_kept_out_of_it(rid, monkeypatch):
    script(monkeypatch, [call("make_plan", steps=[{"kind": "look", "text": "Look at your bills"},
                                                  {"kind": "ask", "text": "Ask you 3 things"},
                                                  {"kind": "finish", "text": "Sum up"}]),
                         call("finish", summary="Done.")])
    st = agent.start(rid, "en", background=False)
    assert [p["kind"] for p in st["plan"]] == ["look", "finish"]        # the step with a number was dropped
    assert st["trace"][0]["kind"] == "think" and "reasoning_tokens" in st["trace"][0]


def test_meter_question_needs_sam3_to_find_the_photo(rid, monkeypatch):
    item = {"item_id": "b2:meter:snapshot_reading", "who": "household", "kind": "meter", "text": "x", "text_ur": "x"}
    monkeypatch.setattr(agent, "_items", lambda b: [item] if b["id"] == "b2" else [])
    monkeypatch.setattr(agent, "meter_found", lambda r, b: False)
    script(monkeypatch, [call("ask_household", item_id="b2:meter:snapshot_reading", reason="It checks the reading."),
                         call("finish", summary="Done.")])
    st = agent.start(rid, "en", background=False)
    assert st["status"] == "done" and st["ask"] is None
    assert any(s.get("tool") == "sam3_find_meter" for s in st["trace"])


def test_unsure_leaves_the_item_open_and_it_is_not_asked_again(rid, monkeypatch):
    script(monkeypatch, [call("ask_household", item_id="b2:date:delivery_date", reason="It decides the time to pay."),
                         call("ask_household", item_id="b2:date:delivery_date", reason="Again."),
                         call("finish", summary="Done.")])
    agent.start(rid, "en", background=False)
    st = agent.reply(rid, "unsure", background=False)
    assert st["status"] == "done" and "delivery_date" not in report._state(rid)["overrides"].get("b2", {})
    assert sum(s["kind"] == "ask" for s in st["trace"]) == 1


def test_a_summary_written_without_finish_is_grounded_too(rid, monkeypatch):
    script(monkeypatch, [call("list_open_items"), {"content": "All checked.", "usd": 0, "cached": False, "tool_calls": []}])
    st = agent.start(rid, "en", background=False)
    assert st["status"] == "done" and st["grounding"] == {"numbers": [], "ok": True, "refused": 0}
