# P1: Latency budget for artificial slip feedback in precision grip (hypothesis H3)
Status: PRE-REGISTERED 2026-09-26 by mathematician. Fixed before any code is run. Simulation only; no human
stimulation parameters are proposed. Latency values are quoted from published studies as model inputs.

## 1. Hypothesis
In a stochastic two-digit grasp of a fragile object that meets unexpected load perturbations, the safety margin is
optimised separately for each feedback condition. Delayed binary slip feedback keeps >= 50% of the benefit of
natural feedback (relative to no feedback) up to an added latency delta*. The prediction is delta* in [50, 150] ms.
H3b: artificial feedback at +100 ms lowers the failure rate by >= 20% relative to vision-only feedback.

## 2. Model (dt = 2 ms, trial length T = 4.0 s, vectorise over trials x safety-margin grid)
Per trial (independent draws; the SAME random numbers are used for every condition = common random numbers):
- mass m ~ U(0.2, 0.5) kg [ASSUMPTION]; g = 9.81 m/s^2
- friction mu ~ U(0.3, 1.2) [ASSUMPTION; Johansson & Westling 1984 (PMID 6499981) show friction-dependent grip, no values opened]
- crush limit G_crush = c * m*g / (2*mu), c ~ U(1.6, 2.5) [ASSUMPTION: fragile object; Flesher 2021 notes their task had no crush penalty]
- planned load: L_plan(t) = m*g * clip((t - 0.5)/0.3, 0, 1)   (lift ramp 0.5-0.8 s)
- perturbations: K ~ Poisson(2) pulses, onset t_k ~ U(1.0, 3.5) s, amplitude dL_k ~ U(0.2, 0.6)*m*g,
  trapezoid: 30 ms rise, 200 ms plateau, 30 ms fall [ASSUMPTION]. True load L(t) = L_plan(t) + sum_k pulse_k(t).
- motor noise: xi(t) is an Ornstein-Uhlenbeck process, tau_xi = 100 ms, unit stationary variance [ASSUMPTION;
  signal-dependent noise as in Todorov & Jordan 2002, PMID 12404008, magnitude not opened].

Controller state: mu_hat (initial mu_prior = 0.75 = prior mean), L_fb (initial 0).
- commanded grip: G_cmd(t) = (1 + SM) * max(L_plan(t), L_fb(t)) / (2 * mu_hat(t))
- grip dynamics: dG/dt = (G_cmd - G)/tau_m, tau_m = 40 ms [ASSUMPTION]; effective grip G_eff = G * (1 + 0.05*xi(t)), G(0) = 0; grip
  command starts at t = 0.3 s (use L_plan with a 0.2 s lead: replace L_plan(t) by L_plan(t + 0.2) inside G_cmd).
- slip physics: condition S(t): L(t) > 2*mu*G_eff(t). While S: v += (L - 2*mu*G_eff)/m * dt; s += v*dt. When not S: v = 0
  (s is kept, not reset). DROP if s > 10 mm [ASSUMPTION]. CRUSH if G_eff > G_crush at any time.
  A trial ends at the first failure. Failure = DROP or CRUSH.
- slip event: first step of S after >= 20 ms without S. Event time t_s.
- feedback: for condition (tau, p_det, vis): each slip event is detected with prob p_det at time t_s + tau.
  For vision (vis = True) the event is detectable only once s > s_vis (2 mm) [ASSUMPTION], at t(s > s_vis) + tau_v.
  On detection: mu_hat <- min(mu_hat, 0.9 * L(t_s) / (2 * G_eff(t_s))); L_fb <- max(L_fb, L(t_s)); after 500 ms,
  L_fb decays toward 0 with time constant 300 ms [ASSUMPTION: reactive hold].
- Before the lift (t < 0.5 s) there is no load, so no slip is possible.

