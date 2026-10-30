# SahiBill: pre-registered evaluation

Written on 21 October 2026. Every prediction below was fixed before any scored run. Results are reported whatever they are, including every prediction that fails.

## What was already seen before this was written

So nobody mistakes these for blind predictions:

- Three smoke tests of Muse Spark Open on 20 October 2026: two images of one synthetic bill (11 of 11
  fields read correctly, clean and phone-degraded) and one real NEPRA decision (MEPCO, 2013, scanned
  upside down, no text layer), where most fields were right but one amount was wrong and the Electric
  Inspector's figures were attributed to NEPRA. That decision is excluded from every end-to-end score.
- The 129 NEPRA decisions in the evaluation set were read and labelled from the page images before
  any model was scored on them. No model under test (Muse Spark Open, Muse Glimmer) wrote or saw a label.

## Data

| Set | What | Size | Fixed by |
|---|---|---|---|
| NEPRA decisions | Published complaint decisions of Pakistan's power regulator (nepra.org.pk, Consumer Affairs, Authority Decisions), labelled: issue, facts with page and quote and speaker, NEPRA's finding, ordered correction | 129, stratified by dispute type; seed 20261021 | sampling before labelling |
| NEPRA end-to-end subset | Billing decisions whose finding is checkable from a bill, excluding the smoke-tested one | 40 of 88 eligible; seed 20261026 | this document |
| Synthetic bills | Generated from the fields the Consumer Service Manual (revised, 26 November 2025, clause 6.4.1) requires, with seeded defects and four photo-damage levels; marked SYNTHETIC; no utility branding | 50 bills x 4 levels = 200 images; 50% calibration, 50% test, split by bill | generator seed fixed in code before the first run |
| Speech | Public speech corpora in Urdu, Punjabi, Sindhi, Pashto, Saraiki (sets and splits fixed in `eval/speech_sets.md` before the first run) | about 100 to 200 clips per language where available | before the first run |
| Real bills | A small number of the author's own bills, fields noted by him from paper | reported with its count | before the run |

NEPRA documents are linked and downloaded by script; they are not redistributed. A random 10% of the
labels is checked by hand.

## Predictions

| ID | Test | Prediction |
|---|---|---|
| E1 | Field reading, Muse Spark Open alone, by damage level, synthetic test half | at least 97% of fields right at level 0; at least 90% at level 3 |
| E2 | Two readers (Spark Open and Glimmer) with calibrated abstention | among accepted fields, at most 1% wrong, while accepting at least 85% |
| E3 | Defect detection, synthetic test half | each check finds at least 95% of its seeded defects; at most 2% of clean bills flagged |
| E4a | NEPRA, rules only, from the labelled facts | the checker raises NEPRA's violation in at least 70% of billing decisions checkable from a bill |
| E4b | NEPRA, end to end, facts read from the page images, 40-decision subset | at least 55%; every gap from E4a attributed to reading or to rules |
| E5 | NEPRA, same correction (revised units, load or months) | equal to NEPRA's order in at least 50% of decisions that state one |
| E6 | NEPRA, reading real scans, 40-decision subset | at least 85% of labelled values read right; Spark Open alone credits a number to the wrong speaker in at least 10% of decisions, and the quote check lowers that |
| E7 | Speech, Omnilingual ASR 7B, character error rate per language | within 3 points of Meta's own published figure; with abstention, Urdu at most 5% CER on accepted clips while accepting at least 80%; lower acceptance for Saraiki and Punjabi, reported as is |
| E8 | The author's real bills | descriptive only: fields right out of fields read, with the count |

Where a written rule and NEPRA's ruling disagree, the checker follows the written rule, and the case is
reported as a disagreement. It is not counted as an error.

## Budget

Paid model calls are capped and staged: a 10-image check, then 200 synthetic images, then the 40-decision
subset. Every model response is cached. Larger runs happen only if stated here first in a dated
amendment.

