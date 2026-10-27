"""E1: field reading accuracy on synthetic bills, against the generator's ground truth.

python eval/e1.py --synth eval-data/synth --reads <dir of reader JSON> --out results/e1.json
A field counts only where the truth printed it. Numbers compare exactly after removing separators;
dates compare as ISO strings; history compares units month by month.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from sahibill.readers.bill import month_key, num

NUMERIC = ["sanctioned_load_kw", "prev_reading", "present_reading", "units", "carried_forward", "snapshot_reading",
           "variable", "fixed", "min_charge", "fca", "qta", "gst", "payable_within"]
DATES = ["reading_date", "prev_reading_date", "issue_date", "due_date"]


def truth_fields(t: dict) -> dict:
    p = t["printed"]
    out = {"billing_month": p["billing_month"], "status": p["status"]}
    for k in DATES:
        if p.get(k):
            out[k] = p[k]
    for k in NUMERIC:
        v = p.get(k)
        if k in ("carried_forward", "min_charge", "fca", "qta") and not v:
            continue
        if v is None:
            continue
        out[k] = v
    return out


def same(k, truth, got):
    if got is None:
        return False
    if k in NUMERIC:
        g = num(got)
        return g is not None and abs(float(g) - float(truth)) < 0.005
    if k == "billing_month":
        return month_key(str(got)) == truth
    if k == "status":
        return str(got).strip().lower() == str(truth).lower()
    return str(got).strip()[:10] == str(truth)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--synth", type=Path, required=True)
    ap.add_argument("--reads", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", default="test")
    a = ap.parse_args(argv)
    by_level = defaultdict(lambda: {"fields": 0, "right": 0, "abstained": 0, "images": 0, "hist": 0, "hist_right": 0})
    errors = []
    for rp in sorted(a.reads.glob("*.json")):
        read = json.loads(rp.read_text())
        bill_id, lv = rp.stem.rsplit("_L", 1)
        t = json.loads((a.synth / "truth" / f"{bill_id}.json").read_text())
        if a.split != "all" and t["split"] != a.split:
            continue
        s = by_level[lv]
        s["images"] += 1
        got = {k: v.get("value") if isinstance(v, dict) else None for k, v in (read.get("fields") or {}).items()}
        for k, tv in truth_fields(t).items():
            s["fields"] += 1
            if got.get(k) is None:
                s["abstained"] += 1
            elif same(k, tv, got.get(k)):
                s["right"] += 1
            else:
                errors.append({"image": rp.stem, "field": k, "truth": tv, "read": got.get(k)})
        hist_read = {month_key(h.get("month")): num(h.get("units")) for h in read.get("history") or []}
        for h in t["printed"]["history"]:
            s["hist"] += 1
            mk = month_key(h["month"])
            if hist_read.get(mk) == h["units"]:
                s["hist_right"] += 1
    summary = {lv: {**v, "accuracy_on_read": round(v["right"] / max(1, v["fields"] - v["abstained"]), 4),
                    "accuracy_all": round(v["right"] / max(1, v["fields"]), 4),
                    "history_accuracy": round(v["hist_right"] / max(1, v["hist"]), 4)}
               for lv, v in sorted(by_level.items())}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"split": a.split, "by_level": summary, "errors": errors}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
