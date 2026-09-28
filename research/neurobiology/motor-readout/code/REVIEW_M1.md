# REVIEW: M1 offline motor-decoder comparison (independent code review, verification gate)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Reviewer: independent code reviewer, 2026-09-27.

**Scope.**
- Code: motor-readout\code\run_m1.py, m1lib\*.py, finalize_m1.py and tests\.
- Checked against prereg\M1_decoder_comparison.md. Its SHA-256 is `9eada9d79c849b2c5572dd4eb629ef29d0dc9b294e8933a05de674a8bd4bd06f`, which I recomputed and which matches the code constant and both cards.
- Reported material: code\RESULTS_M1.md, code\DEVIATIONS.md, results\M1_DEVIATIONS_prerun_snapshot.md, results\M1_*.json, the run logs and data\manifests\.

**What was modified.** Nothing in code\ (outside code\review\), results\, prereg\ or data\ was modified.

**Reviewer checks.** These are in code\review\. Each writes `*_out.json` and `*.log`. None of them imports m1lib or run_m1.
- `m1_reimpl_d1.py`: D1 split, binning, z-score, ridge, KF, M-R2, ρ², M-BITS, KF diagnosis, NC1 and PL-1. It ran in 34 s with a peak working set of 937 MB.
- `m1_reimpl_d2.py`: LINK re-binning, split, ridge drift, R-a, R-b (own FA-EM + Procrustes), H4 and H5. It ran in 5.5 s at 451 MB peak.
- `m1_nc1_d2_reference.py`: the D2 NC1 reference bar. It ran in under 5 s.
- The pytest suite was re-run with bytecode writing and the cache disabled: 40 passed (`m1_pytest.log`).

## Summary

| # | item | status |
|---|---|---|
| 1a | Prereg lock (23:08:18) predates any download (first file 23:17, manifest 23:34) and any data read | **CONFIRMED** |
| 1b | The DEVIATIONS pre-run snapshot predates the real data read, and its "predicted failures" were written first | **CONFIRMED with a correction.** The timing statement in RESULTS is wrong (R1). |
| 2 | Leak-proofness: D1 chronological trial split, D2 per-session time order, day-0 decoder uses day-0 only, z-score / ridge / KF / FA fitted on train only | **CONFIRMED** (two code notes: C1, C2) |
| 3a | D1 M-R2: ridge 0.669, KF 0.286 | **CONFIRMED** (independent: 0.66911 and 0.28608, identical to 1e-7) |
| 3b | D1 M-BITS: ridge 25.6, KF 13.3 bits/s | **CONFIRMED** (independent: 25.60 and 13.27; the difference is null-permutation noise). Note P4 (DC bin). |
| 3c | KF 0.286 "surprisingly low" | **Not a bug.** It follows from the prereg's KF specification (§3 below). |
| 4 | H4/H5 numbers on LINK (ρ, φ_Rb, φ_Ra, Spearman) and "R² ≈ 0 at ≥ 151 d" | **CONFIRMED** (maximum per-session R² difference 0.007). **VERDICT-AT-RISK (conditional H5 only):** φ is ill-conditioned (P3). |
| 5a | PL-1 bar (≥ 0.10) is analytically unreachable | **CONFIRMED** |
| 5b | NC1 I_net bar is mis-specified (coherence ignores sign and gain) | **CONFIRMED**, and the D2 NC1 R² bar is also mis-specified (P2) |
| 6a | Verdict strings: harness FAIL, H1-H5 "not verifiable: harness", H6 NOT TESTED | **CONFIRMED** |
| 6b | Reproducibility: card hash c7bd7ac5...af0 in run1 = rerun | **CONFIRMED** (recomputed; only `runtime` differs; all 10 code hashes and all 16 read-only hashes (15 nfharness + edf_reader) match the files on disk) |
| 6c | A4 cuts (D3 dropped, GRU 1 seed) applied per the prereg order | **CONFIRMED** (note on the DEVIATIONS §C timing argument) |
| R1-R4 | Reporting errors in RESULTS/DEVIATIONS | **BUG (reporting, minor; no verdict changes)** |

**Findings.**
- No code BUG changes a number.
- The final verdicts (harness FAIL, so all H are "not verifiable: harness") stand.
- The harness FAIL is a prereg design failure (PL-1, NC1), not a pipeline leak. My independent checks support this.

## 1. Lock and ordering

