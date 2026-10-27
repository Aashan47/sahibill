# E4a result: the rules engine on real NEPRA decisions, rules only

Run once on 21 October 2026, on inputs frozen before the run (input set SHA-256 prefix 4433bbc52e0a934b),
under the scoring rule and sensitivity check fixed in PREREGISTRATION.md before the run.

## Pre-registered result

| Set | Matched NEPRA's violation | Rate |
|---|---|---|
| All scored decisions | 32 of 64 | 50.0% |
| Strict set (no input field drawn from NEPRA's finding or order) | 20 of 42 | 47.6% |

**Prediction: at least 70% on the strict set. Not met.**

Specificity: on the 8 decisions where NEPRA found no violation, the engine raised a problem in 1
(LESCO_1056: seven months billed as one; CSM 6.4.2 requires segregation, NEPRA found no violation; this
disagreement was recorded before the run).

## Why it missed

- **Abstention, not error, in most misses.** In 27 of the 32 misses the engine raised nothing relevant and
  returned cannot_be_determined, because the decision does not state an input the written rule needs:
  CEO or committee approval for detection periods over three cycles (never printed on a bill), the
  comparison months for the history test, the retrieval date for late retrieval charges. The engine is
  built to say what is missing in those cases. The pre-registered rule counts an abstention as a miss.
- **Two codes for one clause.** In 3 decisions the label coded a CSM 6.4.2 finding as
  slab_not_prorated_long_period while the engine raised accumulated_units_charged_at_once, the code the
  labelling amendment created for the same clause.
- **One disagreement known in advance** (LESCO_1056, above).

## Post-hoc, not a replacement for the result above

Treating the two CSM 6.4.2 codes as one: 35 of 64 (54.7%); strict set 22 of 42 (52.4%). Still below the
prediction.

Per-decision rows (decision file names, NEPRA's codes, the engine's codes, the inputs it reported missing)
are in `e4a.json`.

## After the full re-read of the labels (22 October 2026)

The spot-check found errors in 2 of 13 decisions, above the protocol's 1-in-13 threshold, so all 129 labels
were re-read against the page images by fresh agents (2,176 items in all; every number and quote was right;
15 items wrong and 46 unsure, nearly all violation codes applied unevenly after amendment 1). 27 labels were
corrected, each with an amendment line; the scored code changes were confirmed on the page. Re-scored with
the same inputs and rule (`e4a-relabelled.json`): all scored 32 of 65 (49.2%), strict set 20 of 43 (46.5%);
specificity unchanged (1 false alarm in 8). The pre-registered result above stands as the result of record;
the re-read moves it by about one point.