## Amendments

Any change after the first scored run is dated, explained, and does not delete the original.

**21 October 2026, before any scoring: speech sets fixed.** Test splits only, because Omnilingual ASR
was trained on FLEURS, Common Voice and its own corpus training splits: Urdu, FLEURS `ur_pk` test (299
clips); Punjabi in Shahmukhi, Omnilingual corpus `pnb_Arab` test (84 clips, one speaker, the only public
Shahmukhi test set found); Sindhi, FLEURS `sd_in` test (200); Pashto, FLEURS `ps_af` test (200); Saraiki,
Common Voice 27 `skr` test (results only; its terms forbid re-sharing clips). E7's comparison with Meta's
published per-language error rates is indicative only, because Meta does not state which test sets those
figures come from.

**21 October 2026, before any E4a run: E4a scoring rule fixed.**
- Inputs: each labelled decision's facts are converted into the engine's bill-fact format using only what
  the label states (no inference of numbers), by a converter that does not see the engine or its output.
- Scored set: billing decisions whose label marks the finding as checkable from a bill and whose NEPRA
  violations include at least one the engine can raise (slab_not_prorated_long_period,
  snapshot_missing_or_mismatch, protected_status_wrongly_removed, detection_units_formula_error,
  detection_load_or_period_exceeds_limits, detection_not_justified_by_history,
  average_billing_beyond_limit, average_billing_wrong_basis, retrieval_charge_beyond_time_limit,
  skipped_charges_beyond_recovery_limit, accumulated_units_charged_at_once, due_date_too_short).
- A decision is a match when the engine returns problem_found with at least one of NEPRA's violations.
  cannot_be_determined counts as not matched and is reported separately with what was missing.
- Specificity: on decisions where NEPRA found no violation (none_found), the count of decisions where the
  engine raises any problem is reported.
- The engine is run once on the frozen inputs. The prediction stays as written: at least 70% matched.

**21 October 2026, after the inputs were converted and before the single E4a run: sensitivity check
added.** Some converted inputs take a field from NEPRA's finding or order (for example, whether units were
segregated), which can leak the answer into the input. E4a is therefore reported twice: on all scored
decisions, and on the scored decisions none of whose filled fields cite `nepra_finding` or
`ordered_correction` as their source. The 70% prediction is judged on the second, stricter figure.

**21 October 2026, before any test-half image was read: reader settings frozen for E1 to E3.**
Chosen on the calibration half only (10 images, levels 2 and 3): Muse Spark Open on Nebius at reasoning
effort "low"; a page the model reports as turned 90, 180 or 270 degrees is straightened in code and read
again; the consistency layer holds fields that break bill identities (readings, dates, charges add-up);
E2 accepts a field only where Spark Open and Muse Glimmer agree and it is not held. No tunable threshold
remains, so the calibration half is not read further. Stage 2 reads the 100 test-half images (25 bills x 4
levels) once, within the approved budget. Calibration observations already seen, disclosed: level 2, 82 of
82 fields right; level 3 before straightening, 21 right, 14 wrong, 47 unread; after straightening (4
rotated images), 44 of 62 read fields right.

**21 October 2026, before Muse Glimmer read any test-half image: Glimmer settings frozen for E2.**
Decided on the 10 calibration images: Glimmer (open weights, Ollama, two Kaggle T4 GPUs) read level-2 photos
82 of 82 right, but spent 2,700 to 6,500 output tokens per bill on hidden reasoning (3 to 8 minutes each)
and read sideways pages poorly. For E2 it runs with thinking switched off, at temperature 0, on the same
image Spark Open read: the straightened copy wherever Spark Open reported the page turned. E2's rule is
unchanged. Calibration seen so far for the two-reader agreement: level 2, 82 of 82 accepted, all right;
level 3, 11 of 82 accepted, 1 wrong.

