# M1: deviations and implementation specifications

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.

Prereg: `prereg\M1_decoder_comparison.md`, SHA-256 `9eada9d79c849b2c5572dd4eb629ef29d0dc9b294e8933a05de674a8bd4bd06f`
(verified by `download_m1.py` and `run_m1.py` before any data read). Input-lock hash `aa0f8e1b...` recomputed and matched.
Author: coder-verifier (motor-readout), for Marius Carlsson. **Written 2026-09-27 BEFORE the real run.** At this point:
- only the MC_Maze_Small dry run (DANDI 000140) and a synthetic end-to-end run had been scored;
- no MC_Maze_Large or LINK test-block value had been read (LINK: only timing and trial metadata, bin widths and
  target styles were inspected; MC_Maze_Large: only the trial table and unit count).

Anything added after the real run is marked **POST-RUN**.

## A. Deviations from the prereg text

| ID | prereg | what was done | why |
|---|---|---|---|
| DV-1 | D2 SBP bins: "if these are not 32 ms, re-bin to 32 ms and log a deviation" | LINK NWB bins are **20 ms** (median dt 0.0200 s, range 0.019-0.021, no gaps > 50 ms, all 9 sessions). SBP and both velocities are re-binned to 32 ms by area-preserving averaging on the uniform index grid: old bin i covers [20i, 20i+20) ms, new bin m covers [32m, 32m+32) ms. Timestamp jitter is ignored. | anticipated by the prereg |
| DV-2 | D2 target style: CO if present, otherwise RD and flag | Each LINK file holds a single style: 20200228 (lag 32 d) and 20220126 (lag 730 d) are **RD only**. They are used and flagged `flagged_random_targets` in the card; the other 7 sessions are CO. | prereg rule applied |
| DV-3 | M-R2 = sklearn `r2_score(multioutput='variance_weighted')` | sklearn is not installed and was not installed (install rule: h5py + torch only). `r2_vw` = 1 - Σ_d SSE_d / Σ_d SST_d, which is identical to the sklearn definition. It is unit-tested against the weighted per-dimension formula. LDA, logistic regression and Riemannian geometry are numpy/scipy (as data_plan §3 says). | no sklearn |
| DV-4 | Dry run on MC_Maze_Small (§8.2, A4) | The 000140 train file (29.2 MB, DANDI digest matched) was downloaded in addition to the data_plan list. Total download: 730,193,426 B (< 0.80 GB cap). | prereg run order needs it |
| DV-5 | A4 budget | **Cuts (1) D3 and (2) GRU seeds 3 -> 1 (seed 20261001) applied**, logged in the card (`A4_cuts`). See §C. | prereg A4 |
| DV-6 | NC1 "each decoder is retrained on train pairs where trial i's neural data is paired with trial π(i)'s behaviour" | Validation pairs used for λ selection and GRU early stopping are **also shuffled** (an independent permutation of validation trials; D1 stream 2 sub-key 3, D2 stream 2 sub-key 4). An early version selected on honest validation pairs. The synthetic check showed that this lets the "shuffled" decoder pick the λ or epoch whose readout matches the true pairs, i.e. true-pair information enters the negative control. Changed before any real data were scored. | removes a leak INTO the null decoder |
| DV-7 | D2 NC1 / NC2a with variable trial lengths | Each pair is truncated to the shorter trial (aligned at trial start). The D2 negative controls are run on day 0 only (ridge, KF, GRU) and gate on day 0. | prereg silent |

## B. Implementation specifications (prereg silent or ambiguous; fixed before the real run)

1. **Splits.** Trials are sorted by start time. The cut indices are c1 = round(0.6n) and c2 = round(0.8n). The trial at c1 and the
   trial at c2 are the dropped gap trials. D1 (n = 500): 300 / 99 / 99 (+2 gap). D2 (n = 375): 225 / 74 / 74 (+2 gap). The same
   one-trial gap is used in D2 ("the same 60/20/20 chronological split").
2. **D1 grid.** Bins are onset-aligned on [-750, +950) ms (20 ms: 85 bins). The window is bins [-250, +450) (35 bins), preceded by
   H history bins (input only). Every trial has >= 0.968 s before and >= 0.963 s after onset inside [start, stop], so no bin
   leaves its trial. Velocity per bin = mean of the 1 kHz `hand_vel` samples in the bin (m/s). Spike counts use all 162 units,
   including NLB "held-out" units. The NLB train/val column is ignored.
3. **Condition folds (descriptive).** Condition ID = `maze_id` (9 mazes). Fold = (rank of maze_id in sorted order) mod 5, i.e.
   "id mod 5" applied to the sorted index, so that no fold is empty.
