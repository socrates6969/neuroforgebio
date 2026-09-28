# Independent code review, cycle 1 (P1-P4). Verification gate. 2026-09-26
The reviewer did not modify any script or result. The reviewer's own checks are in code\review\check_p{1,2,3,4}.py, with
stdout in code\review\check_p*_output.txt. Line numbers refer to the scripts as reviewed.

| test | status | verdict as reported | reviewer view |
|---|---|---|---|
| P1 | CONFIRMED (code). The verdict TEXT is misleading | H3 ABANDONED, H3b FAIL | The code is faithful and no bug changes a verdict. Do not quote "open-loop margin suffices". |
| P2 | CONFIRMED (verdict). The post-hoc claim is NOT supported | INCONCLUSIVE | d'_lin ~ 0 is real. About 80% of d'_bio comes from the Weber-variance cue. |
| P3 | CONFIRMED | FAIL (2/48) | An independent re-implementation reproduces the RMSE curves. |
| P4 | CONFIRMED | A PASS, B PASS, C PASS | The closed forms and an independent BA match to 1e-4 bits. C is near-tautological, and A is non-blind and fragile. |

## P1 grip latency (p1_grip_latency.py)
Fidelity: the code follows the prereg equations.
- make_trials L72-96 draws m, mu, c, Poisson pulses, the trapezoid and the OU path. OU is exact (L62-69).
- Grip command with the 0.2 s lead: L200-203.
- Slip physics: L100-105 and L206-208. Drop/crush checks: L210-211.
- Event rule (20 ms gap, noS >= 10): L213-214. Detection update min/max: L225-233. Delivery is exactly tau steps later (L171-195); the self-test confirms 37 steps for 74 ms.
- VIS pooling: L239-263. Reactive hold/decay: L197-198.
- CRN: one trial set is shared by all conditions (L463-465). ART(p=0) is bit-identical to NOFB, and ART(delta=0) gives R = 1.000 exactly, as expected.
- R, delta* interpolation and censoring: L333-344 and L379-381. G0: L488. Redesign and abandonment: L527-537.
- Bootstrap: paired, with SM re-optimised in each resample (L374-376).
- No off-by-one, noise-scaling or CRN violation was found.

Consistency: every verdict string matches the JSON.
- G0 ratio 0.829 > 0.5, so G0 fails. The redesign G0 also fails (0.902/0.948), so the result is ABANDONED.
- H3b ratio 1.023 (CI 1.013-1.034) > 0.8, so H3b FAILS.
- The shuffled-feedback R is 0.059.
- Sensitivity: 0/19 configurations, delta* 6.2-46.3 ms.
- Text error in RESULTS_P1_P2.md: "G0 fails in 0/1000 bootstrap resamples". The JSON has G0_boot_frac_holds = 0.0, so it should read "G0 HOLDS in 0/1000".

Zero-perturbation diagnosis: CONFIRMED (check_p1.py).
- Analytic bound: with no noise and no lag, NOFB at K = 0 fails whenever 1+SM < 0.75/mu (slip) or 1+SM > 0.75c/mu (crush).
- Monte Carlo over mu ~ U(0.3,1.2) and c ~ U(1.6,2.5) gives a minimum failure rate of 0.390 at SM = 0.3. Even a continuous SM cannot get below 0.391, and the pass limit is 0.01.
- The coder's simulate() with noise 0 gives F*_NOFB = 0.395 at SM 0.3, which matches the analytic value. So the failure comes from the prereg's parameters, not from the code.
- Pinning mu to the prior (0.75) gives F* = 0.000 for both NAT and NOFB. This is direct evidence that the code is correct and that the mismatch between the friction prior and the friction range is the cause.
- Nuance on the NAT failure (0.089 in the JSON; 0.071 at N = 1000 here):
  - With noise 0, NAT still fails 0.021. These are drops of low-mu trials before the 74 ms feedback plus tau_m can act, not only crush.
  - The crush part (0.047) appears only when noise is on: 5% OU noise peaks on a grip set by the prior.
  - So "trials with high mu crush" is right for the crush share. NAT would still fail the <= 0.01 sanity check even with no noise.

Interpretation risk (not a code bug):
- The prereg's canned abandonment text, "open-loop margin suffices", is contradicted by the data: F*_NOFB = 0.74.
- The correct whitepaper statement is: "H3 not testable: the P1 model fails its own zero-perturbation control". Redesign is the mathematician's call.

## P2 biomimetic vs linear (p2_biomimetic_info.py)
Fidelity:
- Episodes and step thinning: L31-94. Encoders: L98-110. Charge matching raises alpha' on the grid per section 2: L125-133.
- Adaptation (exact): L154-163.
- Calibration: L172-199. It is analytic and correct: Var(sum y) = n_T * sum (w r + sigma0)^2. The coder's MC self-test and the reviewer's recalculation agree (w_inf = 0.2155).
- Noise: L202-205, i.e. s_t = sqrt(n_T)(w r + sigma0). This is the literal prereg noise.
- D1/D2 windows: L209-221. D2 uses k+10..k+20 against k-20..k; D1 takes the max over k..k+20.
- Mann-Whitney AUC with weights: L224-231. It is checked against brute force.
- Verdict rule: L315-319. Controls: L414-432.
- Hold-force target is F_hold, read literally (L284). The true-force secondary gives a ratio of 1.03, which leaves the RMSE criterion unchanged.

Consistency:
- The d' ratio CI is [-212, 327], which contains 1.3, so the result is INCONCLUSIVE, as the rule requires.
- The abandonment rule is correctly not triggered: the best bio AUC is 0.649, which is not below the 0.55 floor.

