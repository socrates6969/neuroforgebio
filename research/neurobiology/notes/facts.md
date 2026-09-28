# Facts for preregs (each cites a source that was opened)

## methods-lit
(methods-lit, 2026-09-26; IDs refer to lit\methods.md; RUO, not clinical claims)

**CHB-MIT dataset facts**
- CHB-MIT: 22 subjects in 23 cases. chb21 = chb01 (same subject, 1.5 y later), so they MUST share a fold. 664 edf, 129 with seizures, 198 seizures total (182 in the original 23 cases), 256 Hz. Gaps between files are usually <= 10 s, sometimes longer. ODC-By 1.0. [M3 PhysioNet page]
- CHB-MIT ictal fraction 0.32% (982.9 h, 183 seizures, 24 subjects, 7.6 +/- 5.8 seizures/subject, seizure 58.6 +/- 65.0 s). [M12 Pale 2023, full text] Counts differ between sources, so count from annotations.

**Patient-specific reference numbers**
- CHB-MIT patient-specific, leave-one-record-out: sensitivity 96% of 173 seizures, **median 2 false detections/24 h** (= 0.083 FA/h), mean latency 4.6 s, median 3 s (91% within 10 s); worst patient 20 FD/24 h. [M1 Shoeb & Guttag ICML 2010, full text]
- Thesis version: 96% of 163 seizures, 844 h, 23 patients, median 3 s, median 2 FD/24 h. [M2]
- Needs >= 3 training seizures: with 1 seizure > 45% missed; with 3, < 5% missed (5-patient curve). [M1]

**Cross-patient / held-out reference numbers**
- Cross-patient event-scored CHB-MIT number under SzCORE: **NOT AVAILABLE** (CHB-MIT bipolar montage could not be scored in the challenge). [M10] Do not set a prereg threshold from "typical" cross-patient CHB-MIT literature.
- Independent held-out benchmark (65 subj, 4,360 h): best event F1 32%, sensitivity 37%, precision 29%, 1.34 FP/day. Top-5 had 1.34-14 FP/day. 23% of subjects had F1 = 0 for all top-5. [M10 Dan 2025/26, full text]
- Patient-independent SzCORE re-implementations: sensitivity ~70%, precision ~14%. [M9 abstract]

**SzCORE / timescoring defaults (lock these)**
- SzCORE event defaults: any-overlap TP; pre-ictal tolerance 30 s; post-ictal 60 s; merge events < 90 s apart; split events > 300 s. FA reported per 24 h. Sample scoring at 1 Hz with a > 50% overlap rule. TN metrics avoided. Personalized: TSCV (>= 5 h and >= 1 seizure initial train, test the next 1 h, grow by 1 h); subject needs >= 3 seizures and >= 1.5 h. [M5 Epilepsia, full text]
- timescoring v0.0.7 (MIT license) implements these defaults. It merges BOTH ref and hyp; FP rate denominator = total scored duration incl. seizures. [M6 source code]

**Leakage inflation magnitudes**
- Siena (window-level, balanced): segment holdout 79.1% (78.8-79.4) vs subject holdout 65.1% (61.3-69.1) accuracy, **+14.0 pp**. Alzheimer: 99.8% vs 53.0%. Only 17/63 (27.0%) DNN-EEG papers avoided subject leakage. [M11 Brookshire 2024, full text]
- Randomized CV vs leave-one-patient-out: accuracy "about 80% to 50%" (seizure *prediction*, XGBoost, 2 datasets). [M14 abstract]
- CHB-MIT personalized: leave-one-seizure-out beats causal TSCV by 3-7% event F1. Balanced subsets gave ~100% event sensitivity vs 80-95% on full data. [M12]

**Metric and normalisation sensitivity**
- Scoring metric alone changes FA by ~100x: same system on TUSZ eval gives OVLP 42.96% sensitivity at 11.45 FP/24 h vs EPOCH 51.58% at 1,301 FP/24 h vs TAES 35.55% at 17.23 FP/24 h. [M8 Shah 2020, full text]
- Normalisation choice alone changes line-length AUC by up to 52%; raw vs feature normalisation up to 22%. [M18 abstract]

**Baseline feature reference**
- Line length on iEEG: 4.1 s mean delay, 0.051 FP/h, 110/111 seizures detected (10 pts, 1,215 h). [M17 abstract] iEEG, not scalp.

**Statistics with few patients**
- Few clusters: cluster-robust tests over-reject with 5-30 clusters (10% vs nominal 5%). [M22] Nested data without hierarchical resampling: FPR > 45% at nominal 5%. [M19] Resample patients with replacement at the top level. [M20, M21] With 2-4 patients, report per-patient results; population CIs are descriptive only.


## data
- [data] CHB-MIT v1.0.0 (https://physionet.org/content/chbmit/1.0.0/, ODC-By 1.0; content page read; RECORDS, summaries and all 686 EDF headers read). fs = 256 Hz on all signals in all 686 EDFs, 16-bit storage. The digital range is -2048..2047 = +/-800 uV (checked in the 29 selected EDFs).
- [data] Whole database: 686 EDFs, 141 with seizures, 198 seizures (summaries). chb21 is the same patient as chb01. chb24 has no start times. RECORDS-WITH-SEIZURES wrongly lists chb07_18 instead of chb07_19.
- [data] Cycle-1 subset (rule fixed before download, notes\data_subset.md): chb01, chb03, chb10 = 29 EDFs, 35.66 h, 21 seizures (7/7/7), 1.512 GB, all SHA-256 verified.
  - chb01: 11 files, 10.65 h, 7 seizures (442 s ictal)
  - chb03: 11 files, 11.00 h, 7 seizures (402 s)
  - chb10: 7 x 2-h files, 14.02 h, 7 seizures (447 s)
  - Non-seizure time is 10.52 / 10.89 / 13.89 h. Seizure durations range from 27 to 101 s.
- [data] Montage: an identical 23-channel bipolar double-banana in all 29 files, with no changes. "T8-P8" appears twice (channels 15 and 23, sample-identical), so there are 22 unique channels.
- [data] A 4th subject does not fit under 1.8e9 B (the cheapest 4-set is 1.819e9 B). chb10 has no seizure-free files, so its false alarms per hour are measured on data within about 2 h of a seizure.
