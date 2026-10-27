# Live voice test (2026-10-22, approved spend)

The deployed speech service (Omnilingual ASR 7B and 1B, Modal L4) and the answer step (Muse Spark Open on
Nebius) were run through the product's own API on the author's September 2026 bill. Questions were spoken by
macOS text-to-speech (a Hindi voice for the two Urdu-language questions, since spoken Hindustani is the same
speech; an English voice for the third). This shows the path works end to end; it is not an accuracy test.

| Question (spoken) | Heard | Sure (E7 threshold) | Time to hear |
|---|---|---|---|
| "Is my bill right?" (Hindi voice) | کیا میرا بل ٹھیک ہے | yes, the two models agree exactly | 69.7 s (cold start) |
| "Why is this month's bill higher?" (Hindi voice) | اس مہینے کا بل زیادہ کیوں ہے | yes | 2.4 s (warm); 12.4 s after a warm-up call |
| "Is my bill right, and what should I do next?" (English) | is my bill right and what should i do next | no: English has no measured threshold, so it is shown back to confirm | 2.8 s |

All four answers (one question asked twice) passed the number check: every figure in them is in the bill's
findings. Found and fixed: a 70 s first wait (the panel now starts loading the models when it opens), an
answer to "why higher" that did not compare the units (prompt now says to), and three Devanagari letters
mixed into one Urdu answer (an answer in the wrong script is now refused and replaced by the findings).
Cost: Nebius $0.0172 (4 answers); Modal from the billing report.
