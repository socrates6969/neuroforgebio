# Results P1 and P2 (coder-verifier A, 2026-09-26)
Simulation only. Seed 20260926. Python venv (numpy, scipy, matplotlib). Interpretations/deviations: code\DEVIATIONS.md.
Self-tests: P1 10/10 PASS (results\p1_selftest.json); P2 11/11 PASS (results\p2_selftest.json).

## P1: grip latency budget (H3, H3b)  -> H3 ABANDONED (G0 fails twice); H3b FAIL
Main run (N = 4000 per condition, SM optimised per condition, 95% bootstrap CI, 1000 resamples):
| condition | F* | 95% CI | SM_opt |
|---|---|---|---|
| NOFB | 0.740 | 0.725-0.751 | 0.3 |
| NAT (74 ms, p .95) | 0.614 | 0.598-0.627 | 0.2 |
| VIS 200 ms | 0.745 | 0.731-0.758 | 0.3 |
| ART +100 ms, p .95 | 0.762 | 0.748-0.775 | 0.3 |
| shuffled feedback | 0.733 | 0.719-0.746 | 0.3 |
- Validity gate G0: F*_NAT/F*_NOFB = 0.83 (it must be <= 0.5), so G0 FAILS. G0 fails in 0/1000 bootstrap resamples, i.e. it never holds.
  The pre-specified redesign (pulse amplitude U(0.4,1.0)*m*g, c ~ U(1.3,2.0)) gives F*_NAT 0.902 and F*_NOFB 0.948, so G0 fails again.
  Per section 6, H3 is ABANDONED: "open-loop margin suffices; latency question not addressable with this task".
  In practice, the failure rate is high under every strategy, and feedback helps little.
- Reported anyway: delta* = 28.2 ms (CI 23.8-30.8). R falls from 1.44 at delta = -20 to about 0 at +50 ms and is negative beyond +75 ms.
  In this model, late feedback only lowers mu_hat (grip goes up), which adds crush failures.
- H3b: F*_ART(+100) / F*_VIS(200) = 1.023 (CI 1.013-1.034). The threshold is <= 0.8, so H3b FAILS.
- Controls: shuffled feedback R = 0.06 < 0.5, PASS. ZERO-PERTURBATION SANITY CHECK FAILS: with K = 0, F*_NOFB = 0.498 and
  F*_NAT = 0.089 (both must be <= 0.01). The cause is structural and was checked analytically: open loop needs 0.75/mu <= 1+SM <= 0.75c/mu,
  a window of width c (at most 2.5x), while mu spans 4x (0.3-1.2). Feedback can only lower mu_hat, so trials with high mu crush.
  The prereg model therefore fails its own sanity check. The friction prior/range and the one-sided mu update must be redesigned
  (this is a mathematician decision) before H3 can be tested.
- Sensitivity (N = 1000, 19 configurations): delta* in [50,150] in 0/19 (robustness criterion >= 70% NOT met). delta* ranges from 6 to 46 ms.
  G0 holds only for c ~ U(2,4) (delta* 46 ms). The Smith-predictor variant gives delta* 25 ms.
- Runtime: main 194 s, sensitivity 186 s, < 1 GB.
- Figures: figures\p1_R_vs_delta.png/.svg, figures\p1_sensitivity.png/.svg. JSON: results\p1_grip_latency.json,
  results\p1_grip_latency_sensitivity.json.

## P2: biomimetic vs linear per unit charge (H1)  -> INCONCLUSIVE (the ratio metric is degenerate)
- Normalisation: charge matching is not possible at alpha' = 0.25. The pre-registered rule raised alpha' to 0.80, giving beta' = 3.76.
  Peak-matched: alpha' 0.25, beta' 0.92, charge ratio 0.625 (inside the [0.5,0.9] realism band; Greenspon observed 0.69), not flagged.
- Primary (charge-matched, tau_ad = inf): d'_bio = 0.542, d'_lin = 0.017, so the ratio is 31.9 with a 95% CI of -212 to 327. Because the CI contains 1.3,
  the result is INCONCLUSIVE by the prereg rule. RMSE ratio 1.022 (CI 1.020-1.024) <= 1.5, which meets the RMSE criterion.
- Why: the calibrated noise gives a per-10-ms-sample sd of about 144 model-uA (sqrt(n_T) = 10 times the train-level noise), while a linear
  +/-20% step moves the amplitude by about 7.5 uA. Linear AUC = 0.50, so the ratio's denominator is about 0. POST-HOC (descriptive only):
  d'_bio 0.54 (CI 0.50-0.58), d'_lin 0.02 (CI -0.01 to 0.05), difference 0.52 (CI 0.48-0.56). The biomimetic code is clearly
  more detectable, but under this noise model neither code detects steps well (d' < 1).
- Increases vs decreases (bio / lin): d' 0.66 / 0.19 for increases, 0.43 / -0.04 for decreases.
- tau_ad sweep (exploratory): d'_bio rises with fast adaptation (2.04 at 0.1 s, 0.82 at 1 s, 0.54 at inf). d'_lin stays about 0 at every tau.
- Controls: noise-free AUC 0.9999 (bio) and 0.999 (lin), PASS. Label shuffle AUC 0.49, PASS. The beta' = 0 control converges to alpha' = 1.0,
  which is identical to linear (ratio 1.0), PASS. Abandonment is not triggered (only linear is at the floor, not both).
- Exploratory alpha' grid: alpha' 0.85 gives ratio 15.6 and alpha' 0.90 gives 8.3. Again undefined-ratio territory; the RMSE ratio is about 1.01-1.02.
- Sensitivity (N = 2000, 16 configurations): d'_lin is between -0.03 and 0 in every configuration, so the ratio is undefined everywhere. d'_bio ranges from 0.16
  (rise 5-20 ms) to 1.06 (rise 80-200 ms); RMSE ratio 1.01-1.04. D and T_train have no or negligible effect, as expected. alpha' 0.1/0.5 are both raised to 0.80 by the matching rule.
- Caveat (post-hoc): Weber noise makes the variance itself a cue. Some of d'_bio may come from variance increases (DEVIATIONS.md).
- Runtime: main 290 s, sensitivity 26 s, post-hoc about 60 s, < 1 GB.
- Figures: figures\p2_dprime_vs_tau.png/.svg, figures\p2_sensitivity.png/.svg. JSON: results\p2_biomimetic.json,
  results\p2_biomimetic_sensitivity.json, results\p2_biomimetic_posthoc.json.

## For the mathematician/queen
P1 needs a redesign because its own sanity control fails, so it is not evidence against H3. P2 should replace the d' ratio with a
difference, or with a detector integrated at the 1-s train level. Any such revision needs a new prereg.
