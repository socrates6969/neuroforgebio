# Deviations and interpretations (coder-verifier A)
All entries in "written before results" were fixed before any P1/P2 outcome was computed.
Items added after a result was seen are listed separately and marked POST-HOC.

## P1 (grip latency budget), written before results
1. Time stepping: explicit Euler, dt = 2 ms, 2000 steps. Order within a step: (a) deliver detections due at this
   step, (b) L_fb hold/decay, (c) G_cmd and grip update dG = dt*(G_cmd-G)/tau_m, (d) G_eff, load, slip physics,
   (e) failure check, (f) slip-event detection and scheduling of feedback.
2. OU noise: exact discretisation xi[n] = a*xi[n-1] + sqrt(1-a^2)*z, a = exp(-dt/0.1), xi[0] ~ N(0,1).
3. K ~ Poisson(mean) is drawn by inverse CDF from one uniform per trial, so the sensitivity runs with other Poisson means keep
   common random numbers (CRN). Pulse amplitudes use lo + (hi-lo)*U with fixed U. At most 30 pulses per trial.
4. CRN: every condition and every SM value of one trial share m, mu, c, pulses, OU path. Detection draws use one uniform
   per (trial, slip-event index), so ART with p = 0 is bit-identical to NOFB (tested).
5. A slip event is S at step n with >= 10 consecutive non-S steps (20 ms) before it; at t = 0 the counter starts as "long ago".
6. Detection update uses L(t_s) and G_eff(t_s) of the event step (as written). mu_c = 0.9*L/(2*G_eff); G_eff floored at 1e-12.
   Several detections due in the same step are combined by min (mu_hat) and max (L_fb).
7. L_fb reactive hold: the 500 ms hold is measured from the LAST delivered detection (each detection restarts the hold);
   after that L_fb *= exp(-dt/0.3) per step. mu_hat never recovers (min only), as written.
8. VIS (primary, literal): s is the cumulative displacement (never reset), so "detectable once s > 2 mm" means an event
   at t_s is delivered at max(t_s, t_cross) + tau_v, where t_cross is the first time s > 2 mm. Events before t_cross are
   pooled (min/max) and delivered together at t_cross + tau_v. EXPLORATORY variant VISEV (not used for any decision):
   displacement counted from the first undelivered event (s - s_ref > 2 mm), tau_v = 200 ms only.
9. If DROP and CRUSH occur in the same step, the failure is counted as DROP.
10. Shuffled control: pass 1 = ART(delta=0, p=0.95) with every detection recorded (its mu_c, L(t_s) and event index, including
    detections whose delivery would fall after trial end/failure). Pass 2: the same detections for the same (trial, SM) are
    delivered at times U(0, T) that are drawn per (trial, event index) and not tied to slips (non-causal replay, as
    literally specified). No slip-driven feedback in pass 2.
