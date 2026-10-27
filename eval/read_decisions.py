"""E4b and E6: Muse Spark Open reads NEPRA decisions from page images (stage 3).

python eval/read_decisions.py --pdfs <dir> --stems <stem> [<stem> ...] --out eval-data/decisions
One call per decision with every page as an image (110 dpi). A page the model reports as turned 90, 180
or 270 degrees is straightened in code and the decision is read again; the upright reading is used.
The model only transcribes: every number carries whose statement it is, its page and a verbatim quote.
Page images and readings stay local (NEPRA documents are not redistributed).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from sahibill.readers.llm import chat, image_part, parse_json

HERE = Path(__file__).resolve().parent
FIELDS = ("sanctioned_load_kw, connected_load_kw, detection_units, detection_months, detection_period_from, "
          "detection_period_to, load_factor, disputed_units, disputed_amount_rs, billing_month, reading_days, "
          "meter_status, consumption_history, tariff_charged, tariff_claimed, average_basis, other")
SPEAKERS = "complainant, disco, electric_inspector (also the POI), nepra, other"
SOURCES = "complainant, disco, electric_inspector, nepra_facts, nepra_finding, ordered_correction, other"

PROMPT = f"""These are the pages of a decision of NEPRA (Pakistan's power regulator) on an electricity billing
complaint. Pages are given in order, starting at page 1. Transcribe; do not calculate, correct or guess.
Pages may be scanned, rotated or upside down.

Return only one JSON object with these keys:

"page_orientation": an object giving, for each page number, the rotation in degrees needed to make it
upright (0, 90, 180 or 270).

"facts": a list of every number or date the decision states about this consumer's billing, each
{{"field": one of [{FIELDS}], "value": the number, "YYYY-MM" or "YYYY-MM-DD" date, or a short text,
"unit": short text or null, "speaker": one of [{SPEAKERS}], "page": page number,
"quote": the sentence it sits in, copied exactly}}.
"speaker" is whose statement the number is, from the sentence it sits in: a number the decision reports
from the Electric Inspector's or POI's decision belongs to electric_inspector even when it is printed in
NEPRA's own decision; a number the consumer claims belongs to complainant; the distribution company's
belongs to disco; nepra only for NEPRA's own findings or order.

"bill_facts": the facts below, as far as the decision states them, in this format. Use only what the
decision states. Never infer, estimate or compute a number, except the plain month count of a stated
period (inclusive: "August to October" is 3). Leave a field out when the decision does not state it.
Where the decision gives two different values for the same thing, leave it out. Prefer NEPRA's own
figures; use a party's statement only when NEPRA does not contradict it.

"bill_sources": for every field filled in "bill_facts" (use dotted names for nested ones, such as
"detection.units"), where it came from: one of [{SOURCES}], plus the page, as {{"source": ..., "page": ...}}.
nepra_facts is NEPRA's account of the case; nepra_finding is its conclusion; ordered_correction is what it
orders.

""" + (HERE / "decision_bill_facts.md").read_text()


def render(pdf: Path, out: Path, dpi: int = 110) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    if not list(out.glob("p-*.png")):
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(out / "p")], check=True)
    return sorted(out.glob("p-*.png"), key=lambda p: int(p.stem.split("-")[1]))


def upright(page: Path, clockwise: int) -> Path:
    from PIL import Image
    dst = page.with_name(f"{page.stem}.cw{clockwise}.png")
    if not dst.exists():
        Image.open(page).convert("RGB").rotate(-clockwise, expand=True, fillcolor=(255, 255, 255)).save(dst)
    return dst


def read_once(pages: list[Path], tag: str) -> dict:
    content = [{"type": "text", "text": PROMPT}]
    for i, p in enumerate(pages, 1):
        content += [{"type": "text", "text": f"Page {i}:"}, image_part(p)]
    r = chat([{"role": "user", "content": content}], reasoning_effort="low", max_tokens=8000, tag=tag)
    try:
        data = parse_json(r["content"])
    except Exception as e:   # noqa: BLE001
        data = {"error": f"unparseable output: {e}", "raw": r["content"][:3000]}
    data["_call"] = {k: r.get(k) for k in ("usage", "usd", "cached", "latency_s", "model", "reasoning_effort")}
    return data


def read_decision(pdf: Path, work: Path, tag: str) -> dict:
    pages = render(pdf, work)
    first = read_once(pages, tag)
    turn = {}
    for k, v in (first.get("page_orientation") or {}).items():
        try:
            o = int(round(float(v))) % 360
        except (TypeError, ValueError):
            continue
        if o in (90, 180, 270) and str(k).isdigit() and 1 <= int(k) <= len(pages):
            turn[int(k)] = o
    if not turn:
        return first
    fixed = [upright(p, turn[i]) if i in turn else p for i, p in enumerate(pages, 1)]
    second = read_once(fixed, tag + ":upright")
    second["_first_pass"] = {"turned": turn, "_call": first["_call"]}
    return second


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", type=Path, required=True)
    ap.add_argument("--stems", nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, default=Path("cache/decision-pages"))
    ap.add_argument("--tag", default="stage3")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    for stem in a.stems:
        dst = a.out / f"{stem}.json"
        if dst.exists():
            continue
        pdf = next(a.pdfs.rglob(f"{stem}.pdf"))
        r = read_decision(pdf, a.work / stem, f"{a.tag}:{stem}")
        dst.write_text(json.dumps(r, ensure_ascii=False, indent=1))
        c = r["_call"]
        print(f"{stem:12} facts={len(r.get('facts') or []):3} turned={(r.get('_first_pass') or {}).get('turned')} "
              f"usd={c.get('usd')} cached={c.get('cached')} {'ERROR ' + r['error'][:60] if 'error' in r else ''}", flush=True)


if __name__ == "__main__":
    main()
