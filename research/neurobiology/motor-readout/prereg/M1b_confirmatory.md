# M1b: confirmatory re-registration of the motor-decoder comparison on FRESH data (POST-HOC-INFORMED)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Author: mathematician (motor-readout track, cycle 2), for Marius Carlsson, 2026-09-27.
Status: **LOCKED at the time of writing.** Its SHA-256 is posted on notes\BOARD.md before any fresh file is downloaded. Changes
before the fresh download go into a versioned amendment (M1b.1, M1b.2) with a new SHA. Changes after the download go to
code\DEVIATIONS_M1b.md, and any change made after a fresh test-block label is read makes the affected result exploratory.

## 0. Honesty statement: this prereg is POST-HOC-INFORMED

M1 (prereg\M1_decoder_comparison.md, SHA `9eada9d7...bd06f`) ended with **harness FAIL**, and every hypothesis was "not
verifiable: harness" (code\RESULTS_M1.md; confirmed by code\REVIEW_M1.md). The reviewer found two causes, both prereg design
errors and neither a leak:
- the PL-1 bar was analytically unreachable (review §5a, P1);
- the NC1 bits/s bar ignored sign and gain, and the D2 NC1 R² bar ignored same-target pairs (review §5b, §5c, P2).

I **have seen** all M1 exploratory numbers: RESULTS_M1, the review, the M1 dry run on MC_Maze_Small and the synthetic cards.
The controls, the Kalman variant, the drift metrics and the predictions below were all designed with that knowledge.

This is legitimate **only** because every confirmatory verdict is scored on data that M1 never downloaded or opened. The fresh
data are:
- MC_Maze_Medium, a different recording session from Large and Small;
- 13 LINK sessions that are not among M1's 9.

The EEG arm (H6) is the one exception to "post-hoc": its data were downloaded in M1, but they were never parsed or scored (A4 cut),
so H6 remains **blind**.

**Metadata only.** When this was written, no fresh file had been downloaded. The only things read were:
- DANDI REST metadata: versions, licences, asset sizes, SHA-256 digests, session start dates, and the per-asset "target style
  CO/RD" description (from `wasGeneratedBy`);
- motor-readout\data\manifests\ (to confirm that the chosen files are absent).

No fresh neural or behavioural value has been seen.

**Scope.** This is unchanged from M1: offline, open-loop decoding of recorded activity, with nothing about closed loop, latency
or stability.

**Same animals.** "Fresh" means new sessions, not new animals:
- D1 is monkey Jenkins in every MC_Maze set;
- D2 is LINK's single animal, Monkey N.

A confirmation here is therefore a within-animal replication across sessions. It says nothing about generalisation across
subjects.

### 0.1 Every change from M1 and why

| # | M1 | M1b | why |
|---|---|---|---|
| C1 | PL-1: v1 + N(0,1) in one column; bar = rise ≥ 0.10 | Both velocity dimensions are planted at noise variance σ² = 0.1 (z-units). The bar is 0.5 × the analytic expected rise E, with E computed from **validation** residuals before the vault opens. E ≥ 0.10 and 0.5E ≥ 3 × the bootstrap SD of the rise are required (§6.2). | Review 5a: the bar could not be reached by design (expected rise 0.035). |
| C2 | NC1 bits gate: coherence I_net ≤ 0.15 bits/s | The gate uses the sign- and gain-sensitive residual-spectrum bound I_mse (§4.2), with bar I_mse,net(shuffled) ≤ 0.10 × I_mse,net(honest ridge). Coherence I_net of shuffled decoders is reported but does not gate. | Review 5b: coherence is invariant to sign and gain, so a shuffled-trained readout of informative data stays coherent. |
| C3 | NC1 shuffle: any permutation; D2 reference = flat training mean | The shuffle is a **condition-constrained derangement**: a trial is never paired with a trial of the same condition (D1) or the same target (D2). References: D1 B0 = onset-aligned mean profile (as in M1); D2 B0 = **trial-start-aligned** mean profile. Bar: R²_shuf ≤ R²_B0 + 0.03. | Review 5c: 26 % of D2 shuffled pairs shared a target, and the flat mean gave no credit for start-locked structure. |
| C4 | PL-2: day-0 decoder trained on the day-k **test** block; bar ρ ≥ 0.9 | The day-k **calib** block is used (true labels), scored on the day-k test block. Bar: recovered loss ≥ 0.5 × (R²_within − R²_fixed). The SessionOrderError check is driven by the day tags of the rows actually passed. | Review §5 (PL-2 passed trivially, in-sample) and C1 (the guard used literal lists). |
| C5 | M-BITS summed f ≤ 10 Hz **including DC** | Primary: 0 < f ≤ 10 Hz (DC excluded). The DC-included value is also reported. | Review P4: DC gave 7.8 of 25.6 bits/s. |
| C6 | One KF (current 20 ms bin, no lag) | KF-0 (the M1 spec, for continuity) **plus KF-L**: lag and boxcar chosen on validation (§3). H2 is split into H2a (the specification matters) and H2b (information-matched KF ≈ ridge). | Review §3: KF 0.286 was a property of the specification. The reviewer's lag and boxcar variants reached 0.38-0.45 on Large **test** data, and that informs the grid. |
| C7 | H4: ratio ρ = R²_fixed/R²_within and Spearman ≤ -0.5 | Uses the **loss difference** L_k = R²_within − R²_fixed. H4b (short lag, 3-14 d) is new. Spearman becomes descriptive. | Review P3: ρ is ill-conditioned when R²_fixed < 0 (M1 median ρ = -2.14). M1 also showed non-monotone drift (Spearman -0.52), and drift was already present at +3 d. |
| C8 | H5: φ = (R²_Rb − R²_fixed)/(R²_within − R²_fixed) | H5a: ψ = R²_Rb/R²_within, with R²_within ≥ 0.15 (a positive, bounded-away denominator). H5b: R²_Rb − R²_Ra (alignment vs re-z-scoring). | Review P3: φ = 0.95 at 241 d while R²_Rb = -0.06. In M1, re-z-scoring recovered as much as alignment. |
| C9 | D1 = MC_Maze_Large; D2 = 9 date-locked LINK sessions with mixed CO/RD | D1 = **MC_Maze_Medium** (fresh). D2 = **13 fresh LINK sessions, center-out only**, from two anchors chosen by a date rule (§1.2). | Fresh data for confirmation. CO-only removes M1's style confound (2 of 9 sessions were RD). |
| C10 | One harness gate for all hypotheses | **Per-arm gates.** The D1 harness gates H1-H3; the D2 harness gates H4-H5; the D3 harness gates H6. The guard suite, reproducibility and the power check gate all arms. | In M1, the D2 verdicts were hostage to a D1 control failure. |
| C11 | Bonferroni over 5 primaries (99 % CI) | 8 primaries: H1, H2a, H2b, H3, H4a, H4b, H5a, H5b. CIs are 99.5 % (α_i = 0.005 < 0.05/8). The H2b TOST uses the 99 % CI (α = 0.005 per side). | More primaries. |
| C12 | Predictions were blind estimates | Predictions come from M1 exploratory values and the MC_Maze_Small dry run (§5). | Legitimate for a confirmation on fresh data; disclosed here. |
| C13 | No pre-data check of control power | A **power check** (§7) runs on synthetic data and on OLD M1 data. It must pass before any fresh file is downloaded. It doubles as the budget dry run and includes D2. | M1 lesson: both failures were foreseeable, and the recommendation was to budget from a dry run that includes D2 (RESULTS_M1 §5 (c)). |
| C14 | GRU cut to 1 seed (A4) | The honest D1 GRU is a 3-seed ensemble again. Control and descriptive GRUs use 1 seed. The A4 cut order is revised (§8). | The M1 real run took 378 s, about 3× under the prediction. |
| C15 | GRU/KF drift curves and D2 NC1 for GRU/KF | Descriptive only. The D2 gate covers ridge and the ridge-based recalibration arms, which are the only decoders in H4/H5. | H4/H5 are ridge-only. |
| C16 | D1 condition folds by maze_id (9) | Condition = (trial_type, trial_version). This is used for the NC1 constraint and for the descriptive condition-held-out folds. | Review C2 (27 conditions in Large). |
| C17 | The pre-run DEVIATIONS snapshot was evidenced by mtime only | Its SHA-256 is posted on BOARD **before** the fresh download, and again before the vault opens. | Review §1 caveat and R1. |

