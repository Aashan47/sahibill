"""Per-visitor and site-wide limits on the public routes, and the retention sweep. No model is called."""
import json
import os
import time

from fastapi.testclient import TestClient

from sahibill import report
from web import limits
from tests.test_report import JUL, store  # noqa: F401  (pytest fixture)


def _client():
    from web.app import app
    limits.reset()
    return TestClient(app)


def test_sample_route_is_limited_per_visitor(store, monkeypatch):  # noqa: F811
    monkeypatch.setitem(limits.PER_VISITOR, "sample", (2, 3600))
    c = _client()
    assert c.post("/api/reports/sample").status_code == 200
    assert c.post("/api/reports/sample").status_code == 200
    r = c.post("/api/reports/sample")
    assert r.status_code == 429 and "wait" in r.json()["detail"]


def test_visitor_is_the_cloudflare_header_only_behind_the_tunnel():
    class Req:
        def __init__(self, peer, cf):
            self.client = type("C", (), {"host": peer})()
            self.headers = {"cf-connecting-ip": cf} if cf else {}
    assert limits.visitor(Req("127.0.0.1", "203.0.113.7")) == "203.0.113.7"
    assert limits.visitor(Req("198.51.100.2", "203.0.113.7")) == "198.51.100.2"   # header from outside: ignored
    assert limits.visitor(Req("127.0.0.1", None)) == "127.0.0.1"


def test_a_forged_header_does_not_buy_more_requests(store, monkeypatch):  # noqa: F811
    monkeypatch.setitem(limits.PER_VISITOR, "sample", (1, 3600))
    c = _client()
    # TestClient's peer is not this machine, so the header is ignored and both count as one visitor
    assert c.post("/api/reports/sample", headers={"cf-connecting-ip": "203.0.113.1"}).status_code == 200
    assert c.post("/api/reports/sample", headers={"cf-connecting-ip": "203.0.113.2"}).status_code == 429


def test_site_ceiling_stops_new_photos_for_everyone(store, monkeypatch):  # noqa: F811
    monkeypatch.setitem(limits.PER_SITE, "photos", (1, 86400))
    c = _client()
    ok = c.post("/api/reports", files=[("photos", ("a.jpg", b"new photo a", "image/jpeg"))])
    assert ok.status_code == 200
    r = c.post("/api/reports", files=[("photos", ("b.jpg", b"new photo b", "image/jpeg"))])
    assert r.status_code == 429 and "today" in r.json()["detail"]


def test_saved_readings_do_not_count_as_new_photos(store, monkeypatch):  # noqa: F811
    monkeypatch.setitem(limits.PER_SITE, "photos", (0, 86400))
    c = _client()
    name, data = store(JUL, "jul")
    assert c.post("/api/reports", files=[("photos", (name, data, "image/jpeg"))]).status_code == 200


def test_unsupported_language_is_refused_before_any_speech_call(store):  # noqa: F811
    c = _client()
    rid = report.create([store(JUL, "jul")], background=False)
    bid = report.view(rid)["bills"][0]["id"]
    r = c.post(f"/api/reports/{rid}/bills/{bid}/hear", files={"audio": ("q.webm", b"x", "audio/webm")},
               data={"language": "klingon"})
    assert r.status_code == 400


def test_sweep_deletes_old_reports_and_unreferenced_photos_only(store, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(report, "LLM_CACHE", tmp_path / "llm")
    old = report.create([store(JUL, "old")], background=False)
    kept = report.create([("k.jpg", b"kept photo")], background=False)
    stale = time.time() - 40 * 86400
    os.utime(report._path(old), (stale, stale))
    for f in report.UPLOADS.iterdir():        # every photo is old on disk; the kept report still points at its own
        os.utime(f, (stale, stale))
    (tmp_path / "llm").mkdir()
    (tmp_path / "llm" / "x.json").write_text("{}")
    os.utime(tmp_path / "llm" / "x.json", (stale, stale))
    n = report.sweep(30)
    assert n == 3                               # the old report, its photo, the old cached answer
    assert report.view(old) is None and report.view(kept) is not None
    kept_file = json.loads(report._path(kept).read_text())["photos"][0]["file"]
    assert [f.name for f in report.UPLOADS.iterdir()] == [kept_file]


def test_security_headers_and_no_api_docs(store):  # noqa: F811
    c = _client()
    r = c.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "swagger" not in c.get("/docs").text.lower()
    assert '"openapi"' not in c.get("/openapi.json").text


def test_a_spent_budget_says_paused_and_does_not_ask_for_a_retake(tmp_path, monkeypatch):
    monkeypatch.delenv("SAHIBILL_FIXTURES", raising=False)
    monkeypatch.setenv("SAHIBILL_BUDGET_USD", "0")
    for name in ("REPORTS", "UPLOADS", "READINGS"):
        monkeypatch.setattr(report, name, tmp_path / name.lower())
    monkeypatch.setattr(report, "_reports", {})
    monkeypatch.setattr("sahibill.readers.llm.CACHE", tmp_path)
    v = report.view(report.create([("n.jpg", b"never read before")], background=False))
    assert v["bills"][0]["status"] == "failed" and v["bills"][0]["error"] == report.PAUSED["en"]
    assert v["bills"][0]["error_ur"] == report.PAUSED["ur"]


def test_a_blurred_photo_is_refused_before_any_model_call(tmp_path, monkeypatch):
    import io
    from PIL import Image, ImageDraw, ImageFilter
    monkeypatch.delenv("SAHIBILL_FIXTURES", raising=False)
    monkeypatch.setenv("SAHIBILL_BUDGET_USD", "0")      # a model call would fail as "paused"; a retake proves the gate ran first
    for name in ("REPORTS", "UPLOADS", "READINGS"):
        monkeypatch.setattr(report, name, tmp_path / name.lower())
    monkeypatch.setattr(report, "_reports", {})
    im = Image.new("L", (1200, 1600), 245)
    d = ImageDraw.Draw(im)
    for y in range(40, 1560, 28):
        d.text((40, y), "UNITS 0123456789 RS 4,512.00 DUE 2026-10-08 " * 2, fill=20)
    buf = io.BytesIO()
    im.filter(ImageFilter.GaussianBlur(9)).convert("RGB").save(buf, "JPEG", quality=90)
    v = report.view(report.create([("blurred.jpg", buf.getvalue())], background=False))
    b = v["bills"][0]
    assert b["status"] == "failed" and b["retake"] is True
    assert b["error"] == report.quality.RETAKE["en"] and b["error_ur"] == report.quality.RETAKE["ur"]
    assert v["status"] == "partial" and v["headline"]["en"].startswith("No bill could be read yet")