d'_lin ~ 0 is not a bug (check_p2.py):
- An independent noise draw and independent D2 arithmetic give a linear |D2| AUC of 0.506 (d' 0.021). The coder reports 0.505 (0.017).
- Analytic view: the mean linear step signal is 7.3 uA, and the sd of the D2 difference is 53 uA, so SNR = 0.13. Folding by |.| leaves AUC ~ 0.50. Even a signed detector on increases only reaches d' 0.16.
- Refinement of the coder's wording: the cause is not the sqrt(n_T) factor itself. After recalibration, the per-sample sd at r = 62 uA is 143.6 uA for T_train = 0.5, 1 and 2 s alike.
- The real cause is the combination the prereg fixes: white 10-ms noise calibrated to a 1-s-train JND of 13.5 uA, detected in 50-200 ms windows with a two-sided |.| score.
- Counterfactual, not the prereg: dropping sqrt(n_T) without recalibrating would give d'_lin 0.72.

NEW finding, which blocks the post-hoc claim:
- Most of d'_bio is the Weber variance cue, not transient information.
- With the same encoders and the coder's detectors (encoder_eval), homoscedastic noise at the same mean per-sample sd (139 uA) gives d'_bio 0.10 against 0.52 under Weber noise. So about 80% of the "biomimetic advantage" comes from event windows being noisier.
- Also, d'_bio barely responds to w in the Weber model (0.52 / 0.62 / 0.90 at w x1 / 0.5 / 0.25), while in the homoscedastic model it scales roughly as 1/noise.
- The post-hoc line "the biomimetic code is clearly more detectable (difference 0.52, CI 0.48-0.56)" must NOT go into the whitepaper as evidence for H1. The coder's caveat in DEVIATIONS.md undersells how large the effect is.

## P3 psi vs staircase (p3_psi_calibration.py)
Fidelity:
- Observer and alpha from theta75: L43-86.
- Psi grid: 40 alpha x 10 beta, lam 0.02, uniform prior in log (L90-103).
- Expected entropy in closed form: L106-114. The algebra is correct, and the coder's brute-force check error is 9e-15.
- Posterior update and estimator exp(E[log theta75]): L117-141.
- 3-down-1-up staircase with reversal estimator: L145-176. N_req interpolation: L180-189. Savings rules: L199-205.
- Decision rule: L243-281. Control rule: L434-449. Lapse follow-up trigger: L485.
- Documented choices: 1.26 is used from the step at the 2nd reversal onward, and the internal level is unrounded. Neither choice can move 2/48 up to 36/48.

Independent re-implementation (check_p3.py):
- It uses a direct posterior, brute-force expected entropy and a scalar staircase, written from the prereg text only.
- It was run on 4 cells: (20,3,.02), (31.5,6,0), (10,1.5,0) and (50,3,.05).
- The RMSE curves agree with the coder's within MC noise. At N = 60, for example, psi is 0.164 vs 0.177 and the staircase is 0.136 vs 0.157.
- Psi bias at N = 60 agrees: -0.057 vs -0.059 and -0.082 vs -0.077.
- Psi is not better than the staircase in these cells, the same as the coder found. The FAIL (2/48, CI 1-3) is far from the 36/48 threshold.
- The bias criterion passes (max 0.086 < 0.0953), and the control and lapse abandonment rules are correctly not triggered (19 and 5 cells).
- Note: the -6 to -8% psi bias appears even in the model-matched cell. It shrinks with N (the self-test gives -0.3% at 600 trials), which is consistent with prior shrinkage and not a bug.

## P4 pooling capacity (p4_pooling_capacity.py)
Fidelity:
- s_of_w: L39-40. N(M): L43-44. M*: L47-48. kappa_hat: L51-52. Model K: L55-58.
- BA with lower/upper bounds: L76-98. Parts A, B and C: L154-240. Pass checks: L167-168 and L196.

Check (check_p4.py):
- Closed forms reproduce:
  - kappa_hat 0.2615 / 0.0794 / -0.2443 / -0.4559.
  - N4(kappa=0) 22.51 / 20.23 / 17.83 / 16.84.
  - M* 81.1 / 239.9 / 1648 / 5806.
  - Model K 52.25 / 54.42 / 61.77.
- An independent BA on a different grid (300 x 900, 15000 iterations) gives C(1) = 1.8082 and C(64) = 3.3066, so dC = 1.4984. The coder has 1.8082, 3.3066 and 1.4984. The verdicts PASS/PASS/PASS match the JSON.

Caveats that do not change the verdicts:
- C: the M = 1 integer count is 10 against an analytic 11.0 (-9.1%, limit 10%). The margin is thin by construction, because an analytic 11.0 floors to 10 whenever any measured w exceeds 0.162. The MC also simulates y = ln(sum a) + noise with sum a = Q, which only re-derives the JND-to-s conversion, as the coder notes.
- B: M* = 81 at w = 0.128 is only slightly above 64.
- A: A is non-blind (disclosed) and fails under N(1) = 7 or 14, Q_max = 80 and both Weber violations. Report it only as "consistent with".

## Bottom line for the queen
- No coding bug changes any pre-registered verdict.
- Before anything reaches the whitepaper:
  - P1: replace "open-loop margin suffices" with "model failed its own sanity control; H3 untested". Fix the G0 bootstrap typo.
  - P2: drop or heavily qualify the post-hoc "biomimetic clearly more detectable" claim, since about 80% of it is a variance artifact.
  - P4: present A as a non-blind consistency check only.
