# M1 results: offline motor-decoder comparison (accuracy, bits/s, across-session drift)

**RESEARCH USE ONLY. NOT A MEDICAL DEVICE.** No clinical claims. This is offline, open-loop decoding of recorded activity.
Software intended for diagnosis, monitoring or treatment decisions may be a medical device under EU MDR 2017/745 (e.g.
Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance and clinical validation (IRB/ethics approval).

- Author: coder-verifier (motor-readout), for Marius Carlsson, 2026-09-27.
- **Status: UNREVIEWED.** HIVE rule 8: an independent reviewer must re-implement M-R2, M-BITS and the split before anything
  goes into THEORY.md.

**Prereg:** `prereg\M1_decoder_comparison.md` SHA `9eada9d7...bd06f` (verified before any data read). Deviations:
`code\DEVIATIONS.md`. A pre-run snapshot is in `results\M1_DEVIATIONS_prerun_snapshot.md` (SHA `f081a37b...`, mtime 00:08:36,
6 s before the real run started).

## 1. Headline

**Harness = FAIL. Per prereg §6 and A2, all hypothesis verdicts are "not verifiable: harness"; every number below is
EXPLORATORY, and a new prereg is needed.**

The two failing items were both predicted in DEVIATIONS §D before the real run:
- **PL-1 is underpowered by construction.** The observed rise was +0.034, and the pre-registered analytic expectation
  w1·r²/(1+r) is +0.035, so the leak was detected at exactly its theoretical power. The ≥ 0.10 bar is unreachable at this
  honest R².
- **NC1's I_net ≤ 0.15 bits/s bar.** This fails because a shuffled-trained readout of informative neural data is still
  coherent with the true kinematics (coherence ignores sign and gain). All NC1 R² values were at or under their thresholds on
  D1; on D2 day 0 the GRU R² was 0.072 > 0.05.

Everything else in the harness passed:
- NC2a;
- PL-2 (ρ 1.02 ≥ 0.9; SessionOrderError raised);
- PL-3 (GRU +0.124 ≥ 0.01; RandomSplitForbiddenError and CausalFeatureError raised);
- the guard suite (40/40 pytest; 20 guard tests with 20 `pytest.raises` violation cases over the 10 named errors);
- **reproducibility**: the card hash `c7bd7ac5...af0` was identical in the fresh-process rerun.

| ID | final verdict (prereg) | conditional verdict if the harness had passed (EXPLORATORY) | key numbers | prediction check |
|---|---|---|---|---|
| H1 GRU > ridge (D1) | not verifiable: harness | PASS | ΔR² = +0.143, 99% CI [+0.115, +0.170] | predicted GRU-ridge +0.07 (0.72 vs 0.65); observed larger (0.812 vs 0.669) |
| H2 KF ≈ ridge (D1) | not verifiable: harness | FAIL | ΔR² = -0.383, 98% CI [-0.435, -0.335], entirely outside ±0.05 | predicted -0.03; KF far worse (0.286) |
| H3 bits/s follows R² | not verifiable: harness | PASS | order GRU > ridge > KF on both metrics; I_net GRU-ridge = +6.31 bits/s, 99% CI [+3.10, +9.97] | ordering correct; levels ~5× the estimate (ridge 25.6 vs ~5, GRU 31.9 vs ~7), outside the stated factor-3 band |
| H4 day-0 decoder drifts (D2 ridge) | not verifiable: harness | PASS | median ρ (lag ≥ 30 d, 5 usable) = -2.14, 99% CI [-2.89, -1.63]; Spearman(lag, R²_fixed), 8 later sessions = -0.52 | predicted +32 d 0.5 (obs 0.40), ≥ 151 d ≤ 0.2 (obs negative); drift already at +3 d (ρ -1.09 vs predicted 0.85) |
| H5 FA-Procrustes recovers (R-b) | not verifiable: harness | PASS | median φ_Rb = 0.59, 99% CI [0.46, 0.72]; R-a (re-z-score) median φ = 0.62 | predicted 0.4 / 0.3; see §4: R-b is no better than re-z-scoring, and the recovered R² is ≈ 0 at ≥ 151 d |
| H6 Riemannian > LDA (EEG) | NOT TESTED | NOT TESTED | A4 cut (1) | - |

## 2. Data and run facts

- **Inputs.** 131 files, each SHA-256 matched to the DANDI `dandi:sha2-256` or PhysioNet SHA256SUMS digest
  (`data\manifests\motor_manifest.csv`); 730.2 MB downloaded (cap 0.80 GB). The input-lock hash `aa0f8e1b...` matched.
  The real run used 10 files (D1 + 9 LINK).
- **D1 (MC_Maze_Large train, DANDI 000138).**
  - 500 trials, 162 units (916,892 spikes), 9 mazes, no NaN velocity.
  - Split 300/99/99 (+2 gap trials), chronological.
- **D2 (LINK, DANDI 001201).**
  - The files hold **20 ms** bins, re-binned to 32 ms (DV-1).
  - 375 trials per session, split 225/74/74 (+2 gap).
  - 20200228 (+32 d) and 20220126 (+730 d) are random-target (RD) sessions and are flagged; the other 7 are center-out (CO).
- **A4 (budget).**
  - The dry run predicted an overrun, so cuts were applied: (1) D3 dropped, (2) GRU 3 seeds → 1 (seed 20261001).
  - Actual: run1 378 s, 1,268 MB peak; rerun 339 s, 1,267 MB. Both are < 20 min and < 1.5 GB.
  - **POST-RUN note:** the real run was ~3× faster than the dry-run-based prediction. This was not knowable before the run,
    and the cuts stand.
- **A3.** Honest ridge validation R² was 0.685 on D1 and 0.349 on D2 day 0 (≥ 0.20), so the vault was opened.
- **A5.** torch 2.14.0+cpu was installed from download.pytorch.org/whl/cpu, so the GRU was tested. h5py 3.16.0; numpy 2.5.3;
  scipy 1.18.1; Python 3.12.10.
- **Timeline (run log).**
  - 00:08:56 split lock written → 00:08:57 first model fit.
  - 00:13:51 80 models frozen (`M1_frozen_models_run1.json`, SHA `cf37eba3...`) → declared planted-leak reads → 00:14:55
    vault opened for final scores.

## 3. D1: within-session decoding (MC_Maze_Large, 20 ms, causal, no look-ahead lag)

| decoder | test R² [99% CI] | ρ² | I_raw | null median | I_net bits/s [99% CI] | condition-held-out R² |
|---|---|---|---|---|---|---|
| ridge (H = 10, λ = 3162) | 0.669 [0.636, 0.696] | 0.663 | 26.21 | 0.60 | 25.61 [23.56, 28.47] | 0.523 |
| Kalman (steady state, 23 Riccati iterations) | 0.286 [0.217, 0.341] | 0.346 | 13.68 | 0.42 | 13.26 [11.75, 15.59] | 0.163 |
| GRU (1 seed, best epoch 37/42) | **0.812** [0.779, 0.840] | 0.811 | 32.58 | 0.65 | **31.93** [28.74, 36.45] | 0.618 |
| B0 (onset-aligned mean velocity) | 0.061 | 0.062 | 6.08 | 6.08 | 0.00 | - |

Descriptive checks:
- **Bin sweep** (R², ridge / KF): 10 ms 0.674 / 0.218; 20 ms 0.669 / 0.286; 50 ms 0.667 / 0.398; 100 ms 0.640 / 0.449.
  Ridge is flat; KF improves with longer bins (the error side of TD §4.2).
- **NC2b lag sweep** (target velocity at t+τ, causal features). The argmax is at τ = +100 ms for both ridge (0.683) and GRU
  (0.813), inside the predicted [0, +300] ms. At τ = -500 ms, R² ≈ 0. This matches neural activity leading movement.
- **Condition-held-out:** every decoder loses 0.12-0.19 R² when the maze is unseen, and GRU still leads (0.618 vs 0.523).

I_net is the Gaussian coherence lower bound on the offline information about 2-D hand velocity (0-10 Hz, 99 segments of
0.7 s, dimensions summed under an independence assumption). **It is not a BCI speed** and must not be compared with
closed-loop achieved bitrates (TD §1.3).

## 4. D2: across-session drift (LINK, 32 ms, SBP 96 ch, index + MRP velocity)

| session | lag d | style | ridge R²_within | R²_fixed | ρ [99% CI] | R-a R² | R-b R² | φ_Rb | GRU within / fixed | KF within / fixed |
|---|---|---|---|---|---|---|---|---|---|---|
| 20200127 | 0 | CO | 0.329 | 0.329 | 1 | 0.329 | 0.254 | - | 0.513 / 0.513 | 0.184 / 0.184 |
| 20200130 | 3 | CO | 0.308 | -0.337 | -1.09 [-1.73, -0.65] | 0.246 | 0.231 | 0.88 | 0.472 / -0.764 | 0.187 / -3.079 |
| 20200204 | 8 | CO | 0.306 | -0.120 | -0.39 [-1.02, 0.03] | 0.236 | 0.247 | 0.86 | 0.487 / 0.198 | 0.157 / -2.768 |
| 20200211 | 15 | CO | 0.282 | 0.001 | 0.01 [-0.40, 0.28] | 0.238 | 0.227 | 0.80 | 0.483 / 0.080 | 0.179 / -0.364 |
| 20200228 | 32 | RD | 0.326 | 0.129 | 0.40 [0.20, 0.56] | 0.211 | 0.245 | 0.59 | 0.445 / 0.211 | 0.220 / -0.120 |
| 20200626 | 151 | CO | 0.193 | -0.071 | -0.37 [-0.95, 0.02] | 0.039 | -0.050 | 0.08 | 0.266 / -0.026 | 0.141 / -0.492 |
| 20200924 | 241 | CO | 0.254 | -6.160 | -24.2 [-38.2, -17.2] | -0.005 | -0.060 | 0.95 | 0.435 / -1.133 | 0.119 / -6.686 |
| 20210223 | 393 | CO | 0.263 | -0.563 | -2.14 [-2.90, -1.63] | -0.051 | -0.154 | 0.50 | 0.421 / -0.107 | 0.158 / -0.517 |
| 20220126 | 730 | RD | 0.248 | -0.828 | -3.33 [-5.30, -2.26] | -0.036 | -0.025 | 0.75 | 0.391 / -0.570 | 0.170 / -0.588 |

Findings (EXPLORATORY):
- **Drift.** A day-0 SBP decoder does not survive to +3 d on this monkey, whichever decoder class is used. Negative R²_fixed
  (worse than predicting the mean) is the bias term of TD §5.1: ||WΔμ||² dominates. It is extreme at +241 d (R² -6.2).
  Retention is not monotone in lag (Spearman -0.52), so ρ = R²_fixed/R²_within is unstable when R²_fixed < 0. A median ρ of
  -2.1 means "worse than useless", not "2× drift".
- **Recalibration.** φ_Rb ≈ 0.59 passes the H5 bar only in the conditional sense.
  - Re-z-scoring alone (R-a, φ 0.62) recovers as much. The FA-Procrustes alignment adds nothing measurable over removing
    the per-channel mean/scale shift.
  - At ≥ 151 d, both arms give R² ≈ 0 (range -0.15..0.04). A large φ there means "removed a catastrophic bias", not "restored
    a usable decoder".
  - This is with all 96 channels and no stable-channel selection (a stated simplification of R38).
- **Within-day accuracy** is modest for LINK SBP at 32 ms without smoothing: ridge 0.19-0.33, GRU 0.27-0.51, KF 0.12-0.22.
  The GRU leads on every session, consistent with D1.

## 5. Controls (prereg §6)

| control | result | criterion | pass |
|---|---|---|---|
| NC1 D1 (shuffled trial pairing; train and val shuffled, DV-6) | R² ridge 0.067 / KF -0.225 / GRU 0.027 (≤ max(0.05, B0 0.061+0.02) = 0.081); I_net ridge 2.22 / KF 0.79 / GRU 0.85 bits/s | R² ≤ 0.081 **and** I_net ≤ 0.15 | **FAIL** (I_net) |
| NC1 D2 day 0 | R² ridge 0.047 / KF 0.060 / GRU 0.072 (bar 0.05); I_net 0.88 / 1.48 / 1.07 | same | **FAIL** |
| NC2a (trial shift s = 1..5) | D1 max R² -0.47; D2 day-0 max R² -0.21 | ≤ bar | PASS |
| PL-1 label-in-feature | ridge 0.669 → 0.703 (+0.034); expected analytic rise +0.035 (r_v1 = 0.284, w1 = 0.556); FeatureWhitelistError raised | rise ≥ 0.10 + guard | **FAIL** (power) |
| PL-2 future-session | ρ(+32 d) 0.40 → 1.02; SessionOrderError raised | ρ ≥ 0.9 + guard | PASS |
| PL-3 random bins + centred window | GRU 0.812 → 0.936 (+0.124); ridge 0.669 → 0.641 (descriptive); both guards raised | GRU ≥ +0.01 + guards | PASS |
| guard suite | 40/40 pytest (20 guard tests, 20 raise-assertions over the 10 named errors; 10 metric fixtures; 10 synthetic decoder tests) | 100%, ≥ 10 | PASS |
| reproducibility | card SHA `c7bd7ac5...` = rerun SHA | identical | PASS |

**What this means.** The harness FAIL is a **prereg-design** failure, not evidence of a leak in the pipeline:
- Every code guard fired.
- Two of the three planted leaks were caught, and PL-1 moved R² exactly as far as theory allows.
- NC2a is clean.
- NC1 fails on the information metric, not on accuracy (except the D2 GRU at 0.072).

A re-registration should:
- (a) give PL-1 near-certain power, e.g. plant both dimensions or use a higher SNR, with the analytic power computed from
  the dry run;
- (b) replace the absolute NC1 I_net bar with a comparison against a null distribution of shuffled-trained decoders, or
  gate NC1 on R² only;
- (c) budget from a dry run that includes D2.

These are recommendations for the mathematician and queen; they were not applied here.

## 6. Abandonment rules

| rule | outcome |
|---|---|
| A1 | No sign-up; all files present; all hashes MATCH |
| A2 | Harness FAIL → no confirmatory verdicts; this document is exploratory; new prereg needed |
| A3 | Passed (0.685 / 0.349 ≥ 0.20) |
| A4 | Cuts (1) D3 and (2) GRU seeds 3→1 applied from the dry-run prediction; actual 378 s / 1.27 GB |
| A5 | torch CPU installed |
| A6 | Not evaluated (D3 cut). The code path passed a synthetic check |

## 7. Files

Results:
- `results\M1_card_run1.json` (full card: input hashes, code/nfharness hashes, versions, seed, streams, all numbers)
- `results\M1_card_rerun.json`
- `results\M1_verdict.json` (harness + gated verdicts)
- `results\M1_split_lock.json`
- `results\M1_frozen_models_run1.json`
- `results\M1_run_log_run1.txt`
- dry/synthetic cards: `M1_card_dry.json`, `M1_card_synthetic.json`

Figures:
- `figures\M1_decoder_comparison.{png,svg}`
- `figures\M1_bits_vs_r2.{png,svg}`
- `figures\M1_drift_vs_days.{png,svg}`

Code:
- `code\run_m1.py`
- `code\m1lib\` (guards, data, decoders, metrics, synthetic)
- `code\finalize_m1.py`, `code\figures_m1.py`, `code\download_m1.py`
- `code\tests\` (40 tests)

nfharness was imported read-only; its file hashes are in the card.

Attribution:
- MC_Maze_Large: Churchland & Kaufman (2022), DANDI 000138/0.220113.0407, CC-BY-4.0.
- LINK: Temmar et al., DANDI 001201/0.251023.2336, CC-BY-4.0.
- No raw data are redistributed.
