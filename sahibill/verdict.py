"""Turn findings into the verdict the user reads: a headline and one line per check, in English and Urdu.

Every sentence is assembled by code from the finding's own numbers; no model writes or edits a number here.
"""
from __future__ import annotations

from sahibill.rules.core import CBD, OK, PROBLEM, Finding

TITLES = {
    "1": ("Billing period", "بلنگ کی مدت"),
    "2": ("Meter reading snapshot", "میٹر ریڈنگ کی تصویر"),
    "3": ("Your category (lifeline, protected)", "آپ کا زمرہ (لائف لائن، محفوظ)"),
    "4A": ("Detection bill units", "ڈیٹیکشن بل کے یونٹس"),
    "4B": ("Detection bill months", "ڈیٹیکشن بل کے مہینے"),
    "4C": ("Detection bill against your history", "ڈیٹیکشن بل اور آپ کی کھپت"),
    "5": ("Average billing", "اوسط بلنگ"),
    "6": ("Retrieved meter units", "پرانے میٹر سے نکالے گئے یونٹس"),
    "7": ("Back-charges", "پچھلے چارجز"),
    "8": ("Several months in one bill", "کئی مہینوں کے یونٹس ایک بل میں"),
    "9": ("Charges arithmetic", "چارجز کا حساب"),
    "10A": ("Due date", "آخری تاریخ"),
    "10B": ("Time to pay", "ادائیگی کا وقت"),
}

STATUS_WORDS = {PROBLEM: ("Problem found", "مسئلہ ملا"), OK: ("Looks right", "درست لگتا ہے"),
                CBD: ("Cannot be determined", "طے نہیں ہو سکا")}


def _fmt(x):
    if isinstance(x, float):
        return f"{x:,.2f}".rstrip("0").rstrip(".") if abs(x) < 1e6 else f"{x:,.0f}"
    if isinstance(x, int):
        return f"{x:,}"
    return str(x)


FPA_NOTE = {   # (matches, does not match)
    "fpa_month": ("The fuel adjustment is charged on {e} units, two months back, as it should be.",
                  "The fuel adjustment should be charged on the units of {e}; the bill uses {b}."),
    "fpa_units": ("The fuel adjustment uses {e} units, the same as that month in your history.",
                  "The fuel adjustment should be on {e} units (that month in your history); the bill uses {b}."),
    "fpa_rate": ("The fuel adjustment rate, Rs {e} per unit, is NEPRA's rate for that month.",
                 "NEPRA's fuel adjustment rate for that month is Rs {e} per unit; the bill uses Rs {b}."),
}
FPA_NOTE_UR = {
    "fpa_month": ("فیول ایڈجسٹمنٹ دو ماہ پہلے ({e}) کے یونٹس پر لگی ہے، جیسا کہ ہونا چاہیے۔",
                  "فیول ایڈجسٹمنٹ {e} کے یونٹس پر لگنی چاہیے؛ بل میں {b} استعمال ہوا ہے۔"),
    "fpa_units": ("فیول ایڈجسٹمنٹ {e} یونٹس پر ہے، جو آپ کی ہسٹری میں اسی مہینے کے یونٹس ہیں۔",
                  "فیول ایڈجسٹمنٹ {e} یونٹس پر ہونی چاہیے؛ بل میں {b} یونٹس ہیں۔"),
    "fpa_rate": ("فیول ایڈجسٹمنٹ کا ریٹ {e} روپے فی یونٹ نیپرا کے فیصلے کے مطابق ہے۔",
                 "اس مہینے کا نیپرا ریٹ {e} روپے فی یونٹ ہے؛ بل میں {b} روپے ہے۔"),
}
LINE_NAMES = {"variable": "energy", "fixed": "fixed", "fpa": "fuel adjustment (FCA)", "qta": "quarterly adjustment (QTA)"}


