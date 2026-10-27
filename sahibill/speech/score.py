"""Character error rate and the two-model disagreement used for abstention."""
from __future__ import annotations

import re
import unicodedata

_TAG = re.compile(r"<[a-z_]+>")          # Omnilingual corpus tags: <laugh>, <hesitation>, <unintelligible>, <noise>
_PUNCT = re.compile(r"[؀-؏؛-؟٪-٭۔.,!?;:\"'()\[\]{}\-‘-‟]")


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = _TAG.sub(" ", t)
    t = _PUNCT.sub(" ", t)
    t = t.replace("‌", "").replace("‍", "")
    return re.sub(r"\s+", " ", t).strip()


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    r, h = normalise(reference), normalise(hypothesis)
    return edit_distance(r, h) / max(1, len(r))


def disagreement(a: str, b: str) -> float:
    """Symmetric character disagreement between two transcripts (0 = identical)."""
    x, y = normalise(a), normalise(b)
    return edit_distance(x, y) / max(1, max(len(x), len(y)))


def threshold_for(dev: list[tuple[float, float]], target_cer: float) -> float | None:
    """Largest disagreement threshold whose accepted dev clips have mean CER at most target (None if none)."""
    best = None
    for t in sorted({d for d, _ in dev}):
        acc = [c for d, c in dev if d <= t]
        if acc and sum(acc) / len(acc) <= target_cer:
            best = t
    return best