11. ART tau = 74 ms + delta in every configuration, including the NAT-tau sensitivity runs (only NAT's tau changes there),
    as the table defines ART tau = 74 + delta.
12. Predictive variant: L_fb update uses L(t_s + tau) (the load is exogenous and known in the simulation). The mu_hat update
    keeps the matched pair L(t_s)/G_eff(t_s) because a friction estimate needs load and grip at the same instant. This
    is an interpretation.
13. Bootstrap: 1000 resamples of trials (N = 4000), shared across conditions (paired). SM is re-optimised in every resample
    by taking the min over the 16 SM values of the resampled rates (no re-simulation needed, outcomes are per trial x SM).
    delta* CI: the first 200 of these resamples at the full N = 4000 (not a 1000-trial subsample). Percentile CIs; censored
    delta* (">300", "<-20", or undefined when the resampled denominator is <= 0) are ranked as +inf, -inf, NaN(excluded, counted).
14. Verdict H3: G0 on point estimates. If G0 holds: PASS if the delta* point estimate and the whole 95% CI lie in [50,150];
    INCONCLUSIVE if the CI contains 50 or 150; FAIL otherwise. H3b: point estimate decides PASS/FAIL (the prereg gives no
    INCONCLUSIVE rule for H3b); the paired bootstrap CI of the ratio F*_ART(100,.95)/F*_VIS(200) is reported and flagged
    if it straddles 0.8.
15. Split into two invocations (main; sensitivity) to keep each run < 10 min. Same code, same seed.
16. Sensitivity robustness: fraction of the 19 configurations (18 one-factor + predictive) with delta* in [50,150].
    delta* censored or G0-failing configurations count as "not in [50,150]"; G0 status is reported per configuration.

## P2 (biomimetic vs linear), written before results
1. Steps: a Poisson process (rate 1/s) over the allowed onset interval [hold_start+0.2, t_off-0.2] with dead-time thinning
   (a candidate < 300 ms after the last accepted step is dropped). dF = sign * U * F(just before the step), linear rise.
2. Force is not clipped. The linear amplitude is clipped at A_cap (F can exceed F_max after + steps).
3. dF/dt: one-step backward difference, first sample 0.
4. CHARGE-MATCHED normalisation: bisection on beta' in [0, 1000]. If the charge target is unreachable at alpha' = 0.25
   (even at beta' = 1000), alpha' is raised on the fixed grid 0.25, 0.30, ..., 1.00 to the FIRST value where it is reachable,
   then beta' is found by bisection. (Minimal-increase reading of "first scale alpha' up".) As an exploratory check, the d' ratio is
   also reported at the next two grid alpha' values (not used for the verdict).
   PEAK-MATCHED: bisection on beta' so that the 99th percentile of a_bio over all samples of all episodes (including
   zero samples) equals that of a_lin.
5. Adaptation: exact exponential update z[t+1] = k*a[t] + (z[t]-k*a[t])*exp(-dt/tau), r[t] = max(a[t]-z[t], 0), z[0] = 0
   at episode start (and at the start of each calibration train).
6. Noise calibration: solved ANALYTICALLY for every tau_ad (not only inf). For a flat train the sum of y is Gaussian with
   mean sum(r) and variance n_T * sum((w*r+sigma0)^2), so P(c judged > 60) = Phi(...), JND = (c75 - c25)/2, and w is found by root
   finding. A 20000-pair Monte Carlo check of the analytic JND is a self-test.
7. Detector windows (samples of 10 ms, inclusive): D1(k) = |mean(y[k-4..k]) - mean(y[k-14..k-5])|, max over k = e..e+20.
   D2 = |mean(y[e+10..e+20]) - mean(y[e-20..e])|. Detection deadline sensitivity replaces 200 ms by the deadline:
   D1 max over e..e+deadline; D2 post window e+deadline/2..e+deadline; the pre window stays 200 ms.
8. Null windows: non-overlapping 200 ms windows tiled from hold_start, kept if the whole window [t_n, t_n+0.2] is >= 300 ms
   from every step onset and >= 200 ms from both ramps (so t_n >= hold_start + 0.2 and t_n + 0.2 <= t_off - 0.2). Scores are
   computed as for an event with onset t_n.
9. d' per encoder = the larger of d'(D1), d'(D2), chosen again in every bootstrap resample. The AUC is pooled over all episodes.
   Bootstrap = resampling episodes (1000), with events/nulls weighted by episode multiplicity.
10. Hold-force estimation (PRIMARY, literal): target = F_hold (the sampled ramp-up target), predictor = mean y over
    [t_off-0.5, t_off). Episodes with any step onset in that window are skipped. Fit on the first half of the (usable)
    episodes, test on the second half. SECONDARY (reported, not used for the verdict): target = true mean force in that window.
    Bootstrap of the RMSE ratio: resample episodes, split the resample into halves by position, fit and test.
11. Noise: eps = s_t * Z with one standard-normal matrix Z shared by both encoders and all tau_ad (CRN).
12. INCONCLUSIVE if the 95% CI of the d' ratio contains 1.3. Otherwise PASS iff d' ratio >= 1.3 and RMSE ratio <= 1.5
    (point estimates).
13. Sensitivity (N = 2000, charge-matched, tau_ad = inf): every item re-runs normalisation, and calibration where the item
    changes the noise model (T_train, sigma0); "w x" scales the calibrated w. alpha' in {0.1, 0.5} is the STARTING alpha' of
    the charge-matching rule in item 4 (it may be raised by that rule). D only rescales beta', so no effect is expected
    under charge matching.
14. beta' = 0 control: alpha' found by bisection in [0, 5] so that charge matches the linear encoder.

## P3 (psi vs staircase), coder-verifier B, written before results unless marked
1. File names: script is code\p3_psi_calibration.py (name given by the queen's task); outputs keep the prereg names
   (results\p3_psi_staircase.json, figures\p3_savings_map.png/.svg) plus an extra figures\p3_rmse_curves.png/.svg.
2. Psi entropy: expected posterior entropy over the 400-point (alpha,beta) grid is computed in closed form
   (Z log Z - E_s + (1-Z) log(1-Z) - E_f); checked against brute force (max abs err 9e-15). Ties -> lowest candidate.
   Candidates: 40 log-spaced values in [2,100] rounded to unique integers (fewer than 40 remain after rounding, as the prereg implies).
3. Staircase: the internal level is kept unrounded (multiplied/divided by the step factor, clipped to [1,100]); the PRESENTED
   stimulus is round(clip(level)). Reason: rounding the stored level would lock the track at 1 uA (1*1.26 rounds to 1).
   A reversal is a step whose direction differs from the previous step; its amplitude is the stimulus presented on that trial.
   The step taken at the 2nd reversal already uses 1.26. "Reversals after the 2nd" = reversals 3, 4, ...; if fewer than 2,
   the estimate is the last presented stimulus. The correct-counter resets after each down-step and on every error.
4. Estimates at budget N use only the first N trials of one 150-trial run (sequential, as in practice).
5. N_req: first budget with RMSE <= ln 1.2; linear interpolation from the previous budget; if already met at N = 10, N_req = 10.
6. Logistic variant (a): F = 1/(1+exp(-s(ln x - ln m))), with F(theta75) equal to the Weibull value and dp/dx matched at theta75
   (s = beta*u/q; checked numerically, rel. mismatch 1e-8).
7. Drift (b): the whole function scales by 1 + d*t/149 (t = 0..149, d = +/-0.2). Error is against the threshold at the
   last trial used (trial N), i.e. the current threshold.
8. Control abandonment rule: "within 10%" = N_req(CTRL) <= 1.10 * N_req(PSI); both ">150" counts as within.
9. Variants (c) psi lam 0.05 reuses the main staircase runs; (d),(e) reuse the main psi runs. CONTROL runs only in the main analysis.
10. CIs: 95% bootstrap over runs within each cell (1000 resamples main, 300 variants) for the count of cells with savings >= 0.30;
    per-cell bias CI = mean +/- 1.96 SE. The verdict uses the point estimates, as the prereg specifies.
11. Runs: 300 per cell and method (no reduction needed; main run 31 s).
12. POST-HOC NOTE (no change made): in cell theta75=20, beta=6, lam=0 the staircase reaches the target at N=10 because the
    deterministic 80->50->32->20 track lands on x79.4 (~21.7) by trial 10 and the "last stimulus" rule applies. This is a literal
    consequence of the prereg rule; it affects one cell and does not change the verdict.

## P4 (pooling capacity), coder-verifier B, written before results unless marked
1. File names: script code\p4_pooling_capacity.py; outputs results\p4_pooling_capacity.json, figures\p4_capacity_vs_M.png/.svg.
2. Blahut-Arimoto stopping (DEVIATION, decided after a timing test on the sanity channels, before any A/B/C result): the certified
   gap (upper - lower bound) < 1e-6 bits needs > 200k iterations (~15-20 s) per channel; ~130 channels would not fit the budget.
   Rule used: stop when gap < 1e-6 bits OR the lower bound improves by < 1e-9 bits per iteration. On test channels the reported
   C is within 2e-5 bits of the 200k-iteration value and the certified gap is < 1e-4 bits; the gap is stored for every entry (C_upper).
3. Channel discretisation: 400 input points on [ln Q_thr, ln Q_max]; 800 output points over [xmin-5s, xmax+5s]; bin probabilities
   from Gaussian CDF differences with open-ended edge bins. Capacity depends only on range/s, so results are cached on that ratio.
4. Input range for B: R(M) = N(M)*ln(1+w) (from N(1) = 11, i.e. A_thr = 100/(1+w)^11 uA at each w). Q_thr is not taken from elsewhere.
5. Model K: JND_Q = (100 - Q_thr)/11 and N(4) = (400 - Q_thr)/JND_Q with Q_thr fixed (not scaled with M), as written.
6. K independent channels: E = 64, M/K = 64/K electrodes each; C for kappa, w as in the B table; N(64/K) < 2 -> 0 bits.
7. Monte Carlo C: kappa = 0 (the model under test), w = 0.162, Q_thr = A_thr = 19.18 uA, Q_max = 100*M; 5 standards log-spaced
   from Q_thr to Q_max; 9 ln-increments (0.2-2.5 x ln 1.162), 20000 trials each; per-electrode amplitudes split equally and summed.
   JND = 75% point by linear interpolation (nonparametric, P = 0.5 at 0 prepended); w(Q) between standards by interpolation in ln Q.
   Level count = number of whole JND steps from Q_thr that stay <= Q_max (literal, integer); fractional count also reported.
8. Sensitivity N(1) in {7,14}: A and B recomputed with that N(1) (model K re-anchored to that N(1)).
   Q_max = 80 uA: A_thr held at the baseline-implied value, so N(1) falls (e.g. 9.5 at w=0.162); model K keeps JND_Q from baseline.
   Weber violation: N(M) = integral of dlnQ/ln(1+w(Q)); A_thr solved so that N(1) = 11; kappa_hat solved numerically; capacity with
   x-dependent noise s(x). M* reported as null where N never reaches 47.5 (treated as > 64).
   Frequency: separate log-frequency channel, 20-50 Hz, w = 0.15, same noise conversion; capacity by BA.

## P1/P2 POST-HOC notes (coder-verifier A, added AFTER results were seen; none of them changes a verdict)
- P1: no model change after results. Figure titles were edited for readability only.
- P2 file name: the script is code\p2_biomimetic_info.py (the name in the task), not p2_biomimetic.py (the name in the prereg). The results
  file uses the prereg name, p2_biomimetic.json.
- P2 code fixes made during the run, with no change to the model: (a) JND root finding is restricted to comparison amplitudes >= 0, and the
  JND counts as unreachable (1e6) when the 25%/75% points do not exist. This hit only the self-test bracket. (b) The observer
  with sigma0 = 0 and w = 0 is handled as noise-free, since the formula otherwise divides 0 by 0. Neither fix changes any primary number.
- P2 POST-HOC supplement (code\results\p2_biomimetic_posthoc.json): d'_lin is about 0, so the prereg d' ratio is undefined
  and its CI runs from about -200 to +300. Separate bootstrap CIs are therefore given for d'_bio, d'_lin and their difference. They are descriptive only.
- P2 observation: the Weber (signal-dependent) noise lets |.|-max detectors pick up variance increases. A synthetic
  +7.6 uA step alone gave AUC 0.58, while a matched step with constant noise gave about 0.51. The biomimetic transients raise r for both increases and decreases,
  so part of the biomimetic d' may come from this variance cue and not from the mean shift. This was not quantified further.

## P3b (threshold-only Bayesian adaptive recalibration), coder-verifier B, cycle 2, written before results unless marked
1. File names: script code\p3b_psi_threshold_only.py (name given in the queen's task; the prereg says p3b_threshold_psi.py).
   Outputs keep the prereg names: results\p3b_threshold_psi.json, figures\p3b_savings_map.png/.svg; extra figures\p3b_rmse_curves.png/.svg.
2. Reuse: code\p3_psi_calibration.py is IMPORTED unchanged (observer, run_psi, expected_entropy, staircase, N_req, evaluate, bootstrap).
   The 1-D grid is passed to the same run_psi/expected_entropy (they are dimension-agnostic). Prior uniform in ln alpha (as P3).
   Candidates identical to P3 (40 log-spaced values in [2,100] rounded to unique integers). Ties -> lowest candidate.
3. Estimate: exp(posterior mean of ln theta75(alpha, beta_a, lam 0.02)) = exp(E ln alpha) * u^(1/beta_a); the identity is a self-test.
4. Staircase arms use P3's exact code AND rng keys, so they are bit-identical to P3's staircases (asserted against
   results\p3_psi_staircase.json at run time). A arms use new rng namespaces (vid 200-206).
5. A-oracle: a separate 1-D grid per true beta (1.5/3/6); evaluated with the same rule; reported, no verdict; used for the
   "stop this line" abandonment rule (< 24/48 cells).
6. Sensitivity (c) = beta_a in {2, 4.5} for ALL cells (A re-run; staircase from main). (a),(b),(d),(e) as in P3 (A with beta_a = 3).
7. P3's lapse follow-up rule (P3 section 7) is read as REPLACED by P3b section 3 (which lists only the two P3b abandonment rules);
   the number of lam = 0.10 bias failures is reported, but no free-lapse follow-up is run.
8. Control rule "within 10%" = N_req(CTRL) <= 1.10 * N_req(A); both ">150" counts as within (as in P3).
9. CIs: bootstrap over runs within cell (1000 main/oracle, 300 variants) for the count of cells with savings >= 0.30; per-cell bias
   CI mean +/- 1.96 SE. Verdict uses point estimates (as in P3).

## P1b (grip latency budget v2), coder-verifier A cycle 2, written BEFORE any P1b result was computed
1. File names: script code\p1b_grip_latency_v2.py (name given in the queen's task; the prereg says p1b_grip_latency.py).
   Outputs keep the prereg names: results\p1b_grip_latency.json, figures\p1b_R_vs_delta.png/.svg; extra files
   results\p1b_grip_latency_sensitivity.json, results\p1b_boot_R.npz, results\p1b_selftest.json, figures\p1b_sensitivity.png/.svg.
   The cycle-1 script is imported read-only; its simulate() is copied into the new file and changed only at C1/C2.
2. C1 memory prior: eps = u * hw with one u ~ U(-1, 1) per trial, drawn from a SEPARATE stream (default_rng(seed + 1000)),
   so every cycle-1 random number (m, mu, c, pulses, OU, detection uniforms) is bit-identical to cycle 1 (self-tested), and the
   sensitivity half-widths ln 1.05 / ln 1.15 reuse the same u (CRN). Uniform in eps (log space), as written.
3. C2 two-sided update: on delivery mu_hat <- mu_c (replace). L_fb keeps max(L_fb, L(t_s)) as in P1 (only the mu update is
   named in C2). Several deliveries to one lane in the same step cannot occur for FB conditions (fixed tau); for VIS pooled
   events (P1 item 8) the pooled measurement is the MOST RECENT event's mu_c (replace semantics), not the min.
4. Shuffled control under C2: the recorded measurements of ART(0, 0.95) are replayed at random times and REPLACE mu_hat
   (literal: same update rule as every other delivery).
5. G_Z (C3): run first, N = 4000, K = 0, NAT and NOFB, SM re-optimised per condition, 95% bootstrap CI (1000 resamples, seed+2).
   If it fails, the script stops (no main run, no H3/H3b verdict). The reference config (fixed prior 0.75 + min update) G_Z is run
   right after as the regression check (|F*_NOFB(K=0) - 0.498| <= 0.03); it does not gate anything else.
6. Redesign (only if G0 fails): P1 section 6 parameters (amp U(0.4,1.0), c U(1.3,2.0)) with the P1b friction model; its G_Z is
   computed; H3 is ABANDONED if the redesign's G0 or G_Z fails. Bootstrap/delta* rules as P1 items 13-14.
7. Sensitivity: the 18 one-factor items of P1 with mu_prior replaced by memory half-width {ln 1.05, ln 1.15}, plus the Smith
   predictor = 19 configurations (N = 1000), plus a "baseline (N=1000)" row and the reference config row (neither counted).
   For every row G_Z (K = 0, N = 1000, no bootstrap) is also reported. Robustness counts a row only if G0 holds and delta* in [50,150].
8. H3b: as P1 item 14 (point estimate decides; CI reported). H3 verdict requires G_Z AND G0.
10. POST-HOC NOTE (P3b, after results; no change made): the A-oracle beta = 3 cells use the same model as A but a different rng
    namespace; their N_req differs from A's by up to ~10 trials (e.g. 26.0 vs 28.3), which is the Monte Carlo noise of N_req at
    300 runs. The bootstrap CIs on the cell counts carry this noise.

## P5 (spatial channel capacity), coder-verifier B, cycle 2, written before results unless marked
1. File names: script code\p5_spatial_capacity.py (task name; prereg says p5_spatial_channels.py). Outputs keep the prereg names:
   results\p5_spatial_channels.json, figures\p5_neff_vs_amplitude.png/.svg; extra figures\p5_example_pfs.png/.svg.
2. Array layout: each S1 array = 6 x 10 grid, 400 um pitch (3.6 x 2.0 mm). Chequerboard = sites with (row+col) even (30);
   2 extra wired sites per array drawn uniformly (without replacement) from the 30 odd sites, re-drawn in EVERY Monte Carlo draw.
   The two arrays have parallel long axes and are separated centre-to-centre by D_arr PERPENDICULAR to the long axis (along the
   6-row axis), so D_arr = 3 mm does not make the arrays physically overlap (3.6 mm long axis). [ASSUMPTION; orientation not reported]
3. Somatotopy: c_i = 5 * x_i + e_i (mm), e_i ~ N(0, sigma_c^2 I2). The mean Pearson r (over draws) between the 2016 electrode
   distances and centroid distances is fitted to 0.69 by bisection on sigma_c in [0, 50] mm using 2000 draws with COMMON random
   numbers (fixed standard-normal noise and fixed extra sites, scaled by sigma_c), so r(sigma_c) is deterministic and monotone.
   Main runs use fresh draws (separate rng stream). Sensitivity configurations reuse the same 500 base draws (common random numbers).
4. PF areas: log-normal (median 2.5 cm2, sigma_ln 1.10) TRUNCATED to [0.1, 30] cm2 by inverse-CDF sampling (not clipping).
   Amplitude sweep: areas multiplied by (I/60)^1.43 AFTER truncation (truncation refers to the 60 uA survey distribution).
5. Overlap C_ij = lens area / sqrt(A_i A_j), C_ii = 1; N_eff = 64^2 / sum_ij C_ij^2. Distributions over 500 draws; PASS/FAIL uses
   the 2.5th/97.5th percentiles over draws. MC uncertainty of those percentiles is reported by bootstrap over draws (descriptive).
6. P_pack: greedy, PFs sorted by area ascending, a PF is added if it is disjoint (d >= r_i + r_j) from every PF already chosen.
7. Union U: raster of 0.5 mm spacing over the bounding box of all discs, point-in-any-disc count x 0.25 mm2. Computed for all 500
   draws in the primary configuration and for the D_arr 3 and 8 mm configurations (needed for the abandonment rule).
8. Lens closed-form check: 100 random partially overlapping pairs (radii from the PF distribution, d uniform on (|r1-r2|, r1+r2)).
   The < 1% criterion is applied to a 1500 x 1500 raster over each lens's bounding box (a fixed 0.5 mm raster cannot resolve small
   lenses to 1%); the 0.5 mm raster errors are reported as well (descriptive).
9. Capacity consequence: K = floor(median N_eff) (also floor of the 2.5th/97.5th percentiles), M = 64/K electrodes per group
   (non-integer M allowed in N(M) = 11 + ln M / ln(1 + w)), total = K * C(64/K) with P4's capacity_M (w = 0.162, kappa = 0),
   imported from code\p4_pooling_capacity.py unchanged; C = 0 if N(64/K) < 2 (as P4).
10. Cortical N_eff: sphere centres at the electrode tips (all in one plane: same shank length); equal-sphere overlap volume
    V = pi (4r + d)(2r - d)^2 / 12 for d < 2r; C_ij = V / (4/3 pi r^3). Primary D_arr 5 mm. r(I) = 0.1 mm (I/10)^0.653;
    Tehovnik: r = sqrt(60 / K) mm.
11. Controls: tiny-PF (all areas 0.001 cm2, same centroids); identical-PF (all centroids 0, all areas 2.5 cm2);
    no-somatotopy null (centroids uniform on a disc of 165 cm2, same areas; compared on the median N_eff and per draw);
    area-shuffle (areas permuted across electrodes within each draw; criterion: |median N_eff(shuffled) / median N_eff - 1| < 0.10,
    the per-draw relative change is also reported).
12. Robustness grid: 36 configurations D_arr {3,5,8} x sigma_c {fitted, 0.5x, 2x} x I {40,60,80,100} uA (sigma_c NOT re-fitted);
    each classified with the same PASS/FAIL/INCONCLUSIVE percentile rule (gates V1/V2 are evaluated on the primary only).
    "Robust" = the primary verdict holds in >= 70% of the 36 (i.e. >= 26). The re-fitted sigma_c for D_arr 3 and 8 mm is also reported.
13. POST-HOC (P5, after the first run; no model or rule change): the tiny-PF control FAILED its literal criterion (min N_eff 62.1;
    2.8% of draws < 63; median 64.0). A diagnostic block was added to the script (results key posthoc_tiny_pf_diagnostic):
    with sigma_c = 0 the tiny-PF N_eff is exactly 64.0 in every draw, and with the fitted sigma_c = 6.54 mm on average 0.46
    centroid pairs per draw land < 0.36 mm apart. So the failure comes from the pre-registered random-scatter somatotopy (two
    noisy centroids can coincide), not from the overlap code (identical-PF, lens and null controls pass). It is reported as a FAIL
    of that control. The re-run with the diagnostic reproduced every other number exactly (same seeds).
14. POST-HOC (P5): the truncated log-normal (sigma_ln 1.10) gives 5th/95th percentiles 0.41/13.7 cm2 vs the reported 0.3/11.3 cm2
    (the prereg's sigma is the mean of the two one-sided fits). The model union (median 44.3 cm2) is above all three reported unions
    (12, 33, 30 cm2) but inside the V1 gate [6, 66]. Both point to PFs that are, if anything, more spread than the data.

## P2b (biomimetic d' difference), coder-verifier A cycle 2, written BEFORE any P2b result was computed
1. File names: script code\p2b_biomimetic_ddprime.py (name given in the queen's task; the prereg says p2b_biomimetic_diff.py).
   Outputs keep the prereg names: results\p2b_biomimetic_diff.json, figures\p2b_delta_dprime.png/.svg; extra
   results\p2b_biomimetic_diff_sensitivity.json, results\p2b_selftest.json, figures\p2b_sensitivity.png/.svg. Cycle-1 code is imported read-only.
2. Delta = d'_bio - d'_lin, each d' = max over D1/D2 (P2 item 9), the detector re-chosen in every bootstrap resample.
   95% CI: paired percentile bootstrap over episodes, 1000 resamples (seed + 7, the cycle-1 post-hoc stream), same episode
   multiplicities for both encoders. V = 1 - Delta_FV / Delta_Weber from point estimates.
3. FV arm (C3): rbar_ep = mean of adapted r over the episode's samples with a > 0 (per encoder; both encoders share the contact mask
   F > 0.02 N). The frozen sd sqrt(n_T)(w rbar_ep + sigma0) is applied to contact samples; non-contact samples keep the Weber sd,
   which equals sqrt(n_T) sigma0 there because r = 0. All detector and RMSE windows lie inside contact, so this choice cannot
   affect any metric. w = the Weber-calibrated w for that tau_ad (not recalibrated), as C3 says "same w".
4. HS arm (C4): per-sample sd = sqrt(n_T) * sigma_h, sigma_h = 13.5 * G / (Phi^-1(0.75) * sqrt(2 * n_cal * n_T)), G = sum of the
   flat-train adaptation gain over the 1-s train. At tau_ad = inf this is 13.5 / (0.6745 sqrt 2) = 14.15 (per-sample 141.5 model-uA).
   For finite tau_ad (exploratory sweep only) sigma_h is recalibrated the same way (P2 calibrates per tau_ad). MC-checked in the self-test.
5. Variance-only probe: y = s_t Z with s_t the Weber sd time course of the charge-matched biomimetic code and a zero mean. D1/D2 are
   differences of window means inside the hold, so any constant mean ("a stays at the pre-step value") cancels exactly; mean 0 is
   the same detector input. Also reported for the linear code (descriptive).
6. Decision (section 2): R0 gate first (|Delta_W - 0.52| <= 0.02 and |d'_bio,W - 0.542| <= 0.02), else stop. PASS/FAIL/INCONCLUSIVE
   exactly as written, using Weber-arm lower CI, FV-arm CI, V and the Weber-arm RMSE ratio (point estimate, as P2 item 12).
7. HS disagreement: "variance-control dependent" is flagged whenever the HS label differs from the FV label; a FV PASS is downgraded to
   INCONCLUSIVE whenever HS is not also PASS (conservative reading of "disagree on PASS/FAIL"). A FV FAIL stays FAIL.
8. Abandonment (section 5): FV-arm floor = both best AUCs < 0.55. If hit, all three arms are rerun once on new episodes with steps
   U(0.3, 0.6) (new charge matching, same calibrated w and sigma_h), and the decision rule is applied to the rerun; R0 is not re-applied.
9. Controls: beta' = 0 control in all three arms (each must have Delta < 0.30); noise-free (w = sigma0 = 0; identical for all arms);
   label shuffle on the FV-arm biomimetic D1 scores (seed + 3). Peak-matched results are reported descriptively for all arms.
10. Sensitivity: the P2 list (16 items), N = 2000, all three arms, point estimates, tau_ad = inf. "w x" scales w and sigma_h alike.
    tau_ad sweep (exploratory, no verdict): 7 values x 3 arms, charge-matched, w and sigma_h recalibrated per tau_ad, 200-resample CIs.

## P1b/P2b POST-HOC notes (coder-verifier A, added AFTER results were seen; no model change, no verdict change)
- P1b: R = (F*NOFB - F*ART)/(F*NOFB - F*NAT) is undefined (NaN) because F*NAT > F*NOFB (denominator < 0), so delta* and its CI are
  "undefined" (200/200 resamples). The P1b figure therefore plots F*_ART(delta) with NOFB/NAT/VIS reference lines instead of R.
- P1b diagnostic (N = 1000, NAT, SM 0.7, not a prereg metric): every trial with >= 1 delivered detection fails (22.4% of trials, fail rate
  1.00, mostly crush). Mechanism: after a slip, L_fb = L(t_s) (pulse load) is multiplied by (1+SM) and divided by mu_hat ~ 0.9*mu, which
  exceeds the crush limit c*m*g/(2*mu) for c in [1.6, 2.5]. This is a property of the unchanged P1 reactive-hold rule, reported, not fixed.
- P2b precedence: the FV floor triggered the section-5 abandonment rerun; the rerun FV arm was again at the floor, so the formal verdict
  is ABANDONED. The section-2 decision rule on the same primary data gives FAIL (V_FV = 0.79 > 0.5; upper CI of Delta_FV 0.14 < 0.30),
  and it also gives FAIL on the rerun data. Both are reported; no rule was changed.
- Figure titles were shortened for readability (verdict moved to a suptitle).

## P2c (biomimetic vs linear, MEASURED adaptation), coder-verifier A cycle 3, written BEFORE any P2c result was computed
1. File names: script code\p2c_biomimetic_adaptation.py (name given in the task; the prereg says p2c_biomimetic_adapt.py). Outputs keep
   the prereg names: results\p2c_biomimetic_adapt.json, figures\p2c_delta_by_arm.png/.svg; extra results\p2c_biomimetic_adapt_sens.json,
   results\p2c_selftest.json, figures\p2c_adaptation_fit.png/.svg. P2 and P2b code are imported read-only (episodes, encoders, charge
   matching, calibrate_w, sigma_h, FV/HS noise_sd, Scored, detectors, AUC, RMSE); nothing older is modified.
2. A0 protocol and time mapping. The digitised recovery points (360.8 ... 608.6 s) line up with train ENDS only if each rest period
   precedes its train: adaptation train k (k = 0..49) ends at 6(k+1) s, recovery train j (j = 0..4) ends at 300 + 62(j+1) s (61 s rest
   before each). The literal on-then-off order would put the first recovery train 5 s after the last adaptation train and the
   recovery ends at 301-549 s, which does not match the five digitised points. Rest-first is identical for the adaptation period
   (g = 1 at the start). Each of the 42 digitised points is paired with the model train whose end time is nearest (several points can
   share a train). Model value = mean g over the train's 100 on-bins, normalised to train 0. a/60 = 1 during trains, so p plays no role.
3. Integration: for piecewise-constant a in each 10-ms bin the gain ODE is linear, so g is advanced with the exact exponential update
   g <- g_inf + (g - g_inf) exp(-(k_a + k_r) dt), k_a = (a/60)^p / tau_a, k_r = 1/tau_r, g_inf = k_r/(k_a + k_r). Percept r_t = g_t a_t
   with g_t the value at the START of the bin (as p2.adapt uses z before its update). Rest gaps (a = 0) use the closed form
   g <- 1 - (1 - g) exp(-G/tau_r). The self-test checks this against Euler at dt = 0.1 ms.
4. A0 fit: scipy least_squares on (ln tau_a, ln tau_r), multi-start, all 42 points. Approx. 95% CI = exp(theta +/- 1.96 SE), SE from
   s^2 (J^T J)^-1 (Gauss-Newton). A0 passes iff RMSE <= 0.06 AND the fitted value of train 49 (end of adaptation) is in [0.335, 0.535].
   The refit values (not the prereg's 14.6/120) are used everywhere tau_a/tau_r are "fitted". Descriptive out-of-sample: continuous
   100 Hz from rest (percept = g) at 5 s and 15 s; 100/200/500-ms bursts at 50% duty from t = 0, g at 20 s and 30 s vs the digitised Fig 2B.
5. Session (C3): encoder sessions of 250 consecutive episodes (session s = episodes 250s .. 250s+249; N = 4000 -> 16 sessions,
   N = 1000 -> 4), vectorised over sessions. Each 3-s episode (300 bins) is followed by a gap of G s with a = 0. Each session is preceded
   by a warm-up of ceil(600 / (3 + G)) episodes from a separate warm-up set (gen_episodes, seed 20260926 + 1000, same step settings,
   same encoder coefficients as the main set), which is discarded; g carries over everywhere. Warm-up stays 600 s in every row including
   tau_r = 600 s: the relaxation time of g is ~1/(duty/tau_a + 1/tau_r), about 30-45 s, far below 600 s; the drift of g between the first
   and last 50 episodes of each session is reported as a steady-state check. Bio and lin sessions share trajectories and the Z matrix (CRN).
6. Noise arms: FV sd = sqrt(n_T)(w rbar_ep + sigma0) with rbar_ep = mean ADAPTED r over contact samples (P2b noise_sd with adapted r);
   HS sd = sqrt(n_T) sigma_h. Calibration unadapted: w = calibrate_w(inf) = 0.2155, sigma_h = 14.15 (P2b values). Sensitivity row
   "JND calibrated adapted": g_ss,lin = mean g over contact samples of that row's linear session; w re-solved with a flat gain vector
   g_ss,lin over the 1-s train (p2.p_greater), sigma_h = g_ss,lin x 14.15 (exact for a constant gain).
7. Delta = d'_bio - d'_lin, each the max over D1/D2 (detector re-chosen per resample); paired percentile bootstrap over EPISODES,
   1000 resamples, seed + 7 (as P2b). The dependence between episodes through carried-over g is ignored, as the prereg specifies an
   episode bootstrap. RMSE ratio = point estimate per arm (hold-force RMSE, as P2/P2b).
8. Decision rule per arm: PASS_arm iff Delta >= 0.30 and CI lower > 0 and RMSE ratio <= 1.5; FAIL_arm iff (Delta < 0.30 and CI upper
   < 0.30) or RMSE ratio > 1.5; else INC_arm. Overall: RMSE ratio > 1.5 in either arm -> FAIL; both PASS -> PASS; both FAIL -> FAIL;
   labels differ -> INCONCLUSIVE ("variance-control dependent"); else INCONCLUSIVE.
9. Precedence (same as P2b): floor = best AUC < 0.55 for BOTH encoders in BOTH arms (primary). If hit, the primary is rerun once with
   steps U(0.3, 0.6) (new episodes, warm-up set, charge matching; same w, sigma_h, tau_a, tau_r); if still at floor the FORMAL verdict is
   ABANDONED. The decision-rule label on the primary data (and on the rerun) is always reported next to it. The floor rule is applied to
   the primary perceptual arm only; for all other rows it is reported descriptively.
10. Robustness: 9 one-at-a-time rows at N = 1000 (tau_a 7/30, tau_r 60/600, p 0.5/2, G 1/10, adapted calibration), 1000 bootstrap
    resamples each; row call = decision-rule label; primary call = decision-rule label on the N = 4000 primary. VERIFIED iff >= 7 of 10
    rows give the primary call.
11. Secondary neuronal: p2.adapt (subtractive z, k_ad, tau_n; z starts at 0 in each episode, which equals a continuous session because
    a = 0 for >= 0.2 s before contact and gaps are >= 1 s >> tau_n). w and sigma_h recalibrated per (tau_n, k_ad) with p2.calibrate_w and
    p2b.sigma_h (P2 practice). Primary cell (0.04 s, 0.5) at N = 4000 with 1000 resamples; the other 8 grid cells at N = 1000 with 1000
    resamples. VERIFIED iff >= 7 of 9 cells give the primary-cell call (>= 70%).
12. Combined arm (descriptive): r = g x max(a - z, 0), g from the primary perceptual session (driven by a), z neuronal primary;
    calibration = the neuronal (tau_n, k_ad) w and sigma_h at g = 1.
13. Controls: identical-encoder null = the linear code run through the biomimetic slot as its own session (CI must contain 0);
    variance-only probe per arm = y = sd_arm(adapted r_bio) Z with zero mean, bio d' < 0.05 required in FV and HS (lin descriptive);
    beta' = 0 control = p2.beta0_alpha code with its own session, Delta < 0.30 in both arms; noise-free = adapted r with w = sigma0 = 0
    and sigma_h = 0, best AUC > 0.99 for both encoders; label shuffle = FV bio D1 scores permuted (seed + 3), |AUC - 0.5| <= 0.02;
    power check = HS, g = 1, sigma_h / 4 (descriptive); gain-scaling = Delta_HS(primary) / (g_ss x Delta_HS(g = 1)) within [0.75, 1.25],
    g_ss = mean of the two encoders' contact-sample mean g. Peak-matched variant = enc "peak" (alpha' 0.25) with its own session,
    descriptive, 200 resamples.
14. g_ss per encoder = mean g over contact samples (a > 0) of the evaluation episodes; the session time-average (incl. gaps) is also given.

## P5b (channels from measured somatotopy), coder-verifier B, cycle 3, written BEFORE any P5b result was computed
1. Files: code\p5b_channels_measured.py (new; imports p5_spatial_capacity.py and p4_pooling_capacity.py read-only). Outputs:
   results\p5b_channels_measured.json (+ results\p5b_fits.json, cache of the calibration stage), figures\p5b_K_bounds.png/.svg
   (prereg name), extra figures\p5b_calibration.png/.svg and figures\p5b_K_vs_amplitude_web.png/.svg (single-panel web figure).
   The script runs in stages (--stage fit, --stage run) so that each run stays < 10 min; same seeds either way.
2. Geometry: participant code map as quoted (BCI02 = C1, CRS02 = P2, CRS07 = P3). Each array's 32 wired sites (x_mm, y_mm from the
   CSV) are centred on the mean of its wired sites. The wiring maps are identical for all arrays except CRS02 lateral (one site differs).
   Map rotation: one uniform angle per draw applied to both arrays of a participant (same cortical frame); the CSV ArrayRotations are
   not used (prereg 3.1).
3. Calibration geometry: the digitised curve pools within-array pairs of 5 arrays (C1 M/L, P2 M/L, P3 medial; P3 lateral excluded as
   in the released code). The fit therefore uses this POOLED geometry (draws cycle through the 5 arrays, 80 draws each = 400 draws),
   one fit per (scatter model x map x W x curve level). The fitted theta is applied to every participant configuration; V1/V2 are then
   re-checked per configuration with that participant's geometry on fresh draws. All 32 sites enter the calibration and V1/V2 (the
   data pairs are PF electrodes, but exclusion is random and independent of position, so it changes only the pair count).
4. Field: f = sigma_f * S_l z, with S_l the symmetric square root (eigh, negative eigenvalues clipped to 0) of the squared-exponential
   kernel exp(-d^2 / (2 l^2)) over the cortical sites; u and v components independent. Same-digit test: floor((u_i + phi)/W) ==
   floor((u_j + phi)/W), phi ~ U(0, W) per draw and array. Pooled r = Pearson r over all same-digit pairs of all draws; per-array r =
   per (draw, array). Bin means m_b pooled over all same-digit pairs in the bin; an empty bin gives objective 1e6. Nelder-Mead
   (scipy, bounds as in the prereg) from 5 fixed starts (g, sigma_f, l, sigma_n): (5,8,1.5,1.5), (3,4,0.5,0.5), (8,14,3,3),
   (12,2,6,6), (2,20,1,0.5); independent model (g, sigma_n): (5,1.5), (3,0.5), (8,3), (12,6), (2,8). maxfev 600 per start. Best
   objective wins. CRN: the same normals, angles and phases for every objective evaluation of a fit.
5. PF exclusion: exactly n_keep = round(f x 32) PF electrodes per array (C1/P2 24, P3 13, f = 1.0: 32), chosen uniformly at random
   per array and draw. Equal counts per array make the bound identity K_high = 4/(1/N_A1 + 1/N_A2) exact (it needs tr C1 = tr C2).
6. PF areas: two-piece log-normal (median 2.5 cm2, sigma_ln 1.289 below / 0.917 above; CDF Phi((ln A - mu)/s) with s by side, each
   half weight 0.5) truncated to [0.05, 40] cm2 by inverse-CDF sampling. Amplitude conditions scale areas by (I/60)^gamma AFTER
   truncation.
7. Pair bounds per draw: array 1 uses the joint 64-site field of the shared frame (K_low placement); K_low = N_eff over both arrays'
   PF electrodes in the shared frame (array 2 same origin, same field realisation, own nugget, areas and exclusion). K_high uses the
   same array 1 and an array 2 with an INDEPENDENT field (own normals), same nugget/areas/exclusion as in K_low (common random
   numbers); K_high = participation ratio of the block-diagonal C (computed, then checked against the identity). N_A = the per-array
   participation ratios of the K_high draw (both arrays; each is a valid single-array draw), pooled.
8. Ellipses: all ellipses share one orientation (long axis along v) and aspect 2:1, so the affine map v -> v/2 turns them into discs
   of radius a = sqrt(A / (2 pi)) and scales every area by 1/2; C_ij (a ratio) and the union (x 2) are then EXACT via the closed-form
   lens. This replaces the prereg's 0.25 mm raster for ellipse overlaps (exact and faster); a raster check of the transform is a
   self-test. Ellipse draws stay at 100 as pre-registered.
9. Unions (V3 and secondary metric): 0.25 mm raster (p5.union_area, h = 0.25) on the first 100 draws of each configuration (compute
   budget; the gate uses medians). U_low = union of both arrays' PFs in the shared frame; U_high = U(array 1) + U(array 2) (disjoint
   territories). V3 uses the participant's own U_p; the pooled primary needs V3 to hold for each of C1, P2, P3.
10. V1 compares with the CENTRAL digitised values for every configuration (including the +/-1 mm curve rows, whose fits target the
    shifted curves). V1/V2 use the K_high-sample arrays (independent single arrays), all draws of the configuration.
11. Primary configuration = the three participant configurations (isotropic, W 20, disc, participant f, central curve) with their draws
    pooled (3 x 500). Per-configuration class (for robustness): PASS if p2.5 K_low >= 5; else CONDITIONAL if p2.5 K_high >= 5; FAIL if
    p97.5 K_high < 5; else INCONCLUSIVE. The overall verdict uses the prereg section-6 rule on the defensible configurations of the
    correlated model; K_design = 2.5th percentile over all draws pooled over the defensible configurations (discs 500, ellipses 100 draws,
    unweighted, as written). CIs: stratified bootstrap (draws resampled within configuration), 400 resamples.
12. Scatter-artefact flag: the independent-scatter model "passes the gate" if its primary configuration passes V1-V3. Then its
    K_design (low and high) is computed over its own defensible configurations; if either differs from the correlated model's by
    > 30% (relative to the correlated value), the flag is raised, K_design,low/high = min of the two models, the robustness fractions
    are taken as the min of the two, and "VERIFIED" is withheld.
13. Controls (pre-set criteria): field-shuffle (permute f(x_i) among the electrodes of each array; pass if median N_A rises);
    no-somatotopy null (centroids uniform on a 165 cm2 disc; pass if model median N_A < null median N_A); tiny-PF (A = 0.001 cm2):
    because random nugget/field scatter can make two centroids coincide (REVIEW_cycle2 flaw), the criterion is read on the MEDIAN over
    draws (N_A, K_low, K_high each >= 0.98 n_PF), and a strict per-draw check (every draw >= 0.98 n_PF) is applied to N_A of the pure
    linear map (sigma_f = sigma_n = 0), which tests the overlap code; min and fraction below are reported for all. Identical-PF:
    |N_eff - 1| < 1e-9. Hand boundary: 30 primary draws (10 per participant), PFs clipped to a 165 cm2 disc around the array's (N_A) or
    the pair's (K_low) mean centroid, clipped overlaps by 0.25 mm raster; pass if median K_clip / K_unclipped <= 1.01 (1% raster
    tolerance). Lens vs raster: p5.raster_lens (1500 x 1500) on 100 random pairs, max rel. error < 1%. Bound identity:
    max |K_high - 4/(1/N_A1 + 1/N_A2)| < 1e-9. D-sweep (primary, correlated): D in {0,2,4,8,16} mm, random direction per draw, joint
    field over both arrays; K(0) must equal K_low exactly (same normals); monotone if each median >= previous median - 2 bootstrap SE;
    "approach" if |median K(16) / median K_high - 1| < 0.10.
14. Amplitude conditions (40, 80 uA x gamma 0.77/1.43) are run on every configuration defensible at 60 uA (correlated model), no verdict.
15. Capacity (3.9): C_total = K x C_P4(n_PF / K), w 0.162, kappa 0, for K = floor(K_design,low), floor(K_design,high), with n_PF = 48
    (C1, P2) and 26 (P3); pooled reference K = 1. Descriptive.
16. Geometry-only row: BCI03 / CRS08 (identity UNVERIFIED) at the primary settings with f = 0.75, descriptive, not in any count.
17. Downey index: cosine similarity of the two arrays' 5-digit coverage vectors per participant (C1, P2, P3; C2 and P4 descriptive).

## P2c POST-HOC notes (coder-verifier A, added AFTER results were seen; no model change, no verdict change)
- Gain-scaling control FAILED (Delta_HS primary 0.00002 vs predicted g_ss x Delta_HS(g=1) = 0.015). Diagnosis (computed from the
  reported AUCs, not a new run): the |.| detectors respond ~quadratically to a small mean signal in symmetric noise, so d' scales ~g^2,
  not g. D1-only Delta_HS: g=1 0.074, primary 0.0053 = 0.072 x 0.074 (g_ss^2 = 0.074). In addition, max(D1, D2) then selects the
  noise-driven D2 (AUC 0.503, identical for both codes because Z is shared), so the reported Delta_HS collapses to ~0. The prereg's
  linear gain-scaling assumption, not within-episode gain dynamics, explains the departure.
- Precedence as in P2b (item 9): formal ABANDONED (floor twice); decision rule FAIL on primary and on rerun. Both reported.
18. POST-HOC (P5b, added AFTER the results; no rule, model or verdict change):
    a) Gate outcome: V1 failed in 84/84 configurations of BOTH scatter models; the primary also fails V3 (C1: measured union 12 cm2
       < 0.7 x median U_low = 19.2 cm2). The verdict is ABANDONED (prereg sections 4 and 9). All K numbers in RESULTS_P5b.md are
       DESCRIPTIVE (computed over all configurations, gate ignored) and are labelled so in the JSON (rule_all_configs_DESCRIPTIVE).
    b) Diagnostic stage (--stage posthoc, results\p5b_posthoc_v1_reachability.json): differential evolution on the worst-bin V1
       violation shows that V1 AND the V2 r-window are jointly reachable for corr/iso/W20 (g 6.6, sigma_f 24.9, l 11.5, sigma_n 1.7;
       worst violation 0.73 <= 1). The pre-registered least-squares fit prefers a theta that misses the bin-3 tolerance (8.0 +/- 2 mm).
       So the V1 failure comes partly from the fitting objective, not only from the model class. At that theta, V3 still fails for
       C1 (lower bound 17.1 cm2 > 12), so the primary still fails the gate: ABANDONED does not depend on the fit. Not a re-tune; no
       verdict uses it.
    c) The tiny-PF control FAILED for K_low (median 0.71 n_PF; N_A and K_high medians 1.00; the strict linear-map check 1.00).
       Cause: the K_low placement puts array 2's wired sites on array 1's sites (identical wiring maps, same frame, same field), and
       the fitted nugget is ~0 (sigma_n 0.004 mm), so co-located electrodes get coincident centroids. This is a property of the
       pre-registered K_low bound, not of the overlap code (identical-PF, lens, bound-identity and hand-boundary controls pass).
    d) The figure-1 x-axis and the "factor medians" use all configurations (none is defensible); the key name
       factor_medians_defensible is kept for stability, and the JSON field descriptive_basis states this.