4. **Selection.** Final models are fitted on train (D2: calib) only. Validation only selects λ / γ / C and GRU early stopping. On
   ties the first grid value wins.
5. **Ridge.** The intercept is unpenalised (X and Y centred on training means). Features are z-scored counts / SBP lagged
   k = 0..H-1 (lag-major), zero outside the array. D2 lags are computed on the continuous session, so history can come from the
   preceding gap trial or block (neural input only; labels never cross a partition).
6. **Kalman.**
   - Fitting: A by least squares on consecutive bin pairs within segments, with the constant row fixed to [0,0,1]. C by least
     squares. Q and R are residual covariances (divide by n); Q's constant row and column are 0.
   - Gain: steady-state K by iterating the Riccati recursion from P = Q until max|ΔK| < 1e-13, then the constant-gain filter
     z_t = (I-KC)A z_{t-1} + K x_t from z_{-1} = train mean state.
   - D1: fitted on window bins of train trials; run from the window start of each trial.
   - D2: fitted on the contiguous calib block; run continuously from the start of each block.
7. **GRU.**
   - Targets are z-scored with train mean/SD and inverted after prediction. Loss = MSE over masked bins. The best-validation-epoch
     weights are restored.
   - D1: sequence = 10 history + 35 window bins; the history bins are the warm-up (not in the loss).
   - D2: non-overlapping 64-bin chunks of the calib block (last partial chunk dropped; the first 10 bins of each chunk are not in
     the loss). Val/test are run continuously over the block with a 10-bin neural-only warm-up from the preceding bins.
   - Threads: torch.set_num_threads(4) and deterministic algorithms (prereg). numpy BLAS threads = 1 (owner rule).
8. **R-a** re-z-scores day-k SBP with day-k calib mean/SD; the fixed day-0 ridge weights are then applied.
9. **R-b.**
   - Inputs are scaled by the day-0 calib SD on every day (common units for the loadings); each day's FA estimates its own mean.
   - FA: 10 factors, EM for 200 iterations. Init = PCA loadings with noise variance = mean of the remaining eigenvalues. Ψ floor
     = 1e-6 · mean diag(S).
   - Posterior mean E[z|x]; aligned latents = E[z|x]·O with O = UVᵀ from svd(L_kᵀL_0).
   - Day-0 ridge on the lagged (H = 6) latents, λ by day-0 val.
   - Unit test: 10/40 channels given new loadings plus an offset are re-aligned (R² 0.8+ vs day-0 latents). A pure latent
     rotation L0 -> L0·Q is not identifiable from x and is not claimed.
10. **M-BITS.**
    - `np.hanning` (symmetric) taper, rfft. f_j = j·1000/(n·bin_ms) Hz, kept if f_j <= 10 Hz (exact integer test; DC
      included). D1: j = 0..7 (Δf = 1.4286 Hz, 10.0 Hz included). D2: j = 0..20 (Δf = 0.488 Hz).
    - γ² is clipped to [0, 1-1e-12] and defined as 0 where a spectrum is identically zero (constant B0 prediction).
    - Null = 200 random derangements (stream 3). Bootstrap CIs of I_net use I_raw on resampled segments minus the fixed
      full-sample null median (the null is not recomputed per replicate).
11. **Bootstrap.**
    - D1 units = test trials. D2 units = consecutive 64-bin segments of the test block; the last partial segment is a unit for
      R² but not for bits.
    - Weights come from `numpy.random.default_rng(SeedSequence(20261001, spawn_key=(1, ...)))`.
    - CI of the median ρ / φ over sessions: each session's bootstrap is drawn independently, and the median is taken per
      replicate.
12. **D2 bins in partitions.** Trial owner per 32-ms bin is set by bin centre, with trial k spanning [start_k, stop_k + 20 ms).
    Bins with no owner inside a block range are excluded from loss and scoring. Every bin has exactly one owner
    (`assert_bins_disjoint`).
13. **PL-1.**
    - One un-lagged column `planted_v1` = (v1 - train mean)/train SD + N(0,1) (stream 6) is appended to the ridge design, with
      the same λ grid and selection on val.
    - Test values come from `vault.planted_access` (declared, logged). The undeclared call is made first and must raise
      FeatureWhitelistError.
14. **PL-2.** Ridge on day-0 calib plus the day-32 (20200228) test block. λ is fixed to the honest day-0 λ; day-0 z-scoring is
    used. The undeclared call must raise SessionOrderError.
