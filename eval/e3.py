"""E3: seeded-defect detection on the synthetic test half, through the product path.

Reading (frozen, from stage 2) -> consistency layer -> facts -> rules. Run once.
A seeded defect counts as found when its violation code is raised. Clean bills count a false flag when
any problem is raised. Reported per damage level and per defect type; defects the bill cannot show
(determinable_from_bill false) are reported separately.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from sahibill.readers import consistency
from sahibill.readers.bill import to_facts
from sahibill.rules import run_all, violations

synth, reads, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
every_bill = "all" in sys.argv[4:]     # a fresh set with no calibration half (amendment of 29 Oct)
confirmed = "confirmed" in sys.argv[4:]  # the household confirms the absences SahiBill asks about
per = defaultdict(lambda: {"seeded": 0, "found": 0, "not_determinable": 0, "clean": 0, "false_flag": 0})
per_type = defaultdict(lambda: {"seeded": 0, "found": 0})
rows = []
for rp in sorted(reads.glob("*.json")):
    bill, lv = rp.stem.rsplit("_L", 1)
    t = json.loads((synth / "truth" / f"{bill}.json").read_text())
    if t["split"] != "test" and not every_bill:
        continue
    read = consistency.apply(json.loads(rp.read_text()))
    raised = violations(run_all(to_facts(read, confirmed_absent=confirmed)))
    s = per[lv]
    if not t["defects"]:
        s["clean"] += 1
        s["false_flag"] += bool(raised)
    for d in t["defects"]:
        if not d["determinable_from_bill"]:
            s["not_determinable"] += 1
            continue
        s["seeded"] += 1
        hit = d["violation"] in raised
        s["found"] += hit
        per_type[(lv, d["defect"])]["seeded"] += 1
        per_type[(lv, d["defect"])]["found"] += hit
    rows.append({"image": rp.stem, "defects": [d["defect"] for d in t["defects"]], "raised": sorted(raised)})
summary = {lv: {**v, "detection_rate": round(v["found"] / v["seeded"], 3) if v["seeded"] else None,
                "false_flag_rate": round(v["false_flag"] / v["clean"], 3) if v["clean"] else None}
           for lv, v in sorted(per.items())}
types = {f"L{lv} {d}": v for (lv, d), v in sorted(per_type.items())}
out.write_text(json.dumps({"summary": summary, "by_type": types, "rows": rows}, indent=1))
print(json.dumps(summary, indent=1))