**21 October 2026, before Muse Glimmer read the test half (amends the Glimmer settings above).** The
thinking-off, strict-JSON setting failed on the calibration images (Glimmer echoed the instructions and
read nothing), so its 100 test readings are discarded unused. A calibration-only comparison chose the
setting for E2: thinking off, temperature 0, no strict-JSON switch, output capped at 3,000 tokens, on the
same image Spark Open read (straightened where reported turned). Calibration seen with it: Glimmer alone,
level 2, 82 of 82 right; level 3, 50 right, 27 wrong of 77 read. Two-reader agreement with the
consistency layer: level 2, 82 of 82 accepted, all right; level 3, 54 accepted, 9 wrong.


**22 October 2026, before any E7 clip is scored: E7 procedure fixed.** Seen so far: 10 Saraiki dev clips
(timing run, `results/E7-TIMING.md`); no test clip.
- Clips (`eval/e7_sets.py`, seed 20261022 on sorted file names): test sets as amended on 21 October;
  dev sets for thresholds: Urdu FLEURS `ur_pk` dev (all 267), Saraiki CV 27 dev (200 of 1,145), Sindhi
  `sd_in` dev (200 of 426), Pashto `ps_af` dev (all 217), Punjabi `pnb_Arab` dev (all 77). 8.53 hours of
  audio in all.
- Models: `omniASR_LLM_7B_v2` (the answer) and `omniASR_LLM_1B_v2` (second opinion), conditioned on
  `urd_Arab`, `skr_Arab`, `snd_Arab`, `pus_Arab`, `pnb_Arab`. Pashto test is also run once without a
  language code (reported beside the conditioned run, not used for abstention).
