# Results P2c: biomimetic vs linear encoding, variance-controlled noise, MEASURED adaptation (coder-verifier A, cycle 3, 2026-09-26)
Simulation only, in model units (not stimulation settings). Seed 20260926. Script: code\p2c_biomimetic_adaptation.py (imports P2/P2b
read-only; no older file changed). Runs: main 137 s, sens 135 s, < 1 GB. Interpretations: DEVIATIONS.md section P2c (written before any
result) + P2c POST-HOC notes. Self-tests 17/17 PASS (results\p2c_selftest.json; includes all P2/P2b helper tests, exact-integrator vs
Euler, periodic fixed point, A0 parameter recovery, R0 path bit-identical to p2b.arm_eval, adapted-calibration MC JND, decision rule).
Results: results\p2c_biomimetic_adapt.json, results\p2c_biomimetic_adapt_sens.json. Figures (model, not settings):
figures\p2c_delta_by_arm.png/.svg, figures\p2c_adaptation_fit.png/.svg.

## Verdict
- PRIMARY (perceptual gain): FORMAL = ABANDONED (both encoders at the AUC floor < 0.55 in FV and HS, and again on the U(0.3,0.6) rerun).
  Decision rule alone = FAIL (FV and HS both FAIL; not variance-control dependent). Robust: same call (FAIL) in 10/10 rows -> VERIFIED.
- SECONDARY (neuronal, tau_n 0.04 s, k_ad 0.5): FAIL. Grid: same call 5/9 -> NOT VERIFIED (PASS in all three k_ad = 0.9 cells).
- Prereg prediction: primary FAIL, P(PASS) ~0.05 -> confirmed (floor/ABANDON not predicted). Secondary FAIL/INCONCLUSIVE -> confirmed at
  the primary cell; k 0.9 prediction (Delta ~0.25) missed badly (observed 1.1-1.9).

## A0 gate (adaptation fit to DIGITISED Hughes 2022 Fig 3B, 42 points): PASS
- Refit: tau_a 13.2 s on-time (approx. 95% CI 11.5-15.1), tau_r 108 s (92-127), RMSE 0.047, end of adaptation 0.439 (0.435 +/- 0.10).
  Prediction 14.6 / 120 s (+/-10%): both just inside (-9.8%, -10.0%). The difference is the train-time pairing (DEVIATIONS P2c item 2).
- Known misfits (as the prereg stated): end of recovery 0.895 vs quoted 0.726; continuous 100 Hz g = 0.69 at 5 s (quoted "unchanged"),
  0.36 at 15 s (quoted 0.64 +/- 0.36). Out of sample (Fig 2B bursts): model 0.51 at 20 s and 0.39 at 30 s for all burst lengths vs
  digitised 0.64/0.48/0.46 and 0.52/0.34/0.01 (100/200/500 ms): the model cannot produce burst-length dependence or extinction.
- g_ss (contact samples): bio 0.2726, lin 0.2730 (predicted ~0.27, within 0.03: confirmed). Drift over a session -0.003 (steady state).

## R0 (g = 1): PASS, exact reproduction of P2b (deviation 0.0000): FV d' 0.129 / 0.017, HS 0.077 / 0.022.

## Primary perceptual (charge-matched, alpha' 0.80, beta' 3.76, p = 1, G = 3 s; N = 4000; paired 95% CI, 1000 resamples)
| arm | d'_bio (CI) | d'_lin (CI) | Delta (CI) | best AUC bio / lin (D) | RMSE ratio | label |
|---|---|---|---|---|---|---|
| FV | 0.098 (0.062-0.135) | 0.015 (-0.016-0.050) | 0.083 (0.038-0.110) | 0.528 D1 / 0.504 D2 | 1.025 | FAIL |
| HS | 0.011 (-0.015-0.048) | 0.011 (-0.017-0.047) | 0.000 (-0.001-0.008) | 0.503 D2 / 0.503 D2 | 1.003 | FAIL |
- Increases / decreases Delta: FV 0.076 / 0.026; HS 0.005 / 0.000.
- Rerun, steps U(0.3,0.6): FV 0.061 (0.015-0.106), HS -0.001 (-0.002-0.008); still at floor (best AUC 0.526 / 0.512).
- Predictions: Delta_HS ~0.03 (-0.02-0.10) -> observed 0.000, inside; Delta_FV ~0.07 (0.0-0.20) -> 0.083, confirmed.