**Prereg and data timeline.**
- The prereg mtime is 2026-09-26 23:08:18. download_m1.py is from 23:17:29, the first raw files from 23:17-23:18, and motor_manifest.csv from 23:34:32 (131 rows, 0 mismatches).
- BOARD line 25 posts the lock with SHA 9eada9d7 before the run.
- run_m1.py checks the prereg SHA and the input-lock SHA before reading anything.

**Real-run log (run1).**
- 00:08:42 start → 00:08:43 input hashes → 00:08:56 pytest → 00:08:56.23 split lock written → FIRST DATA READ → 00:08:57 FIRST MODEL FIT → 00:13:51 80 models frozen → 00:14:55 vault open.
- The split lock precedes the first fit, as prereg §2 requires.
- The vault log shows only declared `planted|` reads (PL-1, PL-3, PL-2) after `freeze`, then `score|` reads.

**Snapshot.**
- results\M1_DEVIATIONS_prerun_snapshot.md has SHA `f081a37b...c74b`, which matches RESULTS.
- Its CreationTime and LastWriteTime are both **00:08:51.7**.
- So it was written about 10 s **after** the run1 process started, but 4.5 s **before** the first data read. Between those times the process had only hashed files and run pytest.
- RESULTS says "mtime 00:08:36, 6 s before the real run started". **That is wrong (R1).**
- The substantive claim, that the predictions were written before any real value existed, still holds.

**Snapshot content.**
- `diff` against the current DEVIATIONS.md shows only §E (POST-RUN) is new. The current file was re-created at 00:23:00, so its own mtime carries no evidence.
- The pre-run numbers in §D match the earlier cards:

| pre-run number in §D | source | value in that card |
|---|---|---|
| Dry PL-1 0.574 → 0.614 | M1_card_dry.json, 23:47 | 0.5740 → 0.6139 |
| Synthetic D2 NC1 I_net 8.97 / 2.81 / 1.67, KF R² 0.114 | M1_card_synthetic.json, 00:08:22 | 8.968 / 2.808 / 1.666, KF R² 0.1137 |
| Synthetic expected PL-1 rise 0.053 | M1_card_synthetic.json | 0.0525 |
| Dry KF 0.25 vs ridge 0.57 | M1_card_dry.json | 0.246 / 0.574 |

**Caveat.** The evidence is filesystem timestamps only; no pre-run hash of the snapshot was posted. I found no sign of an earlier real run: there is only one run1/rerun pair, the split-lock hash is identical across them, and the frozen models were written once. From files alone, however, an overwritten earlier run cannot be excluded.

## 2. Leak-proofness (code reading + independent re-implementation)

**D1.**
- **Split.** Trials are sorted by start_time, with 300/99/99 and the trial at each cut index dropped. F6 is asserted.
  - My independent split gives the same partitions, since R² agrees to 1e-7.
  - The grid [-750, +950) ms around onset stays inside each trial (checked in the code, DEVIATIONS B.2).
- **Test labels.** Test velocities are deposited in the vault and NaN-ed in every grid (20/10/50/100 ms and all τ) before any fit.
- **Normalisation.** The z-score is fitted on train-trial rows only (history + window), and `ZScore.fit` refuses non-train owners.
- **Fits.**
  - Ridge is fitted on train only, with λ chosen on val.
  - The KF (A, Q, C, R) is fitted on train window bins only.
  - The GRU is trained on train, with early stopping on val.
  - PL-1 and PL-3 use the honest train z-scorer.
- **Condition-held-out.** It trains on train/val trials of other folds and scores held-out-fold test trials.

**D2.**
- **Split.** Each session is split chronologically (225/74/74 + 2 gaps). Bin owner is set by bin centre, and `assert_bins_disjoint` passes. My loader confirms calib < val < test in bin order in all 9 sessions.
- **Day-0 decoder.** M0 (ridge, KF, GRU, z-score, FA and FA-ridge) is built from day-0 calib/val only. Day-k data enter only through `d2_apply` (prediction) and the day-k FA (calib neural only, unsupervised, which the prereg allows).
- **Lags.** Ridge lags and the GRU/KF warm-up read neural bins from the preceding gap/val block only. Labels never cross a partition.
- **NC1.** The DV-6 change (shuffled validation pairs as well) removes a real leak into the null decoder.

**Code notes (no leak found):**
- **C1. The SessionOrderError guard is decorative in the real pipeline.** `d2_fit_day` calls `assert_session_order(0, [0], ["calib","val"])` with literal lists, and PL-2's "undeclared" call uses the literal `[0, 32]`. Neither is derived from the data actually passed. D2's time-order safety therefore rests on structure, which I verified, not on the guard. The prereg requirement ("the undeclared version must raise") is met only in this weak sense. Wire the guard to the rows actually fed to the fit in the next prereg.
- **C2. Condition folds use maze_id.** The file has 9 maze_ids but **27** (trial_type, trial_version) conditions. Folds are therefore maze-disjoint, which is stricter than condition-disjoint. This is disclosed in B.3 and descriptive only.

