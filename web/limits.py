"""Limits on the public routes that cost money or disk: per visitor per hour, and a ceiling per day for the site.

Behind the Cloudflare tunnel every request arrives from 127.0.0.1, so the visitor is the CF-Connecting-IP
header, trusted only when the direct peer is this machine. Counts live in memory: the app runs as one worker,
and a restart clearing them is acceptable. Paid reading is also capped in money by SAHIBILL_BUDGET_USD.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

HOUR, DAY = 3600, 86400

# bucket: (events allowed, window in seconds). Photos are counted one by one, every other bucket per request.
PER_VISITOR = {
    "photos": (24, DAY),     # new bill photos read by the model
    "upload": (8, HOUR),
    "sample": (30, HOUR),
    "hear": (30, HOUR),      # speech models on Modal
    "ask": (40, HOUR),       # Muse Spark answers
    "meter": (30, HOUR),     # SAM 3 on Modal
    "warm": (20, HOUR),
    "edit": (200, HOUR),     # answers and corrections: no model call, only disk
}
# Whole site per day: Modal calls (speech, SAM 3, warm-up) and new photos.
PER_SITE = {
    "modal": (int(os.environ.get("SAHIBILL_MODAL_CALLS_PER_DAY", "400")), DAY),
    "photos": (int(os.environ.get("SAHIBILL_PHOTOS_PER_DAY", "300")), DAY),
}
MESSAGE = "Too many requests from this connection. Please wait a while and try again."
SITE_MESSAGE = "This service has reached its limit for today. Please try again tomorrow, or open a sample bill."

_lock = threading.Lock()
_events: dict[tuple[str, str], deque] = defaultdict(deque)
_swept = time.time()


def visitor(request: Request) -> str:
    peer = request.client.host if request.client else ""
    cf = request.headers.get("cf-connecting-ip", "").strip()
    return cf if cf and peer in ("127.0.0.1", "::1") else peer or "unknown"


def _take(key: tuple[str, str], allowed: int, window: int, n: int, now: float) -> bool:
    q = _events[key]
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) + n > allowed:
        return False
    q.extend([now] * n)
    return True


def _sweep(now: float) -> None:
    """Drop visitors with no recent events, so memory stays bounded."""
    global _swept
    if now - _swept < 600:
        return
    _swept = now
    for key in [k for k, q in _events.items() if not q or q[-1] <= now - DAY]:
        del _events[key]


def check(request: Request, bucket: str, n: int = 1, site: str | None = None) -> None:
    """Count n events against this visitor's bucket (and the site's daily bucket); 429 when over."""
    if os.environ.get("SAHIBILL_NO_LIMITS"):
        return
    now = time.time()
    with _lock:
        _sweep(now)
        allowed, window = PER_VISITOR[bucket]
        if not _take((bucket, visitor(request)), allowed, window, n, now):
            raise HTTPException(429, MESSAGE)
        if site:
            allowed, window = PER_SITE[site]
            if not _take((site, "*"), allowed, window, n, now):
                raise HTTPException(429, SITE_MESSAGE)


def reset() -> None:
    with _lock:
        _events.clear()