## P6 (empirical digit channels, model-free), coder-verifier, cycle 4, written BEFORE any P6 count was computed
Prereg prereg\P6_empirical_channels.md is FIXED. Before writing this I inspected only CSV headers, the set of distinct label values
and the segment table in greenspon2025_ed1_extraction.json (labels + areas); no per-participant/per-digit count was computed.
1. Territory map extended to segment-table tags that never occur in the per-electrode CSV (needed only by Null A and relabelling
   neighbours): palm non-digit tags (Pk-mcp, P0-*) -> PALM; dorsum non-digit tags (P-dr, P-pr, P-pu, P-du) -> DORSUM_HAND;
   wrist 'W' (both surfaces) -> WRIST, a separate class that is never a digit and is NOT counted in the K_terr 6th territory.
   Null A uses the full segment table literally (29 palm + 19 dorsum merged tags, incl. W and the D5 palm tags); a variant without
   W is reported descriptively.
2. Segment-level classes are surface-qualified ("palm:<tag>", "dors:<tag>"); palm and dorsum tags never collide anyway.
3. K_terr class HAND = PALM + DORSUM_HAND pooled (prereg 4a). For level-6 attrition the exact DP runs over 6 disjoint classes
   (D1..D5, HAND). R3 for level 6: an electrode counts for HAND only if every non-empty segment maps to PALM or DORSUM_HAND.
