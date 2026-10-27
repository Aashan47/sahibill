"""SahiBill web app: photos of one or more bills in, a household report out (the API in 10-PRODUCT-DESIGN.md).

Run: .venv/bin/python -m uvicorn web.app:app --port 8770
Fixture mode (no model calls): SAHIBILL_FIXTURES=../../data-local/fixtures .venv/bin/python -m uvicorn web.app:app --port 8770
Paid model calls are capped by SAHIBILL_BUDGET_USD (default 0: only saved readings are served).
Uploaded photos stay on this server, in cache/uploads/, and are never committed. With SAHIBILL_KEEP_DAYS set (the
live site uses 30), reports, photos, readings and cached answers older than that are deleted. Unset, nothing is
deleted, so a development cache keeps its evaluation calls. Routes that cost money or disk are limited per visitor (web/limits.py).
The built frontend (web/dist/) is served when present; otherwise the earlier one-page app in web/static/.
"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sahibill import report, voice
from sahibill.pipeline import analyze
from sahibill.readers.llm import BudgetExceeded
from web import limits

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
mimetypes.add_type("application/manifest+json", ".webmanifest")
UPLOADS = report.UPLOADS
SAMPLES = report.SAMPLES
MAX_BYTES = 12_000_000
KEEP_DAYS = float(os.environ["SAHIBILL_KEEP_DAYS"]) if os.environ.get("SAHIBILL_KEEP_DAYS") else None


def _sweeper(stop: threading.Event) -> None:
    while True:
        report.sweep(KEEP_DAYS)
        if stop.wait(6 * 3600):
            return


@asynccontextmanager
async def lifespan(_app):
    """Deletes reports, photos and readings older than KEEP_DAYS at start and every six hours."""
    stop = threading.Event()
    if KEEP_DAYS:
        threading.Thread(target=_sweeper, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="SahiBill", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
    return resp
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


class SampleRequest(BaseModel):
    set: str = "synthetic"


class Answer(BaseModel):
    question: str
    absent: bool


class Question(BaseModel):
    question: str
    language: str


class Correction(BaseModel):
    field: str
    value: str | float | int | None = None


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/samples")
def samples():
    return [{"name": p.name, "url": f"/static/samples/{p.name}"} for p in sorted(SAMPLES.glob("*.jpg"))]


@app.post("/api/reports")
async def create_report(request: Request, photos: list[UploadFile] = File(...)):
    if not 1 <= len(photos) <= report.MAX_PHOTOS:
        raise HTTPException(400, f"Send 1 to {report.MAX_PHOTOS} photos of your bills.")
    limits.check(request, "upload")
    items = []
    for ph in photos:
        data = await ph.read()
        if not data or len(data) > MAX_BYTES:
            raise HTTPException(400, "Each photo must be under 12 MB.")
        items.append((ph.filename or "photo.jpg", data))
    new = sum(report.stored_reading(report.photo_sha(d)) is None for _, d in items)   # saved readings cost nothing
    if new:
        limits.check(request, "photos", new, site="photos")
    return {"id": report.create(items)}


@app.post("/api/reports/sample")
def create_sample(request: Request, req: SampleRequest | None = None):
    if (req or SampleRequest()).set != "synthetic":
        raise HTTPException(400, "Unknown sample set.")
    limits.check(request, "sample")
    return {"id": report.create_sample()}


@app.get("/api/reports/{rid}")
def get_report(rid: str):
    v = report.view(rid)
    if v is None:
        raise HTTPException(404, "No such report.")
    return v


@app.post("/api/reports/{rid}/bills/{bill_id}/answer")
def answer(request: Request, rid: str, bill_id: str, body: Answer):
    limits.check(request, "edit")
    try:
        v = report.answer(rid, bill_id, body.question, body.absent)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if v is None:
        raise HTTPException(404, "No such report.")
    return v


@app.post("/api/reports/{rid}/bills/{bill_id}/correct")
def correct(request: Request, rid: str, bill_id: str, body: Correction):
    limits.check(request, "edit")
    try:
        v = report.correct(rid, bill_id, body.field, body.value)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if v is None:
        raise HTTPException(404, "No such report.")
    return v


def _bill(rid: str, bill_id: str) -> dict:
    v = report.view(rid)
    if v is None:
        raise HTTPException(404, "No such report.")
    b = next((b for b in v["bills"] if b["id"] == bill_id and b.get("status") == "done"), None)
    if b is None:
        raise HTTPException(404, "No such bill, or it is still being read.")
    return b


@app.post("/api/voice/warm")
def voice_warm(request: Request):
    """Called when someone opens 'Ask about this bill', so the speech models are loading before they speak."""
    try:
        limits.check(request, "warm", site="modal")
        return {"warming": voice.warm()}
    except Exception:  # noqa: BLE001  (over a limit, or speech service unavailable: typing still works)
        return {"warming": False}


@app.post("/api/reports/{rid}/bills/{bill_id}/hear")
async def hear(request: Request, rid: str, bill_id: str, audio: UploadFile = File(...), language: str = Form(...)):
    """A spoken question: both speech models transcribe it; `sure` says whether to confirm it first."""
    _bill(rid, bill_id)
    data = await audio.read()
    if not data or len(data) > 5_000_000:
        raise HTTPException(400, "Send one recording, under 5 MB.")
    if language not in voice.THRESHOLDS:
        raise HTTPException(400, "Unsupported language.")
    limits.check(request, "hear", site="modal")
    fmt = (audio.filename or "q.webm").rsplit(".", 1)[-1].lower()[:5] or "webm"
    try:
        return voice.hear(data, fmt, language)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001  (speech service unavailable)
        raise HTTPException(503, "Listening is not available right now. Type the question instead.") from e


@app.post("/api/reports/{rid}/bills/{bill_id}/ask")
def ask(request: Request, rid: str, bill_id: str, body: Question):
    """Answer a confirmed or typed question from this bill's findings only."""
    q = body.question.strip()
    if not q or len(q) > 500:
        raise HTTPException(400, "Ask one short question.")
    if body.language not in voice.THRESHOLDS:
        raise HTTPException(400, "Unsupported language.")
    bill = _bill(rid, bill_id)
    limits.check(request, "ask")
    return voice.answer(bill, q, body.language)


