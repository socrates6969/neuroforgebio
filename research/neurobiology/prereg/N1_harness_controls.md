# N1: Pre-registration of harness controls (leak-proofness, sensitivity, determinism, forbidden operations, scorer equivalence)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Author: mathematician/methodologist, 2026-09-26. Status: LOCKED at the time of writing. Changes go to code\DEVIATIONS.md.
Harness rules S*/F*/C* refer to notes\harness_requirements.md. The "baseline" is the N2 pipeline exactly as locked in
prereg\N2_baseline_detection.md (features, normaliser, L2 logistic regression C = 1, k-of-n 4/5, tau rule, split hash
433d818f...f1e2). Seed 20261001 with the RNG streams listed in N2 §8.

**Blindness statement.** No model result on CHB-MIT signals existed when this was written. Only annotations were used.

**Rule.** N1 is PASS only if every part (a)-(e) is PASS. Any FAIL means "the harness cannot be trusted": every model claim (N2 and later)
is reported as "not verifiable: code". Parts (c)-(e) run first, on synthetic data and fixtures, before any real-data model fit.
Parts (a)-(b) run on the real data in the same run as N2 (they need test labels, which only the scorer reads).

---

## (a) POSITIVE leak control: the harness must be able to see leakage

**Honest arm.** The N2 primary causal split; window AUROC on the test windows of each subject (raw p_i, N2 window-label rule).

**Leaky arm (C2a).** Same subject, same features, normaliser and classifier, but a random window-level split: every 2-s window of
every file of the subject is assigned to train independently with probability p_s = the honest training fraction of windows
(chb01 0.657, chb03 0.273, chb10 0.429), RNG stream k = 0. Overlapping windows (1-s step) therefore land on both sides of the split,
and every seizure contributes to training. No buffer. The normaliser is fitted on the leaky training windows. This arm runs with an
explicit `allow_random_split=True` flag; the same call without the flag must raise (S5, tested in (d)).

**Secondary leaky arm (C2b), descriptive only.** Honest split, but the z-score normaliser is fitted on train + test windows.

**Criterion (fixed).** Let D_s = AUROC_leak,s - AUROC_honest,s and E_s = (1 - AUROC_leak,s) / (1 - AUROC_honest,s).
- PASS if [mean_s D_s >= 0.05] OR [mean_s AUROC_honest,s >= 0.95 AND mean_s E_s <= 0.50] (ceiling clause: when the honest AUROC is
  already >= 0.95, a +0.05 gain is nearly impossible, so the leak must instead at least halve the window-level error),
  AND D_s > 0 in at least 2 of the 3 subjects.
- Otherwise FAIL: the harness (with this baseline) does not reveal leakage, so its "leak-proof" claim is untested.
The 0.05 margin is the NB2 F1 value; the reference inflation sizes are +14 pp accuracy on Siena (M11) and ~80% vs ~50% (M14).

**Prediction.** Honest mean AUROC 0.93 (per subject 0.92-0.95, see N2 §6); leaky mean AUROC 0.99; mean D = +0.06; P(PASS) = 0.75.
Main risk: a linear model with 133 parameters memorises little, so the gain from random splitting may be small. That outcome is a real
FAIL of this control, not something to re-define away; the only permitted follow-up is a new prereg.

## (b) NEGATIVE controls: label shuffle and circular shift

Both use the N2 primary causal split and the full N2 pipeline (including the tau rule on training OOF scores), with training labels replaced:
- **NC1 i.i.d. permutation** of the training window labels (same number of positives), RNG stream k = 1.
- **NC2 circular shift** of each training file's 1-Hz label sequence by an offset drawn uniformly from {600, ..., T - 600} s
  (so a shifted seizure lands >= 10 min from its true position; seizure-free files stay all-zero), stream k = 2.
- R = 10 replicates of each per subject (fallback R = 5 only under the N2 §8 budget rule). Test labels are never altered.

**Criteria (all must hold, separately for NC1 and NC2).**
1. Window AUROC: the grand mean over 3 subjects x R replicates lies in [0.45, 0.55] (NB2 F1 band), and each subject's mean over its
   R replicates lies in [0.35, 0.65]. (A single null replicate can land far from 0.5, because a random direction in feature space can
   correlate with ictal power; hence the replicate mean.)
