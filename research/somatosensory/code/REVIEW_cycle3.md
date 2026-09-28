# Independent code review, cycle 3 (P5b, P2c). Verification gate. 2026-09-26
The reviewer did not modify any script or result. The reviewer's checks are in code\review\check_p5b.py and check_p2c.py, with
stdout in code\review\check_p5b_output.txt and check_p2c_output.txt. Line numbers refer to the scripts as reviewed.

| test | status | verdict as reported | reviewer view |
|---|---|---|---|
| P5b | CONFIRMED (code and ABANDONED). No bug | ABANDONED, 0/84 defensible | An independent model reproduces N_A / K_low / K_high and every gate number. V3 for C1 cannot be met by ANY map: it is set by the pooled PF-area model, not by units or fitting. |
| P2c | CONFIRMED (code, A0, and ABANDONED / FAIL) | formal ABANDONED; decision rule FAIL | The independent A0 fit and gain session match to 1e-5. The gain-scaling explanation is proven directly: constant gain equals session gain, and D1 scales as g^2. |

## P5b channels from measured somatotopy (p5b_channels_measured.py)
Fidelity to the prereg:
- Gate (L435-449):
  - V1 tolerance is max(2 mm, 25%) for bins 1-6 and 40% for bin 7. Bin 3 is 8.0 +/- 2.0.
  - V2 is pooled r in [0.59, 0.79] and median per-(draw, array) r > 0.40.
  - V3 is U_meas in [0.7 x median U_low, 1.3 x median U_high], per participant. The pooled primary needs all three participants (L849-854).
  - This is exactly prereg section 4.
- Bins are edges linspace(0,4,8) with np.digitize (L152-155).
- The same-digit strip is floor((u + phi)/W) with phi ~ U(0, W) (L162-163).
- The LS objective (L232-240) has s_b = 1/1/1/1/1/1/3 mm and r SD 0.03, as in 3.3.
- Unions are unit-correct: areas in cm2 x 100 give mm2 (L387), and the raster mm2 / 100 gives cm2 (L402-405).
- Ellipses use an exact affine map, v/2 and area/2 (L285-289). Aspect 2:1 gives semi-axes a, 2a with a = sqrt(A/2 pi), which is correct.
- The K_low / K_high / N_A construction (L355-378) follows 3.6 and DEVIATIONS 7. The abandonment rule (L896) follows sections 4 and 9.

Data check:
- The digitised CSV equals notes\data_cycle3.md A1.4 and the prereg table (3.1/6.0/8.0/11.8/18.2/24.1/26.6).
- The bin centres equal the linspace(0,4,8) centres.
- 9 of 10 arrays have the same wiring. CRS02 lateral differs by one site, which moves its centred coordinates. That matches DEVIATIONS 2.
- The reviewer's own sampler gives area quantiles 2.50/0.305/11.2 cm2 (V4).

Independent re-implementation (check_p5b.py):
- It uses no project code: Cholesky field, rejection-sampled areas, its own lens formula, its own raster union, its own pair statistics and its own seeds.
- Primary (theta from the LS fit, 3 x 500 draws):

  | quantity | reviewer | coder |
  |---|---|---|
  | N_A (p2.5/med/p97.5) | 4.27/7.12/11.32 | 4.33/7.11/11.30 |
  | K_low | 5.08/8.31/13.01 | 5.02/8.19/12.97 |
  | K_high | 9.56/14.04/20.01 | 9.58/14.03/20.08 |
  | N_A medians C1/P2/P3 | 7.75/7.62/6.20 | 7.63/7.68/6.24 |

- V1 bin means match: reviewer 4.71/7.62/10.97/14.33/17.92/21.95/26.13, coder 4.69/7.57/10.91/14.26/17.92/22.00/26.07. Bin 3 fails (|dev|/tol 1.49).
- V2 passes: r 0.738 (coder 0.738) and per-array median r 0.80.
- V3 bracket lower bounds:

  | participant | reviewer | coder | measured | result |
  |---|---|---|---|---|
  | C1 | 18.9 | 19.2 | 12 | FAIL |
  | P2 | 19.5 | 18.2 | 33 | ok |
  | P3 | 16.7 | 16.4 | 30 | ok |

