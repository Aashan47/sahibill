"""Shared types and helpers for the rules engine.

Every check returns Findings. A Finding has exactly one status: problem_found, looks_right or
cannot_be_determined; cannot_be_determined always names what is missing. No model decides anything
here: numbers come from the bill and the written rules only.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

PROBLEM = "problem_found"
OK = "looks_right"
CBD = "cannot_be_determined"


@dataclass
class Finding:
    check: str                 # e.g. "1", "4A", "10B"
    status: str
    violation: str | None = None   # LABEL-PROTOCOL vocabulary when status is problem_found
    clause: str = ""
    numbers: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)
    note: str = ""

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v not in (None, "", [], {})}


@dataclass
class BillFacts:
    """What a bill (plus any supplementary or detection bill) states. Every field is optional."""
    billing_month: str | None = None          # "YYYY-MM"
    tou: bool = False
    phase: int | None = None
    sanctioned_load_kw: float | None = None
    connected_load_kw: float | None = None
    mdi_kw: float | None = None
    reading_date: str | None = None
    prev_reading_date: str | None = None
    issue_date: str | None = None
    due_date: str | None = None
    delivery_date: str | None = None
    holidays: set | None = None               # None = no calendar available
    units: int | None = None
    peak_units: int | None = None
    offpeak_units: int | None = None
    carry_forward_shown: bool | None = None
    # the bill states its present reading is pro-rata, not the recorded one (CSM 6.1.1.1), and the units carried forward
    pro_rata_reading: bool | None = None
    carried_forward_units: int | None = None
    # snapshot: per register name ("total", "peak", "offpeak") -> reading; None = unreadable
    snapshot_present: bool | None = None
    snapshot: dict | None = None
    present_reading: dict | None = None
    mf: float | None = None
    snapshot_stamp_date: str | None = None
    snapshot_stamp_present: bool | None = None   # False = the snapshot shows no time stamp
    snapshot_geotag: bool | None = None
    mco: bool = False
    mco_final_snapshot_present: bool | None = None
    # history: most recent first; each {"month": "YYYY-MM", "units": int|None, "mode": str}
    history: list | None = None
    status_billed: str | None = None          # lifeline | protected | unprotected | tou
    rate_billed: float | None = None          # headline Rs/kWh applied to the month
    variable_billed: float | None = None
    fixed_billed: float | None = None
    fpa_billed: float | None = None
    # the bill's own FPA note: the month whose units it is charged on, those units, and the rate per unit
    fpa_ref_month: str | None = None
    fpa_ref_units: int | None = None
    fpa_rate: float | None = None
    qta_billed: float | None = None
    detection: dict | None = None
    average: dict | None = None
    retrieval: dict | None = None
    skipped: dict | None = None
    accumulated: dict | None = None
    # False when an absence (no meter photo, no stamp) comes only from reading a photo: it is then asked, not alleged
    absence_confirmed: bool = True


def round_half_up(x: float, places: int = 0) -> float:
    q = Decimal(1).scaleb(-places)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def money(x: float) -> float:
    return round_half_up(x, 2)


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


def days_in_month(ym: str) -> int:
    y, m = map(int, ym.split("-")[:2])
    return calendar.monthrange(y, m)[1]


def month_index(s: str) -> int:
    y, m = map(int, s.split("-")[:2])
    return y * 12 + m - 1


def add_months(d: date, k: int) -> date:
    t = d.year * 12 + d.month - 1 + k
    y, m = t // 12, t % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def is_month_only(s: str) -> bool:
    return len(s) == 7


def worst(statuses) -> str:
    statuses = list(statuses)
    if PROBLEM in statuses:
        return PROBLEM
    if CBD in statuses:
        return CBD
    return OK