2. Event sensitivity near chance: chance is estimated from the control's own hypothesis. For each replicate and test file, the
   hypothesis mask is circularly shifted by 1,000 random offsets (stream k = 4) and rescored; the pooled TP count over the 12 test
   seizures x R replicates must not exceed the 99th percentile of the pooled shifted TP counts. This matches the alarm rate exactly
   (harness C3), including degenerate "always alarm" or "never alarm" nulls.
3. Random-alarm control (C3): alarms at random times with the N2 model's own alarm rate give pooled event F1 <= 0.05 (NB2 F2).

**Predictions.** NC1 grand mean AUROC 0.50 (per-subject means 0.42-0.58); NC2 0.50 (0.40-0.60); pooled null sensitivity equal to the
chance rate, about 0.04 at 1 alarm per hour (N2 §7), and never above the 99th percentile; random-alarm F1 about 0.01. P(PASS) = 0.85.
Main risk: NC2 keeps seizure-length blocks, and if a shifted block overlaps high-artifact periods the per-subject mean may leave
[0.35, 0.65] in one subject.

## (c) Determinism and provenance

1. **Input hashes.** At run start the harness recomputes SHA-256 of all 29 EDFs, 21 .edf.seizures files and 3 summaries, and compares
   them with data\manifests\chbmit_manifest.csv (itself checked against PhysioNet SHA256SUMS.txt). Any mismatch = FAIL, and the run stops.
2. **Split hash.** Recomputed from the manifest; it must equal 433d818f305ba2095ef854b1f7f8b594895ad070f5fc28584a5507bdc7d9f1e2.
3. **Rerun identity.** The full pipeline is run twice in fresh processes (OMP/OPENBLAS/MKL_NUM_THREADS = 1, same seed, same package
   versions). The evaluation-card JSON, serialised with sorted keys and repr() floats, **excluding only** a separate `runtime` block
   (wall time, peak RAM, timestamps, hostname), must have an identical SHA-256. Any byte difference = FAIL.
4. The card records the prereg file hashes (N1, N2) and a timestamp that precedes the first test-label access in the scorer log.

Prediction: PASS (P = 0.95); the only realistic failure is BLAS thread nondeterminism, which the thread pin prevents.

## (d) Forbidden-operation assertions, each with a deliberate-violation unit test

Every assertion lives in the harness (not only in tests) and runs on the real pipeline. For each, one pytest test builds a synthetic
dataset (stream k = 5), deliberately commits the violation, and must see the harness raise a named exception. **PASS = 9/9 violations
caught AND all assertions silent on the honest real run.** A violation test that passes silently = FAIL.

| ID | Assertion in the harness | Deliberate violation in the test |
|---|---|---|
| F1 | The normaliser stores the IDs (file, window) it was fitted on; at apply time, fit_ids intersected with test_ids must be empty. | Fit the z-scorer on train + test windows. |
| F2 | The model config hash (features, bands, C, class weights, k, n, tau grid, FA target) equals the hash of the N2 locked config; the inner-CV / search routine refuses any test-file ID. | Pass a test file into the inner CV; separately change C to 0.5. |
| F3 | The threshold selector accepts only score arrays tagged `train_oof`; tau must come from the locked grid; k, n are 4, 5. | Choose tau on test scores; separately set k = 3. |
| F4 | Every window [start, end) lies inside one file and one partition; no training window ends within B = 10 s of any test-file start or end (absolute subject time). | Build a window spanning a file end; place a training window 5 s before a test file. |
| F5 | Any resampling/augmentation routine receives only training IDs (N2 uses none; the guard still exists). | Oversample positives from the pooled train + test set. |
| F6 | Primary split: max(end time of training files) <= min(start time of test files), per subject. | Move a later file (e.g. chb01_26) into training. |
| F7 | The feature matrix column names are all in the whitelist of 132 signal features (LL and 5 band powers x 22 channels). | Append a `file_index` or `time_of_day` column. |
| F8 | Test labels are readable only through the scorer, which logs a hash of every call; any other read raises. | Read a test file's labels inside the training routine. |
| F9 | timescoring version == 0.0.7 and parameters == (30, 60, 0, 300, 90); scorer parameters are frozen at import. | Score with toleranceStart = 20. |

Also tested (same PASS rule): S5 (a random window split without `allow_random_split=True` raises), S7 (split hash mismatch raises),
S1 (in the cross-patient analysis, set(train_subjects) & set(test_subjects) must be empty; put chb01 on both sides and expect a raise).

