# N2: Pre-registration of a baseline seizure DETECTION model (CHB-MIT chb01, chb03, chb10)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Author: mathematician/methodologist, 2026-09-26. Status: LOCKED at the time of writing. Any change after this point goes to
code\DEVIATIONS.md with a reason, and a change made after any test-label access makes the affected result exploratory.
Source IDs M1-M27 refer to lit\methods.md; numeric facts come from notes\facts.md. Harness rules S*/F*/C* refer to
notes\harness_requirements.md. Companion prereg: prereg\N1_harness_controls.md (N1 must PASS before any N2 verdict counts).

**Blindness statement.** When this was written, no model, feature or score had been computed on any CHB-MIT signal. Only the
annotations (seizure start/end seconds, file durations and header start times, from notes\data\chbmit_selection.csv) were used.

---

## 1. Data and the locked split

Dataset: CHB-MIT v1.0.0 (DOI 10.13026/C2K01R, ODC-By 1.0), the 29 SHA-256-verified EDFs in data\manifests\chbmit_manifest.csv.
Files are ordered by EDF header start time (not file name; see data_subset.md). Windows never cross file boundaries (R0.2).

Primary split (patient-specific, causal): training = every file up to and including the file containing the subject's 3rd
seizure (Shoeb M1: with >= 3 training seizures, < 5% missed); test = every later file.

| subject | train files (chronological) | train h | train sz (ictal s) | test files | test h | test sz (ictal s) | test seizure-free files |
|---|---|---|---|---|---|---|---|
| chb01 | 01,02,03,04,05,06,15 | 7.000 | 3 (107) | 16,18,21,26 | 3.646 | 4 (335) | none |
| chb03 | 01,02,03 | 3.000 | 3 (186) | 04,05,06,07,08,34,35,36 | 8.000 | 4 (216) | 05,06,07,08 (4 h) |
| chb10 | 12,20,27 | 6.008 | 3 (170) | 30,31,38,89 | 8.009 | 4 (277) | none |

Every subject has exactly **4 test seizures**, each in its own file, each 47-101 s long. No test seizure is < 90 s from another or
> 300 s, so the SzCORE merge/split rules should leave N_ref = 4 per subject. If the scorer reports N_ref != 4 for any subject, that
is a harness flag (investigate before reporting).

Test-set window prevalence (2-s windows fully inside a seizure / all test windows): chb01 331/13121 = 2.52%, chb03 212/28792 = 0.74%,
chb10 273/28830 = 0.95%. These are the AUPRC chance levels.

**Split hash (S7).** SHA-256 of the UTF-8 string below (3 lines joined by "\n", no trailing newline) =
`433d818f305ba2095ef854b1f7f8b594895ad070f5fc28584a5507bdc7d9f1e2`
```
chb01;train=chb01_01.edf,chb01_02.edf,chb01_03.edf,chb01_04.edf,chb01_05.edf,chb01_06.edf,chb01_15.edf;test=chb01_16.edf,chb01_18.edf,chb01_21.edf,chb01_26.edf
chb03;train=chb03_01.edf,chb03_02.edf,chb03_03.edf;test=chb03_04.edf,chb03_05.edf,chb03_06.edf,chb03_07.edf,chb03_08.edf,chb03_34.edf,chb03_35.edf,chb03_36.edf
chb10;train=chb10_12.edf,chb10_20.edf,chb10_27.edf;test=chb10_30.edf,chb10_31.edf,chb10_38.edf,chb10_89.edf
```
The harness recomputes this from the manifest and aborts if it differs.

**Buffer (S4).** B = 10 s (>= 2-s window + 4-s smoothing span, rounded up). Training windows whose end lies within 10 s of the start
of any test file are dropped. In practice this removes the last 10 s of the last training file (inter-file gaps are ~7 s).

**Known deviations from SzCORE TSCV (stated here, not in DEVIATIONS.md).** (i) One causal split per subject instead of a growing
1-h TSCV. (ii) chb03 has only 3.0 h of training data (< the 5-h SzCORE minimum) because its first three files each contain a seizure.
(iii) CHB-MIT is bipolar, so results are not comparable with the SzCORE leaderboard (M5, M10).

**Peri-ictal caveat.** chb10 has no seizure-free files at all, and chb01's four test files all contain a seizure. Their test FA rates are
therefore measured on data within about 1-2 h of a seizure, not on remote interictal EEG. Their FA is reported separately and flagged
"peri-ictal only". chb03 is the only subject with remote-interictal test data (chb03_05..08); its FA is also split into seizure-file vs
seizure-free-file parts (descriptive).