## Robustness (N = 1000 each, all FAIL; Delta FV / HS; g_ss)
tau_a 7: 0.108 / 0.004 (0.16); tau_a 30: 0.147 / 0.022 (0.46); tau_r 60: 0.144 / 0.017 (0.40); tau_r 600: 0.062 / 0.001 (0.06);
p 0.5: 0.131 / 0.009; p 2: 0.122 / 0.007 (g_ss bio 0.248 vs lin 0.254); G 1: 0.117 / 0.005; G 10: 0.147 / 0.021;
JND calibrated adapted: 0.154 / 0.098. Max CI upper bound anywhere 0.18 < 0.30. p = 2 did not lower Delta vs p = 1 at N = 1000
(prediction "p = 2 lowers Delta" not supported; both far below 0.30 as predicted).

## Secondary neuronal (P2 subtractive depression, JND recalibrated per cell)
- Primary cell (0.04 s, 0.5; N = 4000): FV 0.241 (0.195-0.270), HS 0.185 (0.136-0.213); RMSE 1.05/1.04 -> FAIL. Predicted 0.12 (0.03-0.30).
- Grid (Delta FV / HS, call): k 0.25: 0.18/0.11, 0.21/0.14, 0.22/0.15 FAIL; k 0.5: 0.23/0.16 FAIL, [primary] FAIL, 0.36/0.27 INCONCLUSIVE
  (tau_n 0.15, variance-control dependent); k 0.9: 1.18/1.08, 1.86/1.64, 1.68/1.11 PASS (d'_lin <= 0.08). 5/9 same call: NOT VERIFIED.
- Required statement (prereg section 5, applies to the k 0.9 cells): any biomimetic benefit depends on unmeasured sub-second neuronal
  depression in humans; this is NOT a design recommendation. Requires IRB/FDA-approved clinical study to test.
- Combined perceptual x neuronal (descriptive): FV 0.137 (0.091-0.162), HS 0.004 (0.000-0.018).

## Controls
- Identical-encoder null: Delta 0, CI [0, 0] both arms: PASS. Variance-only probe d'_bio: FV 0.043, HS 0.010 (< 0.05): PASS (FV close).
- beta' = 0: alpha' -> 1.0 (= linear), Delta 0: PASS. Noise-free: best AUC bio 1.000, lin 1.000: PASS. Label shuffle AUC 0.492: PASS.
- Power check (HS, sigma_h/4, g = 1): Delta 0.80 (0.75-0.85): the pipeline CAN reach 0.30 when noise is 4x lower.
- Gain-scaling (HS): FAILED. Observed 0.00002 vs g_ss x Delta(g=1) = 0.015. Explained post hoc: |.| detectors are ~quadratic in a small
  mean signal (D1-only Delta 0.0053 = g_ss^2 x 0.074), and max(D1, D2) then picks the shared noise-driven D2, so Delta collapses to 0.
- Peak-matched (descriptive, charge 0.63x): g_ss bio 0.374 vs lin 0.273 (prediction +0.05-0.1: larger, +0.10); Delta FV 0.046, HS -0.001
  ("charge-saving effect", not H1).

## Caveat
Even the PASS cells say "better per unit charge" within this noise model. Primary d' < 0.1: neither code detects 10-30 % steps within 200 ms
at the published JND once measured human adaptation is applied. The episode bootstrap ignores the dependence between episodes via g (as prereg).
