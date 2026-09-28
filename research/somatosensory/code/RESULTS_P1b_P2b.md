# Results P1b and P2b (coder-verifier A, cycle 2, 2026-09-26)
Simulation only, in model units (no stimulation settings). Seed 20260926. Python venv (numpy, scipy, matplotlib). Each run was under 4 min and under 1 GB.
Scripts: code\p1b_grip_latency_v2.py and code\p2b_biomimetic_ddprime.py. They import the cycle-1 scripts read-only; the cycle-1 files are unchanged.
Interpretations: code\DEVIATIONS.md, sections P1b and P2b, were written before any result. The post-hoc notes were added after and are marked.
Self-tests: P1b 11/11 PASS (results\p1b_selftest.json). P2b 15/15 PASS (results\p2b_selftest.json). Each includes the cycle-1 helper tests.
Both preregs are post-hoc redesigns, so the evidence is weaker than a blind test would give.

## P1b: grip latency budget v2 (H3, H3b). Result: H3 ABANDONED; H3b FAIL
- G_Z hard gate (K = 0, N = 4000): PASS. F*_NOFB = 0.00125 (CI 0.00025-0.0025) and F*_NAT = 0.00025 (CI 0-0.0005), both at SM 0.2.
  The prediction was <= 0.002; it holds. The friction-model repair works.
- Reference config (cycle-1 friction model): F*_NOFB(K=0) = 0.498 (CI 0.481-0.512). The target was 0.498 +/- 0.03, so the regression check PASSES.
  In self-tests, the reference simulate() is also bit-identical to cycle 1.
- Main run (N = 4000, SM optimised per condition, 95% CI from 1000 bootstrap resamples):
  | condition | F* | 95% CI | SM_opt | drop / crush |
  |---|---|---|---|---|
  | NOFB | 0.398 | 0.382-0.413 | 0.6 | 0.161 / 0.237 |
  | NAT (74 ms, p 0.95) | 0.593 | 0.580-0.609 | 0.7 | 0.015 / 0.578 |
  | VIS 200 ms | 0.475 | 0.459-0.489 | 0.6 | 0.150 / 0.324 |
  | ART +100 ms, p 0.95 | 0.593 | 0.580-0.609 | 0.7 | 0.066 / 0.527 |
  | shuffled | 0.593 | 0.580-0.608 | 0.7 | |
- G0: F*_NAT / F*_NOFB = 1.49. The gate needs <= 0.5, so G0 FAILS; it held in 0/1000 bootstrap resamples.
  Feedback makes failure MORE likely. R's denominator is negative, so R, delta* and the shuffled-control R are all undefined.
- Pre-specified redesign (pulse amplitude U(0.4,1.0), c ~ U(1.3,2.0)): its G_Z FAILS (F*_NOFB(K=0) = 0.107, CI 0.097-0.117;
  NAT 0.037). Its G0 also FAILS (0.873 / 0.884 = 0.99). Per section 4, H3 is ABANDONED in this model class.
- H3b: F*_ART(+100) / F*_VIS(200) = 1.25 (CI 1.23-1.28). The threshold is <= 0.8, so H3b FAILS.
- Sensitivity (19 configurations, N = 1000): delta* is in [50,150] in 0/19, so the robustness criterion is not met.
  - G0 fails in 19/19. The ratio F*_NAT/F*_NOFB is 1.09-1.93, and it is above 1 even with noise 0 (1.35) and with the Smith predictor (1.43).
  - G_Z holds in 17/19. It fails for c U(1.3,2.0) (0.096) and noise 0.1 (0.098). Memory +/-15% gives G_Z 0.007/0.000, which passes; the prereg expected 0.5-2%.
- Diagnosis (post-hoc, not a prereg metric; NAT at SM 0.7): 100% of trials with a delivered slip detection fail, mostly by crush.
  - The unchanged P1 reactive-hold rule holds L_fb = L(t_s) (the pulse load), scales it by (1+SM) and divides by mu_hat ~ 0.9*mu.
  - That grip exceeds the crush limit c*m*g/(2*mu) for c <= 2.5.
  - So the latency question is blocked by the reactive-hold rule, not by latency. That is a mathematician's call.
- Predictions vs outcome: G_Z PASS as predicted. G0 FAIL as predicted (~60%), but through a different mechanism: the ratio is 1.49, not the predicted 0.65. F*_NOFB 0.40 vs the predicted 0.20.
- Wording for the whitepaper: "with a repaired friction prior, P1b passes its sanity gate, but in this model delivered slip feedback
  (any latency) raises failures via the reactive-hold rule, so H3 is untested". Do NOT write "open-loop margin suffices".
- Files: results\p1b_grip_latency.json, results\p1b_grip_latency_sensitivity.json, results\p1b_boot_R.npz;
  figures\p1b_R_vs_delta.png/.svg (plots F* vs delta, since R is undefined) and figures\p1b_sensitivity.png/.svg.

