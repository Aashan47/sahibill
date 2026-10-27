"""Export the tariff tables and worked examples for the browser's 200-unit cliff scene.

python scripts/export_tariff.py   ->  frontend/src/cliff/tariff.json
The browser recomputes the same numbers; frontend/src/cliff/model.test.ts checks it against these examples,
which come from the rules engine itself (expected_variable, round_half_up).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from sahibill import tariff as T
from sahibill.rules.consumption import expected_variable
from sahibill.rules.core import round_half_up


def rows(table):
    return [{"upto": None if math.isinf(u) else u, "fixed_per_kw": f, "rate": r} for u, f, r in table]


examples = [{"status": s, "units": u, "energy": expected_variable(s, u)}
            for s, us in (("protected", (1, 99, 100, 101, 180, 200)), ("unprotected", (150, 200, 201, 204, 240, 300, 301)))
            for u in us]
prorata = [{"units": u, "days": d, "month_days": m, "billed": int(round_half_up(u * m / d))}
           for u, d, m in ((204, 34, 30), (240, 40, 30), (186, 31, 31), (208, 33, 30), (54, 33, 30), (199, 35, 31))]
out = {"source": "sahibill/tariff.py (NEPRA decision of 11-02-2026, S.R.O. 279(I)/2026)",
       "protected_limit": T.PROTECTED_LIMIT, "protected_months": T.PROTECTED_MONTHS,
       "protected": rows(T.PROTECTED), "unprotected": rows(T.UNPROTECTED),
       "examples": examples, "prorata_examples": prorata}
Path("frontend/src/cliff/tariff.json").write_text(json.dumps(out, indent=1))
print(len(examples), "energy examples,", len(prorata), "pro-rata examples")
