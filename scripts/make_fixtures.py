"""Saved readings so the app can be built and tested without model calls.

python scripts/make_fixtures.py
1. Real bills (personal, local only): ../../data-local/real-bills-e8/<stem>.jpg + ../../data-local/real-bills-reads/<stem>.json
   -> ../../data-local/fixtures/<sha24>.json. Run the server with SAHIBILL_FIXTURES=../../data-local/fixtures.
2. Synthetic samples (committed, no personal details): the readings of web/static/samples/*.jpg are recovered from
   cache/llm/ by recomputing their cache keys with each earlier version of the reader prompt (git history of
   sahibill/readers/bill.py), following read_bill's straighten-and-reread, -> web/static/samples/readings/<sha24>.json.
No model is called.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sahibill.readers.bill import _upright  # noqa: E402
from sahibill.readers.llm import CACHE, PROVIDERS, image_part, parse_json  # noqa: E402
from sahibill.report import SAMPLE_READINGS, SAMPLES  # noqa: E402

LOCAL = ROOT.parents[1] / "data-local"


def real_bills() -> int:
    out = LOCAL / "fixtures"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for img in sorted((LOCAL / "real-bills-e8").glob("*.jpg")):
        read = LOCAL / "real-bills-reads" / f"{img.stem}.json"
        if read.exists():
            sha = hashlib.sha256(img.read_bytes()).hexdigest()
            (out / f"{sha[:24]}.json").write_text(read.read_text())
            n += 1
    return n


def _old_prompts() -> dict[str, str]:
    commits = subprocess.run(["git", "log", "--format=%h", "--", "sahibill/readers/bill.py"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    prompts = {}
    for c in commits:
        src = subprocess.run(["git", "show", f"{c}:sahibill/readers/bill.py"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout
        head = "\n".join(line for line in src[:src.index("\ndef ")].splitlines() if not line.startswith("from sahibill"))
        ns: dict = {}
        exec(head, ns)  # noqa: S102  (our own file from our own git history: module constants only)
        prompts[c] = ns["PROMPT"]
    return prompts


def _cached(prompt: str, img: Path) -> dict | None:
    cfg = PROVIDERS["nebius"]
    body = {"model": cfg["model"], "max_tokens": 6000, "reasoning_effort": "low",
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, image_part(img)]}]}
    p = CACHE / "llm" / (hashlib.sha256(json.dumps(["nebius", body], sort_keys=True).encode()).hexdigest() + ".json")
    return json.loads(p.read_text()) if p.exists() else None


def _as_read(r: dict) -> dict:
    data = parse_json(r["content"])
    data["_call"] = {k: r.get(k) for k in ("usage", "usd", "latency_s", "provider", "model", "reasoning_effort")}
    data["_call"]["cached"] = True
    return data


def samples() -> tuple[int, list[str]]:
    SAMPLE_READINGS.mkdir(parents=True, exist_ok=True)
    prompts = _old_prompts()
    done, missing = 0, []
    for img in sorted(SAMPLES.glob("*.jpg")):
        read = None
        for c, prompt in prompts.items():      # newest first
            first = _cached(prompt, img)
            if first is None:
                continue
            read = _as_read(first)
            o = read.get("orientation")
            try:
                o = int(round(float(o))) % 360
            except (TypeError, ValueError):
                o = 0
            if o in (90, 180, 270):
                second = _cached(prompt, _upright(img, o))
                if second is None:
                    read = None
                    continue
                read = {**_as_read(second), "_first_pass": {"orientation": o}}
            read["_recovered_from"] = f"cache/llm, reader prompt at commit {c}"
            break
        if read is None:
            missing.append(img.name)
            continue
        sha = hashlib.sha256(img.read_bytes()).hexdigest()
        (SAMPLE_READINGS / f"{sha[:24]}.json").write_text(json.dumps(read, ensure_ascii=False, indent=1))
        done += 1
    return done, missing


if __name__ == "__main__":
    print("real-bill fixtures:", real_bills())
    n, missing = samples()
    print("sample readings recovered:", n, "missing:", missing)