15. **PL-3.**
    - Bin-level random 60/20/20 split over all 500 × 35 window bins (stream 6). Centred ±5-bin features (11 × 162 = 1782)
      with the honest train z-scorer.
    - GRU: loss on random-train bins; early stopping on random-val bins; R² on random-test bins vs the honest GRU test R².
      Ridge is descriptive.
    - Labels of test-block trials come via `vault.planted_access` (logged). The undeclared split and features must raise.
16. **Vault.**
    - All test-block behaviour is deposited before any fit.
    - `final_score` is allowed once per (key, score_id) after `freeze(sha256 of all model hashes)`.
    - The frozen-model file `results\M1_frozen_models_<tag>.json` is written before the first vault read. The run log
      timestamps "split lock written", "FIRST MODEL FIT", "models frozen" and "VAULT OPEN".
17. **RNG streams** (seed 20261001): k=1 bootstrap, 2 NC1 shuffles, 3 bits null, 4 H6 sign-flip, 5 D3 label permutations,
    6 planted leaks. GRU seeds are 20261001-3 (after the A4 cut: 20261001).
18. **D3 (cut by A4; code kept and synthetic-tested).**
    - scipy `butter(4, [8, 30], 'bandpass', fs=160)` + `sosfiltfilt` per run; epoch [onset+0.5, onset+2.5) s = 320 samples.
    - log-variance with ddof 0. γ = 0 LDA uses pinv; the LDA bias includes the log prior ratio.
    - Logistic: 0.5‖w‖² + C·Σ log-loss, intercept unpenalised, L-BFGS-B. Riemannian mean initialised at the arithmetic mean.
    - A6 operationalised as: only T0/T1/T2; both T1 and T2 present; T1/T2 durations in [3.5, 5.0] s; file 110-130 s.
    - c = mean interval between consecutive T1/T2 cue onsets in run 12, pooled over subjects.
    - Miller-Madow bias = (Bx-1)(By-1)/(2n ln 2).
19. **A3** is evaluated on the honest ridge validation R² (D1 and D2 day 0), before `freeze()`.
20. **Reproducibility.** The card hash (nfharness `card_hash`: canonical JSON minus `runtime`) must be identical between
    `--tag run1` and a fresh-process `--tag rerun`.

## C. A4 budget decision (from the dry run, before the real run)

- Dry run (MC_Maze_Small, D1 only, 3 GRU seeds, all D1 controls and descriptives): **196 s wall, 802 MB peak** (pytest 19 s).
  The Small GRUs used all 50 epochs.
- Synthetic timings: a D2-sized GRU (160 chunks × 64 × 96) takes 0.44 s/epoch/seed; a D1-Large-sized GRU takes
  0.32 s/epoch/seed; the PL-3 GRU (500 × 45 × 1782) takes 1.4 s/epoch/seed.
- The machine is shared with other agents: a later synthetic run of the same D1 code took ~1.6× longer.
- **Prediction for the full run:**
  - D1 on MC_Maze_Large ≈ 5 × the dry-run D1 time (5× the trials) ≈ 865 s.
  - D2 GRUs (10 ensembles × 3 seeds × 30-50 epochs) ≈ 400-650 s. D3 + loading + pytest ≈ 100 s.
  - **Total ≈ 1,350-1,600 s > 1,200 s → overrun.**
- Cut (1) D3 (saves < 1 min; still ≈ 1,300-1,550 s) → cut (2) GRU seeds 3 → 1. Predicted ≈ 500-700 s (×1.6 contention:
  ≤ 1,100 s) < 1,200 s. **Stop cutting.** NC2b, the bin sweep and D2 GRU are kept.
- Consequences:
  - **H6 = NOT TESTED (A4 cut 1).**
  - The GRU in H1/H3 and in the GRU drift curves is a **single-seed** GRU (seed 20261001), not a 3-seed ensemble.

## D. Pre-run power notes (predictions recorded BEFORE the real run; they change no rule)

