# P2c: Biomimetic vs linear encoding under variance-controlled noise with MEASURED adaptation (H1'', cycle 3)
Status: PRE-REGISTERED 2026-09-26 by mathematician (cycle 3). BLIND: fixed before any P2c code runs. I have NOT opened
code\RESULTS_*, code\REVIEW_*, code\results\* or result lines on BOARD.md. Simulation only; amplitudes (uA) are model units
anchored to published psychophysics, not proposed stimulation settings.
Parents: prereg\P2_biomimetic_info_per_charge.md and prereg\P2b_biomimetic_dprime_difference.md (NOT edited). Everything not listed
here is identical to P2/P2b: force trajectories, encoders, charge matching (incl. alpha' raise rule), detectors D1/D2 (better per
encoder), null windows, AUC -> d', hold-force RMSE, paired bootstrap (1000), N = 4000 episodes, dt = 10 ms, seed 20260926.

## 0. Disclosure (what I know)
- Queen: "P2b found that Weber-noise variance creates a spurious biomimetic cue, so test only under variance-controlled noise".
- theories.md (queen, allowed): the cycle-1 independent review found d'_bio ~ 0.10 under homoscedastic noise at tau_ad = inf
  (vs 0.54 under Weber noise). My predictions use this; they are therefore partly informed. I do NOT know P2b's FV/HS numbers.
- Changes vs P2b: (C1) Weber arm dropped (only frozen-variance FV and homoscedastic HS arms); (C2) adaptation taken from human
  PERCEPTUAL data (primary) and neuronal data (secondary) instead of an assumed tau grid; (C3) episodes run as a continuous
  session so slow adaptation can reach steady state; (C4) PASS rule as specified by the queen (Delta >= 0.30, CI lower > 0).

## 1. Hypothesis
Under variance-controlled noise and measured adaptation, at matched mean charge, the biomimetic code gives a larger 200-ms
force-step detection d' than the linear code by Delta = d'_bio - d'_lin >= 0.30.

## 2. Adaptation models
### 2.1 PRIMARY: perceptual divisive gain, fitted to Hughes 2022 (the observer is perceptual, so its timescale must be)
Gain state g in (0, 1], percept drive r(t) = g(t) * a(t).
  dg/dt = - g * (a/60)^p / tau_a  +  (1 - g) / tau_r        (a = 0 -> recovery only)
Fit (DERIVED by me, disclosed): least squares of the train-mean g, normalised to train 1, to the DIGITISED Hughes 2022 Fig 3B
intermittent curve (notes\published-derived\hughes2022_fig3b_intermittent_DIGITISED.csv; 1 s on / 5 s off x 50, then 1 s on / 61 s off x 5;
100 Hz, 60 uA, so a/60 = 1 during trains), dt = 10 ms, all 42 points (adaptation + recovery):
  tau_a = 14.6 s of on-time (approx. 95% CI 12.8-16.7), tau_r = 120 s (102-141), RMSE 0.046.
  Fitted end of adaptation 0.438 (quoted 43.5 +/- 10%). Known misfits, stated now: recovery end 0.885 vs quoted 72.6% (a slower
  component is missing), and continuous 100 Hz at 5 s gives 0.72 vs quoted "unchanged" (median; drop onset 8.3 s DIGITISED), at
  15 s 0.39 vs quoted 64 +/- 36%. So the model adapts too early under continuous drive and recovers too fast.
  The coder re-fits this with the same data and procedure as gate A0 (section 5).
Mapping choices [ASSUMPTION unless quoted]:
- Frequency: P2 codes amplitude at a fixed rate; Hughes found intermittent adaptation did not differ between 20, 100 and 250 Hz
  (p >= 0.05, quoted), so the 100 Hz fit is used as is.
- Amplitude dependence of the drive: exponent p = 1 (charge-rate proportional), sensitivity p in {0.5, 2}. Not measured anywhere opened.
- Session: episodes are concatenated with an inter-episode gap G of a = 0 (primary G = 3 s; sensitivity {1, 10} s), a warm-up of
  600 s (5 tau_r) of episodes is discarded, and g carries over between episodes (continuous prosthesis use). Encoders run in
  separate sessions with common trajectories.
