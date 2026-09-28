# RESULTS: N1 harness controls and N2 baseline detection (CHB-MIT chb01, chb03, chb10)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Coder-verifier, 2026-09-26. Status: NOT YET REVIEWED (HIVE rule 8: an independent reviewer must check code\ before any of this reaches a report).

## Verdicts

| prereg | verdict | basis |
|---|---|---|
| **N1** | **FAIL** | (a) PASS, **(b) FAIL**, (c) PASS, (d) PASS, (e) PASS. N1 is PASS only if all of (a)-(e) pass. |
| **N2** | **not verifiable: code (harness not validated)** | Rule: N2 counts only if N1 passes. The decision-rule result itself would be **INCONCLUSIVE** (chb01 INCONCLUSIVE, chb03 INCONCLUSIVE, chb10 PASS; no FAIL). |

## N1 details (results\N1_verdict.json, N1_ab.json, N1_cde_synthetic.json; figure figures\N1_controls.png/.svg)

**(a) Positive leak control: PASS through the ceiling clause** (predicted: PASS by mean D, +0.06).
| subject | honest AUROC | leaky C2a AUROC | D | E = (1-leak)/(1-honest) | C2b (normaliser on train+test) |
|---|---|---|---|---|---|
| chb01 | 0.9835 | 0.9969 | +0.013 | 0.19 | 0.9851 |
| chb03 | 0.9891 | 0.9994 | +0.010 | 0.06 | 0.9893 |
| chb10 | 0.9748 | 0.9906 | +0.016 | 0.38 | 0.9745 |
The mean D is +0.013, which is below 0.05. The ceiling clause applies because the mean honest AUROC is 0.982 (>= 0.95) and the mean E is 0.21 (<= 0.50). D > 0 in 3 of 3 subjects. So (a) passes: the random window split still more than halves the window-level error.

**(b) Negative controls: FAIL** (predicted PASS, P = 0.85). R = 10 replicates, with no budget fallback.
- NC1 (i.i.d. permutation): grand mean AUROC 0.4545, which is inside [0.45, 0.55]. Subject means are 0.422, 0.447 and 0.494, all inside [0.35, 0.65]. So criterion 1 is met.
  Criterion 2 fails: the pooled TP is **67/120**, above the shift-null 99th percentile of **65** (null mean 61.6).
  Many NC1 replicates chose tau = 0.05 and then alarm almost all the time (chb03: TP 4 and FP 90 in 9 of 10 replicates).
- NC2 (circular shift): **grand mean AUROC 0.353, outside [0.45, 0.55]**. Subject means are chb01 **0.116** (outside [0.35, 0.65]), chb03 0.555 and chb10 0.387.
  Criterion 2 also fails: pooled TP is **20/120**, above the null 99th percentile of **15.0** (null mean 9.85).
