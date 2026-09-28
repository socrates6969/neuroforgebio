# RESULTS N3: harness validation on fresh subjects chb23/chb24 (blind prereg) + the locked N2 model re-run

**RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.** Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance and
clinical validation (IRB/ethics approval).

- Coder-verifier, 2026-09-26.
- Prereg: prereg\N3_harness_validation_fresh.md, SHA-256 954e4abb...fc32b. It was locked before the download (results\cards\N3_prereg_lock.json), and every run re-checks it.
- Deviations and interpretations: code\DEVIATIONS.md §N3 (N3-1 to N3-16). They were written before any run.
- **Status: INDEPENDENTLY REVIEWED afterwards (code\REVIEW_N3.md, 2026-09-26): all verdicts CONFIRMED.** (The original text at writing time said "NOT YET INDEPENDENTLY REVIEWED"; queen annotation.)

## Verdicts (strictly per prereg §4, §5)

| item | result |
|---|---|
| **N3 harness** | **PASS**: all 13 §4 items met, no FLAG |
| N2 locked model, chb23 | **PASS**: 4/4 detected, FP 1 in 4.007 h (grid: meets bar at FP ≤ 4) |
| N2 locked model, chb24 | **FAIL**: 4/4 detected, but FP 8 in 2.000 h (grid: FAIL at FP ≥ 6) |
| **N2 overall (N2 rule, S = 2)** | **INCONCLUSIVE** (1 PASS, 1 FAIL) |

- The harness passed, so the model verdict counts. Its label is "N2 locked model, confirmatory on fresh subjects; harness gate pre-registered blind".
- The overall confirmatory result is INCONCLUSIVE. It is not a PASS.
- chb23 and chb24 test files are now **burned**.
- Under §7 there is no tuning on these subjects. The next model needs a new prereg on another open dataset.

## Run facts

- **Data.** The 7 R2 EDFs plus 7 .seizures files and 2 summaries: 16/16 files SHA-256-verified against PhysioNet SHA256SUMS. The manifest was appended (+16 rows). Total raw data is 2.062e9 B (cap 2.10e9).
- **Locked code.** The 17 nfharness/edf_reader/run_n2 hashes equal the N2 run card, and the n1b hashes equal the N1b card. The config hash was recomputed and matches.
- **Pre-run checks.**
  - The montage E1 assertion passed on all 7 EDFs.
  - The split hash equals 9320fa73...
  - The segment table matches §2.2: chb23 train 3.73 h / test 2.40 h; chb24 0.50 / 0.97 h.
  - The FP grids equal the prereg: chb23 (4, 8), chb24 (2, 5).
  - N_ref = 4 for each subject.
- **Tests.** pytest 83/83: 68 existing + 15 new in tests\test_n3.py. The new tests cover:
  - the pooled statistic on a hand fixture;
  - the montage assertion;
  - PL-B-code;
  - chunked-writer byte identity;
  - the null recomputation against n1b;
  - the gate logic;
  - stream rebinding.
- **Synthetic dry run** (stream 26, 100 NC-P replicates): **PASS on the first attempt**.
  - One-sided KS p: T_A up 0.090, T_A lo 0.85, event arm 1.0 / 1.0.
  - Fraction of p-values below 0.05: ≤ 0.06.
  - PL-A T_A Fisher 1.6e-14.
- **Real run** 86 s, peak 1191 MB; **rerun** in a fresh process 123 s. The card SHA-256 excluding runtime was **identical** (ce980b76...5fad22). BLAS threads = 1, seed 20261001.

## Harness gate numbers (real data; 10 NC-P + 5 PL-A replicates per subject, M = 999, M_C = 1000)

| gate item | value | criterion | met |
|---|---|---|---|
| V1-A: NC-P T_A Fisher up / lo (20 reps) | 0.469 / 0.238 | both ≥ 0.0025 | yes |
| V2-A: window-flagged | 0 / 20 | ≤ 1 | yes |
| V1-E: pooled ΣF1 p_up / p_lo (18 retained) | 0.779 / 0.222 (T = 2.082, null mean 2.511) | both ≥ 0.0025 | yes |
| C3' (i): \|MC mean − μ\*\| | \|0.1375 − 0.1352\| = 0.0023 | ≤ 0.0091 | yes |
| C3' (ii): fraction above q95 (0.308) | 0.049 | ≤ 0.0698 | yes |
| **PL-A trips T_A**: Fisher up | **5.9e-16** (mean T_A 0.745) | < 0.0025 | yes |
| PL-B-code | raises ThresholdSelectionError (pytest and in-process on the real test scores) | must raise | yes |
| PL-C: fraction above q95 | 0.419 | > 0.0698 | yes |
| PL-B specificity: T_A p identical to NC-P | 20 / 20 | 20 / 20 | yes |

