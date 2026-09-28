# N3: Harness validation on FRESH CHB-MIT subjects (blind), with the locked N2 model re-run as the model test

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Author: mathematician/methodologist, hive cycle 2, 2026-09-26. Status: **DRAFT-LOCKED**.
- The text is final unless the queen or reviewer returns it.
- It becomes LOCKED when the queen approves the data plan in §2.4. Its SHA-256 is then recorded in the N3 card before any N3 EDF is downloaded.
- Changes go to code\DEVIATIONS.md (section N3).

**Blindness statement.** No EEG sample, feature, score, model output or hypothesis exists for any subject named here.
- The only inputs were the CHB-MIT annotations and EDF headers already in notes\data\chbmit_inventory.csv.
- The synthetic power analysis (notes\n3_power.md, results\n3_power\power_sim.json) was also used. It is calibrated on the burned
  subjects chb01/03/10 only.
- The N2 and N1b results on chb01/03/10 are known to the author. They inform the design but not the new subjects.

Companion documents: prereg\N2_baseline_detection.md (locked model and rule, **unchanged**), prereg\N1b_negative_controls_v2.md (the NC-P,
C3' and planted-leak definitions, reused except where §4 states a change), code\RESULTS_N1b.md, code\REVIEW_N1b.md.

## 0. Why N3, and what is different from N1b

- N1b failed because the event-arm controls were powerless (PL-A T_E Fisher 0.012, PL-B 0.51), not because a leak was found.
  Under N1b §7 harness validation therefore moves here, and chb01/03/10 stay burned.
- The power analysis (notes\n3_power.md) found two things.
  - **(i)** Literal Fisher on discrete p-values has an actual size of about 0 (0/6,000 at α = 0.05). An exact **pooled** conditional-randomisation
    statistic keeps the nominal size and dominates it in power.
  - **(ii)** Even with the pooled statistic, the event arm needs ≥ 4 subjects × 4 references (PL-A) or ≥ 3 × 7-10 (PL-B) for power 0.8.
    Fresh subjects that the unchanged N2 code can run give 2 × 4, where power is 0.59 (PL-A) and 0.31 (PL-B).
  - The window arm has power 0.96-1.00 for PL-A at 2 × 4, and 0.93 for a leak 3x weaker (T_A 0.65).
- **Changes from N1b** (each justified by the power result and fixed before any N3 data exist):
  - **D1.** The **window arm T_A is the formal leak gate**, and PL-A must trip it. N1b required PL-A to trip BOTH T_A and T_E.
  - **D2.** The event arm uses the **pooled ΣF1** statistic (§4.2) instead of literal Fisher. It stays a **validity** check, so a trip in either
    tail FAILS the harness. Its planted-leak trips are **descriptive**, not required.
  - **D3.** PL-B is no longer a required statistical trip. Threshold leaks are covered by a **mandatory code-level violation test**
    (§4.4) and reported descriptively in the event arm.
  - **D4.** Fresh subjects, fixed by the rule in §2. The model test is a re-run of the locked N2 model and rule (§5).

## 1. What stays locked (byte-identical)

- Every file in code\nfharness\ plus edf_reader.py and run_n2.py (17 files) must match the SHA-256 values in results\N2_run_card.json.
- LOCKED_CONFIG hash b6775e9a...1e4f; the features, normaliser, classifier, 4-of-5 smoothing, τ grid and τ rule (train-OOF FA ≤ 12/24 h);
  the buffer; and timescoring 0.0.7 with (30, 60, 0, 300, 90).
- The N1b sampler S, PhantomVault, order log, t_rm (1.323 events/h), degeneracy flags, C3' exact enumeration and the PL-A/PL-C
  definitions, as reviewed (REVIEW_N1b §1), including N1b-15 (training phantoms span ≥ 2 training files).
- New code only:
  - code\run_n3.py: the subject list, the split string, and the FP grid computed by the N2 §4 Garwood rule.
  - code\n3\: the pooled statistic, the D1-D3 verdict logic, and the §4.4 test.
  - If an nfharness or n1b file would need an edit, stop and log it. Do not edit.
- **Montage assertion (new, outside nfharness).** The N2 reader selects channels by index. run_n3.py must therefore assert, before reading any signal,
  that every N3 EDF header lists exactly the 23 standard labels in the standard order (E1). Otherwise it aborts.

## 2. Subjects: rule fixed now, and the budget

### 2.1 Selection rule (applied to notes\data\chbmit_inventory.csv; annotations and headers only)

- **Download subset per subject (R2):** the seizure-containing files only, ordered by EDF header start time.
  - Training = the files up to and including the one that contains the 3rd seizure (the N2 §1 rule).
  - Test = the following seizure files in order, stopping at the first file where the cumulative test N_ref reaches **4**.
- **Eligibility.** A subject is eligible if all of the following hold:
  - **E0:** not chb01, chb03, chb10 (burned) or chb21 (the same patient as chb01).
  - **E1:** every file in its R2 subset has the standard 23-label montage.
  - **E2\*:** the R2 subset reaches N_ref = 4 test references (seizures < 90 s apart count as one).
  - **E3\*:** every R2 file is in the subject's summary with its seizure times, and the EDF header start times give the order.
  - **E4:** not a known repeat patient.
  - **E5:** the training part has ≥ 2 files, so the N2 inner leave-one-training-file-out CV can run, and every LOFO fold keeps ≥ 1 positive.
- **Choice:** the S = 2 eligible subjects with the smallest total R2 download.
  - S = 2 is the minimum at which the N2 overall rule can PASS, and at which the window-arm power is ≥ 0.93 (notes\n3_power.md §4).

**E3\* replaces cycle-1 E3 ("summary start times available").**
- E3's purpose was chronological ordering, and N2 §1 already orders files by EDF header start time.
- The change matters only for chb24. Its 12 seizure files are all in its summary with seizure times, but its summary lacks start times.
- Stated caveats for chb24:
  - it has no SUBJECT-INFO row (age and sex unknown);
  - PhysioNet does not say that chb24 is a repeat patient, but that is not positively excluded either (UNVERIFIED).

### 2.2 Applying the rule (every non-burned subject checked)

| subject | outcome |
|---|---|
| chb02, chb07 | fail E2\* (3 seizures, so 0 test) |
| chb05, chb08 | fail E2\* (5 seizures, so N_ref 2) |
| chb06 | fails E5: its first file, chb06_01, holds seizures 1-3, so training is 1 file and LOFO is impossible |
| chb04, chb09, chb11-chb20, chb22 | fail E1 (montage changes or dummy channels) |
| **chb23** | eligible |
| **chb24** | eligible (under E3\*) |

The rule therefore **forces** {chb23, chb24}.

| subject | training files (seizures, ictal s) | test files | N_ref | test H | test durations (s) | R2 bytes |
|---|---|---|---|---|---|---|
| chb23 | chb23_06, chb23_08 (3: 113; 20, 47) | chb23_09 | 4 (gaps 4225/1558/1048 s) | 4.007 h | 71, 62, 27, 84 | 379,841,536 |
| chb24 | chb24_01, chb24_03 (4: 25, 25; 29, 25) | chb24_04, chb24_06 | 4 (gaps 291/307 s, both ≥ 90) | 2.000 h | 32, 27, 19, 24 | 169,598,976 |
| **total** | 7 EDFs | | 8 | 6.007 h | | **549,440,512 B = 0.549 GB** |

- **Split hash (S7).** SHA-256 of the two lines below (joined by "\n", no trailing newline) =
  `9320fa73c5e52ce449f7257f47dda5fce87a25b53d812f51dbf6b21bc0397a19`.
  ```
  chb23;train=chb23_06.edf,chb23_08.edf;test=chb23_09.edf
  chb24;train=chb24_01.edf,chb24_03.edf;test=chb24_04.edf,chb24_06.edf
  ```
- **Allowed time.** NC-P uses [on − 600, off + 900) exclusion, segments of at least 120 s.
  - chb23: train 3.73 h, test 2.40 h (segments 1989/2725/3862 s, plus 58 s that is unusable).
  - chb24: train 0.50 h (446/224/1123 s), test 0.97 h (488/936/629/1447 s).
- **chb24 is thin.** Its allowed time is below the 2 h minimum simulated in notes\n3_power.md.
  - Its training time is so short that t_rm will often need zero events, so t_rm will saturate. This is harmless, because the event arm is not the leak gate.
  - Window-arm power on chb24 is extrapolated.
- Both subjects' test FA is on seizure files only, so they are flagged **"FA on peri-ictal data only"** (as chb01/chb10 were in N2).

### 2.3 Budget

- **Used so far:** 1,512,087,040 B of EDF plus ~5 MB of headers and text, about 1.517 GB of the 2 GB cap. **Remaining ≈ 0.483 GB.**
- **Minimal data need for N3:** 0.549 GB. **The shortfall is ≈ 0.066 GB.** No smaller subset satisfies the rule:
  - dropping to N_ref = 3 per subject would break the N2 decision grid "of 4";
  - one subject cannot give an overall PASS.

### 2.4 Data decision (NOT assumed; exactly one of the three applies, and it is recorded in the card)

- **(A) Replace the cycle-1 raw files.** Delete the 29 chb01/03/10 EDFs (1.512 GB) after confirming that data\manifests\chbmit_manifest.csv
  holds their PhysioNet-verified SHA-256 values; they can be re-downloaded bit-identically. **The queen decides.**
- **(B) Raise the cycle cap** from 2.0 to ≥ 2.07 GB. **The lead decides.**
- **(C) Neither is approved: the pre-specified in-budget fallback, "N3-lite".** It uses **chb23 only** (0.380 GB, which fits).
  - The harness gate runs at S = 1. Predicted window-arm power: PL-A 0.91 (R = 5), PL-A-65 0.81.
  - The model test gives a per-subject verdict only. The **overall N2 verdict is INCONCLUSIVE by construction** (it needs ≥ 2 PASS).
  - chb23 was chosen over chb24 because its allowed time is 2.5x larger, and E3\* is not needed.
  - N3-lite is labelled "under-powered harness validation (S = 1)".

The downloader (code\chbmit_download.py, unchanged) runs only after the decision. Every file must match PhysioNet SHA256SUMS before use.

## 3. Order of work

1. Record the hashes of this prereg and the §1 code, then snapshot DEVIATIONS.md.
2. Run the pytest suite (all existing tests, plus the new N3 tests: the pooled statistic's exactness on a hand fixture; the montage assertion;
   the §4.4 violation test).
3. **Synthetic dry run** (stream 26) on a synthetic EDF with the chb23/chb24 file, seizure and duration layout. Each item below must hold;
   a failure is a CODE bug, and a fix does not count as the real-data fix round.
   - (a) The pooled ΣF1 p-value and the T_A p-values over ≥ 100 NC-P replicates are super-uniform: KS against U(0,1) p ≥ 0.01, and the fraction
     below 0.05 is ≤ 0.08.
   - (b) PL-A trips T_A.
4. Download, hash and montage-assert under §2.4.
5. **Real run, in this order.**
   - (i) The locked N2 model on chb23/chb24. Its s and h and their hashes are written to the log BEFORE any control reads a label.
   - (ii) NC-P.
   - (iii) PL-A.
   - (iv) PL-B (descriptive).
   - (v) C3'.
   - (vi) PL-C.
   - (vii) N2 scoring against the real test labels last.
   - The N2 test labels are read by the harness Scorer only in step (vii) and in C3'/PL-C, which need the real references.
6. **Rerun** in a fresh process. The card must be byte-identical (runtime block excluded).

## 4. Harness gate (formal)

Streams: numpy default_rng(SeedSequence(20261001, spawn_key=(k, subject_index, replicate))) with:

| k | use |
|---|---|
| 20 | training phantoms |
| 21 | test phantoms |
| 22 | null draws |
| 23 | PL-A selection |
| 24 | C3' Monte Carlo |
| 25 | PL-C |
| 26 | dry run |

Replicates: R = 10 per subject for NC-P, R_leak = 5 per subject for PL-A. M = 999 null draws. There is one phantom per real test seizure, with the same durations (K = 4 per subject), as in N1b.

### 4.1 NC-P window arm (T_A), the FORMAL leak gate
- Per replicate: the exact p_up and p_lo of the test-window AUROC against the phantom window labels (N1b §2.3-2.4).
- Combination: Fisher over the retained replicates. The AUROC is near-continuous, so the size is nominal; the power analysis measured KS p 0.16.
- **V1-A:** both Fisher p-values (up and lo) are ≥ 0.0025.
- **V2-A:** ≤ 1 of 20 replicates is window-flagged (SD of s < 1e-6).

### 4.2 NC-P event arm (T_E): a VALIDITY check, descriptive for power
- h is taken at t_rm, and the degeneracy flags are decided from h before the draw (as in N1b).
- **Statistic:** T = ΣF1 over the retained replicates of both subjects. The null for draw b is Σ over those replicates of F1(null draw b).
  p_up = (1 + #{T_null ≥ T})/(M + 1); p_lo is the same with ≤.
  - This is exact, because each replicate's (observed, null draws) are exchangeable and the replicates are independent. Measured size:
    0.0018-0.0025 at 0.0025, and 0.046-0.054 at 0.05.
- **V1-E:** both pooled p-values are ≥ 0.0025. **A trip FAILS the harness** (FLAG: event-level leak or sign error).
- **Reported, descriptive, not in the gate:** the literal Fisher (N1b), mid-p Fisher, pooled ΣTP, and the degenerate counts. N1b's V2 limit
  (≤ 1/3 degenerate) becomes descriptive, because the event arm no longer carries a power requirement.
- Family false-FAIL rate for V1-A plus V1-E (4 tests at 0.0025): ≤ 0.01.

### 4.3 C3' random-alarm null (formal, unchanged)
- As in N1b §3, on the N2 hypotheses of chb23/chb24 against their 8 real test references.
- The pmf is exact. PASS iff (i) |mean_MC − μ\*| ≤ 3σ\*/√M_C AND (ii) the fraction above q95 is ≤ a\* + 3√(a\*(1−a\*)/M_C). M_C = 1,000.

### 4.4 Planted leaks

| leak | definition | requirement |
|---|---|---|
| **PL-A** (formal) | 25% of the allowed test windows, with their phantom labels, go into training and into the normaliser fit (N1b §4, reviewed implementation) | **Fisher (T_A, up) p < 0.0025**; otherwise the harness = FAIL (controls powerless) |
| PL-A10 (descriptive) | the same, with 10%, R_leak = 5, stream k = 23 continued | report the T_A and pooled T_E p-values |
| PL-A, event (descriptive) | pooled ΣF1 p on the PL-A fits | report |
| PL-B (descriptive) | τ = the argmax of the test-phantom F1 (ties to the smallest τ), on the NC-P fits | report the pooled ΣF1 p. T_A p-values must equal NC-P's in 20/20 (**formal specificity check**) |
| **PL-B-code** (formal) | a pytest test that calls the N2 threshold selector (nfharness.postprocess.select_tau) with test-tagged scores | must raise ThresholdSelectionError. Together with the N1(d) F3 violation test, this is the coverage for threshold leaks |
| **PL-C** (formal) | the N1b §4 definition (p = 0.25 per seizure-containing test file) | the fraction above q95 is > the (ii) bound |

- A label-free leak (the normaliser fitted on test) remains the job of the F1 guard. No statistical control here can see it.

**N3 harness = PASS** iff all of the following hold:
- steps 2, 3, 5 and 6 of §3 succeed;
- V1-A, V2-A and V1-E hold;
- C3' (i) and (ii) hold;
- PL-A trips T_A;
- PL-B-code raises;
- PL-C trips;
- PL-B specificity holds.

Otherwise the harness is FAIL. A V1-E or V1-A trip additionally sets the FLAG "possible leak".

## 5. Model test: the locked N2 model and rule, re-run unchanged on chb23/chb24

- The locked N2 model is fitted on each subject's training files. τ\* comes from the train-OOF FA ≤ 12/24 h rule. It is scored on the test files
  exactly as in N2 §2-§3, and the N2 §4 decision rule is applied.
- The FP grid is computed by the N2 §4 formula: meets-bar FP ≤ H; FAIL if the Garwood lower 95% bound > 24/24 h.

| subject | H (h) | meets bar (FP) | inconclusive (FP) | FAIL (FP) | sensitivity grid |
|---|---|---|---|---|---|
| chb23 | 4.007 | ≤ 4 | 5-8 | ≥ 9 | of 4: 3-4 meet, 2 inconclusive, 0-1 FAIL |
| chb24 | 2.000 | ≤ 2 | 3-5 | ≥ 6 | of 4: same |

- **Overall (N2 rule):** PASS if both subjects PASS; FAIL if both FAIL; otherwise INCONCLUSIVE.
- **The N3 model verdict counts only if the N3 harness = PASS.** Otherwise it is "not verifiable: code".
- Also reported, descriptively: window AUROC/AUPRC, latency, Clopper-Pearson sensitivity intervals, Garwood FA intervals and "CI uninformative (N_ref = 4)".
- **Non-verification caveat.** If the N_ref reported by the scorer is not 4 for a subject, that is a harness flag, as in N2.
- chb23 and chb24 test files are **burned** after this run.
- **Status label if PASS:** "N2 locked model, confirmatory on fresh subjects; harness gate pre-registered blind". This is the first result in the
  program that is not post hoc.

## 6. Predictions (made blind, with numbers)

| quantity | prediction |
|---|---|
| synthetic dry run passes first time | 0.8 |
| NC-P T_A replicate mean | 0.50 (SD ~0.12; chb24 SD larger, ~0.15). Both Fisher p ~ U(0,1). P(V1-A false FAIL) ≤ 0.005 |
| NC-P pooled ΣF1 p | ~U(0,1). P(V1-E false FAIL) ≤ 0.005 |
| NC-P degenerate (event) | chb23 1-4 of 10; **chb24 4-9 of 10** (0.5 h of training allowed time forces t_rm saturation) |
| **PL-A trips T_A** | **P = 0.93** (simulation 0.96-1.00 at 2 × 4, discounted for chb24's thin time). Mean T_A 0.75 (0.65-0.85) |
| PL-A10 T_A | trips with P ≈ 0.6 (T_A about 0.60-0.65; the simulated power at T_A 0.60-0.65, 2 × 4 is 0.68-0.93) |
| PL-A pooled event p < 0.0025 (descriptive) | P ≈ 0.35 (simulation at R_leak = 5: 0.30 PL-A-hom, 0.83 PL-A) |
| PL-B pooled event p < 0.0025 (descriptive) | P ≈ 0.25 (simulation 0.31); literal Fisher ~0.4, which does not trip |
| PL-B-code raises | 0.99 |
| C3' PASS | 0.93 |
| PL-C trips | 0.8 (only 8 references; untested at this size) |
| **N3 harness PASS** | **P = 0.70** (main risks: PL-A power on chb24; the dry-run implementation of the pooled statistic) |
| N2 model, chb23 | AUROC 0.93 (0.80-0.98); sensitivity 3/4; FP 3; P(PASS) 0.45, P(FAIL) 0.15 |
| N2 model, chb24 | AUROC 0.88 (0.70-0.97); sensitivity 3/4 (seizures of 19-32 s are short for 4-of-5 smoothing); FP 2; P(PASS) 0.35, P(FAIL) 0.25 |
| N2 overall | P(PASS) ≈ 0.16, P(FAIL) ≈ 0.05, INCONCLUSIVE otherwise |
| runtime | < 12 min, < 1.2 GB (7 EDFs; per subject 10 NC-P + 5 PL-A + 5 PL-A10 fits + 1 N2 fit) |

## 7. Abandonment

- **Code bugs.** One fix round for CODE bugs found on real data, logged. Locked N2 values are never touched.
- **PL-A fails to trip T_A** (with the dry run passing). The label-randomisation controls are declared **powerless on CHB-MIT scale data**. The program
  then stops claiming leak detection by randomisation controls. It reports only the code-level guards (N1(d), F1-F9) and the independent review,
  and the harness is labelled "validated by code review and violation tests only". There is no N3b on these subjects.
- **V1-A or V1-E trips on NC-P** (a possible real leak). No model result is reported. The trip goes to the reviewer for a root cause before any further prereg.
- **C3' or PL-C fails.** The harness = FAIL. The scorer path goes back to review. No re-selection of data.
- **N2 model FAIL or INCONCLUSIVE.** It is reported as such. There is no tuning on chb23/chb24, and the files are burned. The next model is a new
  prereg on subjects never downloaded (under the E-rules, CHB-MIT has no strict-eligible fresh subjects left after chb23/chb24, so this means
  another open dataset).
- **Budget.** > 15 min or > 1.5 GB per run stops the run. The only pre-approved fallback is R = 5 for NC-P, logged.
- **If §2.4 ends in (C) N3-lite.** Same rules, S = 1, and the overall N2 verdict is INCONCLUSIVE by construction.
