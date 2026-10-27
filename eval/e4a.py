"""E4a: the rules engine on NEPRA decisions, from facts converted out of the labels (no model reads a page).

Scoring is fixed in PREREGISTRATION.md (amendment of 21 October 2026). Run once on frozen inputs:
python eval/e4a.py --labels <dir> --inputs <dir> --out results/e4a.json
Labels and inputs stay local (NEPRA documents are not redistributed); the output holds stems and codes only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sahibill.rules import BillFacts, PROBLEM, CBD, run_all

ENGINE_VIOLATIONS = {
    "slab_not_prorated_long_period", "snapshot_missing_or_mismatch", "protected_status_wrongly_removed",
    "detection_units_formula_error", "detection_load_or_period_exceeds_limits", "detection_not_justified_by_history",
    "average_billing_beyond_limit", "average_billing_wrong_basis", "retrieval_charge_beyond_time_limit",
    "skipped_charges_beyond_recovery_limit", "accumulated_units_charged_at_once", "due_date_too_short",
}
FIELDS = set(BillFacts.__dataclass_fields__)


def leaky(path: Path) -> bool:
    """True when any filled field's source cites NEPRA's finding or order (pre-registered sensitivity check)."""
    src = json.dumps(json.loads(path.read_text()).get("sources", {}))
    return "nepra_finding" in src or "ordered_correction" in src


def load_facts(path: Path) -> BillFacts:
    raw = json.loads(path.read_text()).get("facts", {}) or {}
    return BillFacts(**{k: v for k, v in raw.items() if k in FIELDS and v is not None})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    scored, specificity, rows = [], [], []
    for lp in sorted(a.labels.glob("*.json")):
        lab = json.loads(lp.read_text())
        stem = lp.stem
        nepra = set((lab.get("nepra_finding") or {}).get("violations", []))
        checkable = bool((lab.get("checkable_from_bill") or {}).get("value"))
        ip = a.inputs / f"{stem}.json"
        if lab.get("issue_categories") == ["other"] or not ip.exists():
            continue
        findings = run_all(load_facts(ip))
        raised = {f.violation for f in findings if f.status == PROBLEM and f.violation}
        cbd = sorted({m for f in findings if f.status == CBD for m in f.missing})
        row = {"stem": stem, "nepra": sorted(nepra), "engine": sorted(raised), "missing": cbd, "leaky": leaky(ip)}
        target = nepra & ENGINE_VIOLATIONS
        if checkable and target:
            row["set"] = "scored"
            row["match"] = bool(raised & target)
            scored.append(row)
        elif nepra == {"none_found"}:
            row["set"] = "specificity"
            row["false_alarm"] = bool(raised)
            specificity.append(row)
        else:
            row["set"] = "not_scored"
        rows.append(row)
    n = len(scored)
    matched = sum(r["match"] for r in scored)
    strict = [r for r in scored if not r["leaky"]]
    sm = sum(r["match"] for r in strict)
    summary = {
        "scored_all": n, "matched_all": matched, "match_rate_all": round(matched / n, 3) if n else None,
        "scored_strict": len(strict), "matched_strict": sm,
        "match_rate_strict": round(sm / len(strict), 3) if strict else None,
        "prediction": "at least 70% matched, judged on the strict set",
        "prediction_met": (sm / len(strict) >= 0.70) if strict else None,
        "unmatched_with_missing_inputs": sum(1 for r in scored if not r["match"] and r["missing"]),
        "specificity_decisions": len(specificity), "false_alarms": sum(r["false_alarm"] for r in specificity),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
