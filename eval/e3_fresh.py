"""E3 re-measured on a fresh synthetic set through the live product path (PREREGISTRATION amendment of 29 Oct).

Each photo goes through the retake gate first; a refused photo is not read. Accepted photos are read by Spark
Open at the E1 stage 2 settings. Resumable. Scoring is eval/e3.py, unchanged, run on every bill.

    SAHIBILL_BUDGET_USD=3.133 python eval/e3_fresh.py eval-data/synth-e3-20261029 eval-data/reads-e3-20261029
"""
import json
import sys
from pathlib import Path

from sahibill.readers import quality
from sahibill.readers.bill import read_bill
from sahibill.readers.llm import BudgetExceeded

synth, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
images = sorted((synth / "images").glob("*"), key=lambda p: (not p.stem.endswith("_L2"), p.name))  # level 2 first
gate, spent = {}, 0.0
for i, img in enumerate(images, 1):
    g = quality.check(img)
    gate[img.stem] = {k: g[k] for k in ("ok", "sharpness", "contrast")}
    dst = out / f"{img.stem}.json"
    if not g["ok"] or dst.exists():
        continue
    try:
        r = read_bill(img, reasoning_effort="low", tag="e3-fresh")
    except BudgetExceeded as e:
        print("STOPPED:", e, flush=True)
        break
    dst.write_text(json.dumps(r, ensure_ascii=False))
    for c in (r["_call"], (r.get("_first_pass") or {}).get("_call") or {}):
        if c and not c.get("cached"):
            spent += c.get("usd", 0)
    print(f"{i}/{len(images)} {img.stem} new spend so far ${spent:.4f}", flush=True)
(out.parent / (out.name + ".gate.json")).write_text(json.dumps(gate, indent=1))
print("DONE new spend", round(spent, 4), "refused", sum(not g["ok"] for g in gate.values()), "of", len(gate))