def explain(f: Finding) -> str:
    """One plain English sentence for a finding, from its numbers."""
    n = f.numbers
    if f.status == CBD:
        return "Needs: " + "; ".join(f.missing) + "."
    if f.check == "1" and f.status == PROBLEM:
        return (f"The reading covered {n['period_days']} days in a {n['days_in_month']}-day month. Prorated, "
                f"{_fmt(n['prorated_units'])} units fall in this month (rate Rs {n['expected_rate']}), with "
                f"{_fmt(n['carry_forward'])} carried forward; the bill charged Rs {n['billed_rate']} per unit.")
    if f.check == "1":
        return f"{n.get('period_days', '?')} days between readings: within the rule."
    if f.check == "2" and f.status == PROBLEM:
        if "snapshot" in n:
            ex = n.get("excess_units")
            ex_s = f" ({_fmt(ex)} units)" if isinstance(ex, (int, float)) else ""
            return f"The snapshot shows {_fmt(n['snapshot'])} but the bill charges up to {_fmt(n['billed'])}{ex_s}."
        return f.note or "The meter-reading snapshot is missing."
    if f.check == "2":
        return "The snapshot matches the billed reading."
    if f.check == "3" and f.status == PROBLEM:
        return f"Your history qualifies for {n['expected_status']} rates; the bill used {n['billed_status']}."
    if f.check == "3":
        return f"Category {n.get('status', n.get('expected_status', ''))} matches your history."
    if f.check == "4A" and f.status == PROBLEM:
        if "excess_units" in n:
            return (f"The manual's formula allows at most {_fmt(n['max_units'])} units "
                    f"({_fmt(n['load_kw'])} kW x {n['load_factor']} x 730 x {n['months']} months); "
                    f"the bill charges {_fmt(n['billed_units'])}.")
        if "excess_over_25pct" in n:
            return f"Even at the higher load factor the limit is {_fmt(n['bound_25pct'])} units; the bill charges {_fmt(n['billed_units'])}."
        return f.note
    if f.check == "4A":
        return "Detection units are within the manual's formula."
    if f.check == "4B" and f.status == PROBLEM:
        return f.note or f"{n.get('months')} months charged; the limit is {n.get('base_limit', n.get('limit'))}."
    if f.check == "4B":
        return f"{n.get('months')} months charged: within the limit."
    if f.check == "4C" and f.status == PROBLEM:
        return "Your consumption in the detection months was not lower than in the months compared, so the history does not support a loss."
    if f.check == "4C":
        return "Your history shows lower consumption in the detection months."
    if f.check == "5" and f.status == PROBLEM:
        if "consecutive_average_months" in n:
            return f"Billed on average for {n['consecutive_average_months']} months in a row; the limit is 2."
        return (f"The rule value is {_fmt(n['rule_value'])} units ({n['basis']} of same month last year and the "
                f"11-month average); the bill charges {_fmt(n['billed'])}.")
    if f.check == "6" and f.status == PROBLEM:
        return "Retrieved units were charged after the time the manual allows from the meter's replacement."
    if f.check == "7" and f.status == PROBLEM:
        return f.note or f"{n.get('months_charged')} months of back-charges; the manual allows at most 6."
    if f.check == "8" and f.status == PROBLEM:
        if "difference" in n:
            return (f"{_fmt(n['lump_units'])} units for {n['months']} months were charged as one month. Split by month, "
                    f"energy charges would be Rs {_fmt(n['segregated_variable'])} instead of Rs {_fmt(n['lumped_variable'])}.")
        return f.note or f"{_fmt(n.get('lump_units'))} units for {n.get('months')} months were charged as one month."
    if f.check == "9" and n.get("line") in FPA_NOTE:
        return FPA_NOTE[n["line"]][f.status == PROBLEM].format(e=n["expected"], b=n["billed"])
    if f.check == "9" and f.status == PROBLEM:
        return f"The {LINE_NAMES.get(n['line'], n['line'])} charge should be Rs {_fmt(n['expected'])}; the bill shows Rs {_fmt(n['billed'])}."
    if f.check == "9":
        return f"The {LINE_NAMES.get(n.get('line', ''), n.get('line', ''))} charge matches the tariff."
    if f.check == "10A" and f.status == OK:
        return f"Due {n.get('issue_to_due_days')} days after the issue date: within the 15 days the manual allows."
    if f.check == "10B" and f.status == OK:
        return f"Delivered {n.get('delivery_to_due_days')} days before the due date."
    if f.check in ("10A", "10B") and f.status == PROBLEM:
        return f.note or "The time to pay is shorter than the manual allows."
    return f.note or STATUS_WORDS[f.status][0] + "."


STATUS_UR = {"lifeline": "لائف لائن", "protected": "محفوظ", "unprotected": "غیر محفوظ"}
LINE_NAMES_UR = {"variable": "توانائی", "fixed": "مقررہ", "fpa": "فیول ایڈجسٹمنٹ", "qta": "سہ ماہی ایڈجسٹمنٹ"}


