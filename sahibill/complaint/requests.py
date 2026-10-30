"""Turn every 'cannot be determined' finding into the right next step, with no model involved.

Each missing input is routed to whoever can supply it:
- utility: a formal request for the record, citing the clause that requires it (goes in the complaint);
- retake: the bill photo did not show it, so the user is asked for a clearer photo;
- user: a fact only the household knows (for example the delivery date);
- limit: SahiBill's own gap (a rate table or a rule the documents leave open); shown to the user,
  never put in the complaint.
"""
from __future__ import annotations

from dataclasses import dataclass

from sahibill.rules.core import CBD, Finding


@dataclass(frozen=True)
class Request:
    audience: str     # utility | retake | user | limit
    en: str
    ur: str
    clause: str = ""


# First match wins. Patterns are substrings of the engine's missing-input messages.
ROUTES: list[tuple[str, Request]] = [
    ("no meter-reading photo is printed", Request("user",
        "We could not see a meter-reading photo on your bill. Please look: is there one? If there is none, tell us and we will check again.",
        "ہمیں آپ کے بل پر میٹر ریڈنگ کی تصویر نظر نہیں آئی۔ براہ کرم دیکھیں: کیا بل پر تصویر موجود ہے؟ اگر نہیں ہے تو ہمیں بتائیں، ہم دوبارہ جانچ کریں گے۔")),
    ("no time stamp is printed", Request("user",
        "We could not see a date and time printed with the meter photo. Please look: is there one? If there is none, tell us and we will check again.",
        "ہمیں میٹر کی تصویر کے ساتھ تاریخ اور وقت نظر نہیں آیا۔ براہ کرم دیکھیں: کیا موجود ہے؟ اگر نہیں ہے تو ہمیں بتائیں، ہم دوبارہ جانچ کریں گے۔")),
    ("one figure on the bill may have been misread", Request("user",
        "One charge does not add up, and it would if one figure we read from your photo is off by a digit. Please check the numbers we read against your bill and correct any that are wrong.",
        "ایک چارج کا حساب پورا نہیں بیٹھتا، اور اگر آپ کی تصویر سے پڑھا گیا کوئی ایک ہندسہ غلط ہو تو بیٹھ جاتا ہے۔ براہ کرم ہمارے پڑھے گئے نمبر اپنے بل سے ملائیں اور جو غلط ہو اسے درست کریں۔")),
    ("read as a date outside this billing period", Request("user",
        "The date printed with your meter photo was read as a date before this billing period began, but the photo shows this month's reading. Please check the date on the bill and correct it below if we misread it.",
        "آپ کی میٹر کی تصویر کے ساتھ چھپی تاریخ اس بلنگ مدت سے پہلے کی پڑھی گئی، جبکہ تصویر میں اسی مہینے کی ریڈنگ ہے۔ براہ کرم بل پر تاریخ دیکھیں اور اگر ہم نے غلط پڑھی ہو تو نیچے درست کریں۔")),
    ("final-reading photo is not printed", Request("user",
        "Your meter was changed, and we could not see the old meter's final-reading photo. Please look: is it printed on the bill?",
        "آپ کا میٹر تبدیل ہوا ہے اور ہمیں پرانے میٹر کی آخری ریڈنگ کی تصویر نظر نہیں آئی۔ براہ کرم دیکھیں: کیا وہ بل پر موجود ہے؟")),
    ("previous reading date", Request("utility",
        "Please state the date of the previous meter reading for this bill, so the billing period can be checked.",
        "براہ کرم اس بل کی پچھلی میٹر ریڈنگ کی تاریخ بتائیں تاکہ بلنگ کی مدت جانچی جا سکے۔",
        "Tariff terms, definition 1 (billing month of 31 days or less)")),
    ("CEO or committee approval", Request("utility",
        "Please provide a copy of the CEO or committee approval for charging the detection bill for more than three billing cycles.",
        "براہ کرم تین بلنگ سائیکل سے زیادہ مدت کے ڈیٹیکشن بل کے لیے سی ای او یا کمیٹی کی منظوری کی نقل فراہم کریں۔",
        "CSM 9.2.3(c)(i)")),
    ("retrieval date", Request("utility",
        "Please provide the meter data retrieval report with the date the data was retrieved.",
        "براہ کرم میٹر ڈیٹا ریٹریول رپورٹ اور ڈیٹا نکالنے کی تاریخ فراہم کریں۔",
        "CSM 4.3.2(c) and (d)")),
    ("sent to the manufacturer", Request("utility",
        "Please state whether the replaced meter was sent to the manufacturer for data retrieval, and when.",
        "براہ کرم بتائیں کہ کیا تبدیل شدہ میٹر ڈیٹا نکالنے کے لیے مینوفیکچرر کو بھیجا گیا، اور کب۔",
        "CSM 4.3.2(d)")),
    ("day of replacement and retrieval", Request("utility",
        "Please state the exact dates of the meter replacement and of the data retrieval.",
        "براہ کرم میٹر کی تبدیلی اور ڈیٹا نکالنے کی صحیح تاریخیں بتائیں۔",
        "CSM 4.3.2(d)")),
    ("meter replacement date", Request("utility",
        "Please state the date the meter was replaced (meter change order).",
        "براہ کرم میٹر تبدیل ہونے کی تاریخ (ایم سی او) بتائیں۔",
        "CSM 6.4.1 (MCO snapshot)")),
    ("display-wash defect", Request("utility",
        "Please state the defect recorded for the replaced meter.",
        "براہ کرم تبدیل شدہ میٹر کی درج شدہ خرابی بتائیں۔",
        "CSM 4.3.1, 4.3.2")),
    ("comparison months", Request("utility",
        "Please provide the monthly consumption used as the basis of the detection bill, and the same months of the previous year.",
        "براہ کرم ڈیٹیکشن بل کی بنیاد بننے والی ماہانہ کھپت اور پچھلے سال کے انہی مہینوں کی کھپت فراہم کریں۔",
        "CSM 9.2.3(b)")),
    ("detection reasons", Request("utility",
        "Please state the reasons for the detection bill, with the units, amount, period and taxes.",
        "براہ کرم ڈیٹیکشن بل کی وجوہات، یونٹس، رقم، مدت اور ٹیکس بتائیں۔",
        "CSM 9.2.5")),
    ("date of checking", Request("utility",
        "Please state the date on which the discrepancy was checked or discovered.",
        "براہ کرم بتائیں کہ یہ فرق کس تاریخ کو جانچا یا معلوم کیا گیا۔",
        "CSM 7.5.5")),
    ("period of charging", Request("utility",
        "Please state the period for which the supplementary charges were raised, with the reason and amount.",
        "براہ کرم اضافی چارجز کی مدت، وجہ اور رقم بتائیں۔",
        "CSM 7.5.5")),
    ("number of months the units cover", Request("utility",
        "Please state the months the accumulated units cover, so they can be billed month by month.",
        "براہ کرم بتائیں کہ جمع شدہ یونٹس کن مہینوں کے ہیں تاکہ ان کا بل ماہ بہ ماہ بنایا جا سکے۔",
        "CSM 6.4.2")),
    ("same month of the previous year", Request("utility",
        "Please provide the consumption of the same month last year used for average billing.",
        "براہ کرم اوسط بلنگ کے لیے پچھلے سال کے اسی مہینے کی کھپت فراہم کریں۔",
        "CSM 4.3.1(b)")),
    ("last eleven months", Request("utility",
        "Please provide the consumption of the last eleven months used for average billing.",
        "براہ کرم اوسط بلنگ کے لیے پچھلے گیارہ مہینوں کی کھپت فراہم کریں۔",
        "CSM 4.3.1(b)")),
    ("phase of the connection", Request("utility",
        "Please confirm whether the connection is single phase or three phase.",
        "براہ کرم تصدیق کریں کہ کنکشن سنگل فیز ہے یا تھری فیز۔",
        "CSM Annexure V (load factor)")),
    ("delivery date", Request("user",
        "On what date did the bill reach you?",
        "یہ بل آپ کو کس تاریخ کو ملا؟")),
    ("meaning of 'clear seven days'", Request("limit",
        "The rules do not say exactly how the seven clear days are counted, so this check is left open.",
        "قواعد یہ واضح نہیں کرتے کہ سات دن کیسے گنے جائیں، اس لیے یہ جانچ کھلی چھوڑی گئی ہے۔")),
    ("past 6 months' includes", Request("limit",
        "The rules do not say whether the current month counts toward protected status, and the answer changes here, so both are shown.",
        "قواعد یہ نہیں بتاتے کہ محفوظ زمرے کے لیے موجودہ مہینہ شامل ہے یا نہیں، اس لیے دونوں نتائج دکھائے گئے ہیں۔")),
    ("public holiday calendar", Request("limit",
        "SahiBill does not have the holiday calendar for this date, so the due-date limit is left open.",
        "صحیح بل کے پاس اس تاریخ کا تعطیلات کیلنڈر نہیں، اس لیے آخری تاریخ کی جانچ کھلی ہے۔")),
    ("rate table for this billing month", Request("limit",
        "SahiBill does not have the tariff for this billing month yet, so the charges were not recomputed.",
        "صحیح بل کے پاس ابھی اس مہینے کا ٹیرف نہیں، اس لیے چارجز دوبارہ نہیں جانچے گئے۔")),
    ("FCA rate", Request("limit",
        "SahiBill does not have the fuel adjustment rate for this billing month, so that line was not checked.",
        "صحیح بل کے پاس اس مہینے کا فیول ایڈجسٹمنٹ ریٹ نہیں، اس لیے یہ لائن نہیں جانچی گئی۔")),
    ("QTA rate", Request("limit",
        "SahiBill does not have the quarterly adjustment rate for this billing month, so that line was not checked.",
        "صحیح بل کے پاس اس مہینے کا سہ ماہی ایڈجسٹمنٹ ریٹ نہیں، اس لیے یہ لائن نہیں جانچی گئی۔")),
    ("billing history", Request("retake",
        "Please include the billing history table (the last 12 months) in the photo.",
        "براہ کرم تصویر میں بلنگ کی تاریخ کا جدول (پچھلے 12 مہینے) شامل کریں۔")),
    ("snapshot", Request("retake",
        "The meter-reading picture on the bill is not clear. Please take the photo again, flat and in daylight.",
        "بل پر میٹر ریڈنگ کی تصویر واضح نہیں۔ براہ کرم بل کو سیدھا رکھ کر دن کی روشنی میں دوبارہ تصویر لیں۔")),
    ("units of ", Request("retake",
        "Please include the billing history table in the photo; one month's units could not be read.",
        "براہ کرم تصویر میں بلنگ کی تاریخ کا جدول شامل کریں؛ ایک مہینے کے یونٹس پڑھے نہیں جا سکے۔")),
]
RETAKE_FIELD = Request("retake",
    "Part of the bill could not be read. Please take the photo again, flat and in daylight, with the whole bill in view.",
    "بل کا کچھ حصہ پڑھا نہیں جا سکا۔ براہ کرم پورا بل سیدھا رکھ کر دن کی روشنی میں دوبارہ تصویر لیں۔")
BILL_FIELDS = ("billing month", "issue date", "due date", "reading date", "units", "rate applied", "status or rate",
               "billed present reading", "billed charge lines", "peak/off-peak units", "load")


def route(missing: str) -> Request:
    for pat, req in ROUTES:
        if pat in missing:
            return req
    if any(missing.startswith(b) for b in BILL_FIELDS):
        return RETAKE_FIELD
    raise KeyError(f"no route for missing input: {missing!r}")


def build_requests(findings: list[Finding]) -> dict[str, list[dict]]:
    """Group the next steps by audience, without duplicates, keeping which checks needed each one."""
    out: dict[str, dict[str, dict]] = {}
    for f in findings:
        if f.status != CBD:
            continue
        for m in f.missing:
            r = route(m)
            slot = out.setdefault(r.audience, {}).setdefault(r.en, {"en": r.en, "ur": r.ur, "clause": r.clause, "checks": []})
            if f.check not in slot["checks"]:
                slot["checks"].append(f.check)
    return {k: list(v.values()) for k, v in out.items()}
