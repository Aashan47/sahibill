"""E7: fix the speech clips (dev for thresholds, test for scoring) before any clip is scored.

python eval/e7_sets.py --speech ../../data-local/speech --out ../../data-local/speech/e7-manifest.json
Sets and sizes are those of the 21 October amendment; random subsets use seed 20261022 on the sorted
file names. Common Voice transcripts stay in data-local (no re-sharing).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

SEED = 20261022
CV = "cv27-skr/cv-corpus-27.0-2026-09-11/skr"
# (language, corpus, corpus code, split, size or None for all)
SETS = [
    ("urdu", "fleurs", "ur_pk", "dev", None), ("urdu", "fleurs", "ur_pk", "test", None),
    ("saraiki", "cv", "skr", "dev", 200), ("saraiki", "cv", "skr", "test", None),
    ("sindhi", "fleurs", "sd_in", "dev", 200), ("sindhi", "fleurs", "sd_in", "test", 200),
    ("pashto", "fleurs", "ps_af", "dev", None), ("pashto", "fleurs", "ps_af", "test", 200),
    ("punjabi", "omni", "pnb_Arab", "dev", None), ("punjabi", "omni", "pnb_Arab", "test", None),
]
OMNI_HOURS = {("pnb_Arab", "dev"): (77, 1.22), ("pnb_Arab", "test"): (84, 1.48)}   # SPEECH-EVAL-DATA.md 1A


def pick(items: list[dict], k: int | None) -> list[dict]:
    items = sorted(items, key=lambda x: x["file"])
    return items if k is None or k >= len(items) else sorted(random.Random(SEED).sample(items, k), key=lambda x: x["file"])


def fleurs(speech: Path, code: str, split: str) -> list[dict]:
    rows = csv.reader(open(speech / "fleurs-tsv" / f"{code}.{split}.tsv", encoding="utf-8"), delimiter="\t",
                      quoting=csv.QUOTE_NONE)
    return [{"id": f"{code}-{split}-{r[1][:-4]}", "file": r[1], "ref": r[2], "seconds": int(r[5]) / 16000} for r in rows]


def cv(speech: Path, split: str) -> list[dict]:
    d = speech / CV
    rows = csv.DictReader(open(d / f"{split}.tsv", encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)
    durs = {}
    dur_file = d / "clip_durations.tsv"
    if dur_file.exists():
        durs = {r["clip"]: int(r["duration[ms]"]) / 1000 for r in csv.DictReader(open(dur_file), delimiter="\t")}
    return [{"id": r["path"][:-4], "file": r["path"], "ref": r["sentence"], "seconds": durs.get(r["path"])} for r in rows]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--speech", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    out = []
    for lang, corpus, code, split, k in SETS:
        if corpus == "fleurs":
            items = pick(fleurs(a.speech, code, split), k)
        elif corpus == "cv":
            items = pick(cv(a.speech, split), k)
        else:
            items = None          # all rows of the parquet split; read inside the Modal container
        n, hours = (len(items), sum(i["seconds"] or 0 for i in items) / 3600) if items else OMNI_HOURS[(code, split)]
        out.append({"language": lang, "corpus": corpus, "code": code, "split": split, "size": k, "n": n,
                    "hours": round(hours, 3), "items": items})
        print(f"{lang:8} {corpus:6} {code:9} {split:5} n={n:5} hours={hours:.2f}")
    print("total hours", round(sum(s["hours"] for s in out), 2))
    a.out.write_text(json.dumps({"seed": SEED, "sets": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
