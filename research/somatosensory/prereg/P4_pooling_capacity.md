# P4: Channel capacity of amplitude-coded ICMS and the limit of multi-electrode pooling (H2)
Status: PRE-REGISTERED 2026-09-26 by mathematician. Theory and simulation on published psychophysical summary numbers.
DISCLOSURE: before writing this file I computed the headline analytic prediction (20.2 levels for quartets vs the
observed 19.5). Part A is therefore a consistency check, NOT a blind test. Parts B-C are not yet computed.

## 1. Hypotheses
A (pooling model). Perceived intensity depends on pooled charge Q = sum_i a_i with Weber noise. The detection threshold in
pooled charge scales as Q_thr(M) = A_thr * M^kappa. Full spatial summation (kappa = 0) predicts the quartet gain in
discriminable levels reported by Greenspon 2025. No summation (kappa = 1) predicts none.
B (capacity). The Shannon capacity per symbol of a single pooled amplitude channel grows only as log2 of a quantity linear in
ln M. Matching natural force resolution (45-50 levels, Greenspon 2025) by pooling alone needs > 64 electrodes for every
w in the reported biomimetic JND IQR.
C (verification of the math). A Monte Carlo 2AFC simulation of the pooled observer reproduces the analytic level count
within 10%.

## 2. Model and parameters
- Levels: N(M) = ln(Q_max(M)/Q_thr(M)) / ln(1 + w), with Q_max = 100*M uA (each electrode capped at 100 uA, as used by
  Greenspon 2025 for level counting). Hence N(M) = N(1) + (1 - kappa) * ln M / ln(1 + w).
- Inputs (Greenspon 2025, PMC12176618, exact): single-electrode biomimetic levels N(1) = 11; quartet levels 19.5 (M = 4);
  biomimetic median JND 9.7 uA at a 60 uA standard (IQR 7.7-16.1), giving w = 0.162 (IQR 0.128-0.268); flat/linear
  median JND 13.5 uA, giving w = 0.225; natural levels 45-50 (use 47.5).
  Fig. 7e legend (re-read in the full text): levels for linear single-electrode, biomimetic single-electrode and biomimetic quartets are
  n = 22, 22, 8 with medians 8, 11, 19.5. The main text gives a median of 7 (range 2-14) for flat trains on n = 35 electrodes.
  CAVEAT: Greenspon computed levels assuming a constant w, so part A tests internal consistency of pooling within their own convention.
- Competing model K (constant absolute JND, no Weber law). This follows the monkey report of an amplitude JND of ~30 uA that is
  roughly constant from 30-100 uA standards (Kim 2015, PMID 26504211, per neurobiologist's facts; I only opened the abstract).
  K predicts N(M) = (100*M - Q_thr)/JND_Q, with JND_Q fixed by N(1) = 11 and Q_thr = A_thr in {20, 24, 35} uA.
  This gives a roughly linear gain with M.
- Noise model for B/C: log-intensity channel. Input x = ln Q in [ln Q_thr, ln Q_max]; output y = x + N(0, s^2), with
  s = ln(1 + w) / (Phi^-1(0.75) * sqrt(2)) (JND = 0.6745 * sqrt(2) * s for a two-stimulus comparison).

## 3. Computations
A. kappa_hat = 1 - (19.5 - 11) * ln(1 + w) / ln 4 for w in {0.128, 0.162, 0.225, 0.268}. Also the predicted N(4) at kappa = 0 and 1.
B. For M in {1, 2, 4, 8, 16, 32, 64, 256, 1024}, kappa in {0, 0.25, 0.5} and the four w values: compute the capacity C(M) in bits/symbol with
   Blahut-Arimoto (input grid 400 points, output grid 800 points over x range +/- 5 s, convergence 1e-6 bits). Also compute
   log2 N(M) and M* = exp((47.5 - N(1)) * ln(1+w) / (1 - kappa)). Bits/s = C / T_sym for T_sym in {0.1, 0.2, 0.5, 1} s
   [ASSUMPTION: the JND is assumed independent of train duration here. Kim 2015 (PMID 26504211) reports that duration matters, but its numbers were not opened, so this is flagged].
   Compare with K independent channels of M/K electrodes: total C = K * C(M/K), for E = 64 electrodes and K in {1, 2, 4, 8, 16}.
   Each group must satisfy N(M/K) >= 2, otherwise that channel counts as 0 bits. Independence is an ASSUMPTION (overlapping projected fields break it).
C. Monte Carlo: for M in {1, 4, 16} and w = 0.162, simulate 2AFC comparisons of pooled log-intensities with noise s. Measure the JND at 5
   standards spanning the range, then count levels by stepping from Q_thr upward by the measured JND until Q_max. 20000 trials per psychometric point.

## 4. PASS/FAIL
- A PASS: kappa = 0 prediction N(4) with w = 0.162 lies in [15.6, 23.4] (+/-20% of 19.5) AND the kappa = 1 prediction (11) lies outside
  that interval AND kappa_hat is in [0, 0.3] for w = 0.162 AND model K's prediction for N(4) lies outside [15.6, 23.4] for all
  three Q_thr values (the Weber pooling model is then preferred over constant-JND pooling). FAIL otherwise. If model K fits and Weber
  pooling fails, report "pooling gain is linear", which reverses the conclusion of B.
- B PASS: M* > 64 for all four w at kappa = 0 AND C(64) - C(1) < 2 bits/symbol at w = 0.162, kappa = 0. FAIL otherwise.
- C PASS: Monte Carlo level counts within 10% of analytic N(M) for all three M. FAIL means the analytic formula or the
  JND-to-s conversion is wrong, and A/B must be recomputed with the Monte Carlo counts.

## 5. Why not guaranteed / limits
- A uses two published numbers from different analyses. It could have missed; it was checked non-blind (disclosed above).
- B's capacity depends on the input range in log units and on s, which is not a simple function of N. Blahut-Arimoto can exceed
  log2 N (N is a conservative 1-JND spacing) or fall below it. The "< 2 bits" threshold is a genuine prediction.
- C can fail if the 75% JND convention and the level-counting convention disagree by more than 10%.

## 6. Sensitivity
N(1) in {7, 11, 14} (7 = flat median, 14 = max of the flat range); Q_max per electrode {80, 100} uA; w varying with Q
(Weber violation: w(Q) = w0 * (Q/60)^(-0.2) and ^(+0.2)) [ASSUMPTION]; frequency as an extra dimension: add a second independent
channel with Weber fraction 0.15 over 20-50 Hz (Callier 2020, PMID 31879342: w 0.15 -> 0.5 between 50 and 100 Hz; monkey data;
the range is ASSUMPTION) and report the added bits.

## 7. Abandonment
If C fails and the corrected A also fails, abandon the total-charge Weber pooling model as a description of the Greenspon data
and post to BOARD asking neurobiologist for the Fig. 7 quartet JNDs, so that kappa can be fitted directly.

## 8. Null / control
kappa = 1 (no summation) is the built-in null for A. For B, the K = 1 (all pooled) vs K > 1 (independent) comparison is the
control for "pooling vs spatial coding". Blahut-Arimoto sanity check: for a Gaussian channel with a large uniform input range,
C should lie between log2(range/(s*sqrt(2*pi*e))) - 0.2 and 0.5*log2(1 + range^2/(4 s^2)) bits (high-SNR peak-limited bounds).

## 9. Outputs
code\p4_pooling_capacity.py, code\results\p4_pooling_capacity.json, code\figures\p4_capacity_vs_M.png. Runs in seconds to minutes.
