# REVIEW: N1 harness controls and N2 baseline (independent code review, verification gate)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Reviewer: independent code reviewer, 2026-09-26. Scope: code\nfharness\, code\run_n1.py and code\run_n2.py, checked against
prereg\N1_harness_controls.md and prereg\N2_baseline_detection.md (hashes 27db9d27... and ed929ae0..., the same as in the run
card), code\RESULTS_N1_N2.md, code\DEVIATIONS.md, results\. Nothing in the harness, the scripts or results\ was modified.
The reviewer's checks are in code\review\: each *.py file writes a matching *_out.json or *.log. The venv was used, every
check ran in under 10 minutes and under 1 GB, and the reviewer seeds are SeedSequence(20261001, spawn_key=(99, ...)).

## Summary

| # | item | status |
|---|---|---|
| 1 | Leak-proofness of the honest pipeline | **CONFIRMED** (no path from test data into training was found; 3 minor notes) |
| 2 | Metrics: SzCORE event scoring, FA/24 h, Garwood/CP, AUROC/AUPRC, independent recompute | **CONFIRMED** (exact match in all 3 subjects) |
| 3 | N1(b) FAIL diagnosis | **DESIGN flaw in the prereg controls, not a code bug.** NC2 criterion 1, criterion 2 (NC1 and NC2) and C3 are mis-specified |
| 4 | Verdict strings | **CONFIRMED** as the literal application (N1 FAIL; N2 "not verifiable: code"; counterfactual INCONCLUSIVE) |
| 5 | Provenance and determinism | **CONFIRMED** (1 minor note: DEVIATIONS.md changed after the run, as disclosed) |

No BUG was found that changes any reported number or verdict.

---

## 1. Leak-proofness: CONFIRMED

- **The split is causal and matches the hash.** splits.py:33-48 cuts after the 3rd seizure, and only the counts of files up to the
  cut are consulted. It is hashed and compared before any feature is computed (run_n2.py:132-138).
  - The reviewer's independent code (review\indep_n2.py) hard-codes the prereg split string and asserts its SHA-256 = 433d818f...f1e2.
  - Recomputed from the EDF header clocks, max(train end) <= min(test start) holds in all 3 subjects.
  - Gap from the last training file to the first test file: chb01 7 s, chb03 7 s, chb10 14,453 s.
- **No window straddles a boundary.** Windows are built per file (windows.py:15-31; F4 guard).
  - The buffer (windows.py:40-50, re-checked by assert_buffer at pipeline.py:109) drops training windows whose end lies within 10 s of a test file.
  - The reviewer's own implementation gives the same dropped counts: 3 / 3 / 0 windows. The training window counts also match: 25,190 / 10,794 / 21,627, with 104 / 183 / 167 positives.
- **The normaliser, tau and smoothing are fitted on training data only.**
  - ZScore is fitted in `fit()` on the training parts only (pipeline.py:64-76). The F1 guard compares fit IDs with apply IDs (model.py:56-61).
  - tau comes from `select_tau` (postprocess.py:47-64), which accepts only `train_oof` scores. Its FA callback (pipeline.py:124-126) scores against `TL.mask`, the training labels from `vault.train_mask`, over training durations only.
  - k-of-n has no fitted parameters.
- **The inner LOFO uses training files only** (pipeline.py:113-121).
  - The folds are `[[r] for r in sp.train]` (run_n2.py:159). The test-ID refusal is at pipeline.py:99.
  - OOF predictions are made for held-out training files only. The final model is refitted on the training windows that the buffer keeps (pipeline.py:129).
- **Test labels were not read before the prereg hashes were computed.**
  - The prereg is hashed at run_n2.py:106-107. The first scorer read came 35.6 s later (run card runtime).
  - The current prereg files still match the recorded hashes.
  - The prereg mtimes (18:26-18:27 local) precede the run start (18:46:47 local).