- C3 random alarm (the N2 model's own alarms, circularly shifted, 1,000 draws): the **mean pooled event F1 is 0.081, above the 0.05 limit** (95th percentile 0.164). Mean pooled TP is 1.56 of 12 seizures.
- Possible explanations. These are NOT verified and are for the methodologist; no code bug was found.
  (i) NC2 keeps the real seizures in training but labels them as negatives. A linear model can then learn "seizure-like = negative", which gives an AUROC well below 0.5. The same effect appeared on synthetic data before the real run (logged in DEVIATIONS.md).
  (ii) With only 3.6-8 test hours per subject and a low alarm count, one random alarm per file lands within the -30/+60 s tolerance often enough to give F1 around 0.08.
  (iii) The NC1 excess (67 vs 65) is marginal and comes from near-always-alarm null models.
  Under N2 §8 only bug fixes are allowed, and none was identified, so no fix round was used. Any change to these criteria needs a new prereg.

**(c) Determinism and provenance: PASS.**
- All 53 inputs (29 EDF, 21 .seizures, 3 summaries) match both the manifest and PhysioNet's SHA256SUMS.
- The split hash is 433d818f...f1e2, equal to the prereg.
- Two fresh-process real runs gave an identical card SHA-256 (run card cf2913d8...; the 3 subject cards also match). The synthetic rerun was identical too.
- The prereg hashes were computed before the first test-label read.

**(d) Forbidden operations: PASS.** All 12 violations are caught with named exceptions: F1-F9, S1, S5 and S7.
- 15 violation tests: F2, F3 and F4 each have 2 tests, and F7 has 2 parametrised columns.
- Every guard was called on the real run and none raised. Call counts: F1 901, F2 164, F3 26,713, F4 1,471, F5 82, F6 63, F7 1, F8 517, F9 26,566, S1 3, S5 3, S7 1.

**(e) Scorer equivalence: PASS.** Fixture X1-X12 was reproduced exactly by both timescoring 0.0.7 and the re-implementation, including latencies of +4 s and -15 s on X12. On 1,000 random pairs (stream 5) the two scorers gave identical results in 1,000/1,000.

## N2 details (results\N2_results.json, N2_run_card.json, results\cards\, figures\card_chb*.png/.svg)

| subject | TP/N_ref | sens (CP 95%) | FP / H | FA/24h (Garwood 95%) | F1 | median latency | window AUROC (file boot 95%) | AUPRC (chance) | tau* | decision rule | prediction |
|---|---|---|---|---|---|---|---|---|---|---|---|
| chb01 | 4/4 | 1.00 [0.40, 1.00] | 5 / 3.65 h | 32.9 [10.7, 76.8] | 0.62 | 3 s | 0.984 [0.979, 0.991] | 0.748 (0.025) | 0.05 | INCONCLUSIVE (FP 4-8) | 4/4, FP 2, AUROC 0.95 |
| chb03 | 4/4 | 1.00 [0.40, 1.00] | 9 / 8.00 h | 27.0 [12.3, 51.3] | 0.47 | 2.5 s | 0.989 [0.977, 1.000] | 0.841 (0.007) | 0.05 | INCONCLUSIVE (FP 9-14) | 3/4, FP 6, AUROC 0.92 |
| chb10 | 4/4 | 1.00 [0.40, 1.00] | 0 / 8.01 h | 0.0 [0, 11.1] | 1.00 | 2 s | 0.975 [0.953, 0.998] | 0.925 (0.009) | 0.06 | PASS | 3/4, FP 10, AUROC 0.92 |

- Flags: every subject is flagged "CI uninformative (N_ref = 4)". chb01 and chb10 are also flagged "FA on peri-ictal data only".
- N_ref = 4 in every subject, as expected. All LR fits converged, and every test window was scored.
- The buffer dropped 3 windows each in chb01 and chb03, and 0 in chb10 (see D1).
- Sensitivity and window AUROC exceeded the predictions. False alarms were the weak point in chb01 and chb03, and chb10 was the best subject rather than the worst, which is the opposite of the prediction.
- tau* sits at the bottom of the grid (0.05) for chb01 and chb03.
- **S-a, cross-patient (descriptive):**

  | held-out subject | sensitivity | FA/24h | AUROC |
  |---|---|---|---|
  | chb01 | 5/7 | 0.0 | 0.912 |
  | chb03 | 4/7 | 19.6 | 0.948 |
  | chb10 | 7/7 | 171 | 0.890 |

  chb10 is the worst on FA, as predicted.
- **S-b, future-leak:** non-causal minus causal is +0.006 mean AUROC and +0.147 mean event F1. The criterion is > 0 on either, so the leak demonstration holds.

## Deviations, versions, runtimes
- **Deviations and interpretations:** DEVIATIONS.md D1-D18, written before the real run. No locked value was changed. The ones that matter most:
  - D1: the buffer rule is applied literally (last 3 windows).
  - D7/D8: the chance null and C3 use circular shifts scored by the re-implementation, which (e) validated.
  - D9: the NC1 1-Hz mask is derived from the permuted window labels.
  - D11: S-b uses all 8 chb03 test files.
  - D14: the re-implementation author had seen timescoring's method names but not their bodies.
- **Code change after the synthetic phase:** run_n1.py (figure code only) was edited after the synthetic phase, so its hash differs between N1_cde_synthetic.json and N1_verdict.json. No other file changed between the two real runs.
- **Environment:** Python 3.12.10, numpy 2.5.3, scipy 1.18.1, timescoring 0.0.7 (installed; the only install), matplotlib 3.11.2, pytest 8.4.2. BLAS threads = 1, seed 20261001.
- **Tests:** pytest 54/54 passed (15 deliberate-violation tests + the honest-silence test + 38 unit/fixture tests).
- **Runtimes:**
  - N1 synthetic phase: 64 s.
  - N2 real run 1: 738 s (12.3 min, within the 20-min budget). By stage:

    | stage | seconds |
    |---|---|
    | features | 26 |
    | N2 primary | 12 |
    | N1 (a) | 6 |
    | N1 (b) | 357 |
    | S-a | 48 |
    | S-b | 287 |

  - N2 real run 2 (rerun): 637 s.
  - Peak RAM was 696 MB in each run, under the 1.5 GB limit.
- **Harness module:** code\nfharness\. Modules: config, errors, data, splits, windows, features, labels, model, postprocess, scoring, stats, pipeline, provenance, card. Scripts: code\run_n1.py and code\run_n2.py. Tests: code\tests\.
