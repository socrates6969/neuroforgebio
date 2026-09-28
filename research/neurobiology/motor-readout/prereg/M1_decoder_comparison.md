# M1: Pre-registration of an offline motor-decoder comparison (accuracy, bits/s, across-session drift)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Author: mathematician (motor-readout track), for Marius Carlsson, 2026-09-26. Status: **LOCKED at the time of writing.**
Every change after this point goes to motor-readout\code\DEVIATIONS.md with a reason. Any change made after a test-block label
is accessed makes the affected result exploratory. Sources: R-IDs in lit\readout.md; math in notes\theory_draft.md (TD §);
data in notes\data_plan.md.

**Blindness statement.** When this was written, no file of any dataset had been downloaded or opened. Only DANDI and PhysioNet
metadata were seen: names, licences, sizes, asset IDs and the session dates of LINK. No neural or behavioural value has been
seen. All predictions below are ESTIMATES unless cited.

**Scope.** Offline, open-loop decoding of intended movement from recorded activity. This prereg does **not** test closed-loop
properties: ReFIT (TD §3.3), latency effects on control, or stability (TD §4.3).

**Input lock (S7-style).** SHA-256 of the 3-line UTF-8 string below (joined by "\n", no trailing newline) =
`aa0f8e1b4e86c93b8bb14c108046dcab1d2ae798806cd21d74e5065388e65d7a`
```
000138|0.220113.0407|e67b57b2-e9ad-4d95-b9e3-1262997360dc
001201|0.251023.2336|c002a9a1-664d-4a69-af02-ba810046c4fb,9d1820f1-7583-4faf-bbd0-7e9fb7001ca4,ea07a2e3-d5f4-4036-9b62-93d1f89cba64,9c0ac931-d97e-464b-a134-c366b7c84727,b424f116-7827-4ab0-80ed-1e8951eea67a,88039197-6170-4d06-ba3e-f58b68c6eb7f,b9868d49-f641-4b95-a8e3-6295111b958b,9db3b62a-6fea-493b-98bf-2f6ded6eefec,1a7aadf8-eb08-427b-93e3-8df11d71ae9e
eegmmidb|1.0.0|S001-S020|R04,R08,R12
```
The coder recomputes this hash and raises `SplitHashError` (nfharness.errors) on mismatch. Every downloaded file must match its
DANDI `dandi:sha2-256` or PhysioNet SHA256SUMS entry, or `InputHashError` is raised.

---

## 1. Datasets, targets and features