Conditions:
| name | tau | p_det | notes |
|---|---|---|---|
| NAT | 74 ms | 0.95 | Johansson & Westling 1987 (PMID 3582528): slip -> ratio change 74 +/- 9 ms. p_det ASSUMPTION |
| NOFB | none | 0 | open loop, SM only |
| VIS | tau_v in {150, 200, 250} ms | 1.0 | s_vis = 2 mm; ASSUMPTION (Godlove 2014 PMID 25028989: tactile faster than visual, no numbers opened) |
| ART(delta, p) | 74 + delta | p in {0.5, 0.75, 0.95} | delta in {-20, 0, 25, 50, 75, 100, 150, 200, 300} ms. -20: Sombeck & Miller 2019 (PMID 31778982). 56-215 ms: span of differences between Caldwell 2019 (PMID 30824821) median ranges (DCS 254-528 vs haptic 198-313 ms; pairing per subject not opened). ~48 ms: human ICMS RT slower than intensity-matched vibration (Christie 2022, PMID 35644516, from neurologist's facts; not opened by me) |

Safety margin grid: SM in {0, 0.1, ..., 1.5} (16 values). For every condition use SM_opt = argmin failure rate.
Report F*(cond) = failure rate at SM_opt, plus the drop and crush components.

## 3. Metrics and decision rule
- Benefit retained: R(delta, p) = (F*_NOFB - F*_ART) / (F*_NOFB - F*_NAT).
- delta* = the largest delta in the grid with R(delta, 0.95) >= 0.5, with linear interpolation between grid points.
  If R >= 0.5 at every delta, delta* = "> 300"; if R < 0.5 already at delta = -20, delta* = "< -20".
- Validity gate G0: F*_NAT <= 0.5 * F*_NOFB (feedback matters in this model) AND F*_NAT >= 0.005 (not trivially zero).
- PASS H3: G0 holds and delta* in [50, 150] ms.
- PASS H3b: F*_ART(delta=100, p=0.95) <= 0.8 * F*_VIS(tau_v = 200 ms).
- FAIL otherwise. The number is reported either way.
- Statistics: N = 4000 trials per condition (main run). Give 95% CIs for F* by bootstrap over trials (1000 resamples)
  and for delta* by bootstrap (200 resamples, re-optimising SM each time on a 1000-trial subsample is acceptable). If the delta* CI
  straddles a boundary (50 or 150), report "INCONCLUSIVE" rather than PASS/FAIL.

## 4. Why this is not guaranteed by construction
- The safety margin is optimised per condition, so an open-loop controller can buy back slip protection. The crush limit
  is the only thing that stops it, and whether that limit binds depends on c, mu and the pulse sizes.
- Feedback helps only if the delay is shorter than the time from slip onset to 10 mm of displacement. That time is set by
  pulse size, mass and friction, not by the latency grid, so delta* could land anywhere, including outside the grid.
- The validity gate G0 can fail: with these perturbations, open-loop SM could be nearly as good as natural feedback.

## 5. Sensitivity analysis (N = 1000 trials each; report delta* per configuration)
One factor at a time: tau_m in {20, 80} ms; drop distance {5, 20} mm; pulse amplitude range U(0.1,0.4) and U(0.4,1.0) x m*g;
Poisson mean {1, 4}; c range U(1.3, 2.0) and U(2.0, 4.0); noise gain {0, 0.1}; NAT tau {50, 100} ms (the 74 ms includes
motor onset, so tau_m double-counts part of it); mu_prior {0.4, 1.1}; p_det_NAT {0.8, 1.0}.
Predictive-controller variant (Smith-predictor idea, Miall 1993 PMID 12581990): on detection use L(t_s + tau) instead of L(t_s).
Robustness claim: H3 counts as robustly supported only if delta* lies in [50, 150] in >= 70% of the sensitivity configurations.

## 6. Abandonment criterion
If G0 fails in the main run, run ONE pre-specified redesign: pulse amplitude U(0.4, 1.0)*m*g and c ~ U(1.3, 2.0).
If G0 still fails, abandon H3 in this model class and report "open-loop margin suffices; latency question not
addressable with this task". Do not tune any other parameters to rescue it.

## 7. Null / control conditions
- NOFB (open loop) is the null that feedback conditions must beat.
- Shuffled-feedback control: ART(delta = 0, p = 0.95), but each detection is delivered at a random time within the trial
  (not tied to slips). It must NOT retain >= 50% benefit. If it does, the model rewards any grip increase, not information.
- Zero-perturbation control: with K = 0, F*_NAT and F*_NOFB should both be <= 0.01 (sanity check).

## 8. Outputs (for coder-verifier)
code\p1_grip_latency.py (numpy only, seed 20260926), code\results\p1_grip_latency.json (F*, SM_opt, drop/crush split,
R curves, delta*, CIs, sensitivity table), code\figures\p1_R_vs_delta.png. Budget: < 10 min CPU, < 1 GB RAM.
Tip: vectorise over (trials x 16 SM values). Loop over time steps (2000) and conditions (about 35).
