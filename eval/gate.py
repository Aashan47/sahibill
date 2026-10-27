"""The retake gate on the E2 test half, the author's real photos and a fresh synthetic set (amendment of 27 Oct 2026).

python eval/gate.py test                     # every E2 arm with and without the gate, from existing readings
python eval/gate.py photos <dir>             # the gate's decision on each photo in a directory
python eval/gate.py score <synth> <reads>    # one arm with and without the gate on any synthetic set
A refused photo counts as every field unread. Coverage is accepted fields over all printed fields.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from eval.e1 import same, truth_fields
from sahibill.readers.quality import check

ARMS = {"Spark Open alone": "reads-test-spark", "Glimmer alone": "reads-test-glimmer-A",
        "Spark Open + consistency": "reads-test-spark-consistency",
        "Spark Open + Glimmer + consistency (pre-registered)": "reads-test-agree-A"}


def gate_decisions(images: Path, split: str | None, synth: Path) -> dict:
    out = {}
    for p in sorted(images.iterdir()):
        bill, lv = p.stem.rsplit("_L", 1)
        if split and json.loads((synth / "truth" / f"{bill}.json").read_text())["split"] != split:
            continue
        out[p.stem] = {"level": int(lv), **check(p)}
    return out


def score(synth: Path, reads: Path, gate: dict | None, split: str | None) -> dict:
    fields = accepted = wrong = 0
    for rp in sorted(reads.glob("*.json")):
        bill, lv = rp.stem.rsplit("_L", 1)
        t = json.loads((synth / "truth" / f"{bill}.json").read_text())
        if split and t["split"] != split:
            continue
        read = json.loads(rp.read_text())
        got = {k: v.get("value") if isinstance(v, dict) else None for k, v in (read.get("fields") or {}).items()}
        refused = gate is not None and not gate[rp.stem]["ok"]
        for k, tv in truth_fields(t).items():
            fields += 1
            if refused or got.get(k) is None:
                continue
            accepted += 1
            wrong += not same(k, tv, got.get(k))
    return {"fields": fields, "accepted": accepted, "coverage": round(accepted / max(1, fields), 4),
            "wrong": wrong, "wrong_rate": round(wrong / max(1, accepted), 4)}


def by_level(gate: dict) -> dict:
    c = Counter((g["level"], g["ok"]) for g in gate.values())
    return {lv: {"kept": c[(lv, True)], "refused": c[(lv, False)]} for lv in sorted({g["level"] for g in gate.values()})}


def main(argv):
    root = Path("eval-data")
    if argv[0] == "test":
        synth = root / "synth"
        gate = gate_decisions(synth / "images", "test", synth)
        res = {"gate_by_level": by_level(gate),
               "arms": {name: {"without": score(synth, root / d, None, "test"), "with": score(synth, root / d, gate, "test")}
                        for name, d in ARMS.items()},
               "photos": gate}
    elif argv[0] == "photos":
        res = {p.name: check(p) for p in sorted(Path(argv[1]).iterdir()) if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    else:
        synth, reads = Path(argv[1]), Path(argv[2])
        gate = gate_decisions(synth / "images", None, synth)
        res = {"gate_by_level": by_level(gate), "without": score(synth, reads, None, None),
               "with": score(synth, reads, gate, None), "photos": gate}
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
