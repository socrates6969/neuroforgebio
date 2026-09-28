# P2b: Biomimetic vs linear ICMS encoding: well-posed d' difference plus a Weber-variance-cue control (H1, cycle 2)
Status: PRE-REGISTERED 2026-09-26 by mathematician (cycle 2). Fixed before any P2b code is run. Simulation only. Amplitudes (uA) are
model units anchored to published psychophysics; they are not proposed stimulation settings.
Parent: prereg\P2_biomimetic_info_per_charge.md (NOT edited). Everything not listed under "Changes" is identical to P2 (model,
trajectories, encoders, charge-matching rule incl. the alpha' grid raise, adaptation, noise calibration to JND 13.5 uA, detectors
D1/D2, null windows, AUC -> d', hold-force RMSE, bootstrap, sensitivity list, coder interpretations in code\DEVIATIONS.md P2 1-14).

## 0. Changes vs original and why (POST-HOC redesign; evidence is weaker than a blind test)
Written AFTER seeing cycle-1 results (code\RESULTS_P1_P2.md): P2 was INCONCLUSIVE because d'_lin = 0.017 (per-10-ms Weber noise sd
~144 model-uA vs a ~7.5 uA linear step), so the ratio d'_bio/d'_lin had CI -212 to 327. The coder's POST-HOC descriptive numbers are
known to me: d'_bio 0.54 (CI 0.50-0.58), d'_lin 0.02, difference 0.52 (CI 0.48-0.56); RMSE ratio 1.022. The coder also flagged that
Weber (signal-dependent) noise makes variance itself a cue for |.|-detectors (synthetic +7.6 uA step: AUC 0.58 with Weber noise vs
~0.51 with constant noise). Changes:

| # | Change | Why |
|---|---|---|
| C1 | Primary metric: Delta = d'_bio - d'_lin (charge-matched, tau_ad = inf). The ratio is reported descriptively only. | The ratio is undefined when d'_lin ~ 0. A difference is well posed at the floor. |
| C2 | Pre-set minimum effect size Delta_min = 0.30 d' units. | Convention for a small-to-medium effect in d'. It is set BELOW the known cycle-1 value 0.52, so for the Weber arm the criterion is known in advance to be met: that arm is a regression check, not evidence (stated honestly). |
| C3 | NEW variance-cue control arm "frozen variance" (FV): s_t = sqrt(n_T) * (w * rbar_ep + sigma0), where rbar_ep is the mean of r over that episode's contact samples (a > 0) for that encoder; same w, same Z matrix (CRN). | Removes all within-episode variance modulation, so a detector can only use mean shifts, while each encoder keeps its own average noise power. Under charge matching, mean r is equal across encoders on average, so average noise is matched. |
| C4 | NEW secondary control arm "homoscedastic" (HS): s_t = sqrt(n_T) * sigma_h, sigma_h = 13.5 / (Phi^-1(0.75) * sqrt 2) = 14.15 uA (calibrated to the same JND at 60 uA with constant noise; Gaussian link, see AUDIT row 78). | A second way to remove the variance cue, independent of rbar. |
| C5 | Decision now needs the FV arm (C3), not only the Weber arm. | The mechanism claim (transients carry mean information per unit charge) must survive removal of the variance cue. |
Not changed: seed 20260926 (so the Weber arm must reproduce the cycle-1 numbers: a built-in code regression check), N = 4000, detectors,
200-ms deadline (the question is fast event detection for grip correction), RMSE criterion, abandonment and controls of P2.
Rejected option: a 1-s train-level integrated detector. Steps are >= 300 ms apart, so 1-s windows would mix events; changing the
step statistics would change the question. It may be run as EXPLORATORY only (no verdict).

## 1. Hypothesis (H1, restated)
At matched mean charge, tau_ad = inf, a biomimetic code gives more information about force changes within 200 ms than a linear code,
through mean (not variance) signals, at an acceptable hold-force cost.

## 2. Decision rule (primary: charge-matched, tau_ad = inf; 95% CIs by bootstrap over episodes, 1000 resamples, paired)
- Regression gate R0: Weber arm Delta within 0.02 of 0.52 and d'_bio within 0.02 of 0.542. If not, stop: the code differs from cycle 1.
- PASS iff ALL: (a) Weber arm: lower 95% CI of Delta >= 0.30; (b) FV arm: lower 95% CI of Delta_FV >= 0.30; (c) Delta_FV >= 0.5 *
  Delta_Weber (point estimates; i.e. the variance-cue share V = 1 - Delta_FV/Delta_Weber <= 0.5); (d) RMSE_bio/RMSE_lin <= 1.5 (Weber arm).
- FAIL iff: upper 95% CI of Delta_FV < 0.30, OR V > 0.5, OR RMSE ratio > 1.5. Label a FAIL with V > 0.5 as
  "biomimetic advantage is a Weber-variance artefact".
- INCONCLUSIVE otherwise (e.g. the Delta_FV CI contains 0.30).
- HS arm: reported with the same statistics; if HS and FV disagree on PASS/FAIL, report "variance-control dependent" and downgrade a
  PASS to INCONCLUSIVE.
- Always report: all d', AUCs, ratios (descriptive), increases vs decreases separately, D1 vs D2 chosen, tau_ad sweep for all three
  noise arms (exploratory).

## 3. Predictions (before any P2b code runs)
- R0: Delta_Weber = 0.52 (reproduction).
- FV arm: Delta_FV ~ 0.60 (plausible 0.35-0.90). Reason: at matched mean charge, rbar is equal across encoders, and the biomimetic
  transient (~50-75 uA above baseline for 5-10 samples) now faces noise set by rbar (lower than at the transient peak under Weber
  noise), so the mean-shift signal gains more than the lost variance cue. d'_lin_FV stays ~0 (the 7.5 uA sustained shift vs per-sample
  sd ~140 is unchanged in order of magnitude).
- HS arm: Delta_HS ~ 0.65 (0.35-0.95). V ~ -0.15 (negative: the variance cue was not helping on net).
- RMSE ratio ~1.02. Predicted verdict: PASS (probability ~0.7). Main risk: the Weber transient's variance cue is larger than I think
  (then V > 0.5 and FAIL).
- Caveat stated in advance: even on PASS, d'_bio < 1, i.e. neither code detects 10-30% steps reliably in 200 ms under this noise model.
  A PASS says "better per unit charge", not "good enough".

## 4. Null / control
P2 controls kept: beta' = 0 control (must not reach Delta >= 0.30), noise-free control (both AUC > 0.99), label shuffle (AUC ~0.5).
NEW: FV and HS arms (above); a "variance-only probe": zero the mean change of the step (a stays at the pre-step value) but keep the
noise sd time course of the biomimetic Weber arm; its d' is the variance-cue d' and is reported (expected ~0.2-0.3).

## 5. Abandonment
If in the FV arm both encoders have AUC < 0.55 (floor), rerun FV once with step sizes U(0.3, 0.6) (as P2 section 6). If still at the
floor, abandon H1 in this noise model: "at the published JND with per-bin noise, 200-ms step detection is not measurable for either code".

## 6. Outputs and budget
code\p2b_biomimetic_diff.py (may import code\p2_biomimetic_info.py), code\results\p2b_biomimetic_diff.json,
code\figures\p2b_delta_dprime.png/.svg. Three noise arms x 7 tau_ad; cycle-1 main run was 290 s, so run the tau_ad sweep for FV/HS in
a second invocation if needed. < 10 min per invocation, < 1 GB.
