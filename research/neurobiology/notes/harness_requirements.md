# Leak-proof evaluation harness + evaluation card: requirements (seizure DETECTION, cycle 1)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Author: methods-lit, 2026-09-26. Source IDs (M1-M27) refer to `lit\methods.md`. NB2 = research-lab\nevrobiologi-2\RAPPORT.md;
MAT = research-lab\matematikk\RAPPORT.md. "DESIGN" = my engineering choice with no direct source; the reviewer should challenge these.
MUST = the harness refuses to produce a verdict without it.

## 0. Units and identifiers
- R0.1 MUST: the grouping unit is the **subject**, not the case. CHB-MIT chb01 and chb21 are one subject [M3]. Store a `subject_id` map in the manifest.
- R0.2 MUST: the atomic unit for splitting is a **recording file** (a continuous .edf). Windows never cross file boundaries, because the gaps between files are
  unrecorded, "occasionally" long [M3].
- R0.3 MUST: all times are in seconds from the file start plus a per-case file offset reconstructed from the (surrogate) start times, which preserve ordering within a case [M3].

## 1. Split rules
| ID | Rule | Source |
|---|---|---|
| S1 | **Cross-patient**: subject-disjoint folds (leave-one-subject-out or K-fold over subjects). Assert that `set(train_subjects) & set(test_subjects) == {}`. | M5 §2.2.2; M11; NB2 "Felles regler" |
| S2 | **Patient-specific primary**: time-series CV (TSCV). Train only on files that *end* before the test file *starts*. SzCORE benchmark variant: initial train >= 5 h and >= 1 seizure, test the next 1 h, grow by 1 h. Subjects with < 3 seizures or < 1.5 h are excluded and the exclusion is reported. | M5 §2.2.1/§3; M12 |
| S3 | Leave-one-record-out (Shoeb) or leave-one-seizure-out MAY be run only as a labelled secondary analysis ("non-causal; trains on future data"), never as the primary. | M1 §4.3; M12 (+3-7% event F1); M13 L3.1 |
| S4 | **Buffer**: for detection, no training window may lie within `B` of any test-file boundary. DESIGN: B >= window length + feature context + max post-processing span (with 4-s windows and a 5-s smoother, B >= 10 s). The 4-h buffer in NB2 applies to *forecasting*, not detection. | M16 (blocked CV); M1 (temporal proximity); NB2 |
| S5 | **Segment/window-random splits are FORBIDDEN** except inside the deliberate-leak positive control (C2). | M11; M1; NB2 |
| S6 | Evaluate on **continuous full recordings**. Balanced or sub-sampled test sets are forbidden for FA/h and event metrics. Sub-sampling is allowed only in *training*, and must be logged. | M12 ("data subsets should not be used to estimate the false alarm rate"); M5 |
| S7 | The split is computed *before* feature extraction, from the manifest alone. Its hash (sorted file lists per fold) is written into the prereg. | MAT a.4 (PROV: prereg precedes `used` edges to test data) |

## 2. Forbidden operations (the harness enforces them by construction and asserts them in tests)
| ID | Forbidden | Allowed instead | Source |
|---|---|---|---|
| F1 | Normalisation/scaling (z-score, robust scaler, PCA, ICA, CSP, channel re-referencing statistics) **fitted on data that includes test files** | Fit on training folds only and apply frozen to test, OR use a causal online normaliser such as median decaying memory. Normalisation choice alone moves AUC by up to 52%, so lock it in the prereg. | M13 L1.2; M18 |
| F2 | Feature selection, hyperparameter search or architecture choice using test folds | Nested CV inside training folds, or locked defaults (NB2 F1 locks "no tuning") | M13 L1.3; NB2 F1 |
| F3 | **Choosing the decision threshold, smoothing length, merge gap or minimum-event duration on test data** | Fixed in the prereg, or tuned on an inner validation split of the training data. Report the operating point. | M13 L1.3; M7 (compare at matched FA); M10 (operating-point impact) |
| F4 | **Windows/epochs that overlap across a split boundary**, including stacked context epochs (Shoeb W = 3) and overlapping-stride windows | Windowing happens *after* splitting, per file. Context never reaches outside the file or partition. | M1; M13 L3.2 |
| F5 | Oversampling/SMOTE/augmentation before splitting | Only inside training folds | M13 L1.2 |
| F6 | Training on data recorded after the test data in the primary patient-specific analysis | TSCV (S2) | M13 L3.1; M5; M12 |
| F7 | Using subject identity, file name, file index, recording time or montage idiosyncrasies as features | Signal features only. A metadata-only model is run as a negative control (C4). | M13 L2 |
| F8 | Reading test labels anywhere except in the scorer | Label access goes through one scorer function that logs a hash of every call | DESIGN (MAT a.4 provenance) |
| F9 | Changing timescoring parameters after seeing results | Lock 30/60/0/300/90 in the prereg. Any change goes to code\DEVIATIONS.md. | M5; M6; NB2 |