@app.get("/api/reports/{rid}/bills/{bill_id}/meter")
def meter(request: Request, rid: str, bill_id: str):
    """The meter photo printed on this bill, cut out by SAM 3 and enlarged, for the person to read."""
    from sahibill.vision import meter as m
    b = _bill(rid, bill_id)
    limits.check(request, "meter", site="modal")
    for url in b.get("photo_urls") or []:
        p = report.photo_file(rid, url.rsplit("/", 1)[-1])
        if p is None:
            continue
        data = p.read_bytes()
        try:
            box = m.locate(data)
        except Exception as e:  # noqa: BLE001  (SAM 3 service unavailable)
            raise HTTPException(503, "Finding the meter photo is not available right now.") from e
        if box:
            return Response(m.crop_png(data, box), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
    raise HTTPException(404, "The meter photo was not found on this bill's photos.")


@app.get("/api/reports/{rid}/photos/{pid}")
def photo(rid: str, pid: str):
    p = report.photo_file(rid, pid)
    if p is None:
        raise HTTPException(404, "No such photo.")
    return FileResponse(p, headers={"Cache-Control": "private, max-age=3600"})


# Earlier one-photo endpoints, kept for the web/static page.
def _run(path: Path, confirmed_absent: bool = False):
    from sahibill.readers import quality
    try:
        if not quality.check(path)["ok"]:
            return JSONResponse({"ok": False, "retake": True, "error": quality.RETAKE["en"], "error_ur": quality.RETAKE["ur"]}, 422)
    except (OSError, ValueError):
        pass
    try:
        return analyze(path, confirmed_absent=confirmed_absent)
    except BudgetExceeded:
        return JSONResponse({"ok": False, "error": "Checking new photos is paused on this server. Try a sample bill."}, 429)


@app.post("/api/check/sample/{name}")
def check_sample(name: str, confirmed_absent: bool = False):
    p = SAMPLES / Path(name).name
    if not p.exists():
        raise HTTPException(404, "No such sample bill.")
    return _run(p, confirmed_absent)


@app.post("/api/check")
async def check(request: Request, photo: UploadFile = File(...), confirmed_absent: bool = False):
    """confirmed_absent: the user has looked and confirms that what the reader could not find is not on the bill."""
    data = await photo.read()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(400, "Send one photo of the bill, under 12 MB.")
    limits.check(request, "upload")
    if report.stored_reading(report.photo_sha(data)) is None:
        limits.check(request, "photos", site="photos")
    suffix = ".png" if data[:4] == b"\x89PNG" else ".jpg"
    UPLOADS.mkdir(parents=True, exist_ok=True)
    p = UPLOADS / (hashlib.sha256(data).hexdigest()[:24] + suffix)
    p.write_bytes(data)
    return _run(p, confirmed_absent)


@app.get("/api/{rest:path}")
def api_404(rest: str):
    raise HTTPException(404, "No such API route.")


@app.get("/{rest:path}")
def client(rest: str):
    """The built app (client-side routes fall back to index.html); else the earlier page."""
    if DIST.is_dir():
        f = (DIST / rest).resolve()
        if rest and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
    return FileResponse(HERE / "static" / "index.html", headers={"Cache-Control": "no-cache"})