4. Relabelling: exactly round(x N) PF electrodes per draw (sampling without replacement), each gets its R1 dominant segment
   replaced by one of the 3 nearest OTHER segments of the same surface (uniform), using segment-table centroids (cx, cy) and the
   full table as candidates. Territory = map(new tag). CSV centroid fallback is used only if a tag were missing from the table.
5. Attrition MC agreement (C3): |MC - exact| <= 3 SE with SE = sqrt(P(1-P)/20000) at the exact P; if exact P is 0 or 1, MC must
   equal it exactly. Checked for every participant, L in {2..6} (level 6 with K_terr), p in {0.47,0.54,0.62,0.64,0.75,1.0}.
6. Clustered loss: per array, remove PF electrodes in order of Euclidean grid distance (x_mm, y_mm) from a uniformly random wired
   site (ties broken randomly) until ceil(0.38 n_PF,array) PF electrodes are gone. 2,000 draws. Descriptive.
7. C1 shuffle: the "mean cortical distance between same-territory pairs" is computed over within-array pairs, pooled over both
   arrays of a participant; "change" means |diff| > 1e-12; the >= 95% criterion must hold in every participant.
8. C4 nulls: Null B pooled distribution = R1 dominant-segment labels of all PF electrodes of C1+P2+P3 (digit level = its territory
   map). Null draws with N = the participant's PF count. p = P(null N_eff <= observed) (ties counted).