Descriptive items (not in the gate):
- **NC-P.** T_A replicate mean 0.474 (SD 0.107); subject means chb23 0.452, chb24 0.496.
  - Literal Fisher T_E up / lo: 1.000 / 0.996. Mid-p Fisher up: 0.877. Pooled ΣTP p_up: 0.79.
  - Degenerate replicates: 2/20 (1 per subject, both never-alarm). t_rm saturated at 0.99 in 8/20 replicates.
- **PL-A event arm.** Pooled ΣF1 p_up 0.001 (7 retained).
- **PL-A10.** T_A Fisher up 3.1e-7 (would trip); mean T_A 0.643; pooled ΣF1 p_up 0.159.
- **PL-B.** Pooled ΣF1 p_up 0.001 (tripped). Literal Fisher up 0.094 (does not trip).
- **Model F1 against the random-alarm null.** The N2 model's pooled event F1 is 0.64, above the exact random-alarm q99 (0.40).

## N2 locked model per subject (N2 §3 metrics)

| subject | TP/N_ref | sens (Clopper-Pearson 95%) | FP / H | FA/24 h (Garwood 95%) | window AUROC (file-bootstrap 95%) | AUPRC (prevalence) | tau* | median latency | rule |
|---|---|---|---|---|---|---|---|---|---|
| chb23 | 4/4 | 1.00 [0.40, 1.00] | 1 / 4.007 h | 6.0 [0.15, 33.4] | 0.993 (one test file: CI degenerate) | 0.765 (0.017) | 0.05 | 5 s | **PASS** |
| chb24 | 4/4 | 1.00 [0.40, 1.00] | 8 / 2.000 h | 96.0 [41.4, 189.2] | 0.891 [0.863, 0.920] | 0.277 (0.014) | 0.99 (top of grid) | 7.5 s | **FAIL** |

- Flags on both subjects: "CI uninformative (N_ref = 4)" and "FA on peri-ictal data only".
- chb24 fails on false alarms alone. Its Garwood lower bound, 41.4/24 h, is above 24/24 h.
- The test files are seizure files only, so FA is measured on peri-ictal data.

## Against the blind predictions (prereg §6)

| quantity | predicted | observed |
|---|---|---|
| dry run passes first time | 0.8 | yes |
| NC-P T_A mean (SD) | 0.50 (0.12; chb24 larger, ~0.15) | 0.474 (0.107; chb24 0.105, not larger) |
| NC-P degenerate | chb23 1-4, **chb24 4-9** of 10 | chb23 1, **chb24 1** (miss: t_rm saturated 8/20 but rarely gave never-alarm) |
| PL-A trips T_A; mean T_A | P 0.93; 0.75 (0.65-0.85) | tripped 5.9e-16; 0.745 |
| PL-A10 trips; T_A | P ≈ 0.6; 0.60-0.65 | 3.1e-7 (trip); 0.643 |
| PL-A pooled event p < 0.0025 | P ≈ 0.35 | yes (0.001) |
| PL-B pooled event p < 0.0025; literal Fisher | P ≈ 0.25; ~0.4, no trip | yes (0.001); 0.094, no trip |
| PL-B-code / C3' / PL-C | 0.99 / 0.93 / 0.8 | raised / PASS / tripped |
| **N3 harness PASS** | **P 0.70** | **PASS** |
| chb23 | AUROC 0.93, 3/4, FP 3, P(PASS) 0.45 | 0.993, 4/4, FP 1, PASS |
| chb24 | AUROC 0.88, 3/4, FP 2, P(FAIL) 0.25 | 0.891, 4/4, **FP 8, FAIL** |
| N2 overall | P(INCONCLUSIVE) ≈ 0.79 | INCONCLUSIVE |
| runtime | < 12 min, < 1.2 GB | 1.4 min, 1.19 GB |

## Caveats

- **Detection of planted leaks.** The harness is validated to detect planted label leaks in the window arm, planted threshold leaks at code level, and scorer/alarm leaks (PL-C).
  - It does not detect a label-free leak, such as a normaliser fitted on test data. That remains the job of the F1 guard (§4.4).
- **Small numbers.** S = 2 and N_ref = 4 per subject. Sensitivity intervals are wide ([0.40, 1.00]).
- **chb24.** It has no SUBJECT-INFO row, and its repeat-patient status is UNVERIFIED. Its training allowed time is only 0.5 h.
- **Review (updated by the queen).** Done: code\REVIEW_N3.md confirmed every verdict, and it also covered notes\n3_power.md and power_sim.py (one minor float32 tie-break bug there; no conclusion changes).

## Outputs

- Results: results\N3_card.json, results\rerun\N3_card.json, results\N3_verdict.json, results\N3_synthetic.json, and results\N3_DEVIATIONS_snapshot.md.
- Logs: results\N3_*_stdout.log and results\n3_download.log.
- Cards: results\cards\chb23_N3_card.{json,md} and results\cards\chb24_N3_card.{json,md}.
- Figures (PNG + SVG): figures\N3_controls, figures\N3_synthetic_dryrun, figures\N3_card_chb23 and figures\N3_card_chb24.
- Code: code\n3\ and code\run_n3.py.