- The independent-scatter control also fails V1 (bin 1 |dev|/tol 1.6) and V3 for C1, and passes V2. This matches the JSON gate counts.

Is the C1 V3 failure a gate or units error? NO. It is structural:
- If all 48 C1 PF centroids COINCIDE (zero map spread), the union is the largest single PF.
- Under the pooled area model its median is 18.0 cm2, so 0.7 x 18.0 = 12.6 > 12. Only 45% of draws would even allow it.
- So no theta, no map variant and no W can pass V3 for C1. The prereg's pooled area distribution (the paper says "C1 reporting the smallest PFs") cannot reproduce C1's union.
- Areas would have to shrink to about x0.35-0.5 for C1 to pass. The reviewer found C1 still fails at x0.5 and passes at x0.35.
- This is a design weakness of V3 for C1, which the preregistration made participant-specific while keeping areas pooled. It is not a code bug, and the rule was applied as written.
- ABANDONED also does not rest on V3 alone: V1 fails 84/84 under the pre-registered fit.

Post-hoc claim (a theta satisfies V1 and V2 while V3 still fails for C1): CONFIRMED independently.
- At g 6.59, sigma_f 24.9, l 11.5, sigma_n 1.67 the reviewer gets V1 max |dev|/tol 0.80 and r 0.739 (per-array 0.841), and C1's V3 lower bound is 19.3 > 12.
- The LS objective (1-mm weights in every bin) prefers a near-linear curve that misses bin 3, while the gate is loose in the far bins. That is an objective/gate mismatch in the prereg, not a code error.
- Caveat for anyone citing this: l = 11.5 mm is about 3-5x the array size (2.4 x 4 mm). The "correlated field" is therefore effectively a random per-array affine map, a degenerate corner of the model class. Do not read it as support for the correlated-error model.

JSON consistency: about 40 RESULTS_P5b numbers were spot-checked against p5b_channels_measured.json and p5b_posthoc_v1_reachability.json. All match:
- Gate counts V1 84 (bin 3 in 82), V2 42, V3 28 (all C1).
- K_design 4.21/8.81, K_low p2.5 >= 5 in 30/84, and the class counts.
- Unions 27.4/26.1/23.5, the factor medians, the amplitude changes, the D-sweep, the Downey cosines, the capacity values and the geometry-only rows.
- The ind vs corr difference: -24% / -31%.

Other notes:
- The tiny-PF failure for K_low is correctly diagnosed. Identical wiring plus a shared frame and field plus a nugget of ~0 make co-located electrodes coincide. With 24 of 32 kept per array, about 18 coincident pairs give ~0.57 n_PF for C1.
  - This also shows K_low is an unphysical bound (two arrays cannot occupy the same cortex). K_low 8.2 is a floor under an impossible placement, not a realistic value.
- The model pools pairs across arrays, while the digitised grey line is a mean across arrays. This weighting difference is small and does not change the verdict.

Verdict: P5b ABANDONED is CORRECT. The descriptive bracket (~8 to ~14) may be cited only with RESULTS' own "not a design value" wording. The data needed are per-participant PF areas or per-electrode maps (DABI, restricted).

## P2c biomimetic vs linear with measured adaptation (p2c_biomimetic_adaptation.py)
A0 fit:
- The protocol is at L74-81: rest precedes each train. Train ends are 6..300 s, then 362..610 s, which matches the digitised recovery times 360.8..608.6. The train-mean gain is normalised to train 1.
- The reviewer's independent fit (continuous-time exact train mean, Nelder-Mead, own numerical-Hessian CI):
  - tau_a 13.16 s (CI 11.2-15.4), tau_r 108.0 s (CI 89-131).
  - RMSE 0.0470, end of adaptation 0.439, end of recovery 0.895.
  - This is identical to the coder's 13.17/108.0.
- The literal on-then-off order gives 14.4/118.5 s with RMSE 0.045, which is essentially the prereg's 14.6/120. So the mathematician most likely used that order.
  - But it pairs the 608.6-s point with the 4th recovery train, so the coder's rest-first choice (DEVIATIONS item 2) is the better-supported mapping.
  - A0 passes under both. The difference (<10%) lies well inside the robustness rows (tau_a 7/30, tau_r 60/600), which all FAIL. Not verdict-relevant.

