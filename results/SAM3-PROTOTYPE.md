# SAM 3 meter-photo prototype (2026-10-22, approved spend)

Question: when the reader cannot make out the meter photo printed on a bill (all 12 photos of the author's
real IESCO bills in E8), does cutting it out with SAM 3 first let Muse Spark Open read it?

Model: SAM 3 (`facebook/sam3`, Transformers 5.0.0 `Sam3Model`) on a Modal L4, text prompts "electricity
meter" and "digital meter display", confidence at least 0.4. (SAM 3.1 is published only as a checkpoint for
Meta's sam3 package, aimed at video tracking, with no Transformers integration.)

| Photos | Meter photo found | Crop read by Muse Spark Open |
|---|---|---|
| 12 real (6 bills, close-up and casual) | 8 (April to August; none on the May and September photos at 0.4) | 0 of 8: display and stamp returned as unreadable; also 0 of 4 after straightening two crops by 45 degrees |
| 4 synthetic | 4 | 4 of 4: digits and stamp read |

Finding: SAM 3 locates the printed meter photo well, but on these real bills the photo is small and
half-toned, and a phone photo of the whole bill does not carry the digits. The bottleneck is the image, not
the location. Spark Open declined rather than guessed, which is the behaviour wanted.

What this means for the product: use SAM 3 to show the person the meter photo enlarged, with the question
"What number does the meter show?" (they hold the paper bill), or to ask for a close-up photo of just that
part. Both fit "ask instead of accuse". Not built yet.

Cost: Modal $0.026 (SAM 3, one run); Nebius $0.0436 (16 crop reads). Crops and boxes stay in `data-local/`
(they show account numbers).