## 2. Model (all values locked; F2: no tuning of anything below)

**Channels.** The 23 labelled signals minus index 23 (the duplicate "T8-P8"): 22 bipolar channels in file order. Signals in uV
(edf_reader.py scaling). No filtering, re-referencing or artifact rejection.

**Windows.** Length 2 s (512 samples at 256 Hz), step 1 s, per file. Window i covers [i, i+2) s, i = 0 .. T-2 (T = file duration in s).
Window label = 1 iff > 50% of the window is inside an annotated seizure, which for integer-second annotations means [i, i+2) lies fully
inside [onset, offset). The same rule is used for training labels and for the window AUROC/AUPRC.

**Features (132 = 22 channels x 6, channel-major).** For each channel, x = the window minus its mean.
1. Line length: LL = mean over k of |x[k] - x[k-1]| (511 differences); feature = log10(LL + 1e-3).
2. Band powers: X = rfft(hann(512) * x) (numpy.hanning), P_k = |X_k|^2 at f_k = 0.5 k Hz; BP = sum of P_k with lo <= f_k < hi, for
   bands [1,4), [4,8), [8,13), [13,30), [30,55) Hz (55 Hz upper edge avoids the 60-Hz mains line); feature = log10(BP + 1e-3).
Features are stateless per-window transforms (no fitted parameters), so they may be computed once per file and cached.

**Normaliser (F1).** Per-feature z-score, mean and SD (ddof = 0, SD floor 1e-8) fitted on the training windows only, then frozen.

**Classifier.** L2-regularised logistic regression, minimising
sum_i w_i * log(1 + exp(-y_i (beta . z_i + b))) + ||beta||^2 / (2C), with C = 1.0, unpenalised intercept, balanced class weights
w_i = n / (2 n_{class(i)}), initialised at zero. Either sklearn LogisticRegression(C=1.0, class_weight="balanced", solver="lbfgs",
max_iter=1000, tol=1e-6) or scipy.optimize.minimize(method="L-BFGS-B", gtol=1e-6, maxiter=1000) on the same objective. The coder records
which. Non-convergence within max_iter is logged, not retried with other settings.

**Post-processing (k-of-n, causal).** b_i = 1 if p_i >= tau. d_i = 1 if at least k = 4 of the n = 5 windows i-4 .. i (same file) have
b = 1; d_i = 0 for i < 3. Hypothesis mask at 1 Hz: second j (covering [j, j+1)) = d_{j-1}, the decision of the window that ends at j+1;
second 0 = 0. No extra minimum duration; timescoring merges hypothesis events < 90 s apart.

**Threshold tau (F3, training data only).** Grid tau in {0.05, 0.06, ..., 0.99}. Inner leave-one-training-file-out CV (same features,
normaliser and classifier, refitted per inner fold, on training files only) gives out-of-fold scores for every training window. For each tau
the post-processed OOF hypothesis is event-scored on the training files. tau* = the **smallest** tau whose training OOF false-alarm rate is
<= 12 per 24 h (half the test bar, as a margin for train-to-test shift). That allows at most 3 FP in chb01 (7.0 h), 1 FP in chb03 (3.0 h)
and 3 FP in chb10 (6.0 h). If no tau qualifies, tau* = 0.99. The final model is then refitted on all training windows and applied with tau*.
The inner CV uses later training files to score earlier ones; that is allowed because it never touches test files.

## 3. Scoring (locked; F9)

timescoring == 0.0.7, EventScoring.Parameters(toleranceStart=30, toleranceEnd=60, minOverlap=0, maxEventDuration=300,
minDurationBetweenEvents=90), and SampleScoring at 1 Hz. Each test file is scored separately (files are separated by unrecorded gaps,
so an alarm must not merge across them). Per subject, TP, FP, N_ref and scored duration H are **summed over test files**; per-file scores
are never averaged. (This implements harness §3 "append in time" without cross-gap merging; it is a clarification, not a change.)

Per subject: event sensitivity TP/N_ref; FA/24 h = 24 FP/H (H includes seizure time); precision TP/(TP+FP); F1; latency per TP
(harness definition, can be negative to -30 s; median, IQR, fraction <= 10 s); sample-based sensitivity/precision/F1; window AUROC and
AUPRC from the raw (unsmoothed) p_i on all test windows, with the prevalence shown.

