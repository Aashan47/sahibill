"""E7: score the speech run (CER per language; abstention by two-model disagreement, threshold set on dev).

python eval/e7.py --runs ../../data-local/speech/e7 --out results/e7.json
Procedure fixed in PREREGISTRATION.md (amendment of 22 October 2026). The output holds counts and rates
only, no transcripts (Common Voice terms).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sahibill.speech.score import cer, disagreement, edit_distance, normalise, threshold_for

A, B = "sahibill_omniASR_LLM_7B_v2", "sahibill_omniASR_LLM_1B_v2"
META = {"urdu": 3.5, "punjabi": 31.2, "sindhi": 6.6, "saraiki": 17.0, "pashto": 12.6}   # Meta's CSV, 7B
LANGS = ["urdu", "saraiki", "sindhi", "pashto", "punjabi"]


def stats(rows: list[dict], model: str) -> dict:
    per = [cer(r["reference"], r[model]) for r in rows]
    edits = sum(edit_distance(normalise(r["reference"]), normalise(r[model])) for r in rows)
    chars = sum(len(normalise(r["reference"])) for r in rows)
    return {"n": len(rows), "mean_cer": round(100 * sum(per) / len(per), 2) if per else None,
            "corpus_cer": round(100 * edits / max(1, chars), 2) if rows else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    def load(name):
        p = a.runs / f"{name}.json"
        return json.loads(p.read_text()) if p.exists() else None

    out = {}
    for lang in LANGS:
        test, dev = load(f"{lang}-test"), load(f"{lang}-dev")
        r = {"meta_published_cer_7b": META[lang]}
        if test:
            r["test_7b"], r["test_1b"] = stats(test, A), stats(test, B)
            for kind in ("mean_cer", "corpus_cer"):
                r[f"within_3_points_{kind}"] = abs(r["test_7b"][kind] - META[lang]) <= 3
        else:
            r["test"] = "not run"
        if dev:
            pairs = [(disagreement(x[A], x[B]), cer(x["reference"], x[A])) for x in dev]
            t = threshold_for(pairs, 0.05)
            r["dev_n"], r["threshold"] = len(dev), t
            r["dev_coverage"] = round(sum(d <= t for d, _ in pairs) / len(pairs), 3) if t is not None else 0.0
            if test:
                acc = [x for x in test if t is not None and disagreement(x[A], x[B]) <= t]
                r["test_coverage"] = round(len(acc) / len(test), 3)
                r["test_accepted_7b"] = stats(acc, A) if acc else {"n": 0}
        else:
            r["dev"] = "not run"
        out[lang] = r
    un = load("pashto-test-unconditioned")
    if un:
        out["pashto"]["test_unconditioned_7b"] = stats(un, A)
    u = out["urdu"]
    out["prediction_urdu_abstention"] = {
        "rule": "accepted mean CER at most 5% with coverage at least 80%",
        "met": bool(u.get("test_coverage") is not None and u["test_coverage"] >= 0.80
                    and (u.get("test_accepted_7b") or {}).get("mean_cer") is not None
                    and u["test_accepted_7b"]["mean_cer"] <= 5.0)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
