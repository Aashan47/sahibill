# E4b and E6: NEPRA decisions read from page images (stage 3, 2026-10-22)

Muse Spark Open read the 40 end-to-end decisions (136 pages, one call each, 110 dpi images, reasoning
"low"); procedure fixed in the amendment of 22 October before any of them was read. All 40 outputs
parsed; no page was reported turned. Cost $0.821 (cost log, VAT included), plus $0.046 for the two
calibration decisions. Labels are Claude's and not yet spot-checked by Aashan.

## E4b: the rules engine on facts read from the pages

**Prediction: at least 55%. Result: missed.** 11 of 30 scored decisions matched NEPRA's violation
(36.7%); on the strict set (no engine field taken from NEPRA's finding or order), 3 of 15 (20%).

| Decision by decision, against E4a on the same 30 | Count |
|---|---|
| Both matched | 10 |
| E4a matched, E4b did not (reading loss) | 1 (K-Electric_0470) |
| Neither matched (rules) | 18 |
| E4b matched, E4a did not (reading added) | 1 (HESCO_0268) |

E4a matched 11 of these 30 from the labelled facts; E4b also matched 11. **Reading the pages cost one
decision and added one: the gap to the prediction is the rules, not the reading.** The 18 rules gaps
are the same kind E4a found (inputs the engine needs that decisions do not state, and violations the
engine has no check for).

One engine bug was found: the accumulated-units check crashed when a decision gave the months but not
the units (IESCO_0330). The scorer counted the crash as no finding, as fixed beforehand. The check now
returns a finding or "cannot be determined"; re-scored with the fix, E4b is unchanged (11 of 30).

## E6: reading and attribution

**Value accuracy, prediction at least 85%: met.** 154 of 168 labelled numbers and months read right
(91.7%), same field and same value.

**Attribution, prediction "Spark Open alone misattributes in at least 10% of decisions, and the quote
check lowers that": met as written, but neither half measures what it was meant to.**

- 8 of 40 decisions (20%) have a sentence where Spark Open and the label name different speakers; after
  the quote check, 5 of 40 (12.5%).
- Read one by one, these are sentences in which NEPRA narrates what a party did ("LESCO charged a
  detection bill of 851 units..."). The label itself is not consistent on such sentences (nepra in
  LESCO_0831, disco in IESCO_0342). None is the failure smoke test 3 found, an Electric Inspector's or a
  party's figure credited to NEPRA's own finding or order.
- The quote check failed 393 of 955 quotes, and dropping them lowers value accuracy to 115 of 168
  (68.5%). Diagnosis: most of these PDFs' text layers are old OCR with errors ("penod" for "period",
  "Rs 6552 320"), so a correct quote from the image does not match the text layer (256 partly found,
  72 not found, 64 where a number is not in its quote, 1 on another page). The check measures the text
  layer more than the reader.

What follows for the product: speaker attribution needs a clearer rule (finding and order, versus
narrative) before it can be scored, and a quote check needs a clean reference text (the page image read
again, or a better OCR), not the PDF's own text layer. Both are new work and would be tested on
decisions outside these 40.

Files: `results/e4b-e6.json` (stems, codes and counts only); readings in `eval-data/decisions/` (local).

## After the full re-read of the labels (22 October 2026)

Re-scored with the corrected labels (`e4b-e6-relabelled.json`): E4b 11 of 31 (35.5%), strict 3 of 15; E6
unchanged (154 of 168 values; 8 decisions with a speaker disagreement). See `E4A.md` for the re-read.