**Intervals (within subject).**
- Sensitivity: bootstrap by seizure event (resample the 4 TP/FN indicators with replacement, B = 10,000, percentile 95%), plus the
  Clopper-Pearson 95% interval. With n = 4 the bootstrap is degenerate (4/4 gives [1, 1]), so Clopper-Pearson is the one to read:
  3/4 -> [0.194, 0.994], 4/4 -> [0.398, 1.000], 2/4 -> [0.068, 0.932].
- FA rate: exact Poisson (Garwood) 95% interval on the FP count, lower = chi2(0.025; 2k)/2, upper = chi2(0.975; 2k+2)/2, divided by H.
  For H = 3.646 h (chb01), k = 0 already has an upper bound of 24.3/24 h.
- Window AUROC: block bootstrap over test files within the subject (B = 10,000), descriptive.
- Any across-subject mean with a CI is labelled **descriptive** (3 clusters; M22 over-rejection with 5-30 clusters). The NB2 rule
  "95% bootstrap CI over patients > 0" is **not used**; it is replaced by the per-subject rule below.
- **CI-validity flag**: any subject with N_ref < 10 test seizures gets "CI uninformative (N_ref = 4)". All three subjects carry this flag;
  the verdict below is a pre-registered decision rule on point estimates, not a significance test.

## 4. PASS / FAIL / INCONCLUSIVE (per subject)

**Bars.** Event sensitivity >= 0.75 AND FA <= 24 per 24 h (1 per hour).

Justification from facts.md: Shoeb & Guttag 2010 (M1) reached 96% of 173 seizures, median 2 FD/24 h, worst patient 20 FD/24 h, but with an
RBF-SVM, 3-epoch stacking, >= 24 h of non-seizure training EEG and a **non-causal** leave-one-record-out protocol, which M12 shows
inflates event F1 by 3-7% relative to causal TSCV. Our baseline is linear, causal, and trained on 3-7 h with exactly 3 seizures. So the
sensitivity bar sits about 20 pp below Shoeb, and 0.75 is the only grid point between 0.5 and 1.0 when there are 4 test seizures (it means
>= 3 of 4 detected). The FA bar is 12x Shoeb's median and just above his worst patient; it is also above the held-out top-5 range of
1.34-14 FP/day in M10. It is a deliberately modest bar for a "harness reference baseline", not a clinically useful detector.

**Decision grid (fixed now; FP counts per subject, from the Garwood table computed on the test hours above).**

| component | meets bar | inconclusive zone | FAIL |
|---|---|---|---|
| sensitivity (of 4) | 3/4 or 4/4 | 2/4 | 0/4 or 1/4 |
| FP count, chb01 (H = 3.646 h) | <= 3 (<= 19.7/24 h) | 4-8 | >= 9 (Garwood lower bound > 24/24 h) |
| FP count, chb03 (H = 8.000 h) | <= 8 (<= 24.0/24 h) | 9-14 | >= 15 |
| FP count, chb10 (H = 8.009 h) | <= 8 | 9-14 | >= 15 |

