# P3b: Threshold-only Bayesian adaptive recalibration with an assumed slope vs staircase (H4b, cycle 2)
Status: PRE-REGISTERED 2026-09-26 by mathematician (cycle 2). Fixed before any P3b code is run. Simulated observers only.
Parent: prereg\P3_psi_vs_staircase_calibration.md (NOT edited). P3's verdict (FAIL: savings >= 0.30 in 2/48 cells) STANDS. P3b is a
re-scope to a different, narrower scenario, not a rescue. Everything not listed below is identical to P3 (48 cells, Weibull 2AFC
observer, stimuli 1..100 uA, staircase B, budgets, 300 runs/cell, N_req, savings, bias rule, sensitivity (a),(b),(d),(e), seed).

## 0. Changes vs original and why (POST-HOC re-scope; evidence is weaker than a blind test)
Written AFTER seeing P3 results (code\RESULTS_P3_P4.md): the 2-parameter psi spent trials on slope; it needed > 150 trials in all
beta = 1.5 cells; the coder's Fisher estimate says ~90 trials for 20% RMS at beta = 1.5 even with known slope.

| # | Change | Why |
|---|---|---|
| C1 | Method A becomes a threshold-only Bayesian adaptive method: 1-D posterior over alpha (200 log-spaced values in [2, 200] uA), slope FIXED at beta_a = 3 for every cell, lam fixed 0.02, gamma 0.5; each trial picks the candidate that minimises expected posterior entropy of alpha. Estimate: theta75 from exp(posterior mean of log alpha) with beta_a. | Realistic scenario = RE-calibration: thresholds drift (~3.5 uA/yr, Greenspon 2026 abstract, PMID 42455900, AUDIT row 26; 31.5 -> 10.4 uA over 1400 days, Hughes 2021, PMID 34320481), so re-measurement recurs, while slope costs ~300 trials to estimate (Kontsevich & Tyler 1999, PMID 10492833, abstract) and is therefore assumed, as in QUEST (Watson & Pelli 1983, PMID 6844102; record opened, no abstract; cited only for the existence of an assumed-slope Bayesian method). |
| C2 | One assumed slope for ALL cells (beta_a = 3, the middle of the grid), so 2/3 of cells are slope-misspecified by 2x. | A clinic would use one population slope. I found no opened source on ICMS psychometric slopes across electrodes, so the spread {1.5, 3, 6} is ASSUMPTION (as in P3). Misspecification is built into the primary test, not left to sensitivity. |
| C3 | Added arm A-oracle (beta_a = true beta): reported, no verdict. Sensitivity (c) replaced by beta_a in {2, 4.5}. | Separates the cost of slope misspecification from the method. |
| C4 | CONTROL arm = the same 1-D estimator with random placement (as in P3). | Same logic as P3. |

## 1. Hypothesis H4b and decision rule (thresholds unchanged from P3)
PASS: savings >= 0.30 vs the 3-down-1-up staircase in >= 36/48 cells AND |mean e_A| at N = 60 <= ln 1.10 in every cell with
lam <= 0.05. FAIL otherwise. Errors, targets (theta75 for A, x79.4 for the staircase) and N_req as in P3.

## 2. Predictions (before any P3b code runs)
- Oracle asymptotics (my Fisher estimate: best-placement information per trial ~0.29*beta^2 in ln-threshold units, times ~1.5
  practical inefficiency): N_req ~ 70 (beta 1.5), ~17 (beta 3), ~10 (beta 6, floor).
- Primary (beta_a = 3): savings >= 0.30 in ~28/48 cells (plausible 22-36): most beta = 3 cells (~14/16), about 10/16 beta = 6 cells
  (the staircase is already efficient there), ~4/16 beta = 1.5 cells.
- Bias: max |mean e_A(60)| at lam <= 0.05 ~ 0.12 (> ln 1.10 = 0.095), coming from beta = 1.5 cells, where the assumed steeper slope
  makes the posterior overconfident.
- Predicted verdict: FAIL (P(PASS) ~ 0.25). Predicted minutes per 64-electrode array (4 s/trial, median N_req): A ~ 110 min vs
  staircase ~ 285 min (P3 value), i.e. a useful time saving even if the strict cell-count criterion fails; reported, not a criterion.

## 3. Abandonment
If the random-placement CONTROL is within 10% of A's N_req in >= 75% of cells, the benefit is Bayesian estimation, not placement
(report so). If A-oracle itself reaches savings >= 0.30 in < 24/48 cells, stop this line: even with a correct slope, threshold-only
adaptive placement does not beat a staircase enough in this grid; no further re-scopes of H4 in cycle 2.

## 4. Null / control
Staircase is the null; random-placement CONTROL; A-oracle as an upper bound; self-tests from P3 (observer parameterisation, entropy
closed form vs brute force) re-run on the 1-D posterior.

## 5. Outputs and budget
code\p3b_threshold_psi.py (may reuse code\p3_psi_calibration.py), code\results\p3b_threshold_psi.json,
code\figures\p3b_savings_map.png/.svg. The 1-D posterior (200 values) is cheaper than P3's 400-point grid; P3 main ran in 31 s. < 10 min.