---

## 1. Data (fresh), verified from DANDI metadata on 2026-09-27

### 1.1 D1: MC_Maze_Medium (DANDI 000139, version 0.220113.0408)

| field | value |
|---|---|
| licence / access | CC-BY-4.0, dandi:OpenAccess (no sign-up) |
| asset | `sub-Jenkins/sub-Jenkins_ses-medium_desc-train_behavior+ecephys.nwb`, asset_id `7ef450a8-8684-42e2-8598-cd38ca2b2e50` |
| size | **76,604,764 B** |
| dandi:sha2-256 | `3852799f85f662f1cacadb0d758ba8fa0dc6cca318f46c9b131978adf1baffb6` |
| session | 2009-09-29 |

The other sets are different sessions: Large = 2009-10-06 (M1's D1) and Small (000140) = 2009-09-28 (M1's dry run, so it is
**not** fresh). The test file (`desc-test_ecephys`, 695,928 B) holds no behaviour and is not downloaded.

The trial count is **UNVERIFIED**. NLB's scaled sets suggest 250 trials in the train file (M1 read 500 for Large and 100 for
Small), so the expected split is 150/49/49 (+2 gap trials).

### 1.2 D2: LINK (DANDI 001201, version 0.251023.2336)

**What the metadata show.**
- 312 NWB assets from 303 dates (2020-01-27 .. 2023-06-22), 12,563,287,466 B in total, one subject (Monkey N).
- Each asset's `wasGeneratedBy` description gives the target style: 156 CO and 156 RD files. The 9 dates with two files hold one
  CO and one RD file.
- There are 149 unused CO files, the last on 2022-12-09. A +730 d lag is therefore impossible for any anchor after 2020-12, and
  the 730 target is dropped.

**Selection rule (dates and styles only; fixed now; script in §11).**
- The candidates are CO files that are not among M1's 9 assets, sorted by (date, path).
- Two anchors are used:
  - A1 = the first candidate on or after 2020-07-01;
  - A2 = the first unused candidate on or after 2021-07-01.
- For each anchor and each lag target L in {3, 7, 14, 30, 60, 120, 240, 365} d, take the first candidate not already taken with
  L ≤ lag ≤ L + max(3, round(0.25 L)). If there is none, the slot is empty. There is no substitution later.
- The anchor dates are fixed round dates. They were picked because they (i) lie after M1's anchor and after the Mar-Jun 2020
  recording gap, (ii) leave ≥ 365 d of CO follow-up, and (iii) spread the sample over two recording years. I tried the rule with
  other round anchor dates (2021-01-01 and 2021-03-01, which differ only in which slots fill) before fixing these two. That choice
  used metadata only.

