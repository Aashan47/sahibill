"""E8: Muse Spark Open on the author's real bills (descriptive only: fields right out of fields read, with counts).

python eval/e8.py --photos <dir of upright JPEGs> --truth <truth.json> --reads <dir> --out results/e8.json
Photos, readings and the answer key stay local (personal details); the output holds counts and field names only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sahibill.readers import consistency
from sahibill.readers.bill import month_key, num, read_bill, to_facts
from sahibill.rules import run_all
from sahibill.verdict import verdict


def same(k: str, truth, got) -> bool:
    if got is None:
        return False
    if isinstance(truth, bool):
        return (got if isinstance(got, bool) else str(got).strip().lower() == "true") == truth
    if isinstance(truth, (int, float)):
        g = num(got)
        return g is not None and abs(float(g) - float(truth)) < 0.005
    if k in ("billing_month", "reference_month"):
        return month_key(str(got)) == truth
    if k == "status":
        return truth in str(got).lower()
    if k == "tariff":
        return str(got).replace(" ", "").lower() == truth.replace(" ", "").lower()
    return str(got).strip()[:10] == str(truth)


def score(read: dict, truth: dict) -> dict:
    got = {k: (v.get("value") if isinstance(v, dict) else None) for k, v in (read.get("fields") or {}).items()}
    fl = read.get("fpa_line") if isinstance(read.get("fpa_line"), dict) else {}
    rows = []
    for k, t in truth.items():
        if k == "fpa_line":
            if t is None:
                continue
            for sub in ("reference_month", "units", "rate"):
                if t.get(sub) is not None:
                    rows.append((f"fpa_line.{sub}", t[sub], fl.get(sub)))
        elif t is not None:
            rows.append((k, t, got.get(k)))
    out = {"fields": len(rows), "right": 0, "wrong": [], "unread": []}
    for k, t, g in rows:
        if g is None:
            out["unread"].append(k)
        elif same(k.split(".")[-1], t, g):
            out["right"] += 1
        else:
            out["wrong"].append(k)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--photos", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--reads", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    truth = json.loads(a.truth.read_text())["bills"]
    a.reads.mkdir(parents=True, exist_ok=True)
    rows, cost = [], 0.0
    for p in sorted(a.photos.glob("*.jpg")):
        month, kind = p.stem.split("-", 1)
        dst = a.reads / f"{p.stem}.json"
        if dst.exists():
            read = json.loads(dst.read_text())
        else:
            read = read_bill(p, reasoning_effort="low", tag=f"e8:{p.stem}")
            dst.write_text(json.dumps(read, ensure_ascii=False, indent=1))
        calls = [read.get("_call") or {}] + [(read.get("_first_pass") or {}).get("_call") or {}]
        cost += sum(c.get("usd") or 0 for c in calls if not c.get("cached"))
        checked = consistency.apply(read)
        cards = verdict(run_all(to_facts(checked, phase=1)))["cards"]
        rows.append({"photo": p.stem, "month": month, "kind": kind.lower(),
                     "turned": (read.get("_first_pass") or {}).get("orientation"),
                     "raw": score(read, truth[month]), "after_consistency": score(checked, truth[month]),
                     "consistency_passed": checked["consistency"]["passed"],
                     "held": sorted(checked["consistency"]["held"]),
                     "verdict": [[c["check"] if "check" in c else c["title"], c["status"]] for c in cards]})
        r = rows[-1]
        print(f"{p.stem:14} right {r['raw']['right']}/{r['raw']['fields']} wrong {r['raw']['wrong']} "
              f"unread {len(r['raw']['unread'])} | after consistency wrong {r['after_consistency']['wrong']} "
              f"held {len(r['held'])} | problems {[v[0] for v in r['verdict'] if v[1] == 'problem_found']}", flush=True)

    def tot(kind, key):
        sel = [r for r in rows if kind in (None, r["kind"])]
        f = sum(r[key]["fields"] for r in sel)
        right = sum(r[key]["right"] for r in sel)
        wrong = sum(len(r[key]["wrong"]) for r in sel)
        return {"photos": len(sel), "fields": f, "right": right, "wrong": wrong, "unread": f - right - wrong}

    summary = {k: {"raw": tot(k, "raw"), "after_consistency": tot(k, "after_consistency")}
               for k in (None, "closeup", "casual")}
    summary = {("all" if k is None else k): v for k, v in summary.items()}
    summary["usd_this_run"] = round(cost, 4)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
