"""The complaint letter: a template filled by code, optionally polished by Muse Spark Open.

The template is always correct: every number in it comes from the findings. A polished version is kept
only if every number it contains is one the template already has; otherwise the template is used.
Personal details (name, reference number, address) are placeholders the household fills in; SahiBill
never stores them.
"""
from __future__ import annotations

import re

from sahibill.rules.core import PROBLEM

TIMELINES = [
    ("Errors from wrong meter readings or wrong calculation of charges must be settled within 7 days of the complaint.",
     "میٹر ریڈنگ یا چارجز کے غلط حساب کی شکایت 7 دن میں حل کی جانی چاہیے۔", "CSM 10.3.1(a)"),
    ("Complaints about detection bills must be settled within 15 days of the complaint.",
     "ڈیٹیکشن بل کی شکایت 15 دن میں حل کی جانی چاہیے۔", "CSM 10.3.1(g)"),
]
ESCALATION = ("If the complaint is not settled, I may approach the Provincial Office of Inspection (section 38 of the "
              "NEPRA Act) or file a complaint with NEPRA (sections 39 and 35-A).",
              "اگر شکایت حل نہ ہوئی تو میں صوبائی دفتر معائنہ (نیپرا ایکٹ کی دفعہ 38) یا نیپرا (دفعات 39 اور 35-اے) سے رجوع کر سکتا/سکتی ہوں۔",
              "CSM 15.1.2 to 15.1.4")

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", "").rstrip("0").rstrip(".") if "." in n else n.replace(",", "") for n in _NUM.findall(text)}


def template(verdict: dict, next_steps: dict, billing_month: str | None = None) -> dict:
    problems = [c for c in verdict["cards"] if c["status"] == PROBLEM]
    month = billing_month or "[billing month]"
    en = [
        "To: The Complaint Cell, [distribution company], [sub-division]",
        f"Subject: Complaint about my electricity bill for {month}, reference number [your reference number]",
        "",
        "I have checked my bill against NEPRA's Consumer Service Manual (revised 26 November 2025) and the "
        "domestic tariff in force, and I request correction of the following:",
        "",
    ]
    ur = [
        "بخدمت: شکایت سیل، [ڈسٹری بیوشن کمپنی]، [سب ڈویژن]",
        f"موضوع: میرے بجلی کے بل ({month})، ریفرنس نمبر [آپ کا ریفرنس نمبر] کے بارے میں شکایت",
        "",
        "میں نے اپنا بل نیپرا کے کنزیومر سروس مینوئل (نظرثانی شدہ 26 نومبر 2025) اور نافذ ٹیرف کے مطابق جانچا ہے اور درج ذیل کی درستی کی درخواست کرتا/کرتی ہوں:",
        "",
    ]
    for i, c in enumerate(problems, 1):
        en.append(f"{i}. {c['title']}: " + " ".join(c["lines"]) + (f" ({'; '.join(c['clauses'])})" if c["clauses"] else ""))
        ur.append(f"{i}۔ {c['title_ur']}: " + " ".join(c.get("lines_ur") or c["lines"]))
    reqs = next_steps.get("utility") or []
    if reqs:
        en += ["", "I also request the following records, which the manual requires:"]
        ur += ["", "میں درج ذیل ریکارڈ کی بھی درخواست کرتا/کرتی ہوں جو مینوئل کے مطابق ضروری ہے:"]
        for r in reqs:
            en.append(f"- {r['en']}" + (f" ({r['clause']})" if r.get("clause") else ""))
            ur.append(f"- {r['ur']}")
    en += ["", "Under the manual:"] + [f"- {t[0]} ({t[2]})" for t in TIMELINES] + [ESCALATION[0] + f" ({ESCALATION[2]})"]
    ur += ["", "مینوئل کے مطابق:"] + [f"- {t[1]}" for t in TIMELINES] + [ESCALATION[1]]
    en += ["", "Name: [your name]", "Address: [your address]", "Date: [date]", "",
           "Prepared with SahiBill, which checks a bill against NEPRA's published rules. Please verify before sending."]
    ur += ["", "نام: [آپ کا نام]", "پتہ: [آپ کا پتہ]", "تاریخ: [تاریخ]", "",
           "یہ درخواست صحیح بل کی مدد سے تیار کی گئی ہے۔ بھیجنے سے پہلے تصدیق کر لیں۔"]
    return {"en": "\n".join(en), "ur": "\n".join(ur), "source": "template", "problem_count": len(problems)}


def accept_polished(template_text: str, polished: str) -> bool:
    """A polished letter is usable only if it introduces no number the template does not contain."""
    return bool(polished.strip()) and numbers_in(polished) <= numbers_in(template_text)
