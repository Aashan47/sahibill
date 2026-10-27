"""Domestic (A-1) tariff values in force in October 2026, each with its source.

Sources (saved copies and verbatim quotes in the project research notes):
- Slab table and fixed charges: NEPRA decision of 11-02-2026, Annex-C "GoP Applicable Schedule of
  Tariff", notified by S.R.O. 279(I)/2026.
- Lifeline and protected definitions, billing period, minimum charge: NEPRA CY2026 determinations
  (LESCO, IESCO), Annex-V Terms and Conditions; Annex-A-1 notes.
- FCA: NEPRA decision of 07-10-2026 (FCA for August 2026, billed in October 2026).
- QTA: S.R.O. 1501(I)/2026 of 07-09-2026 (September to November 2026).
"""
from __future__ import annotations

import math

# (upper bound in units, fixed charge Rs/kW/month, variable Rs/kWh)
UNPROTECTED = [
    (100, 275, 22.44), (200, 300, 28.91), (300, 350, 33.10), (400, 400, 36.46),
    (500, 500, 38.95), (600, 675, 40.22), (700, 675, 41.85), (math.inf, 675, 47.20),
]
PROTECTED = [(100, 200, 10.54), (200, 300, 13.01)]
LIFELINE = [(50, 0, 3.95), (100, 0, 7.74)]

PROTECTED_LIMIT = 200      # "consuming <= 200 kWh per month consistently for the past 6 months"
PROTECTED_MONTHS = 6
LIFELINE_LIMIT = 100       # "maximum of last twelve months and current month's consumption <= 100 units"
LIFELINE_MAX_LOAD_KW = 1.0 # "single phase electric connection with a sanctioned load up to 1 kW"
MIN_CHARGE = {1: 75, 3: 150}  # Rs per month where fixed charges do not apply (read from a poor scan)

# FCA is billed two months later, on the units of the reference month.
FCA_BY_BILLING_MONTH = {"2026-10": ("2026-08", 1.1086)}
# The same rates keyed by the reference month (the month whose units carry the FCA). Only rates read from a
# NEPRA decision go here.
# Read from each decision's Gazette notification page (research-raw/FCA-2026-RATES.md); Feb, May, Jun and Jul also
# match the rates printed on real IESCO bills. Billed two months after the reference month; lifeline exempt.
FCA_BY_REFERENCE_MONTH = {
    "2026-02": 1.4235,    # S.R.O. 629(I)/2026, 08-04-2026
    "2026-03": -0.0102,   # S.R.O. 801(I)/2026, 05-05-2026 (decrease)
    "2026-04": 1.1907,    # S.R.O. 919(I)/2026, 04-06-2026
    "2026-05": 0.3364,    # decision 08-07-2026
    "2026-06": 0.7503,    # decision 07-08-2026
    "2026-07": 2.0581,    # decision 04-09-2026
    **{ref: rate for ref, rate in FCA_BY_BILLING_MONTH.values()},   # 2026-08: 1.1086, decision 07-10-2026
}
# QTA: "billed in a period of 03 months i.e. September to November 2026, at a uniform rate of Rs.0.5194/kWh"
QTA_BY_BILLING_MONTH = {
    "2026-03": 0.3504, "2026-04": 0.3504, "2026-05": 0.3504,      # S.R.O. 459(I)/2026, 06-03-2026 (matches his Apr and May bills)
    "2026-06": -1.9857, "2026-07": -1.9857, "2026-08": -1.9857,   # S.R.O. 953(I)/2026, 08-06-2026 (a credit)
    "2026-09": 0.5194, "2026-10": 0.5194, "2026-11": 0.5194,      # S.R.O. 1501(I)/2026, 07-09-2026
}   # all three: every category except lifeline, incremental-package units and prepaid (research-raw/FCA-2026-RATES.md)

# CSM 2025 Annexure V: "A-1 ... Single Phase 20% ... Three Phase 25%"
LOAD_FACTOR = {1: 0.20, 3: 0.25}
HOURS_PER_MONTH = 730          # CSM 9.1.3: "730 = Average number of hours in a month"
DETECTION_MAX_MONTHS_A1 = 3    # CSM 9.2.3(c)(i): three billing cycles, up to six with CEO approval
AVERAGE_MAX_MONTHS = 2         # CSM 4.3.1(b): "for a maximum period of two months"
RETRIEVAL_LIMIT_MONTHS = 3     # CSM 4.3.2(d): three months of meter replacement (six via manufacturer)
SKIPPED_RAISE_WITHIN_MONTHS = 12   # CSM 7.5.5: "within one year"
SKIPPED_MAX_MONTHS = 6             # CSM 7.5.5: "for maximum period of 06 months"
DUE_DATE_MAX_DAYS = 15         # CSM 6.4: "within fifteen (15) days from the issue date"


def slab_row(table, units):
    for i, row in enumerate(table):
        if units <= row[0]:
            return i, row
    return len(table) - 1, table[-1]