- Punjabi clips (all over 40 s, the models' limit) are cut into equal pieces under 35 s and the pieces'
  text is joined in order. Words cut at a boundary count as errors.
- Scoring: CER after Unicode NFKC, removing punctuation and the corpus tags (`<laugh>`, `<noise>` and
  the like), and collapsing spaces (`sahibill/speech/score.py`). FLEURS reference: the raw transcription.
- Abstention: a clip is accepted when the two models' character disagreement is at most the language's
  threshold, the largest threshold whose accepted dev clips have mean 7B CER at most 5%
  (`threshold_for`). If no threshold meets 5% on dev, that language accepts nothing and this is
  reported. Coverage and accepted CER are then measured once on test.
- Order, with a hard stop before any batch that would take spend past $2.20: Urdu dev, Urdu test,
  Saraiki test, Sindhi test, Pashto test, Punjabi test, Saraiki dev, Sindhi dev, Pashto dev, Punjabi dev,
  Pashto test without a language code. Anything not run is reported as not run.

**22 October 2026, before any of the 40 decisions is read: E4b and E6 procedure fixed (stage 3).**
- Reader (`eval/read_decisions.py`): Muse Spark Open, reasoning "low", one call per decision with every
  page as a 110 dpi image; pages reported turned are straightened in code and the decision read again.
  Each number comes with field, value, speaker, page and verbatim quote; the engine's input
  (`bill_facts`, fields as in E4a) comes with a source per field.
- Calibration, outside the 40 (seed 20261027, one text PDF and one scan from the other labelled billing
  decisions): K-Electric_0394 and GEPCO_0231, $0.046. Seen: 6 of 6 labelled values read right; the
  engine input for K-Electric_0394 matched the E4a input closely. Two scorer rules were set on these two
  and are now fixed: (1) speakers are judged sentence by sentence (a read fact counts as misattributed
  only when it quotes the labelled fact's sentence and names a different speaker; restatements the label
  does not record are not judged), because NEPRA often restates a number the label records once;
  (2) on a decision the label marks as a scan, quotes are unverifiable and are kept.
- E4b (`eval/e4b_e6.py`): the E4a rule on the 30 of the 40 that are in E4a's scored set; strict set
  excludes decisions with any engine field sourced from NEPRA's finding or order. Each decision's gap from
  E4a is labelled reading, rules, both matched, or reading added. Prediction unchanged (at least 55%).
- E6: value accuracy over labelled numbers and months (same field, same value); attribution: decisions
  with at least one misattributed sentence, Spark Open alone and after the quote check (a quote must be
  on its stated page, longest common run at least 80% of the quote, and contain the number's digits;
  failing facts are dropped). Prediction unchanged.
- Change from the build plan: E4b runs on Spark Open alone. Muse Glimmer took a median 137 s per bill
  image on Kaggle's free GPUs (E2); a Glimmer reading of the 40, if run, is reported as a separate arm.
- Caveat: the labels are not yet spot-checked by Aashan (13 decisions); results are reported with that.
- Budget: hard stop at $2.17 on the cost log (logged spend $1.157 at the start of stage 3; approved
  about $1.05).

**22 October 2026, before E8 is run: E8 set-up.** Twelve photos of six real IESCO bills (April to September
2026, a close-up and a casual photo each), turned upright from the phone's orientation tag. Answer key
typed by Claude from the close-ups before the run (115 fields; personal details left out), to be confirmed
by Aashan. Changes made after reading the bills by hand and before this run, none tuned on model output:
the reader knows both IESCO layouts, pro-rata readings and outstanding units, the FPA note and
bill-calculation rates; the consistency layer accepts both IESCO totals layouts; the snapshot check
accepts a pro-rata gap equal to the units carried forward (CSM 6.1.1.1). Reported per photo and in total,
before and after the consistency layer, close-ups and casual photos separately. Descriptive only.

**22 October 2026, before any Saraiki, Sindhi or Pashto dev clip is scored: E7 run order changed (his
decision).** The first E7 run stopped when the Punjabi test call hit Modal's 30-minute limit (my batching
mistake; nothing returned). With $0.95 of the E7 approval left, the remaining money goes to the dev sets
that set the refusal thresholds: Saraiki dev, Sindhi dev, Pashto dev, in that order, under the same rule
(threshold = the largest disagreement whose accepted dev clips have mean 7B CER at most 5%). The test CER
of these three languages is already reported (`results/E7.md`); their abstention results on test have not
been computed. Punjabi test and dev and Pashto without a language code are not run, and are reported as
not run.

**27 October 2026, before the gate is applied to any test-half image, real bill or fresh image: a retake gate
for badly damaged photos (approved by Aashan the same day, Nebius estimate $0.10 to $0.20).** E2 missed
(1.65% wrong among accepted fields, all on level 3). The gate is a free local check, `sahibill/readers/quality.py`:
the photo in grey, scaled to a long side of 1200 pixels, sharpness = variance of the Laplacian divided by the
squared 5th-to-95th percentile contrast, times 1000. A photo under **3.0** is refused and the person is asked to
take it again; nothing is read. The signal and the threshold were chosen on the 100 calibration-half images only
(25 bills at levels 0 to 3): 3.0 keeps all 75 calibration images at levels 0 to 2 and refuses 23 of 25 at level
3. The rule used: keep every calibration photo at levels 0 to 2 (a refused good photo stops a household from
using SahiBill), then refuse as many level-3 photos as that allows. Every calibration level-3 photo that was
read (5 in stage 1, 4 re-read in stage 1b) had wrong fields. Predictions, scored once:
- Test half, from the existing readings (no new spend). The gate keeps at least 98% of photos at levels 0 to 2
  and refuses at least 80% at level 3. With the gate, the pre-registered E2 arm (Spark Open + Glimmer +
  consistency) has at most 1% wrong among accepted fields. Its coverage over all 1,632 printed fields is
  expected near 75%, under E2's 85% target, so E2 as first stated stays missed on coverage; this is said
  before scoring. Every other arm is reported with and without the gate, including Spark Open + consistency
  alone (the arm the live product runs): at most 1% wrong among accepted.
