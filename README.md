# SahiBill

**Checks a Pakistani household electricity bill against NEPRA's own rules, in English and Urdu.**

Take a photo of one bill, or of up to twelve months of bills. SahiBill reads them and runs ten checks
written from NEPRA's Consumer Service Manual and the tariff in force. Each check ends in one of three
answers: *problem found*, *looks right*, or *cannot tell yet*. A problem is only called a problem when a
rule and a number say so, and the clause is shown with it. When a check rests on something the photo does
not show, SahiBill asks the household first. When a problem is found, it writes the complaint letter in
English and Urdu, with the response times and escalation route the manual sets.

People can also ask about their bill out loud in Urdu, Sindhi, Pashto, Saraiki, Punjabi or English.

Built for the Meta Global AI Developer Hackathon, Indie track ("Build for Your World").

Live: https://sahibill.aashanjaved.com

## Why it matters

In July and August 2023, NEPRA counted 10,687,614 domestic bills with a reading period over 30 days
(NEPRA, *Inquiry Report in the Matter of Excessive Billing by DISCOs, July & August 2023*, table 3.2).
A reading taken a few days late adds those days' units to one bill. A protected household (at most 200
units a month) that crosses 201 units pays the unprotected rate on every unit and loses protected status
for six months. The manual already has the remedy, pro-rata billing (CSM 6.1.1.1). A household needs to
know it applies, and to cite it.

The 3D scene on the home page shows this mechanism: move the reading day and watch the bill cross the
line, then switch on the pro-rata rule.

The method carries to any utility whose regulator publishes its rules: the manual becomes tested code,
and the open models read the bill and hear the household in its own language.

## Who does what

Models read and listen. Code decides every number.

| Step | Done by | How |
|---|---|---|
| Read the bill photo | **Muse Spark Open** (Meta, open weights) on Nebius Token Factory | Transcribes the printed fields at low reasoning effort. Every number is parsed and checked in code. |
| Hold what does not add up | SahiBill code | Readings, dates and charges must agree with each other (both IESCO bill layouts), or the field is held. |
| Check the rules | SahiBill code | Ten checks from the CSM (revised 26 November 2025) and the CY2026 tariff, each with its clause. |
| Ask before accusing | SahiBill code | Anything that rests on a field being absent becomes a question until the household confirms. |
| Find the meter photo | **SAM 3** (`facebook/sam3`) on Modal | Cuts out the meter snapshot printed on the bill so the person can read the digits and type them. |
| Hear a spoken question | **Omnilingual ASR** 7B and 1B (Meta) on Modal | Both models transcribe; if they disagree beyond the threshold set for that language, SahiBill asks "Did you say...?" |
| Answer the question | **Muse Spark Open** | Answers from this bill's findings only. An answer that adds any number the findings do not contain is thrown away, and a plain answer built from the findings is shown. |
| Write the complaint | SahiBill code | Built only from the findings. |

Muse Glimmer 30B (Meta, open weights) was tested as a second reader in evaluation E2 and is not used live.

## Results

Every target was written down in [PREREGISTRATION.md](PREREGISTRATION.md) before the test ran. Misses
are reported as misses. Full reports are in [results/](results/).

On six real IESCO bills from one household (12 photos), 237 of 248 fields were read right, 2 wrong and 9
not read, and after the fixes that test led to none of the 12 photos raises a false problem (E8). Photos
at phone quality read at 99.8% (E1). Where SahiBill missed NEPRA's finding on real decisions, it mostly
said *cannot tell yet* (E4a).

| Test | Target | Result | |
|---|---|---|---|
| E1 Reading 100 synthetic bill photos | 97% of fields on clean photos, 90% on hard ones | 100% clean, 99.8% phone photos, 52.9% hard photos | partly |
| E2 Two readers with abstention | at most 1% wrong among accepted fields, accepting at least 85% | 85.5% accepted, 1.65% wrong, all of it on the hardest photos. With the retake gate added later (pre-registered amendment, 27 October): 0 wrong, 74.4% accepted | missed |
| E3 Finding seeded defects | 95% | 76.9%; most misses traced to answer-key bugs in the test generator, fixed and not re-measured | missed |
| E4a Rules on 64 real NEPRA decisions | agree with NEPRA in 70% | 47.6% (20 of 42, strict set); 46.5% after all 129 labels were re-read. Most misses are abstentions where the decision does not state an input the rules need | missed |
| E4b The same, read from the page images | at least 55% | 36.7% (11 of 30); 35.5% after the re-read. The gap is the rules: reading lost one decision and added one | missed |
| E6 Numbers read from NEPRA decisions | at least 85% right | 91.7% (154 of 168) | met |
| E7 Speech, Omnilingual ASR 7B | character error within 3 points of Meta's published figure | Urdu 4.91%, Sindhi 7.17%, Pashto 13.16% within; Saraiki 21.99% outside. Punjabi not run | partly |
| E8 Six real IESCO bills, 12 photos | descriptive | 237 of 248 fields right; no false alarm after the fixes this test led to | met |

What these mean for a user:

- Photos at phone quality read almost perfectly. Badly blurred photos do not, and two models that agree
  can still share the same wrong digit (E2). So a free sharpness check now runs before any model call and
  asks for a retake when a photo is too blurred ([results/E2-RETAKE-GATE.md](results/E2-RETAKE-GATE.md)),
  every check shows the numbers it used, and every number can be corrected.
- On real NEPRA cases the rules more often say *cannot tell yet* than disagree with NEPRA (E4a).
  SahiBill is built to abstain when it lacks an input.
- Speech in Saraiki, Punjabi and English has no measured threshold, so every spoken question in those
  languages is shown back to confirm before it is answered.

## Run it

Needs Python 3.12, [uv](https://docs.astral.sh/uv/) and Node 18 or later.

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev,voice]"
(cd frontend && npm ci && npm run build)          # builds into web/dist/
SAHIBILL_BUDGET_USD=0 .venv/bin/python -m uvicorn web.app:app --port 8770
```

Open http://127.0.0.1:8770 and choose a sample bill. With a budget of 0 no model is ever called: the
sample bills come with saved readings (`web/static/samples/readings/`, synthetic, no personal details),
and a new photo is held with a message that checking is paused.

To read new photos, set `NEBIUS_API_KEY` and a small budget, for example `SAHIBILL_BUDGET_USD=0.50`. The
budget is a total in US dollars across every call this server makes, counted from its own cost log.

Voice and the meter crop run on [Modal](https://modal.com):

```sh
modal run sahibill/speech/modal_asr.py::fetch_weights    # once, CPU only
modal deploy sahibill/speech/modal_asr.py
modal deploy sahibill/vision/modal_sam.py                # needs access to facebook/sam3 and a Modal secret "huggingface"
```

Both apps scale to zero when idle.

Tests (no network, no model calls):

```sh
SAHIBILL_BUDGET_USD=0 .venv/bin/python -m pytest -q
(cd frontend && npm test)
```

## Deploy

The live site runs on one small VM behind a Cloudflare tunnel, which provides HTTPS. The app listens
on 127.0.0.1 only. Files are in [deploy/](deploy/):

- `deploy.sh` builds the frontend, copies the app and installs `deploy/requirements.txt` on the server,
  then restarts the systemd unit and checks `/api/health`. It never sends keys, real bills or the local
  cache.
- `sahibill.service` is the unit: one worker, 400 MB memory cap, cache in `~/sahibill/cache`, and
  reports, photos and readings deleted after 30 days.
- `env.example` lists what `~/sahibill/env` (mode 600) holds: the Nebius key, a Modal token, the
  spending cap and the daily ceilings.

Public routes that cost money or disk are limited per visitor and per day (`web/limits.py`): new photos
read, uploads, samples, spoken questions, answers and meter crops. The visitor is the `CF-Connecting-IP`
header, trusted only from the local tunnel.

## Privacy

- Photos are kept on the server for 30 days, then deleted, along with their readings and reports. A
  report's link carries a random id (122 random bits) and is the only key to its photos.
- To be read, each photo is sent to Nebius (Muse Spark Open), and to Modal when the meter photo is cut
  out. Spoken questions are sent to Modal. Nothing else is shared, and there is no tracking or
  third-party script. Fonts are self-hosted.
- The reader copies out billing figures only. It is not asked for names, addresses or account numbers.

## What it cannot do yet

- IESCO's newer bill layout prints only totals (the detail sits behind a QR code), so the itemised
  arithmetic check runs on the older layout only.
- The rules were tested on NEPRA decisions across distribution companies, and on real bills from one
  IESCO household (six months).
- Badly damaged photos read poorly (E1, E2); the retake gate refuses most of them, and a faded photo can still pass it.

## Cost

Measured from the code's cost log, VAT included. Reading the six real bills (12 photos) cost $0.162 on
Nebius, about 1.4 cents a photo. Four answers to spoken questions cost $0.017. Modal GPU time for the
speech and SAM 3 tests was paid from Modal's free monthly credit.

## Data and sources

- Rules: NEPRA Consumer Service Manual (revised 26 November 2025) and NEPRA's CY2026 tariff decisions,
  quoted with their clauses in the code and tests.
- Evaluation: NEPRA complaint decisions (public on nepra.org.pk). The PDFs are not redistributed here;
  the tests hold only the facts needed, each with its source.
- Speech evaluation used FLEURS and Mozilla Common Voice; only scores are published, never clips.
- Synthetic bills are generated from the CSM's field list (`sahibill/synth/`) and labelled as synthetic.
- No real bill is in this repository.

## Layout

| Path | What |
|---|---|
| `sahibill/rules/` | the ten checks |
| `sahibill/readers/` | bill reader, consistency layer, two-reader agreement |
| `sahibill/report.py` | household reports: several months, answers, corrections |
| `sahibill/voice.py`, `sahibill/speech/` | spoken questions |
| `sahibill/vision/` | SAM 3 meter crop |
| `sahibill/complaint/` | complaint letter and requests to the utility |
| `sahibill/synth/` | synthetic bill generator with seeded defects |
| `web/` | FastAPI app and rate limits |
| `frontend/` | React and TypeScript app, English and Urdu, the 3D scene |
| `eval/`, `results/` | evaluation scripts and reports |

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