| anchor | target L | lag (d) | session | bytes | asset_id | dandi:sha2-256 |
|---|---|---|---|---|---|---|
| A1 | 0 | 0 | 20200708 | 38,287,314 | fc9220d7-f3ad-40eb-9cc0-9e2ffd5bd016 | 77e36c28afcce55cbd8f2c8761a9bb17556fc008041c11b7b8273613314d2839 |
| A1 | 3 | 6 | 20200714 | 40,729,090 | f6533dca-9bf3-4656-9718-dce7f1ed83ee | 62ae4e1dec6495243c9e1982220b77acf07cdbb9ad7805f0fc0e6a7694eb6a93 |
| A1 | 120 | 120 | 20201105 | 36,474,162 | 7cbe4ac7-237d-4bab-96f7-f0cf22a57ee9 | 8cd8e3688952fb3d576edffcaf6d7953f7e84ef9f1eb2271fcf0141e2e6d715a |
| A1 | 240 | 244 | 20210309 | 39,664,146 | 3a7198bd-4db8-401e-bd3b-fb3d051e24cc | bf4802fa9e39830d9716928664593dd57fcfd84c02dc5ef12779015950913837 |
| A1 | 365 | 366 | 20210709 | 35,226,610 | 1910e1d3-ccd7-465e-8456-812358683ed4 | 546f074266ddb8870aa2cf80972987ccc2f5d23637244d3d2dd5328013acf589 |
| A2 | 0 | 0 | 20210706 | 36,703,634 | 09987453-cf36-4c89-b4a5-29912abb8248 | 859b94786b0481fdf3d7ad7674fdd8b51deea3c626da07fe65a5610d737142c1 |
| A2 | 7 | 7 | 20210713 | 37,096,322 | 07331f03-5c37-4bd0-bd8f-bb2748c12e41 | e149b2ce3b52793207a40faa676f6bbd3246f159ee3f12da0086c1e82e909fba |
| A2 | 14 | 14 | 20210720 | 36,789,282 | 430ff4b8-1058-4d88-9180-c0aea6ba0c34 | 289003c68af0b75406aa172fcfd4ed548c973c508466438c21696f56156a026b |
| A2 | 30 | 30 | 20210805 | 38,054,610 | 2c5414ff-1263-48d3-b4cc-e37a2dd72c41 | bad4ae1fb0f1a082980ece42549178a1d56ab584727a9f2ca9134576c64e78f1 |
| A2 | 60 | 62 | 20210906 | 38,983,810 | 84ce09b4-6859-49f0-b262-9802a96c6000 | 685557f907abd0df18ed0310ed6f8ba45374a28e2496353d074ed384ce7a4ecc |
| A2 | 120 | 129 | 20211112 | 41,619,506 | eb507345-bb97-42fc-bc96-4b19bfebb757 | 39b64443c9ebb1b86e253c0eadd3aa974f65af5f440fbde3f2e437625beaad8c |
| A2 | 240 | 244 | 20220307 | 39,088,850 | 890cd908-7f96-4eae-ac60-fac59aa52d06 | 4cd2bbb8cf1d1ebb6de1ebc667ccc8458c22da7377e167b668171097a65f39bb |
| A2 | 365 | 377 | 20220718 | 35,818,066 | 19b99ead-c2e8-4a06-b3e4-d2a659634089 | aed9f3433689af14224e46ff3a586f315dfcffc7fb21c52204b7a58db2d4f712 |

**Slot notes.**
- Empty slots: A1 7/14/30/60 and A2 3. The CO sessions in Jul-Oct 2020 are sparse.
- Every file is used once. A1's slots are filled first, so A2's slots can only come from files A1 did not take.
- A2's anchor, 20210706, is the first CO file on or after 2021-07-01.
- 20210709 (A1 +366) and 20210706 (A2 anchor) are 3 days apart. They are different files, and each is used in one role only.

**Hypothesis sets.**
- H4a / H5a / H5b (lag ≥ 30 d): 8 sessions. A1: +120, +244, +366; A2: +30, +62, +129, +244, +377.
- H4b (lag 3-14 d): 3 sessions. A1 +6; A2 +7, +14.

The paths are `sub-Monkey-N/sub-Monkey-N_ses-<YYYYMMDD>_ecephys.nwb`. The NWB layout (20 ms SBP, index/MRS velocity, trial
table with `target_style`, `index_target_position`, `mrs_target_position`) is assumed to match M1's LINK files and is checked by
A6.

### 1.3 D3 (secondary, blind): EEGMMIDB S001-S020, runs 04/08/12

These files are already on disk from M1 (0 new bytes). They were hashed but never parsed or scored. The M1 D3 specification is
unchanged.

### 1.4 Budget (c)

| item | bytes |
|---|---|
| already downloaded (motor_manifest.csv, 131 files) | 730,193,426 |
| + MC_Maze_Medium train | 76,604,764 |
| + 13 LINK sessions | 494,535,402 |
| **motor-readout total after M1b** | **1,301,333,592 (1.30 GB < 1.5 GB; margin 198.7 MB)** |

Every file is matched to its dandi:sha2-256 above (`InputHashError` on mismatch) and appended to motor_manifest.csv.

### 1.5 Input locks (S7 style)

**Fresh lock.** SHA-256 of these 3 lines (UTF-8, joined by "\n", no trailing newline) =
`e6856172aea86e5a0cf6992112824ae45d15803842d2969489d3796d9a112792`
```
000139|0.220113.0408|7ef450a8-8684-42e2-8598-cd38ca2b2e50
001201|0.251023.2336|A1:fc9220d7-f3ad-40eb-9cc0-9e2ffd5bd016,f6533dca-9bf3-4656-9718-dce7f1ed83ee,7cbe4ac7-237d-4bab-96f7-f0cf22a57ee9,3a7198bd-4db8-401e-bd3b-fb3d051e24cc,1910e1d3-ccd7-465e-8456-812358683ed4;A2:09987453-cf36-4c89-b4a5-29912abb8248,07331f03-5c37-4bd0-bd8f-bb2748c12e41,430ff4b8-1058-4d88-9180-c0aea6ba0c34,2c5414ff-1263-48d3-b4cc-e37a2dd72c41,84ce09b4-6859-49f0-b262-9802a96c6000,eb507345-bb97-42fc-bc96-4b19bfebb757,890cd908-7f96-4eae-ac60-fac59aa52d06,19b99ead-c2e8-4a06-b3e4-d2a659634089
eegmmidb|1.0.0|S001-S020|R04,R08,R12
```

**Power-check lock (old M1 data only).** SHA-256 =
`01cf828b85ba1ec252dd50a89bd53204b02c8287724f436afec6ddf7d33e5ce9`
```
000138|0.220113.0407|e67b57b2-e9ad-4d95-b9e3-1262997360dc
000140|0.220113.0408|7821971e-c6a4-4568-8773-1bfa205c13f8
001201|0.251023.2336|c002a9a1-664d-4a69-af02-ba810046c4fb,88039197-6170-4d06-ba3e-f58b68c6eb7f
```
The two LINK files in the power-check lock are M1's 20200127 (anchor) and 20200626 (+151 d, CO).

