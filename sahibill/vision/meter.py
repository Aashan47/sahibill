"""Find and crop the meter photo printed on a bill (SAM 3 on Modal), so the person can read it for us.

The box for each photo is remembered by the photo's SHA-256 under cache/meter/, so a photo is never sent to
SAM 3 twice. SAHIBILL_SAM_FIXTURES may point to a JSON file {sha256: box or null} used instead of Modal
(development and tests).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

from sahibill.readers.llm import CACHE

STORE = CACHE / "meter"
MIN_SCORE = 0.4


def _sha(photo: bytes) -> str:
    return hashlib.sha256(photo).hexdigest()


def locate(photo: bytes) -> list[float] | None:
    """The meter photo's box [x0, y0, x1, y1] on the upright image, or None when SAM 3 finds none."""
    sha = _sha(photo)
    hit = STORE / f"{sha}.json"
    if hit.exists():
        return json.loads(hit.read_text())["box"]
    fixtures = os.environ.get("SAHIBILL_SAM_FIXTURES")
    if fixtures:
        box = json.loads(Path(fixtures).read_text()).get(sha)
    else:
        import modal
        res = modal.Cls.from_name("sahibill-sam", "Sam")().find.remote([{"id": "p", "jpeg": upright_jpeg(photo)}])[0]
        best = next((h for h in res["hits"] if h["score"] >= MIN_SCORE), None)
        box = best["box"] if best else None
    STORE.mkdir(parents=True, exist_ok=True)
    hit.write_text(json.dumps({"box": box}))
    return box


def upright_jpeg(photo: bytes) -> bytes:
    """The photo turned upright by its orientation tag (phones store it sideways), as JPEG."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(photo))).convert("RGB")
    im.thumbnail((2000, 2000))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def crop_png(photo: bytes, box: list[float], margin: float = 0.1, scale: int = 2) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(upright_jpeg(photo)))
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    c = im.crop((int(max(0, x0 - margin * w)), int(max(0, y0 - margin * h)),
                 int(min(im.width, x1 + margin * w)), int(min(im.height, y1 + margin * h))))
    c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    buf = io.BytesIO()
    c.save(buf, "PNG")
    return buf.getvalue()