- **Attempts to find a leak path.**
  - Features are stateless per window, so the cache cannot leak.
  - `TrainLabels` reads `vault.train_mask` for `split.train` only (pipeline.py:28-30).
  - Test windows reach `fit()` only in C2a and C2b. Both are the deliberate controls, gated by flags (`allow_random_split`, `allow_leak`).
  - Every test-label read goes through `Scorer` (scoring.py:127-159). The only other holder of test annotations is the `ann` dict in run_n2.py, which is used for vault construction and for C2a.
  - The GUARD counters and RNG streams are the only state shared across runs.
  - Nothing found.
- **Minor notes (not leaks):**
  - (i) The c4 timestamp measures the first *scorer* read. The first *parse* of test annotations happens earlier, in `load_records` (run_n2.py:129, data.py:107-124). It is still after the prereg hash (line 106 before 129), so c4 holds, but the log understates the earliest read. For the next prereg, log the summary parse too.
  - (ii) F8 is a convention, not enforcement (D15, labels.py:19). This is acceptable as disclosed.
  - (iii) N1(a) C2a measures the leaky AUROC on a different window set (all held-out windows of all files, D10) from the honest AUROC (causal test files).
    - review\c2a_sameset.py reproduces C2a exactly (0.99694 / 0.99937 / 0.99056).
    - Restricted to the causal test files, the leaky AUROC is 0.99827 / 0.99947 / 0.98422. That gives mean D = +0.012 and mean E = 0.26 (per subject 0.105 / 0.048 / 0.627), with D > 0 in 3/3 subjects.
    - (a) therefore still PASSES through the ceiling clause. The (a) verdict does not depend on the D10 interpretation.

## 2. Metrics: CONFIRMED (independent recompute)

review\indep_n2.py imports nothing from nfharness or edf_reader. It has its own EDF parser, features, z-score and logistic
regression (Newton/IRLS rather than L-BFGS), LOFO tau scan, k-of-n, AUROC (scipy mannwhitneyu), and CP/Garwood (binomtest, gamma
quantiles). It scores with timescoring 0.0.7 directly and also with its own any-overlap scorer (-30/+60 s, merge < 90 s, split > 300 s).

| subject | tau* | TP/N_ref (ts = own) | FP (ts = own) | H (h) | FA/24 h | window AUROC (reviewer / harness) | CP 95% | Garwood 95% /24 h |
|---|---|---|---|---|---|---|---|---|
| chb01 | 0.05 = 0.05 | 4/4 = 4/4 | 5 = 5 | 3.6458 | 32.914 = 32.914 | 0.983525 / 0.983524 | [0.398, 1] = | [10.687, 76.811] = |
| chb03 | 0.05 = 0.05 | 4/4 = 4/4 | 9 = 9 | 8.0000 | 27.000 = 27.000 | 0.989145 / 0.989145 | [0.398, 1] = | [12.346, 51.254] = |
| chb10 | 0.06 = 0.06 | 4/4 = 4/4 | 0 = 0 | 8.0094 | 0.000 = 0.000 | 0.974825 / 0.974824 | [0.398, 1] = | [0, 11.054] = |

- The AUROC differences are about 1e-6 and come from the optimiser tolerance. tau*, TP, FP and N_ref are identical, and the test-window and positive-window counts match (13,121/331, 28,792/212, 28,830/273).
- FA/24 h = 24 FP / H, where H is the summed test-file duration including seizure time (pipeline.py:150, 162). This is correct per N2 §3.
- Unit checks (review\prov_metrics_check.py) on 200 random tied-score sets:
  - `stats.auroc` matches Mann-Whitney exactly (max diff 0).
  - `stats.auprc` matches a brute-force step AP (3e-16).
  - Garwood (k = 0..39) and CP (n <= 14) match the scipy gamma/binomtest forms (<= 2e-15).
  - The exact-formula block bootstrap equals a brute-force resample on the same indices.
- Event scoring and the SzCORE defaults are correct as locked: scoring.py:14 and 34-43, F9 guard, and parameters (30, 60, 0, 300, 90).

## 3. N1(b) FAIL: a DESIGN flaw in the prereg controls, not a CODE bug

The code implements the prereg text faithfully (pipeline.py:34-50; run_n2.py:202-256; D7-D9). The failures are properties of
the controls themselves.