1. **PL-1 is probably underpowered by construction (prediction: PL-1 FAIL → harness FAIL).**
   - The planted channel carries v1 at SNR 1 (unit-variance noise on z-scored v1) and nothing about v2.
   - For a linear-Gaussian model, adding an independent unit-noise observation of v1 lowers v1's residual fraction from r to
     r/(1+r). The expected rise of the variance-weighted R² is therefore ≈ w1 · r²/(1+r), with w1 = var(v1)/(var(v1)+var(v2)).
   - At the prereg's predicted honest ridge R² ≈ 0.65 (r ≈ 0.35, w1 ≈ 0.5), the expected rise is ≈ 0.045. Reaching 0.10 would
     need r ≥ 0.56 (honest R² ≤ 0.44) even with w1 = 0.5.
   - Dry run (Small): honest 0.574, planted 0.614, rise 0.040 < 0.10 → PL-1 FAIL, while the code guard (FeatureWhitelistError)
     worked.
   - The prereg's harness rule is kept as written: if PL-1 fails, harness = FAIL, all H verdicts become "not verifiable:
     harness", and the numbers are exploratory (A2).
   - Reported in addition (not gating): the expected rise w1·r²/(1+r) computed from the honest per-dimension residuals, to
     show whether the observed rise matches the leak's theoretical power.
2. **NC1 I_net <= 0.15 bits/s may fail without any leak.**
   - M-BITS is invariant to sign and gain. A decoder trained on shuffled pairs is still some linear (or GRU) readout of neural
     data that carries kinematic information, so its output can be coherent with the true kinematics by chance of direction.
   - Synthetic D2 (low-dimensional, high-SNR): shuffled ridge/KF/GRU gave I_net 2.8-5.0 bits/s with R² ≤ 0.11 (this run
     still selected on honest val; DV-6 fixes that part).
   - Dry run D1 (Small, K = 19 segments): KF 0.59 and GRU 0.67 bits/s, ridge -0.02.
   - After DV-6 (shuffled validation too), the final-code synthetic run still gives D2 NC1 I_net ridge 8.97, KF 2.81 and
     GRU 1.67 bits/s, with KF R² 0.114 > 0.05. So the effect is structural, not a selection leak.
   - With K = 99 in MC_Maze_Large the estimator noise is ~5× smaller, but the random-readout effect remains. The rule is
     kept as written. **Prediction: NC1 is at risk of FAIL on D2 day 0 (and possibly D1) without any leak.**
   - Final-code synthetic PL-1 diagnostic (D1 = MC_Maze_Small): expected rise 0.053, observed 0.040.
3. **KF on D1 is expected to be well below ridge.** In the dry run KF 0.25 vs ridge 0.57. The prereg KF uses the current
   20 ms bin with no lag and is re-initialised at the window start. H2 (TOST ±0.05) is therefore expected to FAIL; this is a
   prediction, not a change.

## E. POST-RUN

**POST-RUN (2026-09-27, after run1 and the rerun; no code, rule or threshold was changed after the vault opened).**
- **Pre-run predictions D.1 and D.2 held.**
  - PL-1: observed rise +0.034 vs analytic expectation +0.035 → FAIL.
  - NC1: I_net 0.79-2.22 bits/s on D1 and 0.88-1.48 on D2 day 0 → FAIL. The D2 day-0 GRU R² 0.072 also exceeds its 0.05 bar.
  - Harness = FAIL, so all H verdicts are "not verifiable: harness" (A2). Conditional verdicts are reported as exploratory in
    RESULTS_M1.md.
- **D.3 held:** KF 0.286 vs ridge 0.669 (H2 conditional FAIL).
- **A4:** the real run took 378 s and 1,268 MB (rerun 339 s), ~3× faster than the dry-run-based prediction. The cuts
  (D3; GRU 1 seed) were decided before the run per prereg A4 and are not revisited.
- **Guard suite:** the pytest summary regex in the card recorded `counts: {}` (the -q output line was not captured). The
  return code was 0 and a manual run gives 40 passed. This is cosmetic.
- **Figures:** the y/x axes are clipped and off-scale values are listed on the plots (R²_fixed down to -6.7, ρ down to -56).
  This was a presentation change only.

## M1b (cycle 2; added 2026-09-27, before any M1b run)

The M1 sections above are unchanged. M1b (prereg\M1b_confirmatory.md, SHA c30873de...d9a1) keeps its deviations and
implementation specifications in **code\DEVIATIONS_M1b.md** (the file the M1b prereg names; its SHA-256 is posted on
BOARD before the fresh download, C17). Summary of the M1b deviations logged there before any run:
- DV-b1: the NC1 condition-constrained derangement falls back to a uniform-target Markov chain when the literal
  rejection sampler hits its 10^5-draw cap (LINK's centre target holds ~50 % of trials, so rejection cannot succeed).
- DV-b2: note that the prereg's "weakly anti-informative" null does not hold with a 50 % class (no rule changed).
- DV-b3: M1b tests live in code\tests_m1b\ so the M1 suite in code\tests\ stays byte-identical.
- DV-b4..b7: BOARD posting, torch threads (M1 torch_setup unchanged), descriptive FA-ridge NC1 in the power check.
