# Results P3b and P5 (coder-verifier B, cycle 2, 2026-09-26)
Simulation and theory only. The preregs were fixed and not edited. Seed 20260926. Venv python, numpy/scipy/matplotlib.
The cycle-1 scripts (p3_psi_calibration.py, p4_pooling_capacity.py) were imported and not modified.
Interpretations and deviations: code\DEVIATIONS.md, sections P3b and P5 (items 1-14).

## P3b (H4b): threshold-only Bayesian adaptive (assumed slope beta_a = 3) vs 3-down-1-up staircase. VERDICT: FAIL
- Rule: savings >= 0.30 in >= 36/48 cells AND |mean e_A(60)| <= ln 1.10 (0.0953) in every cell with lam <= 0.05.
- Savings >= 0.30 in **5/48 cells** (95% bootstrap CI 3-7). All 5 are beta = 3 or 6 cells with lam <= 0.02 and theta75 <= 31.5.
  - beta = 1.5: 0/16. A never reaches RMSE <= ln 1.2 within 150 trials in any of these cells (the staircase needs 84-149).
  - beta = 3: 4/16. Median N_req is 37.5 for A and 47.1 for the staircase.
  - beta = 6: 1/16. Median N_req is 30.7 for A and 34.6 for the staircase.
  - A is > 150 trials in 24/48 cells: all 16 beta = 1.5 cells and all 12 lam = 0.10 cells.
- The bias criterion FAILS in 20 of the 36 cells with lam <= 0.05. Max |mean e_A(60)| = 0.256 (theta75 10, beta 1.5, lam 0.05; CI 0.222-0.289).
  The sign follows the slope misspecification:
  - beta = 1.5: +15% to +26% (every cell).
  - beta = 6, lam <= 0.02: -10% to -13%.
  - beta = 3 cells stay within +/-8%.
  - lam = 0.10: 11/12 cells fail (reported only; see DEVIATIONS P3b-7).
- A-oracle (beta_a = true beta; no verdict): 9/48 cells (CI 7-13). Median N_req is 88.6 / 43.6 / 27.1 at beta 1.5 / 3 / 6. All lam <= 0.05 biases are
  <= 0.113 (1 cell > 0.0953).
- **Abandonment rule triggered.** A-oracle reaches savings >= 0.30 in 9 < 24 cells. So by the prereg, threshold-only adaptive placement
  does not beat the staircase enough in this grid even with the correct slope: **stop this line, no further H4 re-scopes in cycle 2.**
  The control rule is NOT triggered: random placement comes within 10% of A in 24/48 cells, fewer than 36.
- Minutes per 64-electrode array (4 s/trial, median N_req with > 150 counted as 150, so a lower bound):
  | arm | minutes |
  |---|---|
  | A | 533 |
  | staircase | 285 (identical to P3) |
  | A-oracle | 290 |
  | control | 640 |

  The predicted 110 vs 285 min time saving does NOT appear.
- Sensitivity (all FAIL; cells >= 0.30 [CI]; bias failures at lam <= 0.05):
  | variant | cells >= 0.30 [CI] | bias failures |
  |---|---|---|
  | (a) logistic observer | 3 [1-5] | 18 |
  | (b) drift +20% | 6 [4-12] | 22 |
  | (b) drift -20% | 4 [2-7] | 15 |
  | (c) beta_a = 2 | 0 [0-3] | 28 |
  | (c) beta_a = 4.5 | 5 [4-7] | 16 |
  | (d) 2-down-1-up vs x70.7 | 16 [13-18] | 20 |
  | (e) staircase start 40 uA | 4 [2-6] | 20 |
- Prediction check (mathematician):
  | quantity | predicted | observed |
  |---|---|---|
  | cells | 28/48 | 5 |
  | max bias | 0.12 | 0.256 |
  | oracle N_req at beta 1.5 / 3 / 6 | 70 / 17 / 10 | 89 / 44 / 27 |

  The Fisher-based estimate is about 1.3-2.7x optimistic. The verdict FAIL was predicted.
- Self-tests passed:
  - observer 1e-16;
  - 1-D closed-form entropy vs brute force 4e-15;
  - estimator identity exp(E ln alpha)*u^(1/beta_a) 7e-16;
  - model-matched recovery at 600 trials: ratio 1.0005, RMSE 0.029;
  - the staircase arm is bit-identical to P3's (max N_req difference 0.0, asserted against results\p3_psi_staircase.json).
  - Diagnostic: with beta 1.5 true and 3 assumed, the bias is +0.218 even at 600 trials, so it is asymptotic and not a small-N effect.
- Files: results\p3b_threshold_psi.json, figures\p3b_savings_map.png/.svg, figures\p3b_rmse_curves.png/.svg. Runtime 103 s.

## P5 (H7): effectively independent spatial channels of 64 S1 electrodes. VERDICT: INCONCLUSIVE (not robust)
- Gates:
  - V2 holds: sigma_c fitted to 6.54 mm (mean r = 0.6900 on 2000 calibration draws; 0.685 on the 500 main draws).
  - V1 holds: median union U is 44.3 cm2 (2.5-97.5%: 33.9-55.7), inside [6, 66]. It is 38.9 at D_arr 3 mm and 51.6 at 8 mm, so no abandonment.
