"""Photo damage at four levels (07-SYNTHETIC-BILL-SPEC.md): 0 clean, 1 mild, 2 phone photo, 3 hard."""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def _perspective(im, rng, strength):
    W, H = im.size
    d = lambda: rng.uniform(0, strength) * min(W, H)
    src = [(d(), d()), (W - d(), d()), (W - d(), H - d()), (d(), H - d())]
    dst = [(0, 0), (W, 0), (W, H), (0, H)]
    A, B = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B += [u, v]
    coeffs = np.linalg.solve(np.array(A, float), np.array(B, float))
    return im.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(118, 108, 92))


def _light(im, rng, low):
    a = np.asarray(im).astype(float)
    H, W = a.shape[:2]
    gx = np.linspace(1.0, rng.uniform(low, 1.0), W)[None, :, None]
    gy = np.linspace(rng.uniform(low, 1.0), 1.0, H)[:, None, None]
    return np.clip(a * gx * gy, 0, 255)


def degrade(im: Image.Image, level: int, seed: int) -> tuple[Image.Image, dict]:
    rng = random.Random(seed)
    im = im.convert("RGB")
    info = {"level": level}
    if level == 0:
        return im, info
    if level == 1:
        im = im.rotate(rng.uniform(-2, 2), expand=True, fillcolor=(240, 238, 230))
        a = _light(im, rng, 0.85)
        return Image.fromarray(a.astype("uint8")), info
    im = _perspective(im, rng, 0.05 if level == 2 else 0.09)
    a = _light(im, rng, 0.6 if level == 2 else 0.45)
    a = np.clip(a + np.random.default_rng(seed).normal(0, 7 if level == 2 else 11, a.shape), 0, 255)
    im = Image.fromarray(a.astype("uint8"))
    if level == 3:
        dr = ImageDraw.Draw(im, "RGBA")
        W, H = im.size
        y = int(H * rng.uniform(0.35, 0.65))
        dr.line([(0, y), (W, y + rng.randint(-20, 20))], fill=(60, 60, 60, 90), width=3)   # fold line
        cx, cy, r = int(W * rng.uniform(0.2, 0.8)), int(H * rng.uniform(0.2, 0.8)), int(min(W, H) * 0.12)
        for k in range(r, 0, -6):
            dr.ellipse([cx - k, cy - k, cx + k, cy + k], fill=(255, 255, 255, int(70 * (1 - k / r))))  # glare
        rot = rng.choice([0, 0, 90, 180, 270]) + rng.uniform(-4, 4)
        im = im.rotate(rot, expand=True, fillcolor=(118, 108, 92))
        info["rotation"] = round(rot, 1)
    im = im.filter(ImageFilter.GaussianBlur(1.2 if level == 2 else 1.7))
    scale = 0.8 if level == 2 else 0.6
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.BILINEAR)
    im = ImageEnhance.Contrast(im).enhance(0.85 if level == 2 else 0.75)
    info["jpeg_quality"] = 50 if level == 2 else 35
    return im, info