**NC2 criterion 1 (AUROC band) is mis-specified.**
- The circular shift keeps the real seizures in the training set, labelled 0. The model therefore learns "seizure-like = negative", and the test AUROC is biased below 0.5.
- Direct test with the harness's own `run_split` on synthetic features (review\nc_synthetic.py; 3 datasets x 5 replicates):

| condition | NC1 mean AUROC | NC2 mean AUROC | corrected NC2 (true ictal +/-60 s removed from training, then shift) |
|---|---|---|---|
| no signal (delta = 0) | 0.498 | 0.495 | 0.479 |
| signal (seizures shifted +3 SD in every feature) | 0.517 | **0.266** (several replicates 0.000-0.002) | 0.529 |

- With no signal, NC2 is centred at 0.5, which shows the code is correct. With signal, NC2 falls far below 0.5, which reproduces the real chb01 0.116.
- Removing the true ictal windows restores the centre to 0.5. However, the per-replicate spread becomes huge (0.001-1.000), because a random direction still separates the seizure outliers. A fixed [0.35, 0.65] per-subject band is therefore also unsafe for a corrected NC2.

**Criterion 2 (event TP <= p99 of the hypothesis circular-shift null) is mis-specified for both NC1 and NC2.**
- The shift null assumes the hypothesis is independent of the EEG around seizures. A label-shuffled linear model is not independent in that sense: seizures, pre-ictal and post-ictal changes, and artifacts move the features in almost every direction. A random-direction model therefore alarms near seizures more often than chance (either sign of the shift puts extreme scores somewhere in [on-30, off+60)).
- NC2 also keeps peri-ictal states. The shift pushes a block only >= 600 s away, and post-ictal EEG can last longer than that.
- The observed pooled TP (NC1 67 vs p99 65; NC2 20 vs p99 15) is what such a "null" is expected to produce. It is not evidence of a leak.
- The synthetic data (pure additive shift, no peri-ictal state) did not reproduce the criterion-2 failure. This mechanism is therefore an inference, marked **UNVERIFIED** on the real data.

**NC1 tau at the grid floor is a mechanism, and it is verified.**
- D9 builds the NC1 training reference from permuted window labels. That gives scattered 1-s "seizures", which are merged (< 90 s) and extended by -30/+60 s.
- review\prov_metrics_check.py (`nc1_tau_floor`) measures the fraction of training time inside an extended reference event: chb03 0.79, chb10 0.51, chb01 0.31.
- The training FA of an always-alarm hypothesis is:
  - chb03: 0.4/24 h. It passes <= 12 in 100% of draws, so tau* = 0.05 every time.
  - chb10: 20.6/24 h. It passes in 15% of draws.
  - chb01: 60/24 h. It passes in 0% of draws.
- This matches the observed tau* pattern exactly: chb03 10/10 at 0.05; chb10 4/10 at 0.05 (plus one at 0.15); chb01 never.
- So the NC1 null degenerates to "almost always alarm" (chb03 TP 4, FP 90) because an event-level tau rule on i.i.d.-permuted labels is meaningless. This is a design flaw, not a bug.

**C3 (random-alarm F1 <= 0.05) cannot be met at this model's alarm rate** (review\c3_analytic.py and c3_pooled_poisson.py).
- The setup is N_ref = 12 seizures (mean 69 s) in H = 19.66 test hours, i.e. 0.61 seizures per hour.
- Exact enumeration over all circular offsets (every 5 s) of the model's own hypotheses gives:
  - E[TP] = 1.57 and E[FP] = 24.9.
  - F1 = 0.082 (Monte Carlo 0.083; harness 0.081). F1 <= 0.05 in only 19% of draws.
- Closed form: F1 ~ 2E[TP] / (E[TP] + M + N), with E[TP] = sum over seizures of (d + 90 + L)/T.
  - In the high-rate limit, F1 -> 2Nc/(Nc + H) with c = (d + 90 + L)/3600 h. This limit is 0.054 even for 5-s alarms, and 0.084 for 100-s alarms.
  - At the prereg's own "1 alarm/h", F1 = 0.034. The prereg predicted 0.01, an arithmetic slip of about 3x.