def _ok_ur(f: Finding) -> str:
    """Urdu for a check that ran and looks right, as specific as the English."""
    n = f.numbers
    if f.check == "1":
        return f"ریڈنگز کے درمیان {n.get('period_days', '?')} دن: قاعدے کے اندر۔"
    if f.check == "2":
        if n.get("carried_forward") is not None:
            return (f"بل پرو ریٹا ریڈنگ پر بنا ہے؛ تصویر کی ریڈنگ بل سے ٹھیک اتنی زیادہ ہے جتنے یونٹس "
                    f"({_fmt(n['carried_forward'])}) اگلے بل میں جائیں گے۔")
        return "میٹر کی تصویر بل کی ریڈنگ سے ملتی ہے۔"
    if f.check == "3":
        return "آپ کا زمرہ آپ کی کھپت کی ہسٹری کے مطابق ہے۔"
    if f.check == "4A":
        return "ڈیٹیکشن یونٹس مینوئل کے فارمولے کے اندر ہیں۔"
    if f.check == "4B":
        return f"{n.get('months')} مہینوں کا بل: حد کے اندر۔"
    if f.check == "4C":
        return "آپ کی ہسٹری میں ڈیٹیکشن کے مہینوں میں کھپت کم دکھائی دیتی ہے۔"
    if f.check == "9" and n.get("line") in FPA_NOTE_UR:
        return FPA_NOTE_UR[n["line"]][0].format(e=n["expected"], b=n["billed"])
    if f.check == "9":
        return f"{LINE_NAMES_UR.get(n.get('line', ''), n.get('line', ''))} چارجز ٹیرف کے مطابق ہیں۔"
    if f.check == "10A":
        return f"آخری تاریخ اجرا کے {n.get('issue_to_due_days')} دن بعد ہے: مینوئل کی 15 دن کی حد کے اندر۔"
    if f.check == "10B":
        return f"بل آخری تاریخ سے {n.get('delivery_to_due_days')} دن پہلے ملا۔"
    return "قاعدے کے مطابق درست لگتا ہے۔"


