# E7 timing run: 10 Saraiki dev clips (2026-10-21)

Purpose: measure speed and cost before asking for the full E7 run. Dev split only (the threshold is
set on dev; the test split is untouched). Common Voice 27 Saraiki, first 10 rows of `dev.tsv`.
Transcripts are kept outside the repository (Common Voice terms: no re-sharing).

| | omniASR_LLM_7B_v2 | omniASR_LLM_1B_v2 |
|---|---|---|
| Seconds per clip (batch of 8, wall time / clips) | 0.55 | 0.44 |
| Mean CER, 10 clips | 16.2% | 14.5% |

- Whole run, both models loaded and run once: $0.020 of Modal credit (billing report), so start-up is
  about a minute of GPU time.
- Ten clips is far too few to compare the two models; the 1B ahead here is not a finding.
- Disagreement between the two models tracked error on these clips: the six clips where they
  disagreed on at most 10% of characters had 7B CER of 0 to 13%; the four with higher disagreement
  had 17 to 47%. Indicative only at n = 10; E7 tests this on the full splits.
- Clips went in as mp3 and are converted to 16 kHz mono WAV with ffmpeg inside the container (the
  pipeline's own decoder read them as empty).
