"""E4a counted after the test (post hoc; the pre-registered result in E4A.md stays the result of record).

The pre-registered rule counts a match only on violations in a fixed list of codes the engine "can raise".
That list left out detection_procedure_not_followed, which the engine does raise (sahibill/rules/charges.py,
CSM detection procedure), and it holds two codes for one clause (CSM 6.4.2). This recount, from the same
per-decision rows and no new run, asks the household's question: did SahiBill flag at least one violation
NEPRA also found, did it say cannot tell yet, or did it only raise something NEPRA did not find?

    python eval/e4a_posthoc.py results/e4a.json results/e4a-posthoc.json
"""
import json
import sys
from pathlib import Path

SAME_CLAUSE = {"accumulated_units_charged_at_once": "slab_not_prorated_long_period"}


def norm(codes):
    return {SAME_CLAUSE.get(c, c) for c in codes}


src, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = json.loads(src.read_text())["rows"]
result = {}
for name, keep in (("all", lambda r: True), ("strict", lambda r: not r["leaky"])):
    scored = [r for r in rows if r["set"] == "scored" and keep(r)]
    caught = [r for r in scored if norm(r["engine"]) & norm(r["nepra"])]
    silent = [r for r in scored if not r["engine"]]
    only_other = [r for r in scored if r["engine"] and not norm(r["engine"]) & norm(r["nepra"])]
    extra = [r for r in scored if norm(r["engine"]) - norm(r["nepra"])]
    result[name] = {"decisions": len(scored), "flagged_a_violation_nepra_found": len(caught),
                    "rate": round(len(caught) / len(scored), 3), "cannot_tell_yet": len(silent),
                    "raised_only_violations_nepra_did_not_find": [r["stem"] for r in only_other],
                    "also_raised_a_violation_nepra_did_not_find": [r["stem"] for r in extra]}
spec = [r for r in rows if r["set"] == "specificity"]
result["no_violation_decisions"] = {"decisions": len(spec), "false_alarms": sum(r["false_alarm"] for r in spec)}
out.write_text(json.dumps(result, indent=1))
print(json.dumps(result, indent=1))