- **PASS**: both components meet the bar.
- **FAIL**: either component is in its FAIL column.
- **INCONCLUSIVE**: anything else; also, regardless of the numbers, if N_ref < 3 for the subject ("too few test seizures for a CI or a
  verdict"), or if the model did not produce scores for all test windows.
- chb10 and chb01 verdicts carry the flag "FA on peri-ictal data only"; chb10 FA is also reported in its own table row, never pooled
  silently with chb03.

**Overall N2 verdict.** PASS if >= 2 subjects PASS and none FAIL; FAIL if >= 2 subjects FAIL; otherwise INCONCLUSIVE.
N2 counts only if N1 is PASS; otherwise the N2 card says "not verifiable: code".

## 5. Secondary analyses (descriptive, no verdict)

**S-a. Cross-patient leave-one-subject-out (3 folds).** Train on all files of two subjects, test on all files of the third (7 seizures,
10.65 / 11.00 / 14.02 h). Same features, normaliser (fitted on the two training subjects), classifier; tau* chosen by the same FA <= 12/24 h
rule on inner leave-one-training-subject-out scores (2 inner folds). Reported per held-out subject with the same metrics; no bar
(facts.md: no event-scored cross-patient CHB-MIT reference exists). chb21 is not used, so the chb01/chb21 identity is not an issue.

**S-b. Future-leak variant (N2 leakage demonstration).** For each causal test file f of a subject, train on all other files of that subject
(including later test-period files; Shoeb-style leave-one-record-out, non-causal), choose tau by the same rule with inner leave-one-file-out
on those files, and score f. Summed over the same 4 test files per subject, so the test data are identical to the primary analysis.
**Must look better than causal**: mean over subjects of (AUROC_future - AUROC_causal) > 0 OR mean (F1_future - F1_causal) > 0.
If neither holds, the N2 card reports "leak demonstration failed" and N2 becomes "not verifiable: code" until explained.

**S-c. Label-shuffle controls** (i.i.d. permutation and within-file circular shift) are specified and judged in N1 §(b); their
per-subject results are also printed in the N2 card.

## 6. Predictions (made blind; numbers)

| quantity | chb01 | chb03 | chb10 |
|---|---|---|---|
| window AUROC (causal) | 0.95 (0.88-0.99) | 0.92 (0.80-0.98) | 0.92 (0.80-0.98) |
| window AUPRC (chance) | 0.45 (0.025) | 0.25 (0.007) | 0.30 (0.010) |
| event sensitivity | 4/4 | 3/4 | 3/4 |
| FP count (FA/24 h) | 2 (13) | 6 (18) | 10 (30) |
| median latency | 8 s (range -5 to 25 s) | 10 s | 10 s |
| P(PASS) | 0.60 | 0.50 | 0.35 |

Overall: expected number of passing subjects about 1.5; P(overall PASS) about 0.40, P(overall FAIL) about 0.15, the rest INCONCLUSIVE.
chb10 is predicted to be the worst on FA because its non-seizure data are peri-ictal and it is a 3-year-old (more movement artifact).
chb03 is predicted to lose sensitivity on chb03_34-36, recorded about 2.5 days after its 3 h of training data.
Cross-patient (S-a): window AUROC 0.80 (0.65-0.90) per held-out subject, sensitivity about 0.5, FA 30-150/24 h; chb10 (3 y, vs 11 y and
14 y) worst. Future-leak (S-b): +0.02 AUROC and +0.10 event F1 over causal (M12 range: +3-7% F1).

## 7. Why the result is not guaranteed by construction

- The test files are later in time and never seen by the normaliser, classifier or threshold; tau* is set on training OOF scores only.
- The joint bar excludes both trivial detectors: "always alarm" has sensitivity 1 but, after 90-s merging and 300-s splitting, about
  12 FP per hour (288/24 h); "never alarm" has FA 0 but sensitivity 0.
- A random alarm process running at exactly the FA bar (1 per hour) detects a seizure of duration d with probability about
  1 - exp(-(d + 90 s)/3600 s) = 0.032-0.052 for d = 27-101 s. So P(>= 3 of 4 by chance) is about 1e-4 to 5e-4 per subject.
- Real risks of failure: the non-stationarity between training and test (chb03's 2.5-day gap; chb10_89 is about 4.7 days after the last chb10 training file), artifacts
  (chewing, movement) with high line length, and only 3 training seizures with a linear model.

## 8. Abandonment and resource rules

- If N1 fails, N2 is not reported as a model result. Bug fixes are allowed (logged in DEVIATIONS.md) but may not touch any locked N2 value.
  After 2 fix rounds with N1 still failing, the cycle-1 baseline is abandoned and reported as "not verifiable: code".
- If N2 is FAIL or INCONCLUSIVE, the result is reported as such. The model is **not** tuned on these test files. The test files of chb01,
  chb03 and chb10 are then "burned": any new model (N3) is pre-registered anew and its confirmatory test uses subjects not yet downloaded
  (the E1-E4-eligible chb02, 05, 06, 07, 08, 23; requires a new download under the 2 GB cap).
- Budget: peak RAM < 1.5 GB (stream one EDF at a time as int16, convert per channel to float32; features cached as float32, about 70 MB
  for all ~128k windows) and < 20 min CPU for the full run including N1 controls. BLAS threads = 1. If the budget is exceeded, the
  only pre-approved fallback is reducing the shuffle-control replicates from R = 10 to R = 5 (logged). Anything else stops the run.
- Seed 20261001. RNG streams: numpy.random.default_rng(numpy.random.SeedSequence(20261001, spawn_key=(k,))) with k = 0 leak split,
  1 i.i.d. label permutation, 2 circular shift, 3 bootstraps, 4 chance-shift nulls, 5 synthetic fixtures.
- Blindness during development: the coder builds and tests on synthetic EDFs and may read one training file (chb01_01, seizure-free) to
  check the reader and feature shapes. No classifier is fitted on real data and no test label is read before this prereg and N1 are
  hashed into the run log.
