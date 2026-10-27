"""Read the meter photo printed on a bill from a SAM 3 crop: the display digits and the time stamp only."""
from __future__ import annotations

from pathlib import Path

from sahibill.readers.llm import chat, image_part, parse_json

PROMPT = """This is a crop of an electricity bill: the small printed photo of the consumer's meter.
Transcribe only; do not guess. Return one JSON object:
{"display": "the digits on the meter's display, exactly as visible, with ? for any digit you cannot read, or null",
 "stamp": "the date and time text printed on or above the photo, exactly as visible, with ? for unreadable characters, or null",
 "rotation": "the rotation of the meter in the photo, in degrees, roughly"}"""


def read_crop(path: str | Path, tag: str = "") -> dict:
    r = chat([{"role": "user", "content": [{"type": "text", "text": PROMPT}, image_part(path)]}],
             reasoning_effort="low", max_tokens=400, tag=tag)
    try:
        out = parse_json(r["content"])
    except Exception as e:   # noqa: BLE001
        out = {"error": str(e), "raw": r["content"][:300]}
    out["_usd"] = 0.0 if r.get("cached") else r.get("usd")
    return out