- The author's 12 real bill photos (E8, 237 of 248 fields read right): the gate accepts all 12.
- A fresh synthetic set, seed 20261027, 4 bills at levels 0 to 3 (16 images), never seen: the gate keeps all
  photos at levels 0 to 2 and refuses at least 3 of 4 at level 3. Spark Open reads them with the E1 stage 2
  settings (reasoning low, straighten and re-read), levels 2 and 3 first, then 0 and 1 if the money allows;
  with the gate and the consistency layer, at most 1% wrong among accepted fields. How the refused photos
  read is reported as a description.
- Budget: hard stop at $0.25 of new spend on the cost log (logged spend $2.2468 at the start).

**29 October 2026, before the set below was generated or any of it read: E3 re-measured on a fresh set.**
The E3 result of record (21 October, 76.9% at levels 0 to 2) stands for the frozen set. Its diagnosis traced
most misses to the generator's answer key, which was fixed afterwards (oracle test: the rules on a perfect
reading return exactly the seeded problems on 180 bills). This measures the fixed generator through the
product path as it now runs live.
- Set: `python -m sahibill.synth.generate --n 54 --seed 20261029 --levels 2,3`, never seen, every bill used
  (no calibration half: nothing is tuned on it). About 1 bill in 3 is clean.
- Path, per photo: the retake gate (`sahibill/readers/quality.py`, threshold 3.0, unchanged); a refused photo
  is not read and is reported as refused; an accepted photo is read by Spark Open at the E1 stage 2 settings,
  then the consistency layer, then the rules (`eval/e3.py`, unchanged scoring).
- Predictions, scored once, unchanged from E3: at level 2 (phone photos), each check finds at least 95% of
  its seeded defects the bill can show, and at most 2% of clean bills are flagged. Level 3: the share
  refused, and the detection rate on the accepted photos, are reported as a description.
- With about 3 defects per check, a single miss puts that check under 95%; the overall rate is reported too.
- Budget: hard stop at $0.70 of new spend on the cost log (logged spend $2.433 at the start).

**29 October 2026, after the E3 fixes (commit 9a8d6c8) and before the set below was generated: E3 confirmation
on a second fresh set.** The fixes were made after seeing the first fresh set, so their effect there is
in-sample. This set is new and the code is frozen at commit faefdc9 for the run.
- Set: `python -m sahibill.synth.generate --n 54 --seed 20261031 --levels 2,3`, every bill used.
- Path and scoring: as in the amendment above (retake gate, Spark Open at stage 2 settings, consistency
  layer, rules, `eval/e3.py`), scored once without the household's answers, and once more with the
  household confirming the absences SahiBill asks about (`confirmed_absent`), which is how the product
  finds a missing meter photo.
- Predictions: at level 2, at most 2% of clean bills flagged (with about 20 clean bills, that means none);
  with absences confirmed, each check finds at least 95% of its seeded defects. Without confirmation, the
  "snapshot missing" check is expected to find none, by design, and is reported as such.
- Budget: hard stop at $0.70 of new spend (logged spend $2.961 at the start).

**29 October 2026, after the misread fix (commit e4b9fa1) and before the set below was generated: E3 third
fresh set, to measure false alarms on unseen bills after both fixes.** Code frozen at e4b9fa1.
- Set: `python -m sahibill.synth.generate --n 54 --seed 20261030 --levels 2,3`, every bill used; same path
  and scoring as the two amendments above.
- Predictions at level 2: at most 2% of clean bills flagged, scored as the product runs (no answers), which
  with about 20 clean bills means none; with the household confirming the absences SahiBill asks about, each
  check finds at least 95% of its seeded defects. Defects now turned into questions (a charge that adds up
  after one digit is corrected) count as not found, and how many there are is reported.
- Budget: hard stop at $0.70 of new spend (logged spend $3.540 at the start).
