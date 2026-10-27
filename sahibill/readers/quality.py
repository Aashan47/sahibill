"""Photo quality gate: asks for a retake before a badly damaged photo is read (the E2 miss, results/E2.md).

Free and local: no model call. The photo is turned to grey and scaled so its long side is 1200 pixels, which
puts a full-resolution phone photo and a small one on the same footing (a small photo comes out soft, as it
should: it has fewer pixels per printed digit). Sharpness is the variance of the Laplacian divided by the
image's own contrast, so a dim or washed-out photo is not mistaken for a sharp one. The threshold was set on
the calibration half of the synthetic bills only (PREREGISTRATION.md, amendment of 27 October 2026).
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

LONG_SIDE = 1200
THRESHOLD = 3.0    # frozen in the amendment of 27 October 2026, from the calibration half only


def _grey(photo: bytes | str | Path | Image.Image) -> np.ndarray:
    if isinstance(photo, Image.Image):
        im = photo
    elif isinstance(photo, (bytes, bytearray)):
        im = Image.open(io.BytesIO(photo))
    else:
        im = Image.open(photo)
    im = ImageOps.exif_transpose(im).convert("L")
    s = LONG_SIDE / max(im.size)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.BILINEAR)
    return np.asarray(im, dtype=np.float64)


def measure(photo) -> dict:
    g = _grey(photo)
    lap = (g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4 * g[1:-1, 1:-1])
    contrast = float(np.percentile(g, 95) - np.percentile(g, 5))
    return {"sharpness": float(lap.var() / max(contrast, 1.0) ** 2 * 1000), "contrast": round(contrast, 1)}


def check(photo) -> dict:
    """{ok, sharpness, contrast, reason}. ok False means: ask for a retake before reading."""
    m = measure(photo)
    ok = m["sharpness"] >= THRESHOLD
    return {"ok": ok, **{k: round(v, 3) for k, v in m.items()},
            "reason": None if ok else "The photo is too blurred or too small to read the digits reliably."}


# What the photo row shows when the gate refuses (in place of a reading). Urdu not yet checked by a reader of Urdu.
RETAKE = {
    "en": "This photo is too blurred or too small to read the digits reliably. Please take it again: the bill flat, "
          "in daylight, filling the frame, held still.",
    "ur": "یہ تصویر اتنی دھندلی یا چھوٹی ہے کہ ہندسے ٹھیک سے نہیں پڑھے جا سکتے۔ براہ کرم دوبارہ تصویر لیں: بل سیدھا رکھیں، "
          "دن کی روشنی میں، پورا بل تصویر میں ہو، اور ہاتھ نہ ہلے۔",
}