| arm | data | neural features | target | bin |
|---|---|---|---|---|
| D1 within-session | MC_Maze_Large train NWB (DANDI 000138), all sorted units | spike counts per bin | hand velocity (x, y) | 20 ms |
| D2 drift | LINK (DANDI 001201), the 9 locked sessions | SBP, 96 channels (the file's own bins; if these are not 32 ms, re-bin to 32 ms and log a deviation) | index and MRP finger velocity | 32 ms |
| D3 optional EEG | EEGMMIDB S001-S020, runs 4/8/12 (imagined left vs right fist) | 64-ch EEG, band-pass 8-30 Hz (4th-order Butterworth, zero-phase within each run file) | class T1 vs T2 | epoch 0.5-2.5 s after cue onset |

Further rules:
- **D1 evaluation window:** -250..+450 ms around movement onset [R46] (35 bins). History bins before the window may be used as
  input only.
- **Real-time constraint (all arms):** the output at bin t uses neural data from bins <= t only. The target is the velocity in
  bin t (no look-ahead lag). This is stricter than NLB's lagged scoring [R46].
- **D2 target style:** if a session holds both target styles, use center-out. If center-out is absent, use random targets and
  flag the session in the card. Do not mix styles within a session.

## 2. Leak-proof splits (reusing nfharness concepts)

**Unit of splitting = the whole trial.** No bin of a trial may appear in two partitions. The guard is new, `TrialOverlapError`,
subclassing nfharness `HarnessViolation`.

- **D1 primary split (by time):** sort trials by start time. First 60% = train, next 20% = validation, last 20% = test. A gap of
  one trial is dropped at each boundary. `assert_causal` semantics (nfharness F6): max(train end) < min(val start) and
  max(val end) < min(test start).
- **D1 secondary split (by condition, descriptive only):** 5-fold grouped by maze condition ID. Folds are assigned by sorting
  condition IDs and taking id mod 5. Trained on train-block trials of the other conditions; scored on test-block trials of the
  held-out conditions. So it is condition-disjoint **and** still time-ordered.
- **D2, per session:** the same 60/20/20 chronological split into calib / val / test blocks.
  - The day-0 decoder sees only day-0 calib and val.
  - For day k >= 1, "within" decoders see day-k calib and val.
  - Unsupervised recalibration arms see day-k calib **neural data only**.
  - Everything is scored on the day-k test block.
  - `SessionOrderError` (new) is raised if a fitting function receives any day > its declared training day.
- **D3, per subject:** train = runs 4 + 8, test = run 12 (chronological). Inner model selection uses 2-fold by run (4 vs 8).
- **Normalisation:** z-score parameters are fitted on train only (nfharness F1 `NormaliserLeakError`). EEG covariance
  reference means are fitted on train only.
- **Test-label sealing (nfharness F8 concept):** behaviour and labels for the test blocks are loaded into a `LabelVault`. Only
  `final_score()` may read it, after all models are frozen, and only once per (arm, decoder, session). Any other read raises
  `TestLabelAccessError`. Frozen model hashes are written to the card before the vault is opened.
- **Split hash:** after reading trial tables (timing and condition metadata only, not behaviour), the coder writes the trial-ID
  partition strings for D1, D2 and D3 and their SHA-256 to results\M1_split_lock.json **before any decoder is fitted**. The
  reviewer checks the file's timestamp against the first model-fit log line.

## 3. Decoders (hyperparameters locked; selection on validation only)

- **Ridge (Wiener with history):**
  - Lagged features x_{t-k}, k = 0..H-1, with H = 10 bins (200 ms) in D1 and H = 6 bins (192 ms) in D2, plus an intercept.
  - λ from logspace(-1, 5, 13), chosen by validation R².
- **Kalman (velocity KF):**
  - State z = [v1, v2, 1]; A, Q, C, R fitted by least squares on train [R21]; observations = z-scored current-bin features.
  - Run to steady state (TD §3.2). The initial state is the train mean. The filter is re-initialised at each trial start in D1
    (the window starts in pre-movement) and runs continuously in D2.
  - No hyperparameters.
- **GRU (PyTorch CPU; torch.set_num_threads(4)):**
  - 1 layer, h = 64, input dropout 0.2, linear read-out.
  - Adam lr 1e-3, weight decay 1e-4, batch 32 trials (D1) or 32 chunks of 64 bins (D2).
  - At most 50 epochs, early stopping on validation R² with patience 5. Warm-up: the first 10 bins of each sequence are not in
    the loss.
  - An ensemble of 3 seeds (20261001, 20261002, 20261003), averaging predictions.
  - **If torch cannot be installed: GRU arm NOT TESTED (A5).**
- **D3:**
  - (a) Linear baseline: log-variance of the 64 band-passed channels, then shrinkage LDA with γ from {0, 0.1, 0.3, 0.5, 0.9}.
  - (b) Riemannian: covariance + 1e-3·tr(C)/64·I, tangent space at the train Riemannian mean (fixed point, 20 iterations,
    tolerance 1e-8), then L2 logistic regression with C from logspace(-3, 2, 11).
  - Both use the inner run-fold for selection.
- **D2 recalibration arms (ridge only):**
  - (R-a) re-z-score day-k features with day-k calib-block mean and SD (unsupervised).
  - (R-b) FA-Procrustes. Factor analysis with 10 factors (EM, 200 iterations) on day-0 calib and on day-k calib neural data.
    Loadings are aligned by orthogonal Procrustes, O = UVᵀ from svd(L_kᵀL_0) (TD §5.2). A day-0 ridge on the FA posterior
    means (history H = 6) is applied to the aligned day-k latents. All 96 channels are used; no stable-channel selection, which
    is a simplification of R38.

## 4. Metrics (defined exactly)

- **M-R2 (primary accuracy):** coefficient of determination, variance-weighted over the 2 output dimensions (sklearn
  `r2_score(..., multioutput='variance_weighted')`). Pooled over all test-block bins (D1: window bins only). Also reported:
  mean squared correlation ρ² (TD §2.1).
- **M-BITS (continuous, primary information rate):** the Gaussian coherence lower bound (TD §1.1, §2.1). Per output dimension:
  - Segments: D1 = each test trial's 35-bin window; D2 = consecutive non-overlapping 64-bin segments of the test block.
  - Hann taper, then FFT; cross- and auto-spectra averaged over segments; γ²(f_j) = |S_xy|²/(S_xx S_yy).
  - I_raw = Σ_{f_j <= 10 Hz} -log2(1-γ²(f_j)) Δf, with Δf = 1/(segment length in s).
  - **Null:** 200 permutations pairing each decoded segment with a different true segment. I_net = I_raw - median(I_null).
  - Summed over the 2 dimensions (assumes independent dimensions; stated in the card). Unit: bits/s.
  - **The Wolpaw ITR is not used for D1 or D2** (continuous outputs violate TD §1.2 (i)-(iv)).
- **M-MI (D3, discrete):** plug-in MI from the pooled test confusion matrix with the Miller-Madow correction [R4], divided by
  c = the mean interval between consecutive cue onsets in run 12, measured from the annotations. This gives bits/s and
  bits/min. The **Wolpaw ITR** is additionally reported only if T1 and T2 are each 45-55% of test trials; otherwise it is
  "ITR not applicable".
- **M-DRIFT (D2):**
  - R²_fixed(k): day-0 decoder on the day-k test block.
  - R²_within(k): same-class decoder trained on day k.
  - Retention ρ_k = R²_fixed/R²_within. A session with R²_within(k) < 0.10 is marked unusable for ratios.
  - Recovery φ_k = (R²_arm - R²_fixed)/(R²_within - R²_fixed).
  - Also the Spearman correlation between lag and R²_fixed.
- **Uncertainty:** paired trial-level bootstrap over test trials (D2: over 64-bin segments), B = 2000, percentile CIs, seed
  stream k = 1. **Primary CIs are 99%** (Bonferroni over 5 primaries: H1-H5). The H2 equivalence uses a 98% CI (TOST at
  α = 0.01 per side).
- **Descriptive (no verdict):**
  - bin-size sweep {10, 20, 50, 100} ms for ridge and KF on D1 (TD §4.2), keeping the history at 200 ms;
  - condition-held-out R² (§2);
  - GRU and KF drift curves;
  - lag sweep (NC2b).

## 5. Hypotheses, predictions and PASS/FAIL rules (fixed)

The predicted values are ESTIMATES (no opened source gives these numbers for these exact splits). P = my prior probability.

| ID | claim | PASS | FAIL | otherwise | prediction |
|---|---|---|---|---|---|
| H1 | GRU beats ridge on D1 (direction as in R24) | Δ = R²_GRU - R²_ridge >= 0.02 **and** 99% CI lower bound > 0 | 99% CI upper bound < 0.02 | INCONCLUSIVE | ridge 0.65, KF 0.62, GRU 0.72; P(PASS) = 0.55 |
| H2 | KF ≈ ridge on D1 (both linear-Gaussian; TD §3.2) | 98% CI of R²_KF - R²_ridge entirely within [-0.05, +0.05] | 98% CI entirely outside [-0.05, +0.05] | INCONCLUSIVE | Δ = -0.03; P(PASS) = 0.45 |
| H3 | bits/s follows R²: I_net ranks the 3 D1 decoders in the same order as M-R2, and I_net(GRU) - I_net(ridge) > 0 | both hold, with 99% CI lower bound of the GRU-ridge I_net difference > 0 | the order is reversed for GRU vs ridge with 99% CI upper bound < 0 | INCONCLUSIVE | I_net: ridge about 5, GRU about 7 bits/s. This is an ESTIMATE, uncertain by a factor of 3 (TD §2.1: at ρ² about 0.7 over the lowest few 1.4 Hz bins). The ordering is the real prediction. P(PASS) = 0.45 |
| H4 | a day-0 decoder drifts (ridge, D2) | median ρ_k over sessions with lag >= 30 d (32, 151, 241, 393, 730) <= 0.5 **and** Spearman(lag, R²_fixed) over the 8 later sessions <= -0.5 | median ρ_k >= 0.8 | INCONCLUSIVE | ρ: +3 d 0.85, +32 d 0.5, >= 151 d <= 0.2 (can be negative); P(PASS) = 0.65 |
| H5 | unsupervised FA-Procrustes alignment (R-b) recovers drift loss [R38-R40] | median φ_k (lag >= 30 d, usable sessions) >= 0.5 | median φ_k <= 0.1 | INCONCLUSIVE | φ median 0.4; R-a (re-z-score) 0.3; P(PASS) = 0.35 |
| H6 (optional, D3) | Riemannian tangent-space beats the log-variance LDA | mean accuracy difference over 20 subjects >= 0.03 **and** one-sided paired sign-flip permutation p < 0.05 (10,000 flips) | mean difference <= 0 | INCONCLUSIVE | LDA 0.60, TS 0.64 (ESTIMATE); P(PASS) = 0.40. H6 is secondary and not in the Bonferroni family. |

Notes:
- For H4/H5, sessions flagged unusable are excluded. If fewer than 3 usable sessions with lag >= 30 d remain: INCONCLUSIVE
  (underpowered).
- The honest D1 numbers are reported for each decoder regardless of the verdicts.

## 6. Controls (must hold before any H verdict counts)

**Negative / null controls**
- **NC1 shuffled alignment.**
  - Each decoder is retrained on train pairs where trial i's neural data is paired with trial π(i)'s behaviour (1 permutation,
    seed stream k = 2), then scored on true test pairs.
  - Reference B0 (condition-agnostic): predict the mean training velocity at the same bin relative to movement onset (D1) or
    the training mean (D2).
  - PASS if R²_shuf <= max(0.05, R²_B0 + 0.02) for every decoder, and I_net(shuf) <= 0.15 bits/s.
  - D3: 5 label permutations per subject; the mean accuracy over subjects must fall in [0.40, 0.60].
- **NC2a trial-shift null.** Pair test neural data of trial i with test behaviour of trial i+s (circular within the block),
  s = 1..5. The honest decoders are scored. PASS if every s gives R² <= max(0.05, R²_B0 + 0.02).
- **NC2b time-shifted decoding (descriptive theory check, not gating).**
  - Ridge and GRU are refitted to predict the velocity at t+τ, with τ ∈ {-500, -250, -100, 0, +100, +250, +500} ms, using
    causal features.
  - Prediction: the argmax of R² lies in [0, +300] ms, because neural activity leads movement (NLB uses a 100-120 ms lag
    [R46]).
  - Reported against the prediction; no verdict impact.

**Planted-leak positive controls** (lesson from N1b: each leak must have near-certain power, and the code-level guards must be
tested separately)
- **PL-1 label-in-features.** Append one channel = z-scored true v1(t) + N(0,1) noise (SNR 1) to train and test features.
  Ridge R² must rise by >= 0.10 over honest. Separately, with the planted channel present and not declared,
  `FeatureWhitelistError` (nfharness F7 concept) must be raised.
- **PL-2 future-session leak (D2).** Train the "day-0" ridge on day-0 calib plus the day-k **test** block for k = the 32-day
  session. ρ_k must become >= 0.9. The undeclared version must raise `SessionOrderError`.
- **PL-3 random-bin split with non-causal features (D1, GRU and ridge).** Bin-level random 60/20/20 split plus a centred ±5-bin
  feature window. **Required:** GRU R² inflation >= 0.01; ridge is descriptive. The undeclared version must raise
  `RandomSplitForbiddenError` (nfharness S5) and `CausalFeatureError` (new).
- **Code-guard suite (pytest, 100% required):** deliberate violations of each guard must raise:
  - TrialOverlapError;
  - CausalSplitError (F6);
  - NormaliserLeakError (F1);
  - TestLabelAccessError (F8);
  - SessionOrderError;
  - CausalFeatureError;
  - FeatureWhitelistError;
  - RandomSplitForbiddenError;
  - SplitHashError;
  - InputHashError.
  At least 10 cases; all must pass.
- **Reproducibility:** a rerun must give a card hash identical to the first run (nfharness `card_hash`; BLAS threads = 1 via
  `pin_blas_threads`, torch deterministic algorithms on).

**Harness verdict.**
- Harness PASS = NC1 + NC2a + PL-1 + PL-2 + PL-3 (GRU part, if the GRU is tested) + guard suite + reproducibility.
- If harness FAIL: all H verdicts become "not verifiable: harness", and the numbers are exploratory.

## 7. Abandonment rules

- **A1.** A file needs a sign-up, is missing, fails its hash, or the total would exceed 1.5 GB → drop D3 first. If D1 or D2
  fails → stop that arm; its hypotheses are NOT TESTED.
- **A2.** Harness FAIL (§6) → no decoder verdicts; write RESULTS as exploratory; new prereg needed.
- **A3.** Pipeline sanity: honest ridge **validation** R² < 0.20 on D1 or on D2 day 0 (ESTIMATE threshold: a working linear
  decoder on motor-cortex data should clear it by far) → stop before opening the vault. Debug, then log a deviation. Verdicts
  after such a fix are labelled "post-deviation".
- **A4.** Budget: the whole run (all arms, controls, tests) must take < 20 min CPU wall time and < 1.5 GB peak RSS (nfharness
  `peak_rss_mb`). If the dry run on MC_Maze_Small (DANDI 000140) predicts an overrun, cut in this order, with each cut logged:
  - (1) D3;
  - (2) GRU seeds 3 → 1;
  - (3) NC2b and the bin sweep;
  - (4) GRU on D2.
  If still over → GRU arm NOT TESTED.
- **A5.** torch not installable as a CPU wheel → GRU arm NOT TESTED. No substitute implementation under this prereg.
- **A6.** The run map for EEGMMIDB runs 4/8/12 cannot be confirmed (events other than T0/T1/T2, or unexpected durations) → D3
  NOT TESTED.

## 8. Run order and provenance
1. Download and hash (manifest). Compute the input-lock hash.
2. Dry run on MC_Maze_Small (000140; not part of any verdict): pipeline, guard tests, timing.
3. Write results\M1_split_lock.json (split hashes, frozen hyperparameter grids, code hashes).
4. Fit on train, select on val, freeze and hash the models.
5. Controls NC1, NC2a and PL-1..3 (these use train/val and the vault only through `final_score`).
6. Open the vault: final scores.
7. Card: input hashes, script hash, nfharness file hashes (unmodified; imported read-only), package versions, seed 20261001
   with streams k = 1..6, peak RSS, wall time.

New code only in motor-readout\code\. Results in motor-readout\results\. An independent reviewer re-implements M-R2, M-BITS and
the split and checks them before anything reaches THEORY.md (HIVE rule 8).
