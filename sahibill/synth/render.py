"""Render a synthetic bill to HTML, then to PNG with headless Chromium (proper Urdu shaping).

Every image carries a red SYNTHETIC band. Layouts are our own: they carry the fields CSM 6.4.1
requires, in English and Urdu, and copy no utility's name, logo, colours or layout.
"""
from __future__ import annotations

import html
from pathlib import Path

from sahibill.synth.model import Bill

UR = {
    "billing_month": "بلنگ مہینہ", "consumer": "صارف کا نام", "address": "پتہ", "reference_no": "ریفرنس نمبر",
    "tariff": "ٹیرف", "sanctioned_load_kw": "منظور شدہ لوڈ", "meter_no": "میٹر نمبر", "connection_date": "کنکشن کی تاریخ",
    "reading_date": "ریڈنگ کی تاریخ", "prev_reading_date": "پچھلی ریڈنگ کی تاریخ", "issue_date": "اجرا کی تاریخ",
    "due_date": "آخری تاریخ", "prev_reading": "پچھلی ریڈنگ", "present_reading": "موجودہ ریڈنگ", "units": "کل یونٹس",
    "carried_forward": "آگے منتقل یونٹس", "status": "زمرہ", "variable": "توانائی چارجز", "fixed": "مقررہ چارجز",
    "min_charge": "کم از کم چارجز", "fca": "فیول ایڈجسٹمنٹ", "qta": "سہ ماہی ایڈجسٹمنٹ", "gst": "جی ایس ٹی",
    "payable_within": "مقررہ تاریخ تک قابل ادائیگی", "payable_after": "مقررہ تاریخ کے بعد", "history": "بلنگ کی تاریخ (12 ماہ)",
    "snapshot": "میٹر ریڈنگ کی تصویر", "supplementary": "اضافی چارجز",
}
EN = {
    "billing_month": "Billing Month", "consumer": "Name", "address": "Address", "reference_no": "Reference No.",
    "tariff": "Tariff", "sanctioned_load_kw": "Sanctioned Load (kW)", "meter_no": "Meter No.",
    "connection_date": "Date of Connection", "reading_date": "Reading Date", "prev_reading_date": "Previous Reading Date",
    "issue_date": "Issue Date", "due_date": "Due Date", "prev_reading": "Previous Reading", "present_reading": "Present Reading",
    "units": "Units Billed", "carried_forward": "Units Carried Forward", "status": "Category", "variable": "Energy (variable) Charges",
    "fixed": "Fixed Charges", "min_charge": "Minimum Charges", "fca": "Fuel Charges Adjustment", "qta": "Quarterly Adjustment",
    "gst": "GST", "payable_within": "Payable Within Due Date", "payable_after": "Payable After Due Date",
}

CSS = """
body{margin:0;background:#f4f1ea;font-family:Arial,Helvetica,sans-serif;color:#111}
.bill{width:1100px;padding:28px 34px;background:#fbfaf6}
.syn{background:#c62828;color:#fff;font-weight:700;font-size:26px;padding:8px 14px;letter-spacing:1px}
h1{font-size:28px;margin:14px 0 4px} .sub{font-size:15px;color:#444;margin-bottom:12px}
table{border-collapse:collapse;width:100%} td,th{border:1px solid #777;padding:6px 8px;font-size:17px}
th{background:#e7e2d6;text-align:left}
.ur{font-family:"Noto Nastaliq Urdu","DecoType Nastaleeq Urdu";direction:rtl;font-size:15px;color:#333;line-height:1.9}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.box{border:2px solid #444;padding:10px}
.snap{background:#2b2b2b;padding:18px;width:360px;margin-top:8px}
.lcd{background:#c8d6be;font-family:"Courier New",monospace;font-size:46px;letter-spacing:6px;padding:6px 14px;color:#111}
.stamp{color:#ddd;font-size:14px;margin-top:6px}
.hist td{font-size:15px;padding:4px 6px}
.money td:last-child{text-align:right;font-weight:600}
"""


def _row(key, value):
    if value is None or value == "":
        return ""
    return (f"<tr><td>{EN[key]}<div class='ur'>{UR[key]}</div></td>"
            f"<td><b>{html.escape(str(value))}</b></td></tr>")


def _money(x):
    return f"{x:,.2f}"


