"""Spoken questions about a bill: hear (Omnilingual ASR on Modal), confirm when unsure, answer from the findings.

Hearing: two Meta speech models transcribe the clip; their character disagreement is compared with the
threshold set on each language's dev set in E7 (results/E7.md). A transcript within the threshold is used as
heard; anything else, and every language without a measured threshold, is shown back to the user to confirm
or correct first ("Did you say ...?").

Answering: Muse Spark Open writes the answer from this bill's findings only. An answer that contains any
number the findings do not contain is refused, and a plain answer built from the findings is used instead.
"""
from __future__ import annotations

import json
import os
import re

from sahibill.complaint.draft import numbers_in
from sahibill.readers.llm import BudgetExceeded, chat
from sahibill.speech.score import disagreement

# Thresholds from E7 dev sets (5% CER bar). None: no threshold reaches the bar, or not measured: always confirm.
THRESHOLDS = {"urdu": 0.208, "sindhi": 0.069, "pashto": 0.0, "saraiki": None, "punjabi": None, "english": None}
LANG_NAMES = {"urdu": "Urdu", "sindhi": "Sindhi", "pashto": "Pashto", "saraiki": "Saraiki", "punjabi": "Punjabi (Shahmukhi)",
              "english": "English"}
A, B = "sahibill_omniASR_LLM_7B_v2", "sahibill_omniASR_LLM_1B_v2"


def hear(audio: bytes, fmt: str, language: str) -> dict:
    """Transcribe with both models. SAHIBILL_ASR_FAKE (a JSON {"a": ..., "b": ...}) replaces Modal in tests."""
    if language not in THRESHOLDS:
        raise ValueError("Unsupported language.")
    fake = os.environ.get("SAHIBILL_ASR_FAKE")
    if fake:
        f = json.loads(fake)
        text, second = f["a"], f["b"]
    else:
        import modal
        asr = modal.Cls.from_name("sahibill-asr", "ASR")()
        row = asr.transcribe.remote([{"id": "q", "audio": audio, "format": fmt}], language)[0]
        text, second = row.get(A, ""), row.get(B, "")
    d = disagreement(text, second)
    t = THRESHOLDS[language]
    return {"text": text, "language": language, "disagreement": round(d, 3),
            "sure": bool(text.strip()) and t is not None and d <= t}


def _context(bill: dict) -> dict:
    """What the answer may draw on: the bill's checks and next steps, nothing else."""
    return {
        "billing_month": bill.get("billing_month"),
        "headline": (bill.get("headline") or {}).get("en"),
        "checks": [{"check": c.get("title"), "status": c.get("status"), "lines": c.get("lines"), "clauses": c.get("clauses")}
                   for c in bill.get("cards") or []],
        "next_steps": {k: [s.get("en") for s in v] for k, v in (bill.get("next_steps") or {}).items()},
        "has_complaint_letter": bool((bill.get("complaint") or {}).get("problem_count")),
        "units_this_bill": next((r.get("value") for r in bill.get("reading") or [] if r.get("key") == "units"), None),
        "units_by_month": [{"month": h.get("month"), "units": h.get("units")} for h in bill.get("history") or []],
    }


STATUS_EN = {"problem_found": "problem found", "looks_right": "looks right", "cannot_be_determined": "cannot tell yet"}
STATUS_UR = {"problem_found": "مسئلہ ملا", "looks_right": "درست لگتا ہے", "cannot_be_determined": "ابھی نہیں کہہ سکتے"}


def plain_answer(bill: dict, language: str) -> str:
    """The answer built only from the findings, used whenever a written answer cannot be trusted."""
    ur = language != "english"
    cards = bill.get("cards") or []
    order = {"problem_found": 0, "cannot_be_determined": 1, "looks_right": 2}
    lines = [(bill.get("headline") or {}).get("ur" if ur else "en", "")]
    for c in sorted(cards, key=lambda c: order.get(c.get("status"), 3))[:4]:
        title = c.get("title_ur") if ur else c.get("title")
        status = (STATUS_UR if ur else STATUS_EN).get(c.get("status"), "")
        text = " ".join((c.get("lines_ur") if ur else c.get("lines")) or [])
        lines.append(f"{title}: {status}{'۔' if ur else '.'} {text}")
    return "\n".join(x for x in lines if x)


_warm_at = 0.0


def warm() -> bool:
    """Start loading the speech models before a question arrives (at most once every two minutes)."""
    global _warm_at
    import time
    if os.environ.get("SAHIBILL_ASR_FAKE") or time.time() - _warm_at < 120:
        return False
    _warm_at = time.time()
    import modal
    modal.Cls.from_name("sahibill-asr", "ASR")().ping.spawn()
    return True


def answer(bill: dict, question: str, language: str) -> dict:
    ctx = _context(bill)
    allowed = numbers_in(json.dumps(ctx, ensure_ascii=False))
    target = LANG_NAMES.get(language, "Urdu")
    prompt = (
        f"A household in Pakistan asked about their electricity bill, in {target}: \"{question}\"\n\n"
        "Answer in plain, short sentences in " + target + " (Urdu script for Urdu, Saraiki, Punjabi and Sindhi; "
        "Pashto script for Pashto). Use ONLY the checks below, which SahiBill's code produced from NEPRA's rules. "
        "Do not add any number, date, rate or rule that is not in them. If the checks do not answer the question, "
        "say so and say what SahiBill would need. Never say the bill is wrong unless a check says problem found. "
        "If the question is why the bill is higher or lower, compare units_this_bill with units_by_month and say so "
        "plainly; more units used is the usual reason, and say that the checks found or did not find a billing error. "
        "Write only in the script of that language: never mix in Devanagari or Latin words.\n\n"
        + json.dumps(ctx, ensure_ascii=False)
    )
    try:
        r = chat([{"role": "user", "content": prompt}], reasoning_effort="low", max_tokens=700, tag="voice-answer")
        text = (r.get("content") or "").strip()
        cost = r.get("usd") if not r.get("cached") else 0.0
    except (BudgetExceeded, RuntimeError):
        return {"text": plain_answer(bill, language), "source": "findings", "cost_usd": 0.0}
    wrong_script = language != "english" and re.search(r"[\u0900-\u097F]", text or "")
    if not text or wrong_script or not numbers_in(text) <= allowed:
        return {"text": plain_answer(bill, language), "source": "findings", "cost_usd": cost,
                "note": "the written answer was not used: it added a number the findings do not contain, or mixed scripts"}
    return {"text": text, "source": "muse-spark-open", "cost_usd": cost}
