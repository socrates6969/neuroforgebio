# Results P3 and P4 (coder-verifier B, 2026-09-26)
Simulation and theory only. The preregs were fixed and were not edited. Seed 20260926. Python venv, numpy/scipy/matplotlib only.
Interpretations and deviations: code\DEVIATIONS.md, sections P3 and P4.

## P3 (H4): psi vs 3-down-1-up staircase. VERDICT: FAIL
- Rule: savings >= 0.30 in >= 36/48 cells AND |mean e_PSI| at N=60 <= ln 1.10 in every lam <= 0.05 cell.
- Savings >= 0.30 in **2/48 cells** (95% bootstrap CI 1-3). Both cells are theta75 = 10, lam = 0.05, beta 3 and 6 (0.38, 0.42).
  Psi needs more trials than the staircase in most cells (savings -0.04 to -2.4). Psi never reaches RMSE <= ln 1.2 within 150 trials in 19/48 cells:
  all 12 beta = 1.5 cells, plus 7 lam = 0.10 cells. The staircase fails to reach it in 5 cells.
- Bias criterion met: max |mean e_PSI(60)| = 0.086 (< 0.0953) over lam <= 0.05. Psi is biased low by about 7% in most cells. Three cells have a 95% CI touching -0.10.
  In the lam = 0.10 cells the bias fails in 5/12, which is not more than half, so the lapse-grid follow-up was NOT triggered.
- Control (random placement plus the Bayesian estimator) comes within 10% of psi's N_req in 19/48 cells (< 36), so the abandonment rule is NOT triggered.
  Adaptive placement does help psi relative to random placement (control N_req > 150 in 27/48 cells).
- Minutes per 64-electrode array at 4 s/trial (median N_req over cells, with >150 counted as 150): psi 307 min, staircase 285 min, control 640 min.
  Finite range: psi 140-543 min, staircase 43-637 min.
- Sensitivity (all FAIL; cells with savings >= 0.30 [CI]; bias failures at lam <= 0.05):
  (a) logistic observer 2 [2-4], 0; (b) drift +20% 1 [0-2], 18; drift -20% 2 [2-4], 1; (c) psi lam = 0.05: 7 [6-10], 0;
  (d) 2-down-1-up vs x70.7: 8 [5-14], 0; (e) staircase start 40 uA: 0 [0-1], 0.
- Interpretation (not part of the verdict): with a 2-parameter psi (alpha and beta both unknown, entropy over both), trials are spent on
  slope. At beta = 1.5 a 20% RMS threshold needs roughly 90 trials even with a known slope (Fisher-information estimate, ESTIMATE).
  The K&T "< 30 trials" figure does not carry over to this grid. H4 as pre-registered is falsified. Any re-scope (for example a
  threshold-only psi with a fixed slope) would be a NEW prereg, not a rescue of this one.
- Self-tests passed: the observer parameterisation is exact (1e-16); the logistic slope match is within 1e-8; the closed-form entropy matches brute force (9e-15);
  psi recovers theta75 = 20 with 600 trials (estimate/true 0.997, RMSE 0.059 log units); the staircase converges to x79.4 (mean log error -0.033 at 1000 trials).
- Figures: code\figures\p3_savings_map.png/.svg (cell map), code\figures\p3_rmse_curves.png/.svg. Data: code\results\p3_psi_staircase.json.
- Runtime 122 s (main 31 s). Memory well under 1 GB.

## P4 (H2): pooling capacity. VERDICTS: A PASS (non-blind, disclosed), B PASS, C PASS
- A: at w = 0.162 with kappa = 0, the predicted N(4) is 20.23, inside [15.6, 23.4]. With kappa = 1 it is 11.0 (outside). kappa_hat = 0.079 (inside [0, 0.3]).
  Model K (constant JND) predicts N(4) = 52.3, 54.4 and 61.8 for Q_thr 20, 24 and 35 uA, all outside the band. Weber pooling is preferred; all 4 checks pass.
  Across the w values: kappa_hat = 0.261 / 0.079 / -0.244 / -0.456 and N(4 | kappa=0) = 22.5 / 20.2 / 17.8 / 16.8 for w = 0.128 / 0.162 / 0.225 / 0.268.
  At w >= 0.225 the data would need kappa < 0 (super-summation). Part A therefore depends on the biomimetic w = 0.162.