- JND calibration is done UNADAPTED (g = 1), because Greenspon 2025 measured JNDs with 1-s trains and Greenspon 2024 advises long
  inter-trial intervals (> 3 s) to limit interactions. Sensitivity: calibrate at the steady-state g of the linear code.
- Noise arms (P2b C3/C4): FV s_t = sqrt(n_T) (w * rbar_ep + sigma0) with rbar_ep = mean of the ADAPTED r over the episode's contact
  samples; HS s_t = sqrt(n_T) * sigma_h. w and sigma_h calibrated to JND 13.5 uA at 60 uA (as P2b).
Expected steady state (my arithmetic): contact ~2 s per 6 s cycle (duty ~0.33), a/60 ~ 1 -> g_ss ~ 1/(1 + (tau_r/tau_a) x 0.33)
~ 0.27 for both codes when charge-matched and p = 1.

### 2.2 SECONDARY (pre-specified, separate verdict): neuronal fast depression
P2's subtractive model: dz/dt = (k_ad * a - z)/tau_n, r = max(a - z, 0), JND recalibrated per condition (as in P2).
tau_n primary 0.04 s = geometric mean of the quoted 10-150 ms post-pulse suppression (Sombeck 2022, NHP); grid {0.01, 0.04, 0.15} s.
k_ad primary 0.5, grid {0.25, 0.5, 0.9} [ASSUMPTION: bounded by mouse "rapidly adapting" < 85% at 1 s (Hughes & Kozai 2023),
i.e. k >= 0.15, and the natural onset/sustained median 12 (Callier 2019), i.e. k <= 0.92].
Why this mapping is secondary and how it is justified: (i) the depression acts on cortical drive before the percept readout, which
is where P2's z sits; (ii) sub-second depression is INVISIBLE in Hughes 2022 (slider motor lag 1-2 s, quoted) and is absorbed by the
1-s-train JND calibration, so it is neither contradicted nor constrained by perceptual data; (iii) it is measured in animals
(NHP, mouse), not in the human percept. It is the only mechanism here that acts within the 200-ms detection window (the perceptual
gain changes by < 2% in 200 ms at tau_a = 14.6 s), so it is where a transient advantage could appear.
Combined arm (2.1 x 2.2 at primaries): descriptive only.

## 3. Decision rule (primary: charge-matched, perceptual model 2.1 at fitted tau_a, tau_r, p = 1, G = 3 s)
- PASS iff in BOTH FV and HS arms: Delta >= 0.30 AND paired-bootstrap 95% CI lower bound of Delta > 0, AND RMSE_bio/RMSE_lin <= 1.5
  (per arm).
- FAIL iff in both arms Delta < 0.30 with CI upper bound < 0.30, OR RMSE ratio > 1.5 in either arm.
- FV and HS disagree -> "variance-control dependent" = INCONCLUSIVE. Anything else -> INCONCLUSIVE.
- Robustness (one-at-a-time sensitivity, N = 1000 each): tau_a {7, 30} s, tau_r {60, 600} s, p {0.5, 2}, G {1, 10} s, JND calibrated
  adapted: 9 rows + primary = 10. "VERIFIED" requires the same call in >= 7 of 10.
- Secondary neuronal verdict, same rule, at tau_n = 0.04 s, k_ad = 0.5; robustness over the 3 x 3 grid (>= 70%).
- Always report: d'_bio, d'_lin, AUCs, increases vs decreases, g_ss per encoder, D1 vs D2 chosen, peak-matched variant
  (descriptive: at 69% charge the biomimetic code should adapt less; labelled "charge-saving effect", not H1).

## 4. Predictions (before any P2c code runs)
- A0 re-fit: tau_a 14.6 s, tau_r 120 s (+/- 10%). g_ss (primary) ~ 0.27 (0.2-0.45), bio and lin within 0.03 of each other.
- R0 (g = 1): FV and HS d' equal P2b's FV and HS tau = inf values (same seed) within 0.02.
- PRIMARY perceptual: Delta_HS ~ 0.03 (plausible -0.02 to 0.10): under HS, divisive gain scales both signals by g_ss while noise is
  fixed, so Delta_HS ~ g_ss x Delta_HS(inf) ~ 0.27 x ~0.08. Delta_FV ~ 0.07 (0.0 to 0.20): FV noise shrinks with the adapted rbar,
  so d' is roughly gain-invariant (factor ~0.85 via sigma0). Verdict: FAIL. P(PASS) ~ 0.05.