9. "Under what conditions" table: K*(m, p, rule) = highest L with obs K >= L in 3/3 AND min_participant exact P_att(L; p, m) >= 0.8
   (criteria 1-2 only; relabelling and R3 are not recomputed there). Descriptive, no verdict.
10. JHU secondary: pair = left_array_A + left_array_B, PF electrodes only; strict single-hue class; K_finger(m=2), L in {2,3,4}.
    Criterion 1 = observed (1 of 1); 2 = exact attrition p = 0.62; 3 = relabelling x = 0.10 where the neighbour of a hue is an
    adjacent hue in the extraction order red-orange-yellow-green (uniform among 1-2 neighbours; ASSUMES the hue ramp is ordered by
    finger, UNVERIFIED); only single-hue electrodes change (mixed stay mixed); 4 = the strict rule is itself R3-analogous, so
    criterion 4 equals criterion 1. The liberal first-listed-hue variant is descriptive. Right array reported descriptively.
11. K bootstrap: a class counts only if >= m distinct original electrodes are drawn; N_eff bootstrap is the plain resample.
    The bias-corrected inverse Simpson is undefined if every class has size 1 (reported as null).
12. Verdict logic: level L verified iff criteria 1-5 all hold; K* = highest verified L. Levels are checked independently (a
    non-monotone pattern would be reported, not smoothed). Criterion 5 = C1, C2, C3 all pass.