- B: M* (kappa = 0) = 81 / 240 / 1648 / 5806 electrodes, all > 64. C(64) - C(1) = 1.50 bits/symbol (< 2) at w = 0.162, kappa = 0.
  C(1) = 1.81 bits/symbol, which is well below log2 N(1) = 3.46. C(4) = 2.49, C(64) = 3.31, C(1024) = 3.82.
  Bits/s at C(64) are 33.1 / 16.5 / 6.6 / 3.3 for T_sym = 0.1 / 0.2 / 0.5 / 1 s (JND independent of duration: ASSUMPTION).
  Control (independent spatial channels, independence ASSUMED): 64 electrodes as K = 1, 2, 4, 8, 16 groups give 3.3, 6.3, 11.8, 22.0, 39.9 bits/symbol
  (w = 0.162, kappa = 0). Spatial coding beats pooling by a factor of about 12 at K = 16.
- C: Monte Carlo 2AFC (20000 trials per point) gives integer level counts of 10 / 20 / 29 against analytic 11.0 / 20.2 / 29.5 for M = 1 / 4 / 16.
  Relative errors are -9.1% / -1.2% / -1.6%, all within 10%. Fractional counts are 11.0 / 20.3 / 29.6 (< 0.6%). The M = 1 margin comes from integer flooring.
  Measured w is 0.159-0.166 (true 0.162). NOTE: C is close to a tautology, because the noise s is defined from the same JND convention. It checks the code and the formula, not biology.
- Blahut-Arimoto sanity bounds pass: range/s = 30 gives C = 3.04, inside [2.66, 3.91]; range/s = 60 gives C = 3.95, inside [3.66, 4.91]. A BSC(0.1) check gives 0.531 (exact).
- Sensitivity:
  - N(1) = 7: A FAIL (kappa_hat = -0.35), B PASS (dC 1.80).
  - N(1) = 14: A FAIL (kappa_hat = 0.40), B FAIL (M* = 56.5 at w = 0.128).
  - Q_max = 80 uA: A FAIL (kappa_hat = -0.08), B PASS.
  - Weber violation exponent -0.2: A FAIL (kappa_hat = 0.40; the no-summation N(4) is 14.2), B FAIL (M* 19-131; dC 2.02).
  - Weber violation exponent +0.2: A FAIL (kappa_hat = -0.09), B PASS (dC 1.12).
  - In every variant the kappa = 0 prediction N(4) stays inside the +/-20% band. The failures come only from the narrow kappa_hat window.
  - Frequency channel (20-50 Hz, w = 0.15; 6.6 levels) adds 1.31 bits/symbol. Pooled 64 plus frequency gives 4.61 bits/symbol.
- Conclusion: the pre-registered decisions pass. Part A is a non-blind consistency check and is fragile to N(1), Q_max and Weber-law
  assumptions. B's "pooling alone cannot reach natural resolution on 64 electrodes" holds except at N(1) = 14 with w = 0.128, or if w falls with Q.
- Figures: code\figures\p4_capacity_vs_M.png/.svg. Data: code\results\p4_pooling_capacity.json. Runtime 279 s (mostly BA).

## Deviations (summary; details in DEVIATIONS.md)
P3: the staircase keeps an unrounded internal level (the presented stimulus is rounded) to avoid a 1 uA lock. Drift error is measured against the current threshold.
The control "within 10%" rule is one-sided. Script file names follow the task; outputs follow the prereg.
P4: the BA stopping rule adds a stall criterion (1e-9 bits/iteration) to the 1e-6-bit gap criterion. The certified gap is < 1e-4 bits and stored.
Q_max-80 and Weber-violation anchoring choices are documented. The MC uses integer step counts.