Arms:
- The reviewer's own Euler gain session (10 substeps per bin, 1-ms rest steps, 600-s warm-up, carry-over) matches the coder's exact-update session to max |dg| 7.9e-6.
- g_ss is 0.2726/0.2730, which matches both the prereg's predicted ~0.27 and the reviewer's arithmetic 1/(1 + (tau_r/tau_a)/3) = 0.268.
- The gain multiplies the signal only: r = g x a, and y - g x a is pure noise, with HS sd 141.5 = 10 x 14.15.
- FV sd = sqrt(n_T)(w rbar_adapted + sigma0). The reviewer's computation equals p2b.noise_sd exactly. The mean contact sd is 45 adapted vs 140 unadapted.
- After adaptation the charge ratio is 1.0003, so charge matching still holds.
- JND calibration is unadapted (w 0.2155, sigma_h 14.15) as prereg 2.1 states.

Floor and decision logic (L234-262, L482-499):
- The best AUCs are FV 0.528/0.509 and HS 0.503/0.503. The rerun gives 0.526/0.512. All are < 0.55, so the floor is hit twice and the result is formally ABANDONED.
- Decision-rule labels: FV Delta 0.083 (CI 0.038-0.110) and HS 0.000 (CI -0.001-0.008). Both CI upper bounds are < 0.30, so both arms FAIL.
- The precedence matches P2b. The JSON matches RESULTS.
- Wording: "VERIFIED 10/10" is attached to the decision-rule FAIL, but all 9 sensitivity rows were ALSO at the AUC floor. Recommended line: "formally ABANDONED (AUC floor); by the decision rule FAIL, robust in 10/10 rows."

Gain-scaling control failure. The explanation is CONFIRMED by a direct test that the coder did not run:
- Constant gain g_ss = 0.273 on both codes (no within-episode dynamics) gives:
  - HS Delta 0.0000;
  - D1-only Delta 0.0054;
  - session gain gives D1-only 0.0053, a difference of 0.0001.
- So within-episode gain dynamics contribute nothing.
- D1-only Delta against constant g is 0.074 / 0.0415 / 0.0181 / 0.0054 at g = 1 / 0.75 / 0.5 / 0.273. The g^2 prediction is 0.074 / 0.0416 / 0.0185 / 0.0055.
  - This is quadratic, as expected for the |mean-difference| max detector D1 (p2 L219) at small signal-to-noise.
- At g_ss both codes then select the same noise-driven D2 (AUC 0.503, shared Z), so max(D1, D2) cancels to 0.
- The failure is caused by the prereg's linear-scaling assumption, not by a bug. The prereg's section 6 requirement to explain it is met.
- The reviewer's own rank AUC agrees with auc_w to 4 decimals.

Weak controls (pass, but test little):
- The identical-encoder null is deterministic: the same encoder in two identical sessions gives Delta exactly 0.
- The HS variance-only probe is identical for both codes because the sd is constant.
- The FV probe d'_bio of 0.043 is close to its 0.05 limit, as it was in P2b.

Not re-derived:
- The secondary neuronal grid. The k_ad 0.9 cells give Delta 1.1-1.9 with d'_lin <= 0.08, and this asymmetry is large.
- It was not independently re-derived here, so no claim should use it. It is also already fenced by the prereg's "not a design recommendation" statement.
- The known A0 misfits (recovery 0.895 vs 0.726, adaptation too early under continuous drive) point to a missing slow component. More adaptation would only deepen the floor: the tau_r 600 row has g_ss 0.06 and is still FAIL.

Verdict: P2c formal ABANDONED is CORRECT, and the FAIL by the decision rule is CORRECT and robust.

## Bottom line for the queen
- No coding bug changes either verdict. Both RESULTS files match their JSON.
- P5b:
  - ABANDONED stands on two independent gates.
  - The C1 union gate is unreachable for every map under the pooled area model. The reason is the missing per-participant PF areas, not units.
  - The post-hoc V1+V2 theta is real but sits in a degenerate corner (l >> array).
  - K_low assumes co-located arrays, which is unphysical.
- P2c:
  - Cite it as "ABANDONED (AUC floor twice); decision rule FAIL, robust 10/10".
  - The gain-scaling failure comes from the detector's g^2 response and is shown directly.
  - Do not cite the neuronal k 0.9 PASS cells.