Arms, targets, features and bins are as in M1 §1, with these exceptions:
- D2 uses 20 ms → 32 ms re-binning as in M1 DV-1.
- A D2 file whose trial table is not all CO is dropped (A6).

## 2. Splits and leak guards

These are unchanged from M1 §2 and DEVIATIONS B.1-B.2, B.4-B.5, B.11-B.12, B.16-B.17:
- whole-trial units, chronological 60/20/20 with a one-trial gap at each cut;
- vault sealing and train-only normalisation;
- the split lock is written before the first fit.

**Additions.**
- **Row day tags (review C1).** Every D2 design row carries (session_date, block). The session-order check is called with the
  tags of the rows actually passed to each fit. PL-2's undeclared call must raise because of those tags, not because of a
  literal list.
- **NC1 permutations** are drawn **before** any fit and hashed into the split lock.

## 3. Decoders (hyperparameters locked; selection on validation only)

Ridge, KF-0, GRU, the recalibration arms R-a and R-b, and D3 (LDA and Riemannian) are exactly as in M1 §3 and DEVIATIONS
B.5-B.9 and B.18, with two changes:
- The honest D1 GRU is a 3-seed ensemble (20261001-3).
- All control and descriptive GRUs use seed 20261001.

**KF-L (new; pre-registered now, informed by the review).** The pre-registration is informed by review §3: on Large test data, KF
with x_{t-3} reached 0.384 and KF on a 200 ms boxcar reached 0.393. I have seen these numbers.
- **Grid:** the D1 20 ms grid and window, identical to ridge and KF-0.
- **Observation:** o_t = the mean of the z-scored counts over bins t−L−B+1 … t−L. This is causal and uses the same z-scorer as
  ridge.
- **(L, B):** chosen by validation R² over L ∈ {0,…,7} bins (0-140 ms) and B ∈ {1, 2, 5, 10} bins, with L + B ≤ 10 so that the
  KF sees no more than ridge's 200 ms of history. That gives 23 pairs.
  - Ties go to the first pair in (B, L) ascending order.
  - (L, B) = (0, 1) is KF-0.
- **Fitting:** state [v1, v2, 1] and least-squares A, Q, C, R, as for KF-0. `m1lib.decoders.KalmanVel` is used **unchanged**; only
  the observation matrix passed in differs.
- **Running:** the filter runs from the window start of each trial. History bins supply only the observation lags.
- **Not changed (one change at a time):** the bin size (the 50/100 ms KF stays in the descriptive bin sweep, because a different
  grid changes the scored target) and a position+velocity state.
- **D2:** KF-L is not used in D2. The D2 KF remains descriptive.

## 4. Metrics

### 4.1 Unchanged from M1 §4
- M-R2 (variance-weighted) and ρ².
- M-MI (D3).
- The bootstrap: paired over test trials (D1) or 64-bin segments (D2), B = 2000, stream k = 1. For medians over sessions,
  each session is resampled independently and the median is taken per replicate.
- The descriptive items (bin sweep, NC2b, condition-held-out).

### 4.2 Bits/s

The segments are as in M1: D1 uses each test trial's 35-bin window; D2 uses 64-bin test segments. The Hann taper and rfft are
unchanged. Primary frequencies are **0 < f_j ≤ 10 Hz**:
- D1: j = 1..7, Δf = 1.4286 Hz;
- D2: j = 1..20, Δf = 0.488 Hz.

**I_coh (information metric, as in M1 but without DC).**
- I_coh = Δf Σ_d Σ_j −log2(1 − γ̂²_d(f_j)).
- I_coh,net = I_coh − median over 200 derangements (stream 3).
- The DC-included M1 value is also reported.

**I_mse (sign- and gain-sensitive, new).**
- Definition: I_mse = Δf Σ_d Σ_j log2( Ŝ_yy,d(f_j) / Ŝ_ee,d(f_j) ).
  - Ŝ_yy = Σ_k |Y_k|² (true velocity).
  - Ŝ_ee = Σ_k |Y_k − Ŷ_k|², where Ŷ is the decoder output **as issued**, with no refitted gain.
- Terms are **not** clipped at 0.
- Null: the true segments are deranged, so Ŝ_ee^π = Σ_k |Y_π(k) − Ŷ_k|².
- I_mse,net = I_mse − median(null).

**Properties (DERIVATION; unit-tested; §9).**
- (i) For every frequency, Σ_k|Y_k − Ŷ_k|² ≥ min_g Σ_k|Y_k − gŶ_k|² = Ŝ_yy(1 − γ̂²). Therefore **I_mse ≤ I_coh holds
  deterministically in-sample.** For jointly Gaussian stationary processes, it is also a (looser) lower bound on the information
  rate.
- (ii) A decoder whose output is identical on every segment (for example B0) has null = raw, so its net value is exactly 0.
- (iii) Negating a decoder's output lowers I_mse.
  - Example: Ŷ ≈ Y at high R² gives Ŝ_ee ≈ 4Ŝ_yy under negation, so each term ≈ −2 bits per Δf. The coherence value would be
    unchanged. This is the review-§3 demonstration, reversed.
- (iv) Under no leak, a shuffled-trained readout is a fixed linear function of the trial's neural data. It has no systematic
  alignment with the trial-specific kinematics once same-condition pairs are excluded, so E[I_mse,net] ≈ 0, with a small sign
  that is not fixed a priori. §7 measures its spread before any fresh data are read.

### 4.3 Drift metrics (well-conditioned)

For D2 anchor a and session k:
- **Loss:** L_k = R²_within(k) − R²_fixed(k). This is a difference, so it has no denominator.
- **Usable retention of an arm:** ψ_arm(k) = R²_arm(k) / R²_within(k). It is defined only if R²_within(k) ≥ 0.15.
  - The denominator is then ≥ 0.15.
  - In M1 R²_within ranged 0.19-0.33, so the ratio's relative error is bounded by the within-day CI.
