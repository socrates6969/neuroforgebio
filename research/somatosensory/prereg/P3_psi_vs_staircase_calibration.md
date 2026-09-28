# P3: Bayesian adaptive (psi) vs staircase for per-electrode detection-threshold calibration (H4)
Status: PRE-REGISTERED 2026-09-26 by mathematician. Simulated observers only. The 1-100 uA stimulus range is QUOTED
(Greenspon 2025 used 100 uA as the maximum in level counts) as the simulation domain. It is not a protocol.

## 1. Hypothesis
Target: 2AFC detection threshold (75%-correct point, theta75) to within 20% RMS error. The psi method
(Kontsevich & Tyler 1999, PMID 10492833) needs >= 30% fewer trials than a 3-down-1-up staircase in >= 75% of the
48 observer cells. Its |bias| stays <= 10% in every cell with lapse <= 5%.

## 2. Simulated observer
p(x) = 0.5 + (0.5 - lam) * (1 - exp(-(x/alpha)^beta)) (Weibull 2AFC), x in uA.
Cells (4 x 3 x 4 = 48):
- theta75 in {10, 20, 31.5, 50} uA (10.4 and 31.5: human median thresholds at day 1500 and day 100, Hughes 2021 PMID 34320481;
  others ASSUMPTION). alpha is solved from theta75 given beta and lam. (If lam makes 0.75 unreachable, the cell is invalid; it cannot happen for lam <= 0.1.)
- beta in {1.5, 3, 6} [ASSUMPTION]
- lam in {0, 0.02, 0.05, 0.10} [ASSUMPTION]
Stimuli: integers 1..100 uA (cap).

## 3. Methods compared
A. PSI. Parameter grid: alpha with 40 log-spaced values in [2, 200] uA; beta with 10 log-spaced values in [0.7, 10];
   lam fixed at 0.02 in the model (deliberately misspecified for other cells); gamma = 0.5. Prior uniform on the grid in (log alpha, log beta).
   Stimulus candidates: 40 log-spaced values in [2, 100], rounded to unique integers. Each trial picks the candidate that
   minimises the expected posterior entropy over (alpha, beta). Estimate: theta75_hat = exp(posterior mean of log theta75(alpha, beta)).
B. STAIRCASE (transformed up-down, as reviewed by Leek 2001, PMID 11800457): 3-down-1-up; start at 80 uA; multiplicative steps of
   factor 1.585 (4 dB) until the 2nd reversal, then 1.26 (2 dB); clip to [1, 100] and round to an integer. Estimate: geometric mean of
   the reversal amplitudes after the 2nd reversal (if < 2 such reversals, use the last stimulus). It converges on x79.4.
C. CONTROL: the psi posterior/estimator with stimuli drawn uniformly at random from the psi candidate set (separates
   adaptive placement from Bayesian estimation).
Trial budgets evaluated: N in {10, 15, 20, 30, 40, 50, 60, 80, 100, 120, 150}. 300 simulated runs per cell and method
(vectorise over runs). Seed 20260926.

## 4. Metric and decision rule
- Error for PSI and CONTROL: e = ln(theta75_hat / theta75_true). STAIRCASE: e = ln(x79_hat / x79.4_true), each method judged
  against its own convergence target. Also report staircase error against theta75 for completeness.
- RMSE(N) = sqrt(mean e^2); N_req = the smallest N with RMSE <= ln(1.2) (linear interpolation; ">150" if never).
- Savings(cell) = 1 - N_req(PSI) / N_req(STAIR); a cell with ">150" for the staircase and a finite PSI counts as savings >= 0.30.
  A cell with ">150" for PSI counts as a failure.
- PASS: savings >= 0.30 in >= 36 of 48 cells AND |mean e_PSI| at N = 60 <= ln(1.10) in all cells with lam <= 0.05.
- FAIL otherwise. Also report the cell map and minutes per 64-electrode array at 4 s/trial [ASSUMPTION] for both methods.

## 5. Why the result is not guaranteed
- The psi model assumes lam = 0.02 and a Weibull shape. Lapses of 5-10% and the misspecified-shape sensitivity run below can bias
  it, while staircases are nonparametric.
- The 100 uA cap truncates the psychometric function for theta75 = 50 uA with shallow slopes. Both methods then lose
  information, and psi can place many trials at the cap.
- For steep slopes (beta = 6) a staircase is already efficient, so savings could be < 30%.
- Kontsevich & Tyler's "< 30 trials" figure is for vision tasks with different parameters. It does not settle this cell grid.

## 6. Sensitivity
(a) the true observer is a logistic in log x instead of Weibull (same theta75 and a matched slope at theta75);
(b) within-run drift: theta75 changes linearly by +20% and -20% over 150 trials [ASSUMPTION; slow drift over days is documented by Hughes 2021];
(c) psi lam fixed at 0.05; (d) staircase 2-down-1-up (compare against x70.7); (e) staircase start at 40 uA.
Report the PASS/FAIL outcome under each variant.

## 7. Abandonment criterion
If the CONTROL (random placement) is within 10% of PSI's N_req in >= 75% of cells, the benefit comes from Bayesian estimation,
not adaptive placement. Report that and re-scope H4 to "Bayesian estimator on any schedule". If PSI fails bias in more than
half of the lam = 0.10 cells, add lapse as a free grid parameter (4 values 0-0.1) in one follow-up. No other tuning.

## 8. Outputs and budget
code\p3_psi_staircase.py, code\results\p3_psi_staircase.json, code\figures\p3_savings_map.png.
Cost: per trial, a (runs x 400 params x 40 stimuli) likelihood/entropy evaluation = 4.8e6 ops; 150 trials x 48 cells gives ~ 3.5e10
flops. That fits in < 10 min with float32. If it exceeds 10 min, cut the runs to 200 and document the change.