- Under the alternative D8 interpretation (the model's 26 merged alarms placed uniformly over all 19.66 h), mean F1 = 0.054, which also exceeds 0.05.
- The absolute bound therefore tests the data density and the 90-s tolerance, not the harness. The model's own pooled F1 is 0.632, far above the random-alarm p95 of 0.16-0.20.

**Criteria that are mis-specified:**
- (b)1 for NC2 (biased by construction when there is signal).
- (b)2 for NC1 and NC2 (wrong null for a feature-driven model).
- (b)3 C3 (an absolute bound that random alarms at this rate and tolerance exceed).
- The tau rule inside NC1 (degenerate reference).
- (b)1 for NC1 held, only just (0.4545).

**Correctly specified controls (input for a new prereg; not written here):**
- (i) NC2' shifts labels only after removing true ictal +/- a peri-ictal margin (for example 30 min) from training.
- (ii) Judge NC AUROC against a simulated or replicate-derived null distribution, not a fixed band. Alternatively, use the honest-vs-null contrast: the honest AUROC and event F1 must exceed the p99 of the NC replicate distribution.
- (iii) Replace (b)2 with "NC pooled TP is not above the honest model's TP" or with an NC-replicate null. Do not use a hypothesis-shift null.
- (iv) Make C3 relative: the model's pooled F1 must exceed the p99 of the random-alarm F1 at matched rate and durations.
- (v) For NC1, fix tau (for example the honest tau*), or select it on a window-level criterion, because an event-level FA rule on scattered labels is degenerate.

## 4. Verdict strings: CONFIRMED (literal)

- **N1 = FAIL.** (b) fails on (b)1-NC2, (b)2-NC1, (b)2-NC2 and (b)3. N1 requires all of (a)-(e) to pass (run_n1.py:192-194).
- **N2 = "not verifiable: code".** This matches the N1 rule "Any FAIL ... every model claim ... is reported as 'not verifiable: code'".
  - No fix round was used. That is correct because no code bug exists. N2 §8 allows bug fixes only, and changes to the criteria need a new prereg.
- **Counterfactual rule verdict** (run_n2.py:45-77, checked by hand against N2 §4):
  - chb01: TP 4, FP 5, in the 4-8 zone: INCONCLUSIVE.
  - chb03: TP 4, FP 9, in the 9-14 zone: INCONCLUSIVE.
  - chb10: TP 4, FP 0: PASS.
  - Overall: 1 PASS and 0 FAIL gives INCONCLUSIVE.
- Reviewer's caution: per N2 §8, the N2 table in RESULTS_N1_N2.md must stay labelled as not a model result. If a later N1' passes, the N2 numbers are already unblinded and are **exploratory**, not confirmatory. The chb01/03/10 test files are burned.

## 5. Provenance and determinism: CONFIRMED

- **Card hashes.** review\prov_metrics_check.py re-serialises each card with its own code: sorted keys, indent 1, runtime and self-hash removed.
  - The recomputed hash equals the stored hash for all 4 cards in both runs (run cf2913d8..., chb01 58ee1fc9..., chb03 feff67ae..., chb10 8a6a2ce3...).
  - Run 1 and run 2 are identical.
- **Code and prereg.** The current SHA-256 of every nfharness/*.py file, edf_reader.py and run_n2.py equals the run-card values. The prereg files match too.
- **Inputs.** All 53 inputs (29 EDF, 21 .seizures, 3 summaries) re-hashed: each equals the manifest, PhysioNet SHA256SUMS and the card, with 0 mismatches.
- **Determinism beyond rerun identity.** A different implementation (Newton instead of L-BFGS) reproduces every decision-relevant number.
- **pytest.** 54/54 pass on re-run.
- **Minor notes:**
  - (i) DEVIATIONS.md now hashes to d0975fa8..., while the run recorded 2767a6e7.... The file was edited after the run, consistent with the appended run log. The pre-run text of D1-D18 cannot be verified by hash; next time, snapshot DEVIATIONS.md into results\ at run start.
  - (ii) run_n1.py:181-182 hard-codes `all_match_manifest_and_SHA256SUMS: True`. This is justified, because verify_inputs raises on any mismatch, and it was independently confirmed here.
  - (iii) The run_n1.py hash change (figure code only) is disclosed.