## 3. Independent re-implementation of M-R2 and M-BITS (D1) and the KF diagnosis

`m1_reimpl_d1.py` builds everything from the prereg text with its own code: its own h5py reads, searchsorted binning, eigen-ridge path, a KF with a standard-form Riccati iteration, and bits with its own derangement RNG.

| quantity | reported | reviewer |
|---|---|---|
| ridge λ / val R² | 3162 / 0.6852 | 3162 / 0.6852 |
| ridge test R² / ρ² | 0.669 / 0.663 | 0.66911 / 0.66339 |
| ridge I_raw / null median / I_net | 26.21 / 0.60 / 25.61 | 26.210 / 0.613 / 25.60 |
| KF test R² / ρ² / val R² | 0.286 / 0.346 / 0.277 | 0.28608 / 0.34641 / 0.27692 |
| KF I_raw / I_net | 13.68 / 13.26 | 13.679 / 13.27 |
| B0 R² / I_net | 0.061 / 0.00 | 0.0612 / 0.00 |
| KF bin sweep 10 / 50 / 100 ms | 0.218 / 0.398 / 0.449 | 0.218 / 0.398 / 0.449 |

**Why the KF is low: CONFIRMED genuine, not a bug.** The prereg fixes three things: the observation is the **current 20 ms bin only**, there is **no neural-lead lag**, and the state is velocity-only, re-initialised at -250 ms.

Reviewer variants on the same split:

| variant | test R² |
|---|---|
| memoryless ridge on the current bin only (the information one KF observation carries) | 0.206 |
| prereg KF (the dynamics add smoothing) | 0.286 |
| KF with causal observation x_{t-3} / x_{t-5} / x_{t-7} (60-140 ms neural lead) | 0.384 / 0.374 / 0.331 |
| KF on a causal 200 ms boxcar of the features | 0.393 |
| KF with 100 ms bins | 0.449 |
| KF with diagonal R | 0.111 (so the full-R fit helps and is not the problem) |
| KF started at -450 ms instead of -250 ms | 0.246 |