## 3. Metrics (exact definitions)
All event metrics use `timescoring` **pinned to v0.0.7** (MIT) with `EventScoring.Parameters(toleranceStart=30, toleranceEnd=60, minOverlap=0,
maxEventDuration=300, minDurationBetweenEvents=90)` [M5, M6]. Hypothesis annotations are binary masks at 1 Hz after the locked post-processing.

- **Event sensitivity** = TP / N_ref.
  - N_ref counts reference events after merging (< 90 s) and splitting (> 300 s).
  - A reference event is TP if any hypothesis sample overlaps it after extending it by -30 s / +60 s.
  - Per subject. Undefined (NaN) if N_ref = 0. [M5, M6]
- **Precision** = TP / (TP + FP), where FP = a hypothesis event (after merging and splitting) that overlaps no TP-extended reference. [M6]
  When there are no detections, precision is undefined; for the cross-subject mean, set it to 0 and report how many subjects this affected [M10].
- **F1** = 2TP / (2TP + FP + FN). [M6]
- **FA/h** = FP / H, where H = total scored recording duration in hours, **including seizure time and excluding unrecorded inter-file gaps**.
  Also report FP/24 h = 24 x FA/h (the SzCORE unit) [M5, M6].
  - FA are counted *after* the hypothesis is merged at 90 s, so bursts < 90 s apart count once [M6].
  - The denominator follows timescoring: `numSamples/fs` [M6].
- **Detection latency** (per TP event) = t(first hypothesis sample overlapping the extended reference) - t(reference onset).
  - It can be negative, down to -30 s, because of the pre-ictal tolerance.
  - Report the median, the IQR and the fraction within 10 s. Shoeb's definition is "delay between expert-marked seizure onset ... and detector declaration" [M1].
  - timescoring does not compute latency, so the harness does, with a unit test against a hand example. DESIGN.
- **Window-level AUROC and AUPRC** (secondary, ML-facing; they are the NB2 F1 estimand).
  - Computed from continuous window scores on each held-out subject/fold.
  - Window label = 1 if > 50% of the window lies inside a reference seizure (mirrors the SzCORE sample rule [M5]).
  - Report **per subject**, then the mean across subjects. Pooled AUROC is a secondary figure only.
  - AUPRC must be shown with its chance level (the prevalence, ~0.3% on CHB-MIT [M12, M25]).
  - Note: SzCORE avoids TN-based metrics [M5], so AUROC is never the headline clinical metric.
- **Sample-based** sensitivity, precision and F1 at 1 Hz (SzCORE sample scoring) are also reported [M5].
- **Aggregation**:
  - Per subject first, then the arithmetic mean over subjects (SzCORE/challenge convention) [M5, M10].
  - Within a subject's TSCV folds, append predictions in time before scoring. Do not average per-fold scores [M12 §5].
  - The prereg states this explicitly because M12 is internally inconsistent on it.
- Always report sensitivity, precision, F1 and FA/h together, per subject, with the operating point [M5, M7, NB2].

## 4. Confidence intervals and inference
- CI1: the resampling unit is the **subject**. Use a cluster (top-level) bootstrap: resample subjects with replacement and keep each subject's events/windows intact [M20, M21, M19].
  - B = 10,000 (DESIGN), percentile interval, seed 20261001, with a fixed RNG stream recorded [MAT a.4].
- CI2: **with fewer than ~5 subjects, the cluster bootstrap CI is not valid inference** (over-rejection with 5-30 clusters [M22]).
  - Cycle 1 (2-4 CHB-MIT subjects) therefore reports per-subject point estimates plus within-subject intervals, and labels any cross-subject CI "descriptive".
  - The NB2 F1 PASS rule ("95% bootstrap CI over patients above 0") **cannot be evaluated honestly with 2-4 subjects**. Queen/mathematician: either raise N (CHB-MIT has 23 cases, but the < 2 GB budget binds) or restate the rule per subject.
- CI3: within-subject intervals:
  - event sensitivity uses Clopper-Pearson over seizures [M23]. It is optimistic because seizures are not independent.
  - FA/h uses an exact Poisson interval on the FP count over H (standard method; source not opened, UNVERIFIED citation).
  - AUROC uses a block bootstrap over files within the subject (DESIGN).
- CI4: when several algorithms are compared, use Friedman, then Wilcoxon with Holm correction, and Cliff's delta over subjects (SzCORE challenge practice [M10]). Only when N subjects >= ~10 (DESIGN).