- **Alignment gain over re-z-scoring:** Δ_ab(k) = R²_Rb(k) − R²_Ra(k).
- **Usability:** a session with R²_within(k) < 0.10 is excluded from H4. For H5 the cut is 0.15.
- Descriptive: ρ and φ (M1 definitions, for continuity only), Spearman(lag, L_k) per anchor and pooled, per-anchor medians, and
  the bias share of MSE (review R4).

## 5. Hypotheses, predictions and PASS/FAIL rules

The predictions below are ESTIMATES built from **M1 exploratory values** (Large and the 9 old LINK sessions) and the Small dry
run. That use is disclosed (C12). P = my prior probability of PASS.

| ID | claim (arm) | PASS | FAIL | otherwise | prediction and basis |
|---|---|---|---|---|---|
| H1 | GRU (3-seed ensemble) beats ridge (D1, Medium) | Δ = R²_GRU − R²_ridge ≥ 0.02 **and** 99.5 % CI lower bound > 0 | 99.5 % CI upper bound < 0.02 | INCONCLUSIVE | Δ ≈ +0.07, interpolated log-linearly in training trials between Small (60 train, Δ = −0.02) and Large (300 train, Δ = +0.14) at 150 train trials. The 99.5 % CI half-width on 49 test trials is ≈ 0.043 (scaled from M1's 0.028 at 99 trials and 99 %). P = 0.55 |
| H2a | The KF specification matters: KF-L beats KF-0 (D1) | Δ = R²_KF-L − R²_KF-0 ≥ 0.05 **and** 99.5 % CI lower bound > 0 | 99.5 % CI upper bound < 0.05 | INCONCLUSIVE | Δ ≈ +0.10 (review §3: Large +0.10 / +0.11, **test-informed**). P = 0.70 |
| H2b | An information-matched KF ≈ ridge (D1) | 99 % CI of R²_KF-L − R²_ridge entirely inside [−0.05, +0.05] | 99 % CI entirely outside [−0.05, +0.05] | INCONCLUSIVE | Δ ≈ −0.25 (Large: 0.38-0.39 vs 0.669). **Predicted FAIL**; P(PASS) = 0.05 |
| H3 | Bits/s follows R² (D1): the ranking of {GRU, ridge, KF-L} by I_coh,net equals their ranking by M-R2, **and** for GRU vs ridge both ΔR² and ΔI_coh,net have 99.5 % CIs excluding 0 with the same sign | both hold | the 99.5 % CIs of ΔR² and ΔI_coh,net (GRU − ridge) both exclude 0 with **opposite** signs | INCONCLUSIVE (including when ΔR²'s CI covers 0) | The ordering held in M1 (GRU > ridge > KF). Levels, DC excluded: ridge ≈ 14, GRU ≈ 17 bits/s (± factor 2; M1 Large without DC: ridge 17.8). P = 0.45 (tied to H1's power) |
| H4a | A day-0 ridge drifts at lag ≥ 30 d (D2) | median L_k over usable lag-≥-30 sessions ≥ 0.10 **and** the 99.5 % CI lower bound of that median > 0.05 | 99.5 % CI upper bound of the median < 0.05 | INCONCLUSIVE; also INCONCLUSIVE if fewer than 5 of the 8 sessions are usable | median L ≈ 0.4. M1 lag ≥ 30: 0.20, 0.26, 6.4, 0.83, 1.08 (median 0.83). P = 0.85 |
| H4b | Drift is already present at 3-14 d (D2) | median L_k over the 3 short-lag sessions ≥ 0.10 **and** 99.5 % CI lower bound > 0.05 | 99.5 % CI upper bound < 0.05 | INCONCLUSIVE; also INCONCLUSIVE if any of the 3 is unusable | median L ≈ 0.3. M1: +3 d 0.65, +8 d 0.43, +15 d 0.28. P = 0.70 |
| H5a | Unsupervised FA-Procrustes (R-b) restores a **usable** decoder at lag ≥ 30 d | median ψ_Rb ≥ 0.5 **and** 99.5 % CI lower bound > 0.25 | 99.5 % CI upper bound of median ψ_Rb < 0.5 | INCONCLUSIVE; also INCONCLUSIVE if fewer than 5 sessions are usable | median ψ_Rb ≈ 0.0. M1: 0.75 at 32 d (RD), −0.26 / −0.24 / −0.59 at 151 / 241 / 393 d. **Predicted FAIL**; P(PASS) = 0.10 |
| H5b | Alignment adds to re-z-scoring: R-b > R-a at lag ≥ 30 d | median Δ_ab ≥ 0.02 **and** 99.5 % CI lower bound > 0 | 99.5 % CI upper bound < 0.02 | INCONCLUSIVE | median Δ_ab ≈ −0.05. M1: +0.03, −0.09, −0.06, −0.10, +0.01. **Predicted FAIL**; P(PASS) = 0.10 |
| H6 (secondary, blind; not in the family) | Riemannian tangent space beats log-variance LDA (D3) | as in M1 §5 | as in M1 §5 | as in M1 §5 | LDA 0.60, TS 0.64 (M1's blind estimates, unchanged). P = 0.40 |

**Notes.**
- H5a and H5b replace M1's H5. M1's H5 "PASS" meant "a catastrophic offset was removed", and review P3 showed that this metric
  cannot distinguish that from recovery.
- The honest numbers for every decoder, anchor and session are reported whatever the verdicts are.
- Inference in D2 is **conditional on the two fitted day-0 decoders**. Sessions within an anchor share that decoder, and the
  bootstrap resamples test segments only. This is stated in the card.

## 6. Controls (null values derived in advance; each can fail)

### 6.1 Negative controls

**NC1 (shuffled alignment, corrected).** Gating: D1 for ridge, KF-0, KF-L and GRU; D2 for ridge and R-b's FA-ridge on each
anchor day. GRU/KF on D2 are descriptive.

Construction:
- Training pairs and validation pairs are both re-paired by a **condition-constrained derangement** (stream 2), as in DV-6.
  - D1 condition = (trial_type, trial_version).
  - D2 condition = (index_target_position, mrs_target_position), rounded to 4 d.p. (the review's definition).
- Sampler: rejection sampling of uniform permutations until no trial is paired with itself or with a same-condition trial; at
  most 10⁵ draws.
- If one condition holds more than 50 % of the trials, no such derangement exists. In that case, use an unconstrained derangement
  and flag the arm.

**Null values.**
- The shuffled decoder can learn only condition-agnostic, time-locked structure. Its expected R² is therefore that of the correct
  reference B0:
  - D1: onset-aligned mean velocity profile (train);
  - D2: **trial-start-aligned** mean profile over the anchor's calib trials, extended by the last value for longer trials.
- Under a constrained derangement, the expected partner kinematics given a trial's condition c is (Nμ − μ_c)/(N − 1). This is
  weakly *anti*-informative (weight 1/(N−1)), so the R² null is **at or below** R²_B0.
- For I_mse,net the null value is 0 (§4.2 (ii), (iv)).

**PASS (every gated decoder):**
- R²_shuf ≤ R²_B0 + 0.03 **and**
- I_mse,net(shuf) ≤ 0.10 × I_mse,net(honest ridge, same arm).

The descriptive coherence I_coh,net(shuf) is reported with the note that it is expected to be > 0 (M1 5b).

**Can it fail?** Yes. The planted NC1 leak NL-1 (§7, P3) keeps 25 % of the training and validation pairs true. The expected
shuffled readout is then ≈ f·ŷ_h with f = 0.25. For an orthogonal-error honest predictor this gives
R² ≈ R²_h(2f − f²) = 0.44 R²_h, which is ≈ 0.27 at R²_h = 0.62 and far above B0 + 0.03. §7 must show
that NC1 FAILS under NL-1.

**NC2a (trial-shift null).** Unchanged from M1. The bar is max(0.05, R²_B0 + 0.02), with the arm-correct B0. It is gated on D1 and
on each D2 anchor. It passed in M1 by a wide margin (−0.47 / −0.21). Same-target pairs can only make it fail spuriously, never
pass spuriously.

**NC2b.** Descriptive, as in M1.

### 6.2 Positive (planted-leak) controls

**PL-1 (label-in-features, re-powered).** Gated on D1 (ridge) and on each D2 anchor day (ridge).

Construction:
- Append 2 un-lagged columns, p_d = z(v_d) + N(0, σ²), with σ² = 0.1. The z-score uses train mean and SD; the noise uses stream 6.
- Use the same λ grid, with selection on validation.
- Test values come through `vault.planted_access` (declared). The undeclared version must raise `FeatureWhitelistError`.

Analytic expectation (DERIVATION; exact for the best linear predictor):
- Let r_d be the honest residual fraction of dimension d. The optimally combined residual is r_dσ²/(r_d + σ²).
- The expected rise is therefore **E = Σ_d w_d r_d²/(r_d + σ²)**, with w_d = var(v_d)/Σ var.
- Correlated v1 and v2 can only increase it. This formula generalises review 5a, which is the case σ² = 1 with one dimension.
- It was checked while this prereg was written, on synthetic linear-Gaussian data only (n = 2×10⁵, OLS, σ² = 0.1): the observed
  rise was 0.6673 and the analytic E was 0.6669.

The bar is fixed **before the vault opens**:
- E is computed from the honest ridge **validation** residuals.
- If E_val < 0.10, σ² switches to 0.02 and E is recomputed. This fallback is fixed now.
- The bootstrap SD s of the rise is computed on validation trials.
- The control is valid only if 0.5E ≥ 3s. Otherwise PL-1 is FAIL (underpowered). The power check (§7) makes this unlikely.

**PASS:** observed test rise ≥ 0.5E **and** the whitelist guard raises.

Anticipated numbers:
- D1: honest R² ≈ 0.62 → r ≈ 0.38 → E ≈ 0.30, bar ≈ 0.15.
- D2 anchors: r ≈ 0.67 → E ≈ 0.58.
- M1's observed rise matched its analytic value (0.034 vs 0.035; the reviewer's 10 seeds gave 0.028-0.034).

**PL-2' (future-session leak, re-specified).**
- For each anchor, take the first lag-≥-30 session: A1 +120 d (20201105) and A2 +30 d (20210805).
- The "day-0" ridge is trained on the anchor's calib data **plus that session's calib block with true labels**, declared
  `allow_future=True`. It is scored on that session's test block.
- **PASS:** R²_leak − R²_fixed ≥ 0.5 × (R²_within − R²_fixed), **and** the undeclared call raises `SessionOrderError` through the
  row day tags (§2).
- If R²_within − R²_fixed < 0.05, the session shows no drift to recover, and PL-2' is reported as "not informative". It does not
  gate in that case.

**PL-3 (random bins + centred window).** Unchanged from M1 (GRU inflation ≥ 0.01; both guards raise). It is gated on D1.

**PL-4 (D3, new).**
- Append a 65th channel before band-passing. It is white N(0,1) noise with SD × 2 during T2 epochs of train and test (stream 6),
  declared.
- Analytic expectation: the log-variance means differ by ln 4 = 1.39. The within-class SD is ≈ (2/ν)^½ ≈ 0.15, with ν ≈ 2·22 Hz·2 s
  ≈ 88 effective degrees of freedom after the 8-30 Hz filter. So d′ ≈ 9 and LDA accuracy ≈ 1.
- **PASS:** mean test accuracy ≥ 0.90 **and** ≥ honest LDA + 0.15. The undeclared version must raise `FeatureWhitelistError`.

**NC1-D3.** Unchanged from M1: 5 label permutations per subject, with mean accuracy in [0.40, 0.60].

### 6.3 Code and reproducibility (all arms)

- The M1 guard suite (40 tests) is re-run unchanged.
- New tests (§9) are added. Everything must pass at 100 %.
- Reproducibility: a rerun must give an identical card hash (`card_hash`; BLAS threads = 1; torch deterministic).

### 6.4 Harness verdicts (per arm; C10)

- **All-arm prerequisites:** the power check PASS (§7) + the guard suite + reproducibility.
- **D1 harness (gates H1, H2a, H2b, H3):** NC1-D1 + NC2a-D1 + PL-1-D1 + PL-3.
- **D2 harness (gates H4a, H4b, H5a, H5b):** NC1-D2 + NC2a-D2 + PL-1-D2 on both anchors, + PL-2' (where informative).
- **D3 harness (gates H6):** NC1-D3 + PL-4.

A failed arm harness makes that arm's hypotheses "not verifiable: harness".

## 7. Synthetic and old-data power check (run BEFORE any fresh download)

This runs under the power-check lock (§1.5). It uses synthetic data plus OLD M1 data: MC_Maze_Large, MC_Maze_Small, LINK
20200127 → 20200626. No fresh file may exist on disk while it runs; the downloader refuses until `POWER_M1b.json` says PASS.

The outputs are:
- results\POWER_M1b.json (and a card), whose SHA is posted on BOARD;
- the A4 budget projection.

**Synthetic generator (numpy; stream 7).**
- Kinematics: a 2-D velocity, a smooth Gaussian process built as a sum of 8 random reach profiles per trial, with 27 conditions
  (reach directions).
- Neural data: 150 units, x_t = C v_{t+5} + N(0, I)·s. The noise scale s is set so that the honest ridge R² is 0.4, 0.6 or 0.8.
- Trial count: 250 trials (Medium-sized) and 375-trial "sessions", with a mean-shift + rotation drift for D2.

The truth is known.

| item | test | criterion |
|---|---|---|
| P1 | PL-1 power: synthetic at R² ∈ {0.4, 0.6, 0.8}, plus Large, Small and LINK 20200127, over 20 noise seeds | (a) the observed rise is ≥ 0.5E in ≥ 19/20 seeds on every dataset, and (b) on synthetic data the mean observed rise is within ±25 % of E. (b) checks the formula, including ridge shrinkage at small n (Small, 60 train trials, is the worst case). |
| P2 | NC1 clean passes | Ridge, KF-0 and KF-L: 20 constrained derangements each; GRU: 5, on Large, Small, synthetic and LINK 20200127 (ridge). NC1 must PASS in ≥ 19/20 (GRU 5/5). The distribution of I_mse,net(shuf) (mean, SD, max) is reported. On Large, the unconstrained M1 shuffle is also run to reproduce M1's coherence failure (expected I_coh,net > 0.15). |
| P3 | NC1 can fail (NL-1: 25 % of pairs kept true; stream 8 picks them) | The same decoders and datasets as P2. NC1 must FAIL in ≥ 19/20 (GRU 5/5), on R² or on I_mse. |
| P4 | Metric properties | I_mse ≤ I_coh for every decoder and dataset (deterministic). The negated honest ridge output gives I_mse,net < 0 while I_coh is unchanged. B0 gives I_mse,net = I_coh,net = 0 (to 1e-9). The DC-excluded frequency counts are 7 (D1) and 20 (D2). |
| P5 | PL-2' power (old LINK 20200127 → 20200626, and synthetic drift) | The recovered loss is ≥ 0.5 × (within − fixed). The undeclared call raises through row tags. |
| P6 | PL-4 power (synthetic EEG via `m1lib.synthetic`; **no real EEGMMIDB value**) | Accuracy ≥ 0.90 in ≥ 19/20 seeds. NC1-D3 mean is in [0.40, 0.60]. |
| P7 | Budget | Wall time and peak RSS of a full dry run of the real pipeline (on Small as D1, and the two old LINK files standing in for each anchor's sessions, repeated to 13), extrapolated to Medium + 13 sessions. This decides A4 before the download. |

**Gate.**
- If any of P1-P6 fails, the prereg is amended (M1b.1: a new σ², margin or constraint, derived again). The amendment gets a new
  SHA and the check is rerun. **Fresh data are still untouched, so the amendment is legitimate.**
- After 2 failed amendments, M1b is abandoned (A0).
- The power-check numbers never feed the H thresholds.

## 8. Abandonment rules

- **A0.** The power check (§7) fails after 2 amendments → no fresh download; M1b is abandoned and reported as such.
- **A1.** A file needs a sign-up, is missing, fails its hash, or would push the motor-readout total over 1.5 GB:
  - Medium → the D1 arm is NOT TESTED;
  - a LINK anchor → that anchor's sessions are dropped;
  - a LINK non-anchor → that slot is empty (no substitute).
- **A2.** An arm harness fails → that arm's hypotheses are "not verifiable: harness", and its numbers are exploratory.
  **The fresh data of that arm are then spent**: no later confirmatory prereg may reuse them. A further attempt needs new
  sessions.
- **A3.** Sanity, on validation only, before the vault opens:
  - honest ridge validation R² ≥ 0.20 on D1;
  - the same on each anchor day.
  If an anchor fails, its sessions are dropped (no debugging on fresh data). If D1 fails, the D1 arm stops, and any fix is
  "post-deviation".
- **A4.** Budget: < 20 min CPU wall time, < 1.5 GB peak RSS, **decided from P7 before the download**. Cut in this order, each cut
  logged:
  1. D3 / H6;
  2. D2 GRU and KF descriptive drift curves and their NC1;
  3. NC2b and the bin sweep;
  4. the honest GRU ensemble, 3 → 1 seed (this lowers H1 power; stated in the card).
  If the run is still over, the GRU arm is NOT TESTED, and H1 and H3 are NOT TESTED.
- **A5.** torch is unavailable → the GRU is NOT TESTED (torch 2.14.0+cpu was installed in M1).
- **A6.** Schema checks, on trial and timing tables only, before any fit:
  - Medium: no `hand_vel`, no `move_onset_time`, or fewer than 200 trials → D1 NOT TESTED.
  - LINK: a file whose `target_style` is not all CO, whose bins are not ≈ 20 ms, or which has fewer than 300 trials → that
    session is dropped.
- **A7.** Too few usable sessions:
  - H4a, H5a and H5b need at least 5 of 8 usable;
  - H4b needs 3 of 3;
  otherwise INCONCLUSIVE (underpowered).
- **A8.** Contamination: any fresh behavioural value is read outside the vault flow before the split lock → the affected arm is
  exploratory.

## 9. Reuse of M1 code (d)

**Imported unchanged.** These modules were independently reproduced by the review and show no BUG. Their SHA-256 values go in the
card and must equal the M1 card's values.

| module | what is reused |
|---|---|
| `m1lib.guards` | everything: chrono_split, assert_trial_disjoint, assert_bins_disjoint, assert_causal_blocks, random_bin_split, lag_offsets, lagged, feature_names, assert_whitelist, causal_whitelist, ZScore, assert_session_order (called with row-derived tags; the function itself is unchanged), LabelVault, sha256 helpers, assert_input_lock, assert_file_hash |
| `m1lib.metrics` | everything: r2_vw, rho2, unit_stats, r2_from_stats, seg_spectra, _coh, bits_from_spectra (called with a DC-excluded mask), derangements, bits_with_null (the DC-included report only), boot_weights, pct_ci, mi_miller_madow, wolpaw_bits, signflip_p, spearman |
| `m1lib.decoders` | everything: RidgePath/RidgeStream/select_ridge/Ridge/fit_ridge_select, KalmanVel (KF-0 and KF-L), torch_setup/make_gru/GRUEnsemble/train_gru, FA, procrustes, ShrinkLDA, riemann_mean, tangent, reg_cov, LogRegL2 |
| `m1lib.data` | d1_trials, D1Source, rebin, d2_trials, d2_owner, d2_neural, d2_behaviour, edf_annotations, d3_run |
| `m1lib.synthetic` | the D2/D3 synthetic patch (P6 and the tests) |
| nfharness, edf_reader | read-only, as in M1 |

**Not reused.**
- `m1lib.data.file_paths` hardcodes Large and Small. Paths come from a new module instead; m1lib is not edited.
- `run_m1.py` and `finalize_m1.py` are replaced by `run_m1b.py`, `power_m1b.py` and `finalize_m1b.py`. Blocks confirmed by the
  review may be copied, with the source line cited in a comment. The mis-specified control logic may not be copied.

**New code (code\m1b\).**
- A trial-table reader for (trial_type, trial_version) and the LINK target fields.
- `constrained_derangement`.
- The start-aligned B0.
- `freq_mask_nodc`.
- `bits_mse` with its null.
- KF-L features and grid selection.
- PL-1 two-dimensional with the analytic E.
- NL-1.
- PL-2' with row-tag guards.
- PL-4.
- The synthetic generator.

**New tests (at least 12).**
- I_mse ≤ I_coh (property test on random data).
- B0 net = 0.
- Negation lowers I_mse.
- The constrained derangement never pairs a same-condition trial and is a permutation.
- The fallback flag fires when a condition holds more than 50 % of the trials.
- The analytic E is within 10 % on large-n linear-Gaussian data.
- KF-L with (L, B) = (0, 1) gives exactly KF-0.
- The KF-L feature is causal (a feature at bin t is unchanged when bins > t are perturbed).
- The row-tag SessionOrderError fires for a day-k calib row in a day-0 fit.
- The whitelist raises for undeclared p_1/p_2 and for the PL-4 channel.
- NL-1 keeps exactly 25 % of the pairs.
- The lock hashes of §1.5.

## 10. Run order and provenance

1. Post this prereg's SHA on BOARD. Write code\m1b\ and the tests. The pytest suite passes.
2. **Power check (§7)** on synthetic and old data. POWER_M1b.json = PASS; post its SHA on BOARD. The A4 decision is made here.
3. Snapshot DEVIATIONS_M1b.md and post its SHA on BOARD (C17).
4. Download the fresh files (§1). Hash-match each one and append it to the manifest. Check the fresh lock hash.
5. Read trial tables only (A6). Draw the NC1 permutations. Write results\M1b_split_lock.json (partitions, permutations, grids,
   code hashes) **before** the first fit.
6. Fit on train, select on validation, run the A3 check, compute the PL-1 E and s from validation, freeze and hash the models.
7. Run the controls; declared planted reads only.
8. Open the vault and compute the final scores. Run the rerun for reproducibility.
9. Card: input hashes, prereg SHA, power-check SHA, code, m1lib and nfharness hashes, package versions, seed 20261001, streams
   k = 1..8, peak RSS and wall time. Streams: 1 bootstrap, 2 NC1 derangements, 3 bits null, 4 H6 sign-flip, 5 D3 label
   permutations, 6 planted leaks, 7 power-check synthetic, 8 NL-1 subset.

Budget: RAM < 1.5 GB (one LINK session in memory at a time; M1 peaked at 1.27 GB with the twice-larger Large file), CPU < 20 min,
seed 20261001.

An independent reviewer then re-implements, from this text:
- I_mse and I_coh (DC excluded);
- the constrained derangement;
- the PL-1 E;
- L_k, ψ and Δ_ab;
- the D1 split.

This happens before anything reaches THEORY.md (HIVE rule 8).

## 11. Selection script (metadata only; reproduces §1.2 from the DANDI API)

The script is kept in the mathematician's scratchpad (m1b_select.py). Its logic, stated fully:
- load every 001201/0.251023.2336 asset's `wasGeneratedBy[Session].startDate` and `.description`;
- style = the last two characters of the description;
- keep style == "CO" and asset_id ∉ M1's 9;
- sort by (date, path);
- pick A1, then A2, then the lag slots, in the order given in §1.2, marking each chosen asset as taken.

Running it against the API on 2026-09-27 returned exactly the 13 assets above, 494,535,402 B in total. A coder re-running it must
get the same list. If it does not (the dandiset version is pinned, so it should), the locked list in §1.5 governs.

Attribution:
- MC_Maze_Medium: Churchland & Kaufman (2022), DANDI 000139/0.220113.0408, CC-BY-4.0.
- LINK: Temmar et al., DANDI 001201/0.251023.2336, CC-BY-4.0.
- EEGMMIDB: Schalk et al., PhysioNet, ODC-By 1.0.
- No raw data are redistributed.