- The Riccati gain converges (the reviewer's standard-form iteration gives an identical K).
- Literature KF R² of about 0.5-0.7 comes from 50-100 ms bins, lagged observations and position/velocity states. The prereg specified none of these, while ridge got 200 ms of lagged history.
- **H2 (conditional FAIL) is a property of the specification.** A fair KF-vs-ridge equivalence test needs matched information (lag and bin), which is new-prereg material.

**P4 (M-BITS, interpretation, not a bug).**
- The literal prereg sum "f_j ≤ 10 Hz" includes f = 0. That is disclosed in DEVIATIONS B.10.
- For ridge, the DC bin contributes 7.8 of 25.6 bits/s (without DC: 17.8 bits/s).
- A periodic instead of symmetric Hann changes I_net by less than 0.1.
- Part of the "5× the estimate" level comes from DC. The H3 ordering is not affected.

**Sign/gain invariance, demonstrated.**
- Negating the honest ridge output gives R² = **-2.16**, but I_net = **25.62** bits/s, unchanged. That is the mechanism behind 5b.

## 4. H4/H5 drift on LINK (independent ridge / R-a / R-b)

`m1_reimpl_d2.py` uses its own 4 ms common-grid re-binning, its own FA-EM (Rubin-Thayer; 10 factors, 200 iterations) and SVD Procrustes. Per-session R² agree with the card within 0.007 (maximum |Δ| = 0.0066, at 730 d fixed).

| aggregate | reported | reviewer |
|---|---|---|
| day-0 ridge λ / val R² | 3162 / 0.349 | 3162 / 0.349 |
| median ρ (5 usable, lag ≥ 30 d) | -2.14 | -2.144 |
| Spearman(lag, R²_fixed), 8 later sessions | -0.52 | -0.524 (hand-checked from ranks) |
| median φ_Rb / φ_Ra | 0.59 / 0.62 | 0.588 / 0.619 |
| R-a R² at ≥ 151 d | -0.05..0.04 | 0.039, -0.005, -0.052, -0.036 |
| R-b R² at ≥ 151 d | -0.15..-0.02 | -0.050, -0.060, -0.154, -0.024 |

**"R² ≈ 0 at ≥ 151 d": CONFIRMED.** R-b is ≤ 0 in all four sessions, against R²_within of 0.19-0.26.

**P3, VERDICT-AT-RISK (conditional/exploratory H5 only; the final verdict is already "not verifiable").**
- φ = (R²_arm - R²_fixed)/(R²_within - R²_fixed) is inflated when R²_fixed ≪ 0. At 241 d, φ_Rb = 0.95 while the R-b R² = -0.06.
- The conditional H5 "PASS" (median 0.59) therefore reflects removal of a catastrophic offset, not restoration of a usable decoder. RESULTS already says this, and I agree.
- ρ = R²_fixed/R²_within has the same problem, so H4's median -2.14 means "worse than the mean", not a ratio. The H4 conditional PASS is robust anyway: R²_fixed ≤ 0.13 at every late session.

**R4 (reporting).** RESULTS §4 says a negative R²_fixed is "the bias term (‖WΔμ‖²) dominates". My decomposition does not support that in general:
- The squared mean error is **8-82 %** of the fixed decoder's test MSE. It is dominant only at +241 d (82 %); the other sessions are +3 d 41 %, +730 d 46 %, +151 d 8 %.
- Without the bias, R²_fixed would still be about -0.12 at 393 d and about 0.01 at 151 d.
- The day-0 z-units mean shift of day-k calib grows with lag (mean |z| 0.57 at +3 d → 2.39 at +730 d).
- Wording fix: "a large, lag-growing offset explains most of the negative R² at +3, +8, +241 and +730 d, but not all of the loss".

## 5. Harness FAIL diagnosis

**5a. PL-1 is analytically unreachable: CONFIRMED.**
- For any linear read-out, adding p = v1 + e (var e = 1 in v1-SD units) to a best-linear honest predictor with v1 residual fraction r gives the new residual r/(1+r). So the rise in variance-weighted R² is at most w1·r²/(1+r). This is an exact projection result for linear predictors, not a Gaussian approximation.
- Observed here: r = 0.284 and w1 = 0.556, so the expected rise is 0.0349.
- Reviewer empirical rise over 10 fresh noise seeds: 0.028-0.034, mean 0.031. The run reported 0.034.
- To reach 0.10, r must be ≥ 0.523 at this w1 (honest v1 R² ≤ 0.48), or r ≥ 0.370 even with w1 = 1.
- **The prereg was internally inconsistent.** At its own predicted ridge R² of 0.65 the expected rise was about 0.045, so the bar could not be met by design.

**5b. The NC1 I_net bar is mis-specified: CONFIRMED.**
- γ² = |S_xy|²/(S_xx S_yy) is invariant to any complex gain per frequency (sign, scale, delay). A readout trained on shuffled pairs is still a linear function of the trial's own neural data, which carries that trial's kinematics. Its output is therefore coherent with the true kinematics by an arbitrary sign or gain.
- The derangement null removes only pairing-independent (time-locked) structure. B0's I_net is exactly 0, as it should be.
- Reviewer shuffled-trained ridge, 5 new permutations: R² 0.023-0.064 (all ≤ 0.081, so all pass), and I_net -0.18, 0.49, 0.58, 1.74, 1.90 bits/s (4/5 fail the 0.15 bar). No leak is present.

**5c (new). The D2 NC1 R² bar (0.05) is also mis-specified.**
- On LINK day 0, 26 % of shuffled calib pairs share the same target (center-out, 22 target combinations). A shuffled-trained decoder therefore partly learns true kinematics.
- The flat-mean B0 (R² ≈ 0) gives no credit for trial-start-locked structure. A start-aligned mean profile alone gives R² 0.039.
- The D2 NC1 values (GRU 0.072, **KF 0.0597**, ridge 0.047) are therefore expected without a leak. The GRU part is PLAUSIBLE, not proven: I did not re-run the GRU.
- **R3 (reporting).** RESULTS §1 and DEVIATIONS §E name only the GRU as over the 0.05 bar. The KF (0.0597) is over it too. The §5 table has the number; the text omits it.

**Correctly specified controls.** These are for the NEW prereg and are not written here.
- **PL-1.** Size the leak from the dry run so that its analytic power is near-certain:
  - require an observed rise ≥ 0.5 × w·r²/(r + σ²) (the analytic expectation), with the planted SNR chosen so that this is ≥ 3× the bootstrap SD of the rise; or
  - plant both dimensions, or plant v1 at σ² = 0.1, making the expected rise about w1·r²/(r + 0.1) ≈ 0.12 here;
  - pre-compute the bar from the dry run, not from a guess.
- **NC1.**
  - Gate on sign/gain-aware accuracy: R², or a Gaussian information bound computed from the **residual** spectrum after a transfer function fitted on training/validation pairs only (−log2(S_ee/S_yy) per frequency).
  - If coherence bits are kept, compare the pipeline's shuffled decoder against a reference distribution. That distribution should come from M ≥ 20 independent shuffles, or from random-direction readouts of the same test neural data. FAIL only above an upper quantile, or above a fixed fraction (e.g. 10 %) of the honest I_net.
  - For D2: permute across different targets only (or condition on target), and use a trial-start-aligned B0 reference, as D1 uses an onset-aligned one.
- **PL-2.** It passes trivially (in-sample fit on the scored block). Keep it as a guard test, but do not treat it as power evidence.

## 6. Verdicts, reproducibility, A4

- **Verdicts.** M1_verdict.json gives harness FAIL (NC1 False, PL1 False; NC2a, PL2, PL3_gru, guard suite and reproducibility True). H1-H5 are "not verifiable: harness", with conditional verdicts PASS/FAIL/PASS/PASS/PASS; H6 is "NOT TESTED (A4 cut (1))". The finalize_m1.py logic matches prereg §6 and A2. **CONFIRMED.**
- **Reproducibility.**
  - `card_hash` recomputed on both cards (minus the stored hash field) = `c7bd7ac526cb...af0` for run1 and rerun.
  - The only differing top-level key is `runtime`.
  - code_sha256 matches all 10 current code/test files, and nfharness_sha256_readonly matches all 16 files (15 nfharness + edf_reader), so nfharness is unmodified.
  - **CONFIRMED.** The pytest `counts: {}` in the card is cosmetic: my re-run shows 40 passed.
- **A4.**
  - The cuts were applied in prereg order: D3 first, then GRU seeds 3 → 1. The code refuses GRU_SEEDS_1 without D3. The cuts are logged in the card (`A4_cuts`) and in the split lock (seeds [20261001]).
  - They were decided before the real run: the 00:05 synthetic run already carried them.
  - Note on DEVIATIONS §C: its "a later synthetic run … took ~1.6× longer" is not visible in the surviving logs. The surviving synthetic run used 1 seed and its D1 took 37 s, against 127 s for the 3-seed dry run.
  - Rebuilding the estimate from the surviving timings (D1 scales about 4.7× Small → Large; 3 seeds) still gives a total of roughly 1,100-1,300 s, which is borderline over 1,200 s. The overrun prediction was defensible, and the cuts stand. **CONFIRMED.**

## 7. Findings list

| id | severity | finding |
|---|---|---|
| R1 | BUG (reporting) | RESULTS: the snapshot is "mtime 00:08:36, 6 s before the real run". Actual creation/write time is 00:08:51.7, about 10 s after run1 started and 4.5 s before the first data read. |
| R2 | BUG (reporting) | RESULTS §3: the D1 KF has "23 Riccati iterations". The card says 85; 23 is the D2 day-0 KF. |
| R3 | BUG (reporting) | D2 NC1: KF R² 0.0597 also exceeds 0.05. The text names only the GRU. |
| R4 | BUG (reporting) | "The bias term dominates negative R²_fixed" holds only at +241 d. The bias share is 8-82 % of MSE. |
| C1 | code note | The SessionOrderError calls use literal day lists, not the fitted data, so the guard is decorative in D2. No leak exists (verified structurally). |
| C2 | code note | Condition folds use maze_id (9), not the 27 type×version conditions. Disclosed and descriptive. |
| P1 | prereg design | PL-1 is unreachable by construction (5a). |
| P2 | prereg design | The NC1 I_net bar ignores sign/gain (5b); the D2 NC1 R² bar ignores target sharing (5c). |
| P3 | VERDICT-AT-RISK (conditional only) | φ and ρ are ill-conditioned when R²_fixed < 0. The H5 conditional PASS does not mean the decoder is usable. |
| P4 | interpretation | M-BITS includes DC: 7.8 of 25.6 bits/s for ridge. |

**Conclusion.**
- The M1 numbers (D1 ridge/KF R² and bits, D2 drift and recalibration) are independently reproduced.
- No leak was found.
- The final verdicts (harness FAIL, all H "not verifiable: harness", H6 NOT TESTED) are CONFIRMED.
- R1-R4 should be corrected in RESULTS_M1.md before anything reaches THEORY.md, and the numbers remain EXPLORATORY.
- A new prereg is needed for PL-1 and NC1 (§5).
