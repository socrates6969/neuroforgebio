# Platform features fed by the neurobiology program (queen -> build team). Owner: Marius Carlsson. Updated 2026-09-26 (cycle 1)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Software intended for diagnosis, monitoring or treatment decisions may be a medical device
under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. These features are for research evaluation of algorithms, not for patient decisions.

Reference implementation: research\neurobiology\code\nfharness\ (pure numpy/scipy + timescoring 0.0.7, MIT). Tests: code\tests\ (54 pytest).
Status key: VERIFIED = passed its preregistered check AND independent review (code\REVIEW_N1_N2.md). PENDING = redesign in cycle 2.

| # | Feature | What it does | Status | Evidence |
|---|---|---|---|---|
| 1 | Leak-proof split engine | Patient-wise / causal chronological splits, hashed and locked before test labels are read; boundary buffer; a no-window-straddle guard | VERIFIED | N1 (a) plus review item 1 |
| 2 | Forbidden-operation guards | Raise named errors for F1-F9, S1, S5 and S7 (normaliser/threshold fitted on test data, straddling windows, test-ID in training folds, and so on) | VERIFIED | N1 (d): 12/12 violations caught; guards active on the real run |
| 3 | Positive leak control ("leak meter") | Re-scores the same model under a deliberately leaky split and reports the inflation | VERIFIED | N1 (a): leaky split halves window error in 3/3 subjects |
| 4 | Event scorer (SzCORE defaults) | Any-overlap, -30/+60 s tolerance, 90 s merge, 300 s split; FA/24 h; latency | VERIFIED | N1 (e): equals timescoring 0.0.7 on a fixture plus 1000/1000 random pairs; exact independent recompute |
| 5 | Uncertainty | Clopper-Pearson for sensitivity, Garwood for FA rate, file/seizure bootstrap. Few-cluster rule: per-subject verdicts, pooled CIs descriptive only | VERIFIED | review item 2 |
| 6 | Provenance + evaluation card | Input SHA-256 (checked against PhysioNet SHA256SUMS), script and prereg hashes, package versions, seed; bit-identical card on rerun (JSON + Markdown + figure) | VERIFIED | N1 (c), review item 5 |
| 7 | Negative-control suite | Phantom-seizure window-arm null (formal leak gate: a planted leak must trip it); pooled SigmaF1 conditional-randomisation event-arm null (validity only); exact random-alarm null C3'; code-level select_tau guard | VERIFIED (N3, blind, fresh subjects, reviewed). Limitation: with <= 4 test seizures per subject the event arm has no power (0.59/0.31 at 2 x 4), so the card must report its power, not just its p-value | N1b FAIL (power), N3 PASS, REVIEW_N3 |
| 8 | Baseline detector (line length + band power, L2 LR, 4-of-5 smoothing) | Reference model for benchmarking vendor algorithms | NOT VERIFIED as a performer. Confirmatory result on fresh subjects is INCONCLUSIVE: chb23 PASS (4/4, FP 1 in 4.0 h), chb24 FAIL (4/4, FP 8 in 2.0 h). Use it only as a pipeline reference, not as a performance claim | N3, REVIEW_N3 |

## Harness decision (lead-accepted, 2026-09-26)
Canonical platform core = **nf_eval** (research-lab-lead, feature/research-algos). **nfharness** = the reviewed golden oracle.
Port from nfharness into nf_eval, with tests: the timescoring-oracle test, Garwood CIs, latency, the F1-F9/S7 guards, the leak meter,
input provenance, the by-file bootstrap, and the N3 negative-control suite (feature 7). nf_eval needs its own independent review before it is canonical in
production. Ten conventions (FA denominator, time grid, duration units, and so on) must be locked in a platform spec: notes\harness_decision_audit.md.

Build notes:
- The FA denominator includes seizure time (timescoring convention). Scoring convention alone changes FA by about 100x, so the card must state the convention.
- chb01 and chb21 are the same patient, so any split must keep them together (the patient-identity map is a platform requirement).
- Owner-gated datasets (TUSZ, Epilepsyecosystem, IEEG.org, EPILEPSIAE) are not used.
