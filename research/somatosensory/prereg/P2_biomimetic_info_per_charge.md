# P2: Biomimetic vs linear ICMS amplitude encoding: information about force changes per unit charge (H1)
Status: PRE-REGISTERED 2026-09-26 by mathematician. Simulation only. Amplitudes (uA) are model units anchored to
published psychophysics. They are not proposed stimulation settings.

## 1. Hypothesis
At matched mean charge and with no cortical adaptation (tau_ad = infinity), the biomimetic encoder
a = alpha*F + beta*|dF/dt| (Greenspon 2025, PMC12176618) gives a detection sensitivity for +/-10-30% force steps
(within 200 ms) d'_bio >= 1.3 * d'_lin. Its hold-force estimation RMSE is at most 1.5x that of linear encoding.
Secondary (exploratory, no PASS): how the ratio depends on the adaptation time constant tau_ad.

## 2. Model (dt = 10 ms; 3.0 s episodes; N = 4000 episodes; seed 20260926)
Force trajectories [ASSUMPTION, all ranges]:
- contact onset t0 ~ U(0.2, 0.5) s, ramp duration U(0.05, 0.15) s to F_hold ~ U(0.5, 2.0) N; F_max = 2.5 N.
- hold until t_off = t0 + U(1.5, 2.2) s, then ramp down, duration U(0.05, 0.15) s, to 0.
- steps during hold: Poisson rate 1/s, >= 300 ms apart and >= 200 ms from either ramp; size dF = +/-U(0.1, 0.3)*current F
  (sign 50/50), linear rise time U(20, 80) ms. Record step onset times t_e.
Encoders (in uA; A_cap = 100 uA, the maximum amplitude used by Greenspon 2025 for level counting; A_thr = 24 uA,
DERIVED: threshold consistent with the median of 7 levels at w = 0.225, see P4):
- linear: a_lin = 0 if F <= 0.02 N, else A_thr + (A_cap - A_thr) * F/F_max.
- biomimetic: a_bio = 0 if F <= 0.02 N, else A_thr + clip((A_cap - A_thr) * (alpha'*F/F_max + beta'*|dF/dt|/D), 0, A_cap - A_thr),
  with D = 20 N/s, alpha' = 0.25 [ASSUMPTION], dF/dt computed as a one-step backward difference.
  beta' is set by normalisation (two variants):
  (i) PEAK-MATCHED: the 99th percentile of a_bio over all episodes equals that of a_lin;
  (ii) CHARGE-MATCHED (primary): mean over episodes of sum_t a_bio = that of a_lin (solve for beta' by bisection; if impossible
  with alpha' = 0.25, first scale alpha' up. Report the final alpha', beta').
  Realism check (not a pass criterion): in variant (i), report charge ratio sum a_bio / sum a_lin. Greenspon observed
  0.69 +/- 0.07. If ours is outside [0.5, 0.9], flag the trajectories as unrealistic in the report.
Cortical response and observer:
- adaptation: z' = (k_ad*a - z)/tau_ad, r = max(a - z, 0), with k_ad = 0.9 [ASSUMPTION], tau_ad in {0.1, 0.3, 1, 3, 10, 30, inf} s
  (inf means z = 0). Primary = inf. The 10 s and 30 s values reflect neurologist's fact (Hughes 2022, PMID 35671947, opened by
  neurologist) that continuous ICMS led to complete percept loss within 1 min, while intermittent trains did not extinguish.
  Also for context: natural S1 onset/sustained ratio median 12 (neurobiologist fact, PMID 30668644).
- percept samples: y_t = r_t + eps_t, eps_t ~ N(0, s_t^2), s_t = sqrt(n_T) * (w*r_t + sigma0), n_T = T_train/dt,
  T_train = 1 s [ASSUMPTION: integration window of the discrimination trains], sigma0 = 1 uA.
- noise calibration, done separately for each tau_ad: pick w by bisection so that an observer comparing two 1-s flat trains
  (the standard at 60 uA vs a comparison c, both passed through the same adaptation) using the decision variable sum_t y_t
  gives JND = 13.5 uA. JND is half the difference between comparison amplitudes at p = 0.25 and 0.75, the Greenspon 2025 definition.
  Use >= 20000 Monte Carlo pairs per bisection step, or solve analytically for tau_ad = inf.
Detectors (applied identically to both encoders; take the better detector per encoder):
- D1 (transient): D1(k) = |mean(y[k-4..k]) - mean(y[k-14..k-5])|; window score = max over k in [t_e, t_e + 200 ms].
- D2 (sustained): |mean(y[t_e+100..t_e+200 ms]) - mean(y[t_e-200..t_e])|.
- null windows: 200 ms windows during hold that are >= 300 ms from any step onset and >= 200 ms from ramps; same scores.
- AUC by Mann-Whitney (event vs null scores); d' = sqrt(2) * Phi^-1(AUC).
Hold-force estimation: for each episode take mean y over the last 500 ms before t_off with no step in that window
(skip the episode otherwise). Fit F_hold ~ linear in mean y on half of the episodes, test on the other half; RMSE in N.

## 3. Metric and PASS/FAIL (primary: charge-matched, tau_ad = inf)
- PASS: d'_bio / d'_lin >= 1.3 AND RMSE_bio / RMSE_lin <= 1.5.
- FAIL: otherwise. 95% CIs by bootstrap over episodes (1000). If the CI of the d' ratio straddles 1.3, report INCONCLUSIVE.
- Always report the full table: tau_ad x {peak, charge}-matched x {d' ratio, RMSE ratio, AUCs}, plus separate
  d' for increases vs decreases (the |dF/dt| code cannot signal the sign; decreases may suffer).

## 4. Why the result is not guaranteed
- A linear code signals a step as a SUSTAINED amplitude shift that D2 can integrate over 100 ms. The biomimetic
  transient is brief and sits at high amplitude, where Weber noise is largest. Either can win.
- Charge matching takes charge from the sustained part of a_bio (alpha' is small), which can hurt D2 and hold-force RMSE.
- The two noise models (Weber scaling, per-bin noise) are calibrated to the same published JND, not tuned for either encoder.

## 5. Sensitivity (report d' ratio each; N = 2000)
w x {0.5, 1.5} (after calibration); alpha' in {0.1, 0.5}; D in {10, 40} N/s; T_train in {0.5, 2} s; step size ranges
U(0.05, 0.15) and U(0.3, 0.6); rise time ranges U(5, 20) and U(80, 200) ms; detection deadline {100, 400} ms; sigma0 in {0, 5} uA.

## 6. Abandonment criterion
If, for BOTH encoders in the primary condition, AUC > 0.99 (ceiling) or AUC < 0.55 (floor), rerun once with
the step size range U(0.05, 0.15) (ceiling) or U(0.3, 0.6) (floor). If the test is still insensitive, abandon: the
model cannot discriminate the encoders at the published noise level.

## 7. Null / control
- beta' = 0 control (sustained-only code at alpha', charge-matched by raising alpha'): must not beat linear by >= 1.3;
  otherwise the effect comes from charge redistribution, not from transients. Report it as such.
- noise-free control (w = sigma0 = 0): both AUC should be > 0.99 (sanity check).
- label-shuffle control: permute event/null labels; AUC should be ~0.5.

## 8. Outputs
code\p2_biomimetic.py, code\results\p2_biomimetic.json, code\figures\p2_dprime_vs_tau.png. < 10 min, < 1 GB
(4000 x 300 float arrays; loop over the parameter grid).
