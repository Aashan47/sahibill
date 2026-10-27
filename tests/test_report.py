"""Reports and the household layer, with saved readings only (fixture mode): no model is ever called."""
import json

import pytest
from fastapi.testclient import TestClient

from sahibill import report

V = lambda v: {"value": v, "text": None if v is None else str(v)}  # noqa: E731


def reading(month, prev, pres, units, rd, issue, due, snapshot="readable", snap=None, **extra):
    f = dict(billing_month=month, reading_date=rd, issue_date=issue, due_date=due, tariff="A-1a(01)",
             sanctioned_load_kw=2, status="protected", prev_reading=prev, present_reading=pres, units=units,
             snapshot_state=snapshot, snapshot_reading=snap if snap is not None else (pres if snapshot == "readable" else None),
             snapshot_stamp=f"{rd[8:10]}-{rd[5:7]}-{rd[:4]} 09:00", **extra)
    return {"fields": {k: V(v) for k, v in f.items()},
            "history": [{"month": "2026-05", "units": 120, "mode": ""}, {"month": "2026-04", "units": 110, "mode": ""}],
            "supplementary": [], "_call": {"usd": 0.01, "cached": False}}


JUL = reading("2026-07", 3000, 3118, 118, "2026-07-24", "2026-07-26", "2026-08-06")
AUG = reading("2026-08", 3118, 3226, 108, "2026-08-24", "2026-08-26", "2026-09-07")
AUG_GAP = reading("2026-08", 3120, 3226, 106, "2026-08-24", "2026-08-26", "2026-09-07")
AUG_BLANK = reading("2026-08", 3118, 3226, 108, "2026-08-24", "2026-08-26", "2026-09-07", snapshot="blank")


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Fixture mode in a temporary directory: photo bytes -> saved reading."""
    fx = tmp_path / "fixtures"
    fx.mkdir()
    monkeypatch.setenv("SAHIBILL_FIXTURES", str(fx))
    monkeypatch.setenv("SAHIBILL_BUDGET_USD", "0")
    for name in ("REPORTS", "UPLOADS", "READINGS"):
        monkeypatch.setattr(report, name, tmp_path / name.lower())
    monkeypatch.setattr(report, "_reports", {})

    def photo(raw, tag):
        data = f"photo {tag}".encode()
        (fx / f"{report.photo_sha(data)[:24]}.json").write_text(json.dumps(raw))
        return (f"{tag}.jpg", data)
    return photo


def make(store, *pairs):
    return report.view(report.create([store(raw, tag) for raw, tag in pairs], background=False))


def test_bills_are_ordered_and_the_previous_date_is_filled(store):
    v = make(store, (AUG, "aug"), (JUL, "jul"))
    assert [b["billing_month"] for b in v["bills"]] == ["2026-07", "2026-08"]
    aug = v["bills"][1]
    prev = next(r for r in aug["reading"] if r["key"] == "prev_reading_date")
    assert prev["value"] == "2026-07-24" and prev["from_previous_bill"]
    period = next(c for c in aug["cards"] if c["check"] == "1")
    assert period["status"] == "looks_right" and "31 days" in period["lines"][0]
    assert v["household"]["chain"] == [{"from": "2026-07", "to": "2026-08", "ok": True, "note": v["household"]["chain"][0]["note"],
                                        "note_ur": v["household"]["chain"][0]["note_ur"]}]
    assert [m["units"] for m in v["household"]["months"]] == [118, 108]


def test_chain_note_when_readings_do_not_continue(store):
    v = make(store, (JUL, "jul"), (AUG_GAP, "aug"))
    link = v["household"]["chain"][0]
    assert link["ok"] is False and "3118" in link["note"] and "3120" in link["note"]


def test_two_photos_of_one_month_are_merged(store):
    v = make(store, (JUL, "jul-close"), (AUG, "aug-close"), (AUG_BLANK, "aug-casual"))
    assert len([b for b in v["bills"] if b["status"] == "done"]) == 2
    aug = v["bills"][1]
    assert aug["photos"] == ["aug-close.jpg", "aug-casual.jpg"]
    assert "snapshot_state" in aug["photo_agreement"]["disagreements"]
    state = next(r for r in aug["reading"] if r["key"] == "snapshot_state")
    assert state["value"] is None and state["held"]
    assert next(r for r in aug["reading"] if r["key"] == "units")["value"] == 108


def test_headline_stamps(store):
    assert make(store, (JUL, "a"))["headline"]["stamp"] in ("looks_right", "cannot_be_determined")
    asked = make(store, (AUG_BLANK, "b"))
    assert asked["headline"]["stamp"] == "cannot_be_determined" and "question" in asked["headline"]["en"]
    wrong = reading("2026-07", 3000, 3118, 118, "2026-07-24", "2026-07-26", "2026-08-06", snap=3130)
    assert make(store, (wrong, "c"))["headline"]["stamp"] == "problem_found"


def test_answer_flow_question_then_confirmed_absent_is_a_problem(store):
    v = make(store, (AUG_BLANK, "aug"))
    bill = v["bills"][0]
    assert [q["id"] for q in bill["questions"]] == ["snapshot"] and bill["stamp"] == "cannot_be_determined"
    v = report.answer(v["id"], bill["id"], "snapshot", True)
    bill = v["bills"][0]
    assert bill["questions"] == [] and bill["stamp"] == "problem_found"
    assert any(c["check"] == "2" and c["status"] == "problem_found" for c in bill["cards"])


def test_answer_flow_photo_is_there_is_no_problem(store):
    v = make(store, (AUG_BLANK, "aug"))
    v = report.answer(v["id"], v["bills"][0]["id"], "snapshot", False)
    bill = v["bills"][0]
    assert bill["questions"] == [] and bill["stamp"] != "problem_found"


def test_correction_reruns_the_checks(store):
    wrong = reading("2026-07", 3000, 3118, 118, "2026-07-24", "2026-07-26", "2026-08-06", snap=3130)
    v = make(store, (wrong, "jul"))
    assert v["bills"][0]["stamp"] == "problem_found"
    v = report.correct(v["id"], v["bills"][0]["id"], "snapshot_reading", "3118")
    bill = v["bills"][0]
    field = next(r for r in bill["reading"] if r["key"] == "snapshot_reading")
    assert field["value"] == 3118 and field["corrected"] and bill["stamp"] != "problem_found"
    with pytest.raises(ValueError):
        report.correct(v["id"], bill["id"], "units", "many")
    with pytest.raises(ValueError):
        report.correct(v["id"], bill["id"], "consumer_name", "x")


def test_photo_without_a_saved_reading_fails_in_fixture_mode(store):
    rid = report.create([("new.jpg", b"never seen")], background=False)
    v = report.view(rid)
    assert v["status"] == "partial" and v["bills"][0]["status"] == "failed" and v["bills"][0]["error"]


def test_api_routes(store):
    from web.app import app
    c = TestClient(app)
    assert c.get("/api/health").json() == {"ok": True}
    files = [("photos", store(JUL, "jul")), ("photos", store(AUG_BLANK, "aug"))]
    rid = c.post("/api/reports", files=[(k, (n, d, "image/jpeg")) for k, (n, d) in files]).json()["id"]
    v = c.get(f"/api/reports/{rid}").json()
    assert v["status"] in ("reading", "done")
    report._pool.shutdown(wait=True)
    report._pool = report.ThreadPoolExecutor(max_workers=3)
    v = c.get(f"/api/reports/{rid}").json()
    assert v["status"] == "done" and len(v["bills"]) == 2
    aug = v["bills"][1]
    r = c.post(f"/api/reports/{rid}/bills/{aug['id']}/answer", json={"question": "snapshot", "absent": True})
    assert r.status_code == 200 and r.json()["headline"]["stamp"] == "problem_found"
    r = c.post(f"/api/reports/{rid}/bills/{aug['id']}/correct", json={"field": "units", "value": "108"})
    assert r.status_code == 200
    assert c.post(f"/api/reports/{rid}/bills/{aug['id']}/correct", json={"field": "nope", "value": 1}).status_code == 400
    assert c.post(f"/api/reports/{rid}/bills/{aug['id']}/answer", json={"question": "x", "absent": True}).status_code == 400
    assert c.get(f"/api/reports/{rid}/photos/{aug['id']}").status_code == 200
    assert c.get("/api/reports/nope").status_code == 404
    assert c.get("/api/nothing").status_code == 404
    assert c.post("/api/reports", files=[("photos", (f"{i}.jpg", b"x", "image/jpeg")) for i in range(13)]).status_code == 400


def test_sample_report_reads_the_committed_sample_readings(store):
    v = report.view(report.create_sample(background=False))
    assert v["status"] == "done" and len(v["bills"]) == 4 and not v["household_mode"]
    assert all(b["status"] == "done" for b in v["bills"])


def test_delivery_date_from_the_household_runs_the_time_to_pay_check():
    from sahibill.pipeline import analyze_reading
    raw = {"fields": {"billing_month": {"value": "2026-09"}, "issue_date": {"value": "2026-09-26"},
                      "due_date": {"value": "2026-10-08"}}}
    before = [c for c in analyze_reading(raw)["verdict"]["cards"] if c["check"] == "10B"]
    after = [c for c in analyze_reading(raw, overrides={"delivery_date": "2026-09-28"})["verdict"]["cards"] if c["check"] == "10B"]
    assert before[0]["status"] == "cannot_be_determined" and after[0]["status"] == "looks_right"


def test_voice_hear_and_ask_without_any_model(monkeypatch, tmp_path):
    """Hearing uses the fake transcriber; answering falls back to the findings when no model may be called."""
    import json
    from fastapi.testclient import TestClient
    from web.app import app
    from sahibill import report
    monkeypatch.setenv("SAHIBILL_BUDGET_USD", "0")
    rid = report.create_sample()
    c = TestClient(app)
    bill = c.get(f"/api/reports/{rid}").json()["bills"][0]
    monkeypatch.setenv("SAHIBILL_ASR_FAKE", json.dumps({"a": "کیا میرا بل ٹھیک ہے", "b": "کیا میرا بل ٹھیک ہے"}))
    h = c.post(f"/api/reports/{rid}/bills/{bill['id']}/hear", files={"audio": ("q.webm", b"x" * 10)},
               data={"language": "urdu"}).json()
    assert h["sure"] is True and h["disagreement"] == 0
    monkeypatch.setenv("SAHIBILL_ASR_FAKE", json.dumps({"a": "abc", "b": "xyz"}))
    h2 = c.post(f"/api/reports/{rid}/bills/{bill['id']}/hear", files={"audio": ("q.webm", b"x" * 10)},
                data={"language": "saraiki"}).json()
    assert h2["sure"] is False                      # Saraiki has no threshold: always confirm
    a = c.post(f"/api/reports/{rid}/bills/{bill['id']}/ask", json={"question": h["text"], "language": "urdu"}).json()
    assert a["source"] == "findings" and a["text"]


def test_a_written_answer_with_a_new_number_is_refused(monkeypatch):
    from sahibill import voice
    bill = {"billing_month": "2026-09", "headline": {"en": "1 problem found on this bill.", "ur": "اس بل میں 1 مسئلہ ملا۔"},
            "cards": [{"title": "Detection bill units", "title_ur": "ڈیٹیکشن", "status": "problem_found",
                       "lines": ["The limit is 1,642.5 units; the bill charges 2,414."], "lines_ur": ["حد 1,642.5"], "clauses": []}]}
    monkeypatch.setattr(voice, "chat", lambda *a, **k: {"content": "You were overcharged by Rs 9,999.", "usd": 0.001})
    a = voice.answer(bill, "Was I overcharged?", "english")
    assert a["source"] == "findings" and "9,999" not in a["text"]
    monkeypatch.setattr(voice, "chat", lambda *a, **k: {"content": "Yes: the limit is 1,642.5 units and the bill charges 2,414.", "usd": 0.001})
    assert voice.answer(bill, "Was I overcharged?", "english")["source"] == "muse-spark-open"


def test_an_urdu_answer_that_mixes_in_devanagari_is_refused(monkeypatch):
    from sahibill import voice
    bill = {"headline": {"en": "No problem found.", "ur": "کوئی مسئلہ نہیں ملا۔"}, "cards": []}
    monkeypatch.setattr(voice, "chat", lambda *a, **k: {"content": "کुछ چیزیں درست ہیں", "usd": 0.001})
    assert voice.answer(bill, "کیا میرا بل ٹھیک ہے", "urdu")["source"] == "findings"


def test_meter_crop_and_the_persons_reading(monkeypatch, tmp_path):
    """The meter photo is cut out from a fixture box; a typed reading makes the snapshot readable for the rules."""
    import hashlib, json
    from pathlib import Path
    from fastapi.testclient import TestClient
    from web.app import app
    from sahibill import report
    from sahibill.vision import meter as m
    monkeypatch.setenv("SAHIBILL_BUDGET_USD", "0")
    monkeypatch.setattr(m, "STORE", tmp_path / "meter")
    rid = report.create_sample()
    c = TestClient(app)
    bill = c.get(f"/api/reports/{rid}").json()["bills"][0]
    p = report.photo_file(rid, bill["photo_urls"][0].rsplit("/", 1)[-1])
    fx = tmp_path / "fx.json"
    fx.write_text(json.dumps({hashlib.sha256(Path(p).read_bytes()).hexdigest(): [10, 10, 110, 60]}))
    monkeypatch.setenv("SAHIBILL_SAM_FIXTURES", str(fx))
    r = c.get(f"/api/reports/{rid}/bills/{bill['id']}/meter")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    v = c.post(f"/api/reports/{rid}/bills/{bill['id']}/correct", json={"field": "snapshot_reading", "value": "12345"}).json()
    b = next(x for x in v["bills"] if x["id"] == bill["id"])
    got = {f["key"]: f["value"] for f in b["reading"]}
    assert got["snapshot_reading"] == 12345 and got["snapshot_state"] == "readable"