- Primary (60 uA, D_arr 5 mm, 500 draws): N_eff median **14.2** (bootstrap CI 14.0-14.4).
  - 2.5th percentile **11.6** (CI 11.1-11.9) < 16, so not PASS.
  - 97.5th percentile **17.5** >= 16, so not FAIL. The rule therefore gives INCONCLUSIVE.
  - Packing number median 10 (2.5-97.5%: 7-13).
- Robustness (36 configurations): 8 PASS, 18 FAIL, 10 INCONCLUSIVE. No classification holds in >= 70%, so the result is **not robust**.
  - N_eff falls with amplitude: median 20.3 / 14.2 / 11.1 / 9.1 at 40 / 60 / 80 / 100 uA.
  - N_eff rises with sigma_c: 10.9 at x0.5, 21.9 at x2.
  - N_eff rises with D_arr: 11.4 / 14.2 / 16.0 at 3 / 5 / 8 mm.
  - With sigma_c re-fitted per D_arr: D 3 mm gives sigma_c 4.22 and N_eff 9.5 (FAIL). D 8 mm gives sigma_c 10.5 and N_eff 22.2 (2.5th percentile 17.7, PASS).
  - The unreported array separation and the centroid-scatter model therefore decide the verdict.
- Controls:
  | control | result | status |
  |---|---|---|
  | identical PF | N_eff = 1 within 1e-9 | PASS |
  | no-somatotopy null (uniform on the 165 cm2 palm) | median 45.4 > 14.2 (somatotopic lower in 100% of draws) | PASS |
  | area shuffle | median change -0.5% | PASS |
  | lens closed form vs 1500^2 raster | max rel. error 4.7e-5 | PASS |
  | tiny PF | median 64.0 but min 62.1 (2.8% of draws < 63) | **FAILED** |

  Post-hoc diagnosis of the tiny-PF failure (DEVIATIONS P5-13): with sigma_c = 0 it gives exactly 64. The failure is caused by random centroid
  coincidences in the pre-registered scatter model, not by the overlap code.
- Cortical current-spread N_eff (D_arr 5 mm):
  - Stoney power law: 64.0 / 63.9 / 62.9 / 60.0 / 55.4 at 20 / 40 / 60 / 80 / 100 uA.
  - Tehovnik at 60 uA: 30.3 (K = 100), 63.9 (K = 1000), 64.0 (K = 4000 uA/mm2).
  - The bottleneck is perceptual (PF size x gain), not current spread, as predicted.
- Capacity consequence (P4 channel, w = 0.162, kappa = 0; an upper bound because residual overlap is ignored):
  | K = floor(N_eff) | total capacity (bits/symbol) |
  |---|---|
  | 14 (median) | 35.6 |
  | 11 (2.5th percentile) | 29.0 |
  | 17 (97.5th percentile) | 42.0 |
  | 16 (P4's K = 16 reference) | 39.9 |
  | 1 (pooled) | 3.3 |

  P4's K = 16 figure is therefore roughly the right order under this model, but only as an upper bound.
- Prediction check:
  | quantity | predicted | observed |
  |---|---|---|
  | N_eff | ~6 (3-12) | 14.2 |
  | packing number | ~6 | 10 |
  | union U (cm2) | ~25 | 44 |
  | sigma_c (mm) | 5-10 | 6.5 |
  | cortical N_eff | 55-64 | 55-64 |
  | verdict | FAIL, robust | INCONCLUSIVE, not robust |
- Caveats:
  - The model's union (44 cm2) exceeds all three reported unions (12, 33, 30 cm2).
  - The truncated log-normal puts its 5-95% range at 0.41-13.7 cm2 against the reported 0.3-11.3 (DEVIATIONS P5-14).
  - N_eff measures independence of PF location only.
  - Pairwise PF-overlap data (e.g. Greenspon 2025 Fig. 2 source data) would settle it.
- Self-tests passed: lens limits and the equal-radii closed form (0 error); N_eff bounds; sphere overlap; layout (30 + 2 sites per array; chequerboard
  nearest neighbour 0.566 mm); truncated-PF sampler; union of a single disc within 0.1%.
- Files: results\p5_spatial_channels.json, figures\p5_neff_vs_amplitude.png/.svg, figures\p5_example_pfs.png/.svg. Runtime 66 s, < 1 GB.

## Deviations (summary; details in DEVIATIONS.md)
- File names: the script names follow the task (p3b_psi_threshold_only.py, p5_spatial_capacity.py); the output names follow the preregs.
- P3b: the staircase is reused bit-identically from P3. P3's lapse follow-up is read as replaced by P3b section 3 and was not run.
- P5 assumptions:
  - The arrays are separated perpendicular to their long axis.
  - The 2 extra wired sites are re-drawn in every draw.
  - PF areas use inverse-CDF truncation, and amplitude scaling is applied after truncation.
  - Common random numbers are used across configurations.
  - The lens <1% check uses a fine raster (the 0.5 mm raster errors are reported).
  - The area-shuffle criterion is evaluated on the median N_eff.
- Post-hoc: a tiny-PF diagnostic was added. It changed no number or rule.
