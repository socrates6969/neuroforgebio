# M1b: deviations and implementation specifications

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Computational decoding of recorded activity only.

- Prereg: `prereg\M1b_confirmatory.md`, SHA-256 `c30873dec5c65929462dfc9c06451f6e68c1e997207757b16be113484710d9a1`
  (recomputed by the coder before any data read; hard-coded in every M1b script, which refuses to run on mismatch).
- Fresh lock `e6856172...2792` and power-check lock `01cf828b...5ce9` (§1.5) recomputed from the prereg text: both match.
- Author: coder-verifier (motor-readout, cycle 2), for Marius Carlsson, 2026-09-27.
- **Written BEFORE the power check and BEFORE any fresh download.** At this point no fresh file exists on disk. The only
  data read so far are the trial tables (conditions, start/stop times) of the OLD files MC_Maze_Large, MC_Maze_Small, LINK
  20200127 and 20200626 (to size the condition-constrained derangement; see DV-b1). No behaviour or neural value was read.
- Anything added after the power check is marked **POST-POWER**; after the fresh download **POST-DOWNLOAD**; after the vault
  opens **POST-RUN**.

## A. Deviations from the prereg text

| ID | prereg | what is done | why |
|---|---|---|---|
| DV-b1 | §6.1 NC1 sampler: "rejection sampling of uniform permutations until no trial is paired with itself or with a same-condition trial; at most 10⁵ draws" (silent on what happens when the cap is hit) | The literal rejection sampler runs first (10⁵ draws, stream 2 / stream 8). **Only if it hits the cap**, a symmetric random-transposition Markov chain is run on the set of valid constrained derangements: start = the deterministic cyclic shift by the largest class size of the condition-sorted order (valid whenever no class holds > 50 %); 200·N proposed swaps of two images, a swap accepted iff both new pairs are cross-condition. The chain is symmetric and (for this block structure) irreducible, so its stationary law is the uniform law over constrained derangements, the same target as the rejection sampler. The method used ("rejection" / "mcmc" / "unconstrained (>50 %)") and the number of draws are recorded per permutation and in the split lock. The > 50 % rule (unconstrained derangement + flag) is applied as written. | Trial tables of the OLD files (read before this note): LINK 20200127 calib has 112/225 = 49.8 % trials at target (0.5, 0.5) and val 37/74 = 50.0 %; the expected number of same-condition pairs of a uniform permutation is ≈ 59 (calib) and ≈ 20 (val), so P(valid) ≈ e⁻⁵⁹ and the literal sampler cannot succeed in 10⁵ draws. MC_Maze_Large train (300 trials, 27 conditions) has ≈ 11.4 expected same-condition pairs, P(valid) ≈ 1e-5, i.e. about a 30 % chance of hitting the cap. Without a fallback the prereg's NC1 is not computable on D2 at all. This choice needs ratification by the mathematician / reviewer; it is fixed now, before any power-check number exists. |
| DV-b2 | §6.1 NC1 "null values": under a constrained derangement the partner kinematics are only weakly anti-informative (weight 1/(N−1)) | No change to any rule. **Note:** the weight 1/(N−1) holds only when classes are small. With a 50 % centre class every centre trial is paired with an outward trial and vice versa, so the partner is strongly anti-informative (weight ≈ n_c/(N−n_c) ≈ 1). The R² null is then well below R²_B0 and I_mse,net(shuf) is expected < 0; NL-1 (25 % true pairs) may be partly cancelled by this anti-information on D2. §7 P2/P3 measure it. | stated so the power-check reader knows the prediction |
| DV-b3 | §9 "New tests" location | New tests live in `code\tests_m1b\` (new folder), so `code\tests\` (the M1 guard suite, 40 tests) stays byte-identical and is run unchanged. "The full motor-readout suite" = `code\tests` + `code\tests_m1b`. | do not modify M1 files |
| DV-b4 | §10 run order step 1 "Post this prereg's SHA on BOARD" | Already posted by the mathematician (BOARD, "M1b prereg LOCKED ... sha256 c30873de...d9a1"). Not re-posted. | done |
| DV-b5 | Owner rule "BLAS threads = 1" | numpy/scipy BLAS = 1 thread (OMP/OPENBLAS/MKL env set before numpy import). The GRU uses `m1lib.decoders.torch_setup`, **unchanged**, which sets torch intra-op threads = 4 and deterministic algorithms (the M1 prereg spec; M1b §9 requires m1lib to be imported unchanged). | reuse by import only |
| DV-b6 | §10 "Post ... SHA on BOARD" several times (prereg SHA, POWER SHA, DEVIATIONS snapshot twice) vs owner instruction "post one line" | One BOARD line **before the fresh download** carries the POWER_M1b.json SHA and the DEVIATIONS_M1b.md snapshot SHA (C17). The run script re-hashes DEVIATIONS_M1b.md immediately before the vault opens and records it in the card and run log; if it differs from the posted SHA, the change is listed in §E and a second BOARD line is posted. The final report is one more line. | reconcile prereg provenance with the owner instruction |
| DV-b7 | §7 P2 "... on Large, Small, synthetic and LINK 20200127 (ridge)" | Gating as written (LINK: ridge). R-b's FA-ridge NC1 on LINK 20200127 is also run and reported **descriptively** in the power check, because it gates the real D2 harness (§6.1). | early warning only; no new gate |

## B. Implementation specifications (prereg silent or ambiguous; fixed before the power check)

1. **Files and code.** New code only: `code\m1b\` (`__init__.py`, `core.py`, `synth.py`, `pipeline.py`), `code\power_m1b.py`,
   `code\download_m1b.py`, `code\run_m1b.py`, `code\finalize_m1b.py`, `code\figures_m1b.py`, `code\tests_m1b\`. m1lib,
   nfharness and edf_reader are imported unchanged; their SHA-256 values go in every card. Blocks copied from `run_m1.py`
   cite the source line.
2. **RNG streams** (seed 20261001, `nfharness.config.rng`, SeedSequence spawn_key = (k, sub...)): 1 bootstrap, 2 NC1
   derangements, 3 bits null, 4 H6 sign-flip, 5 D3 label permutations, 6 planted leaks, 7 power-check synthetic, 8 NL-1
   subset. Sub-keys are listed in the card. GRU seeds: honest D1 ensemble 20261001-3; every other GRU 20261001.
3. **D1 conditions.** Condition = (trial_type, trial_version) from the trial table. Condition-held-out folds (descriptive):
   fold = (rank of the condition in sorted order) mod 5.
4. **D1 grid / decoders.** As M1 DEVIATIONS B.2, B.5-B.7: 20 ms, window bins [-250, +450) ms (W = 35), history H = 10,
   ridge on lagged z-scored counts (lag-major), λ grid `m1lib.decoders.LAMBDAS`, first max on validation.
5. **KF-L.** Observation o_t = (1/B) Σ_{b=0}^{B-1} z_{t−L−b} (sum of B shifted slices of the z-scored count array, so
   (L, B) = (0, 1) returns the KF-0 observation bit-for-bit). Rows t are window bins; t−L−B+1 ≥ window start − 9 always lies in
   the 10-bin history. `KalmanVel.fit(velocity segments, observation segments)` on train window bins; filter run from the
   window start. Grid order (B ascending, then L ascending); the first maximum of validation R² wins. The NC1 KF-L selects
   (L, B) on its (shuffled) validation pairs.
6. **Bits.** Segments and taper as M1 (Hann `np.hanning`, rfft). Primary mask 0 < f_j ≤ 10 Hz (exact integer test
   j·1000 ≤ 10·n·bin_ms, j ≥ 1). I_coh uses `m1lib.metrics.bits_from_spectra` with that mask; the DC-included value uses
   `m1lib.metrics.freq_mask`. I_mse = Δf Σ_d Σ_j log2(Σ_k|Y_k|² / Σ_k|Y_k − Ŷ_k|²) with Y = true, Ŷ = issued output; no
   clipping (a zero Ŝ_ee would give +inf; this is recorded, never observed in practice). The I_coh and I_mse nulls use the
   **same** 200 derangements of the true segments (stream 3); net = raw − null median. Bootstrap CIs of I_coh,net subtract
   the fixed full-sample null median (M1 B.10).
7. **B0.** D1: mean training window velocity per bin (onset-aligned; as M1). D2: trial-start-aligned mean over the anchor's
   (or, descriptively, the session's) calib trials: bin i of the profile = mean over calib trials with length > i;
   profile length = the longest calib trial; a test trial longer than that repeats the last profile value.
8. **NC1 construction.** D1: M1 DV-6 (train and val pairs both deranged, independently; λ / (L, B) / GRU epoch selected on
   the deranged val pairs). D2: as M1 DV-7 (each pair truncated to the shorter trial, aligned at trial start; ridge lags from
   the continuous session). Gated D2 decoders: ridge and R-b's FA-ridge (FA fitted on anchor calib neural data only, which a
   derangement does not change; the latent ridge is trained on the deranged pairs). D2 KF/GRU NC1: descriptive.
   Permutations for the real run are drawn before any fit and written into the split lock with their hashes.
9. **NL-1.** Stream 8 picks exactly round(0.25·n) kept trials (without replacement); the other trials are re-paired by
   the NC1 sampler among themselves (constrained derangement, DV-b1 fallback, > 50 % rule applied within the subset).
   Train and validation pairs both use NL-1. NC1 "FAIL" under NL-1 = R²_shuf > R²_B0 + 0.03 **or** I_mse,net(shuf) >
   0.10 × I_mse,net(honest ridge).
10. **PL-1.** Columns `planted_v1`, `planted_v2` = (v_d − train mean_d)/train SD_d + N(0, σ²) (stream 6; one fresh draw per
    row, in the order train, val, test), un-lagged, appended to the honest ridge design; same λ grid, first max on
    validation. E = Σ_d w_d r_d²/(r_d + σ²) with r_d = SSE_d/SST_d and w_d = SST_d/Σ SST of the **honest ridge validation**
    predictions. If E < 0.10, σ² = 0.02 and E is recomputed. s = SD over B = 2000 bootstrap replicates (resampling
    validation units: D1 trials, D2 64-bin segments; stream 1) of R²_planted,val − R²_honest,val. Valid iff 0.5E ≥ 3s.
    PASS iff valid, test rise ≥ 0.5E, and the undeclared whitelist call raises `FeatureWhitelistError`. D2: planted on each
    anchor's day-0 ridge (lagged SBP, H = 6), test values via `vault.planted_access` (declared).
11. **PL-2'.** Rows = anchor calib (tags (anchor, calib)) + session-k calib (tags (k, calib)), true labels; λ fixed to the
    honest anchor λ; anchor z-scorer; scored on the session-k test block. The undeclared call passes the **row tags** of
    those rows to `assert_session_order(0, days, blocks)` and must raise `SessionOrderError`. "Not informative" iff
    R²_within − R²_fixed < 0.05 (then it does not gate).
12. **Row tags (review C1).** Every D2 fit derives (lag, block) tags from the rows actually passed (training rows and
    selection rows) and calls `assert_session_order(declared_day, tags_days, tags_blocks)`.
13. **Drift metrics.** Per session k of anchor a: L_k = R²_within − R²_fixed; ψ_arm = R²_arm/R²_within (only if
    R²_within ≥ 0.15); Δ_ab = R²_Rb − R²_Ra. Usable: H4 R²_within ≥ 0.10; H5a/H5b R²_within ≥ 0.15. Bootstrap per session
    (stream 1, independent per session, B = 2000, paired within session); the median over sessions is taken per replicate;
    99.5 % percentile CI.
14. **NC2a.** D1: ridge, KF-0, KF-L, GRU (gated). D2 (each anchor): honest ridge (gated); KF and GRU descriptive (C15).
    Bar max(0.05, R²_B0 + 0.02) with the arm-correct B0.
15. **H3** ranking equality uses point estimates of M-R2 and I_coh,net (DC excluded) of {GRU, ridge, KF-L}.
16. **A6.** Medium: `processing/behavior/hand_vel` and `intervals/trials/move_onset_time` exist and ≥ 200 trials. LINK:
    all `target_style` == CO, median SBP timestamp step in [0.019, 0.021] s, ≥ 300 trials. Trial and timing tables only.
17. **Synthetic generator (stream 7).** D1-like: 250 trials on the M1 grid (85 bins of 20 ms, onset at 750 ms), 27
    conditions = reach directions 2πc/27; velocity = one main reach (Gaussian speed bump at onset + 200 ms, SD 80 ms, gain
    U(0.8, 1.2), condition direction) + 7 random sub-movements (centre U(−750, 1050) ms, SD U(40, 150) ms, gain U(0.2, 0.5),
    random direction) — "a sum of 8 random reach profiles"; 150 units, x_t = C v_{t+5} + s·N(0, I), C ~ N(0, 1). s is set
    by bisection (14 steps on log s, calibration draw with its own sub-key) so that the honest ridge test R² is 0.4 / 0.6 /
    0.8 ± 0.02. D2-like: 375-trial sessions of 20 ms bins, centre-out (every second trial returns to the centre target
    (0.5, 0.5); outward targets from 21 index/MRS positions), 96 channels x = C_k v_{t+3} + μ_k + noise; drift = rotation
    of the loading matrix toward an orthogonal one by angle θ(lag) = (π/2)·min(1, lag/240) plus a mean shift
    μ_k = μ_0 + (lag/120)·N(0, 1).
18. **Power-check datasets.** D1: synthetic (R² 0.4 / 0.6 / 0.8 for P1; 0.6 for P2/P3), Large, Small (M1 splits). D2: LINK
    20200127 as an anchor (P1, P2, P3; ridge gated) and 20200127 → 20200626 (P5), plus a synthetic anchor → +120 d pair
    (P5). Old test labels are read directly (old data; no vault) — this is the power check, never a verdict.
19. **P6** uses the `m1lib.synthetic` EEG generator for 20 synthetic subjects (paths are fake keys; no real EEGMMIDB value).
    "20 seeds" = 20 stream-6 draws of the planted channel; per seed, accuracy = mean over the 20 subjects of the PL-4 LDA
    test accuracy. The real-run bar "≥ honest LDA + 0.15" is reported descriptively (the synthetic data are easy).
20. **P7 and A4.** Dry run = the real pipeline with D1 = MC_Maze_Small, both D2 anchors = LINK 20200127 and all 11
    follow-up slots = LINK 20200626 (13 sessions, one in memory at a time), D3 = synthetic EEG. Projection: wall(D1) × 2.5
    (250/100 trials; M1 measured Small→Large scaling ≈ 0.94 × the trial ratio) + wall(D2) + wall(D3) + pytest. **Rule:** cut
    in the prereg order while 1.25 × projected wall ≥ 1,200 s or projected peak RSS ≥ 1,536 MB (1.25 = margin for machine
    contention). The decision and the numbers go in POWER_M1b.json before the download.
21. **Vault.** As M1 B.16: all fresh test-block behaviour deposited before any fit; `final_score` once per (key, score_id)
    after `freeze`; declared planted reads only (PL-1 D1, PL-1 D2 anchors, PL-3, PL-4 test run).
22. **Reproducibility.** Card hash = nfharness `card_hash` (canonical JSON minus `runtime`) of `--tag run1` and a
    fresh-process `--tag rerun` must be identical.

## C. Power check (POST-POWER entries appended below)

## D. A4 decision (POST-POWER)

## E. POST-DOWNLOAD / POST-RUN

## B2. Pre-read deviation: non-fresh LINK sessions (queen decision, 2026-09-27, BEFORE any M1b read of fresh data; file SHA before this entry 7bfb377d...8135)
Fact (from bci-math's LINK-LEDGER v2, SHA 16bfa28a..., and queen-science): other teams used 6 of M1b's 13 sessions after M1b's prereg was locked, independently of M1b.
- 20210309 and 20211112: fully decoded by bci-hive 028 (including test blocks) and reused by 031.
- 20200708, 20210706, 20220307 and 20220718: neural data read descriptively by bci-hive 007 (SBP amplitude, modulation, impedance; no decoding).
Decision:
1. No substitution (the prereg forbids it). All 13 sessions stay in M1b's CONFIRMATORY analysis. Blindness is about the M1b decision-makers,
   and M1b's prereg, selection rule, thresholds and code were fixed before, and without knowledge of, those experiments.
2. Reverse seal (binding, adopted by queen-science). No M1b agent (mathematician, coder, reviewer) opens any 028/031/007 per-session result for these
   6 sessions until M1b reports. Every M1b agent prompt carries this rule. The queen is not told those results either.
3. Pre-specified, added now and DESCRIPTIVE ONLY (it cannot change a verdict): re-compute H4a/H4b/H5a/H5b excluding the 6 non-fresh sessions.
   If the verdict label on the fresh-only subset differs from the full-set label, report both and add the flag "verdict depends on sessions
   also analysed elsewhere". Two of the 6 are the ANCHORS (20200708 = A1, 20210706 = A2). They were only read descriptively by 007, never decoded, so the anchors and their day-0
   decoders are KEPT. The fresh-only subset drops the 4 non-fresh LAG sessions (20210309 = A1 +244; 20211112 = A2 +129; 20220307 = A2 +244; 20220718 = A2 +377),
   which leaves 4 lag-30-plus sessions (A1 +120, +366; A2 +30, +62) and all 3 short-lag sessions. If fewer than 5 lag-30-plus sessions remain, the fresh-only H4a/H5 labels
   are reported as "descriptive, n < 5", mirroring the prereg's usability rule.
4. The per-session list and the ledger SHA are cited in RESULTS_M1b.md.
