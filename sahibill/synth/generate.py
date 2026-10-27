"""Generate a synthetic bill set: images at four damage levels plus ground truth.

python -m sahibill.synth.generate --n 50 --seed 20261026 --out eval-data/synth
Half the bills (by id) are calibration, half test; a bill never appears in both.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from PIL import Image

from sahibill.synth.degrade import degrade
from sahibill.synth.model import DEFECTS, make_bill
from sahibill.synth.render import render_png

SINGLE = list(DEFECTS)


def family(d: str) -> str:
    """Defects in one family contradict or mask each other, so a bill never carries two of them."""
    if d.startswith("detection"):
        return "detection"
    if d.startswith("snapshot"):
        return "snapshot"
    if d in ("long_period_not_prorated", "accumulated_units"):
        return "units"
    return d


def plan(n: int, seed: int) -> list[list[str]]:
    """Each defect type appears about equally; about 1 bill in 6 is clean; some bills carry two defects."""
    rng = random.Random(seed)
    out = []
    pool = []
    for i in range(n):
        if i % 6 in (0, 3):          # clean bills fall in both halves (even and odd ids)
            out.append([])
            continue
        if not pool:
            pool = SINGLE[:]
            rng.shuffle(pool)
        ds = [pool.pop()]
        if rng.random() < 0.2:
            other = rng.choice([d for d in SINGLE if family(d) != family(ds[0])])
            ds.append(other)
        out.append(ds)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261026)
    ap.add_argument("--out", type=Path, default=Path("eval-data/synth"))
    ap.add_argument("--levels", default="0,1,2,3")
    a = ap.parse_args(argv)
    levels = [int(x) for x in a.levels.split(",")]
    bills, truths = [], []
    for i, ds in enumerate(plan(a.n, a.seed)):
        bid = f"syn{i:04d}"
        b, t = make_bill(a.seed * 1000 + i, bid, ds)
        t["split"] = "calibration" if i % 2 == 0 else "test"
        bills.append(b); truths.append(t)
    raw = a.out / "raw"
    paths = render_png(bills, raw)
    img_dir, truth_dir = a.out / "images", a.out / "truth"
    img_dir.mkdir(parents=True, exist_ok=True); truth_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for b, t, p in zip(bills, truths, paths):
        src = Image.open(p)
        t["images"] = {}
        for lv in levels:
            im, info = degrade(src, lv, a.seed * 7 + int(b.bill_id[3:]) * 10 + lv)
            name = f"{b.bill_id}_L{lv}." + ("png" if lv < 2 else "jpg")
            if lv < 2:
                im.save(img_dir / name)
            else:
                im.save(img_dir / name, quality=info["jpeg_quality"])
            t["images"][str(lv)] = {"file": name, **info}
            manifest.append({"bill_id": b.bill_id, "level": lv, "file": name, "split": t["split"],
                             "defects": [d["defect"] for d in t["defects"]]})
        (truth_dir / f"{b.bill_id}.json").write_text(json.dumps(t, indent=1, ensure_ascii=False))
    (a.out / "manifest.json").write_text(json.dumps({"seed": a.seed, "n": a.n, "levels": levels, "items": manifest}, indent=1))
    print(f"{len(bills)} bills, {len(manifest)} images -> {a.out}")


if __name__ == "__main__":
    main()