## P2b: biomimetic vs linear d' difference (H1). Result: ABANDONED (formal); the decision rule alone gives FAIL (Weber-variance artefact)
- R0 regression gate: PASS. Delta_Weber = 0.525 (target 0.52 +/- 0.02) and d'_bio = 0.542 (target 0.542). This reproduces cycle 1 exactly.
- Primary results (charge-matched, alpha' 0.80, beta' 3.76, tau_ad = inf, N = 4000; paired 95% CIs from 1000 bootstrap resamples):
  | arm | d'_bio | d'_lin | Delta | Delta 95% CI | best AUC bio / lin | RMSE ratio |
  |---|---|---|---|---|---|---|
  | Weber | 0.542 (0.501-0.579) | 0.017 (-0.015-0.053) | 0.525 | 0.479-0.558 | 0.649 / 0.505 | 1.022 (1.020-1.024) |
  | FV (frozen variance) | 0.129 (0.093-0.166) | 0.017 | 0.112 | 0.067-0.141 | 0.536 / 0.505 | 1.047 |
  | HS (homoscedastic, sigma_h 14.15) | 0.077 (0.040-0.112) | 0.022 | 0.055 | 0.008-0.082 | 0.522 / 0.506 | 1.047 |
- Variance-cue share: V_FV = 1 - 0.112/0.525 = 0.79 and V_HS = 0.90. The variance-only probe (bio, mean fixed, Weber sd) gives d' 0.489 (AUC D1 0.635).
  So about 90% of the Weber-arm d'_bio is reproduced by variance alone.
  This confirms the reviewer's finding (about 80%) and refutes the prereg prediction (V ~ -0.15).
- Decision rule (section 2) on the primary data: FAIL. The upper CI of Delta_FV is 0.14 < 0.30, V_FV > 0.5 and V_HS > 0.5.
  FV and HS agree, so the label is "biomimetic advantage is a Weber-variance artefact".
- Abandonment (section 5): in the FV arm, both best AUCs were < 0.55 (0.536 / 0.505). The FV arm was rerun with steps U(0.3,0.6): it was still at the floor (0.536 / 0.511).
  So the FORMAL verdict is ABANDONED: "at the published JND with per-bin noise, 200-ms step detection is not measurable for either code".
  The rerun also gives FAIL by the decision rule: Delta_W 0.567, Delta_FV 0.086 (CI 0.038-0.131), Delta_HS 0.039 (CI -0.009-0.080).
- Increases / decreases, Delta by arm: Weber 0.47 / 0.46; FV 0.10 / 0.04; HS 0.07 / 0.04. Bio uses D1 in every arm; lin mostly uses D2.
- Peak-matched (descriptive), d'_bio / d'_lin: Weber 0.37/0.02, FV 0.08/0.02, HS 0.02/0.02.
- Controls, all PASS:
  - beta' = 0: alpha' goes to 1.0, which is identical to linear, and Delta = 0 in all arms.
  - Noise-free: AUC bio 0.9999, lin 0.999.
  - Label shuffle: AUC 0.490.
- tau_ad sweep (exploratory, no verdict), Delta for Weber / FV / HS:
  | tau_ad | Weber | FV | HS |
  |---|---|---|---|
  | 0.1 s | 2.05 | 1.55 | 1.15 |
  | 0.3 s | 1.62 | 0.93 | 0.49 |
  | 1 s | 0.85 | 0.30 | 0.15 |
  | >= 3 s | 0.53-0.62 | 0.12-0.16 | 0.06-0.08 |

  A mean-signal biomimetic advantage above 0.30 appears only with fast adaptation (tau_ad <= 0.3 s). That is a candidate for a new, blind prereg.
- Sensitivity (16 configurations, N = 2000): Delta >= 0.30 in FV 1/16, HS 1/16 and Weber 15/16. The one FV/HS case is w x0.5 (FV 0.336, HS 0.314, V_FV 0.52).
  V_FV > 0.5 in all 16 configurations. The RMSE ratio is 1.01-1.04.
- Files: results\p2b_biomimetic_diff.json and results\p2b_biomimetic_diff_sensitivity.json; figures\p2b_delta_dprime.png/.svg and figures\p2b_sensitivity.png/.svg.

## Deviations (details in DEVIATIONS.md)
- The script file names follow the task, not the prereg; output names follow the prereg.
- P1b: the memory-prior uniform is drawn from a separate RNG stream, so all cycle-1 random numbers are unchanged. VIS pooled events use the latest measurement. Shuffled replays use the replace rule.
- P2b:
  - FV sd is applied on contact samples only; no metric window leaves contact.
  - HS sigma_h is recalibrated per tau_ad (sweep only).
  - The variance probe uses a zero mean, which is exactly equivalent to a constant mean for difference detectors.
  - An FV PASS is downgraded unless HS also passes.
  - The abandonment rerun re-evaluates all arms.