def explain_ur(f: Finding) -> str:
    """The Urdu sentence for a finding, from the same numbers. Generic only where no specific one exists."""
    n = f.numbers
    if f.status == CBD:
        from sahibill.complaint.requests import route        # the same Urdu the next steps use
        asks = list(dict.fromkeys(route(m).ur for m in f.missing))
        return "ابھی طے نہیں ہو سکا۔ " + " ".join(asks) if asks else "ابھی طے نہیں ہو سکا۔"
    if f.status == OK:
        return _ok_ur(f)
    if f.check == "1":
        return (f"ریڈنگ {n['period_days']} دن کی ہے جبکہ مہینہ {n['days_in_month']} دن کا ہے۔ تناسب سے اس مہینے کے "
                f"{_fmt(n['prorated_units'])} یونٹس بنتے ہیں (ریٹ {n['expected_rate']} روپے) اور {_fmt(n['carry_forward'])} "
                f"یونٹس اگلے مہینے جانے چاہئیں؛ بل میں {n['billed_rate']} روپے فی یونٹ لگایا گیا۔")
    if f.check == "2":
        if "snapshot" in n:
            return f"میٹر کی تصویر میں ریڈنگ {_fmt(n['snapshot'])} ہے مگر بل {_fmt(n['billed'])} تک کا بنایا گیا ہے۔"
        return "میٹر ریڈنگ کی تصویر یا اس کا ٹائم اسٹیمپ بل پر موجود نہیں۔"
    if f.check == "3":
        return (f"آپ کی کھپت کے مطابق آپ {STATUS_UR.get(n['expected_status'], n['expected_status'])} زمرے کے حقدار ہیں مگر بل "
                f"{STATUS_UR.get(n['billed_status'], n['billed_status'])} زمرے کے حساب سے بنایا گیا۔")
    if f.check == "4A":
        if "excess_units" in n:
            return (f"مینوئل کے فارمولے کے مطابق زیادہ سے زیادہ {_fmt(n['max_units'])} یونٹس بنتے ہیں "
                    f"({_fmt(n['load_kw'])} کلو واٹ × {n['load_factor']} × 730 × {n['months']} مہینے)؛ بل میں {_fmt(n['billed_units'])} یونٹس لگائے گئے۔")
        if "excess_over_25pct" in n:
            return f"زیادہ لوڈ فیکٹر پر بھی حد {_fmt(n['bound_25pct'])} یونٹس ہے؛ بل میں {_fmt(n['billed_units'])} یونٹس لگائے گئے۔"
        return "ڈیٹیکشن بل مینوئل کے طریقہ کار کے مطابق نہیں۔"
    if f.check == "4B":
        if f.note:
            return "ڈیٹیکشن بل میں اس کی وجوہات درج نہیں۔" if "reasons" in f.note else "ڈیٹیکشن بل میں اس کی مدت درج نہیں۔"
        return f"{n.get('months')} مہینوں کا ڈیٹیکشن بل لگایا گیا جبکہ حد {n.get('base_limit', n.get('limit'))} مہینے ہے۔"
    if f.check == "4C":
        return "ڈیٹیکشن کے مہینوں میں آپ کی کھپت موازنے کے مہینوں سے کم نہیں تھی، اس لیے کھپت کا ریکارڈ نقصان ثابت نہیں کرتا۔"
    if f.check == "5":
        if "consecutive_average_months" in n:
            return f"مسلسل {n['consecutive_average_months']} مہینے اوسط بل بھیجا گیا جبکہ حد 2 مہینے ہے۔"
        return f"قاعدے کے مطابق {_fmt(n['rule_value'])} یونٹس بنتے ہیں؛ بل میں {_fmt(n['billed'])} لگائے گئے۔"
    if f.check == "6":
        return "پرانے میٹر سے نکالے گئے یونٹس مینوئل کی مقررہ مدت گزرنے کے بعد چارج کیے گئے۔"
    if f.check == "7":
        return f"{n.get('months_charged', '')} مہینوں کے پچھلے چارجز لگائے گئے جبکہ مینوئل زیادہ سے زیادہ 6 مہینوں کی اجازت دیتا ہے۔"
    if f.check == "8":
        if "difference" in n:
            return (f"{n['months']} مہینوں کے {_fmt(n['lump_units'])} یونٹس ایک ہی مہینے میں لگائے گئے۔ ماہ بہ ماہ تقسیم سے توانائی چارجز "
                    f"{_fmt(n['segregated_variable'])} روپے بنتے، {_fmt(n['lumped_variable'])} روپے نہیں۔")
        return "کئی مہینوں کے یونٹس ایک ہی بل میں لگائے گئے۔"
    if f.check == "9" and n.get("line") in FPA_NOTE_UR:
        return FPA_NOTE_UR[n["line"]][f.status == PROBLEM].format(e=n["expected"], b=n["billed"])
    if f.check == "9":
        return f"{LINE_NAMES_UR.get(n['line'], n['line'])} چارجز {_fmt(n['expected'])} روپے ہونے چاہئیں؛ بل میں {_fmt(n['billed'])} روپے ہیں۔"
    if f.check in ("10A", "10B"):
        return "ادائیگی کے لیے دیا گیا وقت مینوئل کی اجازت سے کم ہے۔"
    return "مسئلہ ملا۔"


def verdict(findings: list[Finding]) -> dict:
    by_check: dict[str, list[Finding]] = {}
    for f in findings:
        by_check.setdefault(f.check, []).append(f)
    cards = []
    for check, fs in by_check.items():
        status = PROBLEM if any(x.status == PROBLEM for x in fs) else (CBD if any(x.status == CBD for x in fs) else OK)
        shown = [x for x in fs if x.status == status]
        cards.append({"check": check, "title": TITLES.get(check, (check, check))[0], "title_ur": TITLES.get(check, (check, check))[1],
                      "status": status, "status_text": STATUS_WORDS[status][0], "status_ur": STATUS_WORDS[status][1],
                      "lines": [explain(x) for x in shown], "lines_ur": [explain_ur(x) for x in shown], "clauses": sorted({x.clause for x in shown if x.clause}),
                      "violations": sorted({x.violation for x in shown if x.violation})})
    order = {PROBLEM: 0, CBD: 1, OK: 2}
    cards.sort(key=lambda c: (order[c["status"]], c["check"]))
    p = sum(c["status"] == PROBLEM for c in cards)
    q = sum(c["status"] == CBD for c in cards)
    ok = sum(c["status"] == OK for c in cards)
    if p:
        head = f"{p} problem{'s' if p != 1 else ''} found on this bill."
        head_ur = f"اس بل میں {p} مسئلہ ملا۔" if p == 1 else f"اس بل میں {p} مسائل ملے۔"
    else:
        head = "No problem found in what this bill shows."
        head_ur = "اس بل میں دکھائی گئی معلومات میں کوئی مسئلہ نہیں ملا۔"
    return {"headline": head, "headline_ur": head_ur, "counts": {"problem": p, "cannot_be_determined": q, "looks_right": ok},
            "cards": cards}
