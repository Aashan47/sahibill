"""Synthetic A-1 bills: a correct bill first, then seeded defects, with ground truth.

This module computes bills independently of the rules engine, so a bug in one cannot hide in the
other. Where the tariff notes need interpretation, the reading used here is stated in a comment and
the rules engine's test cases decide it.
"""
from __future__ import annotations

import calendar
import math
import random
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

from sahibill import tariff as T

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Defect type -> violation code it should produce (vocabulary of research-raw/LABEL-PROTOCOL.md, plus
# tariff_arithmetic_error for the synthetic set only).
DEFECTS = {
    "long_period_not_prorated": "slab_not_prorated_long_period",
    "snapshot_mismatch": "snapshot_missing_or_mismatch",
    "snapshot_missing": "snapshot_missing_or_mismatch",
    "protected_wrongly_removed": "protected_status_wrongly_removed",
    "detection_formula_exceeded": "detection_units_formula_error",
    "detection_months_exceeded": "detection_load_or_period_exceeds_limits",
    "detection_vs_history": "detection_not_justified_by_history",
    "average_too_long": "average_billing_beyond_limit",
    "retrieval_late": "retrieval_charge_beyond_time_limit",
    "skipped_beyond_limit": "skipped_charges_beyond_recovery_limit",
    "accumulated_units": "accumulated_units_charged_at_once",
    "due_date_too_short": "due_date_too_short",
    "arithmetic_error": "tariff_arithmetic_error",
}


def month_key(y: int, m: int) -> str:
    return f"{y:04d}-{m:02d}"


def add_months(y: int, m: int, k: int) -> tuple[int, int]:
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


@dataclass
class Supplementary:
    kind: str              # detection | retrieval | skipped_mf
    units: int
    amount: float
    months: int | None = None
    period_from: str | None = None
    period_to: str | None = None
    load_kw: float | None = None
    event_date: str | None = None   # meter change date (retrieval) or date charge raised (skipped)
    note: str = ""


@dataclass
class Bill:
    bill_id: str
    layout: str
    billing_month: str
    consumer: str
    address: str
    reference_no: str
    tariff: str
    phase: int
    sanctioned_load_kw: float
    meter_no: str
    connection_date: str
    reading_date: str
    prev_reading_date: str | None     # printed only on some layouts (CSM 6.4.1 does not require it)
    issue_date: str
    due_date: str
    prev_reading: int
    present_reading: int
    units: int
    carried_forward: int
    snapshot_reading: int | None
    snapshot_stamp: str | None
    status: str                        # lifeline | protected | unprotected (as printed)
    history: list = field(default_factory=list)  # [{"month": "Sep-26", "units": int, "mode": "", "bill": float}]
    variable: float = 0.0
    rate: float = 0.0
    fixed: float = 0.0
    min_charge: float = 0.0
    fca: float = 0.0
    fca_basis: str = ""
    qta: float = 0.0
    gst: float = 0.0                   # assumed 18%, UNVERIFIED rate; printed, never checked
    supplementary: list = field(default_factory=list)
    arrears: float = 0.0
    payable_within: float = 0.0
    lps: float = 0.0
    payable_after: float = 0.0


def classify(phase, load, history_units, current_units):
    """Lifeline, protected or unprotected, from the printed history (most recent first)."""
    last12 = history_units[:12]
    if phase == 1 and load <= T.LIFELINE_MAX_LOAD_KW and max(last12 + [current_units]) <= T.LIFELINE_LIMIT:
        return "lifeline"
    # Reading used: protected needs the past 6 months at or under 200, and the current month too
    # (CSM 6.1.1.1 example: protected status "will remain intact" only while the month stays under 200).
    if max(history_units[: T.PROTECTED_MONTHS]) <= T.PROTECTED_LIMIT and current_units <= T.PROTECTED_LIMIT:
        return "protected"
    return "unprotected"


def energy_charge(status, units, load):
    """(variable Rs, headline rate, fixed Rs, minimum charge Rs)."""
    if status == "lifeline":
        # "residential life line consumer will not be given any slab benefit"
        _, (_, _, rate) = T.slab_row(T.LIFELINE, units)
        return round(units * rate, 2), rate, 0.0, None
    if status == "protected":
        # "only protected residential consumers will be given the benefit of one previous slab"
        i, (_, fx, rate) = T.slab_row(T.PROTECTED, units)
        if i == 0:
            var = units * rate
        else:
            var = 100 * T.PROTECTED[0][2] + (units - 100) * rate
        return round(var, 2), rate, round(fx * load, 2), None
    _, (_, fx, rate) = T.slab_row(T.UNPROTECTED, units)
    return round(units * rate, 2), rate, round(fx * load, 2), None


def _history(rng, y, m, base, n=12):
    """Units for the n months before (y, m), most recent first, with a summer peak."""
    out = []
    for k in range(1, n + 1):
        hy, hm = add_months(y, m, -k)
        season = 1.0 + 0.9 * max(0.0, math.sin((hm - 3) / 12 * 2 * math.pi))
        u = max(5, int(rng.gauss(base * season, base * 0.08)))
        out.append({"month": f"{MONTHS[hm - 1]}-{str(hy)[2:]}", "key": month_key(hy, hm), "units": u, "mode": ""})
    return out


def _cross_slab(status, measured, billed, load):
    """True when billing the raw total lands on a different rate than billing the prorated units."""
    return energy_charge(status, measured, load)[1] != energy_charge(status, billed, load)[1]


def make_bill(seed: int, bill_id: str, defects: list[str], billing_month: str = "2026-10") -> tuple[Bill, dict]:
    """Build a bill in a fixed order so every printed number agrees with every other:
    history and history-changing defects, then category and charges from the final history, then billing
    defects, then the month-based adjustments. Defects that would change nothing are dropped."""
    rng = random.Random(seed)
    y, m = map(int, billing_month.split("-"))
    dim = calendar.monthrange(y, m)[1]
    defects = list(defects)
    dropped = []
    phase = 1 if rng.random() < 0.85 else 3
    load = rng.choice([1, 1, 2, 2, 3, 4]) if phase == 1 else rng.choice([4, 5])
    profile = rng.choices(["lifeline", "protected", "unprotected"], [0.2, 0.4, 0.4])[0]
    if "protected_wrongly_removed" in defects:
        profile = "protected"
    if "long_period_not_prorated" in defects and profile == "lifeline":
        profile = "unprotected"
    if profile == "lifeline":
        phase, load = 1, 1
    base = {"lifeline": 45, "protected": 110, "unprotected": rng.choice([180, 260, 380, 520])}[profile]

    # 1. History and the defects that change it.
    hist = _history(rng, y, m, base)
    if profile == "lifeline":
        for h in hist:
            h["units"] = min(h["units"], 95)
    if profile == "protected":
        for h in hist[:6]:
            h["units"] = min(h["units"], 195)
    supp: list[Supplementary] = []
    lf = T.LOAD_FACTOR[phase]
    det = [d for d in defects if d.startswith("detection")]
    if det:
        months = rng.randint(4, 6) if "detection_months_exceeded" in defects else rng.randint(2, 3)
        # Detection period ends 7 months back; the months after it (future consumption, CSM 9.2.3(b)(ii))
        # are printed in the 12-month history, so the history test can be run from the bill.
        period_idx = list(range(6, 6 + months))                 # hist index 6 = 7 months back
        future_idx = list(range(5, 5 - months, -1))[:months]    # the months right after the period
        if "detection_vs_history" in defects:
            for fi, pi in zip(future_idx, period_idx):          # no shortfall: future not above the period
                hist[fi]["units"] = max(5, int(hist[pi]["units"] * 0.95))
        else:
            for pi in period_idx:                               # theft story: a dip in the period
                hist[pi]["units"] = max(5, int(hist[pi]["units"] * 0.45))
        cap = load * lf * T.HOURS_PER_MONTH * months
        units_d = int(cap * (rng.uniform(1.3, 2.5) if "detection_formula_exceeded" in defects else rng.uniform(0.55, 0.95)))
        pf, pt = hist[period_idx[-1]]["key"], hist[period_idx[0]]["key"]
        approval = "no CEO approval on record" if months > 3 else ""
        supp.append(Supplementary("detection", units_d, 0.0, months, pf, pt, float(load),
                                  note="reason: meter tampering (illegal abstraction)" + (f"; {approval}" if approval else "")))
    if "average_too_long" in defects:
        for h in hist[: rng.randint(3, 4)]:
            h["mode"] = "AVG"
    acc_k = 0
    if "accumulated_units" in defects:
        acc_k = rng.randint(2, 4)
        for h in hist[:acc_k]:
            h["units"], h["mode"] = 0, "NR"

    # 2. This month's reading.
    reading = date(y, m, rng.randint(8, 14))
    days = rng.randint(dim - 3, dim)
    if "long_period_not_prorated" in defects:
        days = dim + rng.randint(3, 7)
    prev_date = reading - timedelta(days=days)
    daily = base * (1.0 + 0.9 * max(0.0, math.sin((m - 3) / 12 * 2 * math.pi))) / 30
    measured = max(5, int(rng.gauss(daily * days, daily * days * 0.06)))
    if profile == "lifeline":
        measured = min(measured, 95)
    if profile == "protected":
        measured = min(measured, 190)
    if acc_k:
        measured += int(base) * acc_k
    if days > dim:
        billed = round(measured * dim / days)
        carried = measured - billed
    else:
        billed, carried = measured, 0
    hist_units = [h["units"] for h in hist]
    status = classify(phase, load, hist_units, billed)

    # 3. Billing defects.
    if "long_period_not_prorated" in defects:
        if _cross_slab(classify(phase, load, hist_units, measured), measured, billed, load) or \
                classify(phase, load, hist_units, measured) != status:
            billed, carried = measured, 0
            status = classify(phase, load, hist_units, billed)
        else:
            defects.remove("long_period_not_prorated")
            dropped.append("long_period_not_prorated (no slab change)")
    if "protected_wrongly_removed" in defects:
        if status == "protected":
            status = "unprotected"
        else:
            defects.remove("protected_wrongly_removed")
            dropped.append("protected_wrongly_removed (household not protected)")
    variable, rate, fixed, _ = energy_charge(status, billed, load)
    min_charge = float(T.MIN_CHARGE[phase]) if status == "lifeline" else 0.0
    if "arithmetic_error" in defects:
        variable = round(variable * rng.choice([1.08, 1.12, 1.2]), 2)

    # 4. Month-based adjustments, from the final printed history.
    fca_ref, fca_rate = T.FCA_BY_BILLING_MONTH.get(billing_month, (None, 0.0))
    fca_units = next((h["units"] for h in hist if h["key"] == fca_ref), 0)
    fca = 0.0 if status == "lifeline" else round(fca_units * fca_rate, 2)
    qta = 0.0 if status == "lifeline" else round(billed * T.QTA_BY_BILLING_MONTH.get(billing_month, 0.0), 2)

    # 5. Remaining supplementary lines.
    for s_ in supp:
        s_.amount = round(s_.units * rate, 2)
    if "retrieval_late" in defects:
        lag = rng.randint(7, 11)
        ry, rm = add_months(y, m, -lag)
        replaced = f"{ry:04d}-{rm:02d}-{rng.randint(1, 28):02d}"
        ty, tm = add_months(ry, rm, rng.randint(4, 6))
        retrieved = f"{ty:04d}-{tm:02d}-{rng.randint(1, 28):02d}"
        u = rng.randint(150, 900)
        supp.append(Supplementary("retrieval", u, round(u * rate, 2), event_date=replaced,
                                  note=f"display wash meter replaced; data retrieved in-house on {retrieved}"))
    if "skipped_beyond_limit" in defects:
        months = rng.randint(7, 24)
        u = rng.randint(80, 400) * months
        supp.append(Supplementary("skipped_mf", u, round(u * rate, 2), months, note="multiplying factor difference"))
    present = None
    prev_reading = rng.randint(1000, 98000)
    present = prev_reading + measured
    snap, stamp = present, f"{reading.isoformat()} 10:{rng.randint(10, 59)}"
    if "snapshot_mismatch" in defects:
        snap = present - rng.randint(15, 400)
    if "snapshot_missing" in defects:
        if rng.random() < 0.5:
            snap = None
        stamp = None
    issue = reading + timedelta(days=rng.randint(2, 4))
    due = issue + timedelta(days=rng.randint(9, 14))
    if "due_date_too_short" in defects:
        due = issue + timedelta(days=rng.randint(2, 5))
    for h in hist:
        h["bill"] = round(h["units"] * rate + fixed, 0)
    supp_total = sum(s_.amount for s_ in supp)
    base_amt = variable + fixed + min_charge + fca + qta + supp_total
    gst = round(base_amt * 0.18, 2)
    within = round(base_amt + gst, 0)
    lps = round(0.10 * base_amt, 0)
    show_prev_date = rng.random() < 0.6
    truth_defects = []
    b = Bill(
        bill_id=bill_id, layout=rng.choice(["A", "B"]), billing_month=billing_month,
        consumer=f"SAMPLE CONSUMER {rng.randint(10, 99)}", address=f"House {rng.randint(1, 9)}, Example Street, Sample Town",
        reference_no=f"SYN {rng.randint(10, 99)} {rng.randint(10000, 99999)} {rng.randint(1000000, 9999999)}",
        tariff="A-1(a)" if load < 5 else "A-1(b)", phase=phase, sanctioned_load_kw=float(load),
        meter_no=f"SM{rng.randint(100000, 999999)}", connection_date=f"20{rng.randint(5, 22):02d}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}",
        reading_date=reading.isoformat(), prev_reading_date=prev_date.isoformat() if show_prev_date else None,
        issue_date=issue.isoformat(), due_date=due.isoformat(), prev_reading=prev_reading, present_reading=present,
        units=billed, carried_forward=carried, snapshot_reading=snap, snapshot_stamp=stamp, status=status,
        history=[{k: h[k] for k in ("month", "units", "mode", "bill")} for h in hist],
        variable=variable, rate=rate, fixed=fixed, min_charge=min_charge, fca=fca,
        fca_basis=f"{fca_units} units of {fca_ref} x {fca_rate}" if fca else "", qta=qta, gst=gst,
        supplementary=[asdict(s_) for s_ in supp], payable_within=within, lps=lps, payable_after=within + lps,
    )
    for d in defects:
        determinable = not (d == "long_period_not_prorated" and not show_prev_date)
        truth_defects.append({"defect": d, "violation": DEFECTS[d], "determinable_from_bill": determinable})
    truth = {"bill_id": bill_id, "seed": seed, "synthetic": True, "defects": truth_defects, "dropped": dropped,
             "measured_units": measured, "reading_days": days, "days_in_month": dim, "printed": asdict(b)}
    return b, truth
