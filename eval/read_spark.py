"""Read a list of synthetic images with Spark Open (frozen settings), one JSON per image. Resumable."""
import json
import sys
from pathlib import Path

from sahibill.readers.bill import read_bill
from sahibill.readers.llm import BudgetExceeded

stems, out = Path(sys.argv[1]).read_text().split(), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
spent = 0.0
for i, stem in enumerate(stems, 1):
    dst = out / f"{stem}.json"
    if dst.exists():
        continue
    img = sorted(Path("eval-data/synth/images").glob(stem + ".*"))[0]
    try:
        r = read_bill(img, reasoning_effort="low", tag="stage2")
    except BudgetExceeded as e:
        print("STOPPED:", e, flush=True)
        break
    dst.write_text(json.dumps(r, ensure_ascii=False))
    for c in (r["_call"], (r.get("_first_pass") or {}).get("_call") or {}):
        if c and not c.get("cached"):
            spent += c.get("usd", 0)
    print(f"{i}/{len(stems)} {stem} new spend so far ${spent:.4f}", flush=True)
print("DONE new spend", round(spent, 4))