- p = 2 lowers Delta (the peaky bio code adapts more); p = 0.5 raises it slightly; neither reaches 0.30 (P > 0.8).
- SECONDARY neuronal (0.04 s, k 0.5): the high-pass plus JND recalibration boosts transients relative to the calibrated sustained
  level by up to 1/(1-k) = 2, more for the brief bio transient than for the linear step. Delta_HS ~ 0.12 (0.03-0.30), Delta_FV ~ 0.12.
  At k 0.9: Delta ~ 0.25 (0.05-0.6). Verdict at primary: FAIL or INCONCLUSIVE; P(PASS) ~ 0.2 (primary), ~ 0.4 at k 0.9.
- Peak-matched descriptive: g_ss(bio) > g_ss(lin) by ~0.05-0.1; Delta_HS ~ +0.05.
- Caveat stated now: even a PASS says "better per unit charge", and d'_bio < 1 means neither code detects 10-30% steps reliably in
  200 ms under this noise model.

## 5. Gates and abandonment
- A0 (adaptation model gate): re-fit RMSE <= 0.06 and fitted end-of-adaptation within 0.435 +/- 0.10. If A0 fails, the primary
  verdict is not issued; report the tau grid descriptively. Out-of-sample check, descriptive only: predicted vs DIGITISED burst
  medians (Fig 2B, 100/200/500-ms bursts, 50% duty) at 20 s and 30 s.
- R0 (regression): if g = 1 does not reproduce P2b FV/HS within 0.02, stop: the code differs from P2b.
- Floor: if both encoders have AUC < 0.55 in both FV and HS arms (primary), rerun once with steps U(0.3, 0.6). If still at floor,
  ABANDON H1 under variance-controlled noise: "200-ms mean-change detection at the published JND is not measurable for either
  code"; the biomimetic question then moves to naturalness or charge endpoints, not d'.
- If the secondary neuronal arm PASSes but the primary FAILs, the report must say: "any biomimetic benefit depends on unmeasured
  sub-second neuronal depression in humans"; this is NOT a design recommendation. Requires IRB/FDA-approved clinical study to test.

## 6. Null / controls (each can fail)
- Identical-encoder null: bio := lin in both sessions -> Delta CI must contain 0 (checks that adaptation handling is symmetric).
- Variance-only probe (P2b): mean step zeroed, noise time course kept -> under HS and FV its d' must be < 0.05 (checks that the
  variance cue is really removed; this is exactly the cue that invalidated P2).
- beta' = 0 control (charge-matched sustained-only code) must not reach Delta >= 0.30; noise-free control: both AUC > 0.99;
  label-shuffle: AUC 0.5 +/- 0.02.
- Power check (descriptive): HS with sigma_h / 4 at g = 1 -> reports whether Delta can reach 0.30 at all in this pipeline.
- Gain-scaling check: under HS, primary Delta must equal g_ss x Delta(g = 1) within 25%; a larger departure means within-episode
  gain dynamics matter and must be explained in the report.

## 7. Why the result is not fully guaranteed by construction (and where it partly is)
Partly by construction: with p = 1, charge matching and HS noise, divisive slow gain scales both codes nearly equally, so the
primary HS Delta is close to g_ss x Delta(inf). I state this in advance; the primary arm is therefore a test of whether measured
human adaptation CREATES a differential advantage, and I predict it does not. Not guaranteed: (i) FV noise follows the adapted
rbar, so gain partly cancels; (ii) p != 1 makes adaptation depend on the code's peakiness; (iii) g varies within and across episodes
differently for the two codes; (iv) the neuronal high-pass with recalibration can favour either code (linear step onsets also become
transients); (v) the controls above can fail.

## 8. Outputs and budget
code\p2c_biomimetic_adapt.py (may import code\p2_biomimetic_info.py / p2b code), code\results\p2c_biomimetic_adapt.json,
code\figures\p2c_delta_by_arm.png/.svg. Session loop: ~4000 x 6 s at 10 ms = 2.4e6 gain updates per encoder (vectorise over 16
parallel sessions of 250 episodes). Primary + 9 sensitivity rows at N = 1000 + 9 neuronal rows: < 10 min per invocation, < 1 GB;
split into two invocations if needed. numpy/scipy only; seed 20260926.