def bill_html(b: Bill) -> str:
    ident = "".join(_row(k, getattr(b, k)) for k in
                    ["billing_month", "consumer", "address", "reference_no", "tariff", "sanctioned_load_kw",
                     "meter_no", "connection_date", "status"])
    read = "".join(_row(k, getattr(b, k)) for k in
                   ["reading_date", "prev_reading_date", "issue_date", "due_date", "prev_reading",
                    "present_reading", "units"] + (["carried_forward"] if b.carried_forward else []))
    money_keys = ["variable", "fixed"] + (["min_charge"] if b.min_charge else []) + \
                 (["fca"] if b.fca else []) + (["qta"] if b.qta else []) + ["gst", "payable_within", "payable_after"]
    money = "".join(_row(k, _money(getattr(b, k))) for k in money_keys)
    supp = ""
    if b.supplementary:
        rows = []
        for s in b.supplementary:
            bits = [s["kind"].replace("_", " ").upper(), f"{s['units']} units", f"Rs {_money(s['amount'])}"]
            if s.get("months"):
                bits.append(f"{s['months']} months")
            if s.get("period_from"):
                bits.append(f"period {s['period_from']} to {s['period_to']}")
            if s.get("load_kw"):
                bits.append(f"load {s['load_kw']:g} kW")
            if s.get("event_date"):
                bits.append(("meter changed " if s["kind"] == "retrieval" else "raised ") + s["event_date"])
            if s.get("note"):
                bits.append(s["note"])
            rows.append(f"<tr><td colspan=2>{html.escape(' | '.join(bits))}</td></tr>")
        supp = (f"<h3>Supplementary charges <span class='ur'>{UR['supplementary']}</span></h3>"
                f"<table>{''.join(rows)}</table>")
    hist = "".join(f"<tr><td>{h['month']}</td><td>{h['units']}</td><td>{h['mode']}</td><td>{h['bill']:,.0f}</td></tr>"
                   for h in b.history)
    snap_val = "&nbsp;" * 6 if b.snapshot_reading is None else str(b.snapshot_reading).rjust(6, "0")
    stamp = f"<div class='stamp'>{html.escape(b.snapshot_stamp)}</div>" if b.snapshot_stamp else ""
    snap = (f"<div class='box'><b>Meter Reading Snapshot</b><div class='ur'>{UR['snapshot']}</div>"
            f"<div class='snap'><span class='lcd'>{snap_val}</span>{stamp}</div></div>")
    histbox = (f"<div class='box'><b>Billing History</b><div class='ur'>{UR['history']}</div>"
               f"<table class='hist'><tr><th>Month</th><th>Units</th><th>Mode</th><th>Bill (Rs)</th></tr>{hist}</table></div>")
    head = ("<div class='syn'>SYNTHETIC SAMPLE, NOT A REAL BILL</div>"
            "<h1>Electricity Bill (domestic) <span class='ur'>بجلی کا بل</span></h1>"
            "<div class='sub'>Test document generated for SahiBill. Not issued by any company.</div>")
    if b.layout == "A":
        body = (f"<table>{ident}</table><br><table>{read}</table><br>"
                f"<div class='grid'>{snap}{histbox}</div><br><table class='money'>{money}</table>{supp}")
    else:
        body = (f"<div class='grid'><table>{ident}{read}</table><div>{snap}<br><table class='money'>{money}</table></div></div>"
                f"<br>{histbox}{supp}")
    return f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='bill'>{head}{body}</div></body></html>"


def render_png(bills: list[Bill], out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1170, "height": 900}, device_scale_factor=1)
        for b in bills:
            page.set_content(bill_html(b))
            page.wait_for_timeout(50)
            path = out_dir / f"{b.bill_id}_L0.png"
            page.locator(".bill").screenshot(path=str(path))
            paths.append(path)
        browser.close()
    return paths


def supplementary_text(s: dict) -> str:
    """The line exactly as the bill prints it (shared by the renderer and the oracle test)."""
    bits = [s["kind"].replace("_", " ").upper(), f"{s['units']} units", f"Rs {_money(s['amount'])}"]
    if s.get("months"):
        bits.append(f"{s['months']} months")
    if s.get("period_from"):
        bits.append(f"period {s['period_from']} to {s['period_to']}")
    if s.get("load_kw"):
        bits.append(f"load {s['load_kw']:g} kW")
    if s.get("event_date"):
        bits.append(("meter changed " if s["kind"] == "retrieval" else "raised ") + s["event_date"])
    if s.get("note"):
        bits.append(s["note"])
    return " | ".join(bits)