## 5. Controls (each can FAIL; a failed control means the verdict is "not verifiable: code")
| ID | Control | Expected | Source |
|---|---|---|---|
| C1 | **Label-shuffle negative control**: train on permuted labels and score the real test labels. DESIGN: use a **circular time shift of the label sequence within each training file** (preserves seizure duration and autocorrelation) rather than i.i.d. permutation, plus an i.i.d. permutation variant. | Window AUROC in [0.45, 0.55]; event sensitivity no higher than the random-alarm control (C3) | M24 (label-permutation test); NB2 F1 ([0.45; 0.55]); MAT a.1 (time-shift surrogates) |
| C2 | **Deliberate-leak positive control**: the same model with (a) a random window-level split across files/subjects and (b) the normaliser fitted on train+test. | Must score higher than the honest split (NB2 F1: dAUROC >= 0.05). Reference magnitude: +14.0 pp accuracy on Siena [M11]; about 80% to 50% [M14]. If no inflation appears, the harness does not detect leakage, so FAIL the infrastructure. | M11; M13; M14; NB2 F1 |
| C3 | **Random-alarm control**: alarms at random times with the model's own alarm rate, scored with the same timescoring parameters. | event F1 <= 0.05 (NB2 F2) | NB2 F2; M7 (compare at matched FA) |
| C4 | **Metadata-only model** (file index, time of day, subject ID as features). | Near chance on subject-disjoint splits; any skill flags L2 leakage | M13 L2 |
| C5 | **Oracle/identity**: hypothesis = reference gives F1 = 1 and 0 FP. **Planted truth**: synthetic recordings with known events reproduce known sensitivity and FA to 1e-9. | Exact | NB2 K1-K2 |
| C6 | **Scorer cross-check**: 10 hand-built annotation pairs (tolerance edges at 30/60 s, merge at 89/91 s, a 301-s event, zero-detection subject) scored by timescoring and by an independent re-implementation. | Identical | M6 (code read); DESIGN |

## 6. Evaluation card (one per run; machine-readable JSON + rendered markdown)
Sections: SzCORE model card items [M5, M27], TRIPOD+AI checklist pointer [M26], Kapoor model-info-sheet leakage answers [M13].
1. **Header**: RUO/not-a-medical-device label (verbatim above); run ID; the verdict (PASS/FAIL/"not verifiable: code"/POSTPONED, per NB2).
2. **Intended use / task**: detection, patient-specific or cross-patient, input montage (CHB-MIT bipolar, 18 common channels [M12] or as preregistered).
3. **Data**:
   - dataset name, version and DOI (CHB-MIT v1.0.0, 10.13026/C2K01R), licence (ODC-By 1.0) [M3];
   - subjects/cases used, with the chb01/chb21 mapping;
   - hours scored, seizures (counted from annotations), exclusions and reasons.
4. **Split**:
   - scheme (S1/S2), fold table (subject, file list, train hours, test hours, seizures);
   - buffer B; the split hash; a statement that the split predates feature extraction.
5. **Model**:
   - features (e.g. band power 1-4/4-8/8-13/13-30/30-70 Hz + line length, 4-s windows [NB2 F1; M17]);
   - classifier; the fitted-on-train normaliser (F1);
   - post-processing (smoothing, merge, minimum duration) and threshold, all with their prereg values.
6. **Metrics**:
   - per-subject table (event sensitivity, precision, F1, FA/h, FP/24 h, median latency, sample-F1, window AUROC, AUPRC, prevalence);
   - cross-subject mean with CI and a CI-validity flag (CI2);
   - number of subjects with undefined precision.
7. **Controls**: C1-C6 results with PASS/FAIL.
8. **Leakage checklist**: Kapoor L1.1-L3.3, each answered yes/no with evidence (the assertion name in the test suite) [M13].
9. **Provenance** (required fields):
   - input file SHA-256 (checked against PhysioNet SHA256SUMS) [HIVE rule 5];
   - manifest hash; split hash; prereg hash + timestamp (it must precede the first test-label access in the log [MAT a.4]);
   - script/code hash (git-free: SHA-256 of each source file) and the `timescoring==0.0.7` + all package versions;
   - Python version, OS/CPU, seed 20261001 + RNG stream IDs, BLAS thread count (DESIGN);
   - wall time, peak RAM (the < 1.5 GB rule);
   - DEVIATIONS.md entries; the reviewer's name and review-file path.
10. **Reproducibility**: a rerun from the provenance ID gives byte-identical scores on the same platform class [NB2 F2(i); MAT a.4].

## 7. Known gaps (do not paper over)
- There is no peer-reviewed event-scored cross-patient CHB-MIT reference number [methods.md §4].
- CHB-MIT's bipolar montage is not SzCORE-standard [M5, M10], so our numbers are not directly comparable with the SzCORE leaderboard.
- The FA/h Poisson CI and the circular-shift shuffle are DESIGN choices without an opened source.