### P6 addendum (coder-verifier, cycle 4 re-spawn), written BEFORE the analysis was run
13. Provenance: items 1-12 above and a 712-line draft of code\p6_empirical_channels.py were left by an earlier coder-verifier
    instance that stopped before running anything (no results\p6* existed). As instructed, I wrote a NEW script at the same path
    (the old draft is kept outside the repo, in the session scratchpad). I ADOPT items 1-12 unchanged; the new script implements them.
14. RNG: one SeedSequence(20260926) spawned into independent streams per analysis (mc, rel, boot, nullA, nullB, shuf, clust,
    joint, jhu, test), so results do not depend on the order of blocks.
15. R3 for K_digit levels: an electrode whose non-empty segments map to more than one territory, or to a digit plus a non-digit,
    is MIXED. An electrode with only palm/dorsum-of-hand segments is HAND (counted only for the level-6 hand class).
16. C3 includes the JHU secondary MC-vs-exact checks (L 2-4, all p); a JHU C3 failure also blocks criterion 5.
17. The C4 "digit-level" null includes WRIST as a class (Null A only; WRIST never occurs in the observed labels).
18. Figure 3 "robust level" markers = highest L in 2..5 with P >= 0.8 per participant (attrition p = 0.62; relabelling
    x = 0.10); 0 if none. Descriptive, the verdict is the ladder.
19. POST-RUN (written after results, no re-tuning): C3 failed on 2 of 108 MC-vs-exact comparisons: P3 L=2 p=0.62 (exact
    0.9999979, MC 0.99995 = 1 miss in 20,000; the item-5 SE at the exact P is 1.0e-5, so one rare event exceeds 3 SE) and JHU L=4
    p=0.64 (exact 0.37532, MC 0.38565, |diff| 3.03 SE). Diagnosis: the exact values match brute-force enumeration to <1e-15 and
    1e6-draw MC gives 0.999998 and 0.374985 (SE 4.8e-4). These are statistical false alarms of the 3-SE rule over 108 tests (and a
    normal SE that is invalid at P ~ 1), not code errors. The prereg verdict rule is applied as written: criterion 5 fails, so
    the formal outcome is "not verifiable: code". The criteria-1-4 ladder is reported alongside as DESCRIPTIVE; it verifies no
    level either (level 2 fails attrition in P2), so the conclusion does not depend on C3. Seeds/streams were NOT changed.
