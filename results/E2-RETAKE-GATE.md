# E2 follow-up: a retake gate for badly damaged photos (2026-10-27)

E2 missed: 1.65% wrong among accepted fields against a 1% target, and every wrong field was on a damage
level 3 photo (`results/E2.md`). This adds a free check that runs before any model call and asks the
person to take the photo again when it is too blurred or too small to read. Set up in the pre-registration
amendment of 27 October 2026, written before the gate touched any test-half image, real bill or fresh image.

## The gate

`sahibill/readers/quality.py`. The photo in grey, scaled to a long side of 1200 pixels; sharpness is the
variance of the Laplacian divided by the squared 5th-to-95th percentile contrast, times 1000. Under **3.0**
the photo is refused. No model call, about 0.04 s on a full phone photo.

Chosen on the 100 calibration-half images only. Rule: keep every calibration photo at levels 0 to 2, then
refuse as many level-3 photos as that allows. Variants tried on calibration only: the Laplacian score at
800, 1000, 1200 and 1600 pixels, a gradient-energy score and a median-filtered Laplacian; all left about one
level-3 photo above the weakest level-2 photo, and 1200 pixels was chosen. On calibration, 3.0 keeps 75 of
75 photos at levels 0 to 2 and refuses 23 of 25 at level 3.

## Test half, from the existing readings (no new spend)

The gate kept 75 of 75 photos at levels 0 to 2 (predicted at least 98%) and refused 24 of 25 at level 3
(predicted at least 80%). **Both met.** The one level-3 photo kept (`syn0029_L3`, sharpness 3.64) carries
the only wrong field left in the Spark Open + consistency arm.

| Arm | Without the gate: coverage, wrong among accepted | With the gate: coverage, wrong among accepted |
|---|---|---|
| Spark Open alone | 95.1%, 113 (7.28%) | 75.9%, 9 (0.73%) |
| Glimmer alone | 94.1%, 125 (8.14%) | 74.9%, 2 (0.16%) |
| Spark Open + consistency (what the live product runs) | 88.0%, 41 (2.86%) | 75.0%, 1 (0.08%) |
| **Spark Open + Glimmer + consistency (pre-registered)** | **85.5%, 23 (1.65%)** | **74.4%, 0 (0.00%)** |

The without-gate column reproduces `results/E2.md` exactly. Coverage is accepted fields over all 1,632
printed fields; a refused photo counts as every field unread.

**What this means for E2.** The accuracy half of the target is now met: 0 wrong among accepted, at most 1%
predicted. **The coverage half is now missed:** 74.4% against 85%, as the amendment said it would be before
scoring. The gate does not make level-3 photos readable. It stops them from being read, and the person is
asked for a better photo. E2 as first pre-registered stays a miss, and is reported as one.

## The author's 12 real bill photos (E8)

All 12 accepted (predicted all 12). **Met.** Their sharpness runs from 47 to 83, far above 3.0, so the gate
costs these photos nothing. It also means the gate has not been tested on a genuinely bad real photo: E8
had none, and the threshold comes from synthetic damage.

## Fresh synthetic set (seed 20261027, 4 bills at levels 0 to 3, 16 images, never seen)

The gate kept 12 of 12 at levels 0 to 2 and refused 4 of 4 at level 3 (predicted all kept, at least 3 of 4
refused). **Met.** Spark Open read all 16 with the E1 stage 2 settings (reasoning low, straighten and
re-read) for **$0.1866**.

| Arm | Without the gate | With the gate |
|---|---|---|
| Spark Open alone | 93.4%, 14 wrong (5.86%) | 75.0%, 1 wrong (0.52%) |
| Spark Open + consistency | 88.7%, 8 wrong (3.52%) | 75.0%, 1 wrong (0.52%) |

With the gate and the consistency layer: 1 wrong among 192 accepted, under the predicted 1%. **Met.** The
wrong field is a due date read as 26 October for 28 October on a level-2 photo (`syn0003_L2`, sharpness
4.04, close to the threshold) and the consistency layer does not catch it. This is the first wrong value
accepted on a level-2 photo in any run so far.

What the four refused photos would have given (description): after the consistency layer, 28 of 64 fields
right, 7 wrong, 29 held or unread, and 9 of 48 history months right. Refusing them was the right call.

## Weaknesses found

- On a washed-out, blurred photo the score can rise: 8-bit rounding noise divided by a small contrast looks
  like detail. A blurred test page at half contrast scores 7.6 and passes. The synthetic level-3 photos
  (contrast 0.75) were still refused, but a faded real photo might not be. Recorded as a strict expected
  failure in `tests/test_quality.py`.
- The score depends on how much print is on the page, so the 3.0 threshold is tied to bill-like pages. A
  photo of something else is not what it is for.
- Two fresh level-2 photos sat at 3.5 and 4.0, near the threshold. A real phone photo that is a little worse
  than level 2 will be refused, and the person will be asked again.

## Cost

$0.1866 of new Nebius spend (cost log 2.2468 before, 2.4334 after), inside the approved $0.10 to $0.20 and
the $0.25 hard stop. The test-half and real-photo results cost nothing.

Files: `eval/gate.py` (scorer), `results/e2-gate.json` (test half per photo and per arm),
`results/e2-gate-fresh-reads-spark*.json` (fresh set). Fresh images and readings stay in
`eval-data/synth-fresh-20261027/` (not committed, like the other evaluation images).