Prediction: PASS (P = 0.90); the likely failure is F8, which is hard to enforce in Python and needs a real access-token design.

## (e) Event-scoring equivalence

Primary: timescoring 0.0.7 (MIT), installed by the coder, vs an independent re-implementation of harness §3 written without reading
timescoring's internals beyond M6's description. Fallback if timescoring cannot be installed: the re-implementation vs the hand-computed
fixture below. Either way the fixture must be reproduced exactly (counts equal; rates to 1e-9).

**Hand-computed fixture.** 1-Hz binary masks, a recording of 3600 s, reference seizure R = [1000, 1060) s unless stated.
"hyp" lists the hypothesis events. Tolerance edges are set 1-5 s away from the boundaries so that 10-Hz resampling cannot flip them.

| case | setup | TP | FP | N_ref | sens | FA/24 h |
|---|---|---|---|---|---|---|
| X1 oracle | hyp = [1000, 1060) | 1 | 0 | 1 | 1 | 0 |
| X2 no detections | hyp = none | 0 | 0 | 1 | 0 | 0 (precision NaN) |
| X3 inside pre-tolerance | hyp = [975, 980) (starts 25 s before onset) | 1 | 0 | 1 | 1 | 0 |
| X4 outside pre-tolerance | hyp = [960, 968) (ends 32 s before onset; extended ref starts at 970) | 0 | 1 | 1 | 0 | 24 |
| X5 inside post-tolerance | hyp = [1115, 1119) (extended ref ends at 1120) | 1 | 0 | 1 | 1 | 0 |
| X6 outside post-tolerance | hyp = [1125, 1130) | 0 | 1 | 1 | 0 | 24 |
| X7 merge at 89 s | hyp = [1000, 1060), [2000, 2010), [2099, 2109) | 1 | 1 | 1 | 1 | 24 |
| X8 no merge at 91 s | hyp = [1000, 1060), [2000, 2010), [2101, 2111) | 1 | 2 | 1 | 1 | 48 |
| X9 301-s false alarm | hyp = [1000, 1060), [2000, 2301) (split into > 1 event) | 1 | 2 | 1 | 1 | 48 |
| X10 two refs 40 s apart | R = [1000, 1060) and [1100, 1130) (merged to 1 ref event); hyp = [1110, 1115) | 1 | 0 | 1 | 1 | 0 |
| X11 FA denominator | 7200-s recording, no seizure, hyp = [100, 110), [1000, 1010), [5000, 5010) | 0 | 3 | 0 | NaN | 36 |
| X12 latency | hyp = [1004, 1030): latency +4 s; separately hyp = [985, 990): latency -15 s | 1 | 0 | 1 | 1 | 0 |

If timescoring disagrees with a row, timescoring governs (it is the locked scorer), the disagreement and timescoring's actual rule are
written to DEVIATIONS.md **before** any real-data run, and the re-implementation is corrected to match. X9 (the split of a long
false alarm) is the row most likely to need this.

**Randomised cross-check (only if timescoring is installed).** 1,000 synthetic reference/hypothesis pairs (stream k = 5; 1-4 h,
0-5 seizures of 10-400 s, 0-20 alarms of 1-500 s): timescoring and the re-implementation must give identical TP, FP and N_ref in all 1,000,
and FA rates equal to 1e-9. Latency (computed only by the harness) is checked on X12.

Prediction: PASS (P = 0.85 with timescoring installed; the likely failure is a split/merge edge semantic, fixable before real data).

## Summary of predictions

| part | criterion | predicted value | P(PASS) |
|---|---|---|---|
| (a) positive leak | mean dAUROC >= 0.05 (or ceiling clause), >= 2/3 subjects positive | +0.06 | 0.75 |
| (b) negative | NC mean AUROC in [0.45, 0.55]; sensitivity <= 99th pct of shift null; random-alarm F1 <= 0.05 | 0.50; ~0.04; ~0.01 | 0.85 |
| (c) determinism | identical card SHA-256; hashes match | identical | 0.95 |
| (d) forbidden ops | 9/9 (+S1, S5, S7) violations caught | 12/12 | 0.90 |
| (e) scorer | fixture exact; 1,000/1,000 identical | exact | 0.85 |

P(N1 PASS on the first attempt) is about 0.5; most expected failures are code issues that can be fixed before real data are touched,
except (a) and (b), which are only observable on the real data. Abandonment: see N2 §8 (2 fix rounds, then "not verifiable: code").
