# P1b: Latency budget for artificial slip feedback in precision grip, friction-model repair (H3, cycle 2)
Status: PRE-REGISTERED 2026-09-26 by mathematician (cycle 2). Fixed before any P1b code is run. Simulation only; no human
stimulation parameters are proposed. Latency values are quoted from published studies as model inputs.
Parent: prereg\P1_grip_latency_budget.md (NOT edited). Everything not listed under "Changes" is identical to P1 and is
incorporated here by reference (sections 2-8 of P1).

## 0. Changes vs original and why (POST-HOC redesign; evidence from P1b is weaker than a blind test)
This redesign was written AFTER seeing cycle-1 results (code\RESULTS_P1_P2.md): P1 was ABANDONED because its own
zero-perturbation sanity control failed (K = 0: F*_NOFB = 0.498, F*_NAT = 0.089; both had to be <= 0.01). The coder's
diagnosis, which I checked: with a fixed friction prior mu_hat = 0.75 and a crush limit G_crush = c*m*g/(2*mu), an open-loop
grip is safe only if 0.75/mu <= 1+SM < 0.75*c/mu. That window has width ratio c <= 2.5, while mu spans 4x (0.3-1.2), and the
slip update (min) can only lower mu_hat, so high-mu trials over-grip and crush. I also know the cycle-1 numbers (delta* = 28 ms,
CI 24-31; G0 ratio 0.83; 0/19 sensitivity configurations in [50,150]). Only the two diagnosed defects are changed:

| # | Change | Why (defect fixed) |
|---|---|---|
| C1 | Controller friction prior is per trial: mu_hat(0) = mu * exp(eps), eps ~ U(-ln 1.10, +ln 1.10) (one uniform per trial, common random numbers), replacing the fixed mu_prior = 0.75. | Structural window defect. Johansson & Westling 1984 (PMID 6499981, abstract opened): grip/load ratio is higher for more slippery objects, set "on the basis of a memory trace", updated by tactile afferents (~0.1 s after grip onset). A controller with sensorimotor memory of THIS object class starts near the true mu. The +/-10% width is an ASSUMPTION chosen as a design constraint (section 1), not a measured value. |
| C2 | Two-sided slip update: on detection mu_hat <- 0.9 * L(t_s) / (2 * G_eff(t_s)) (replace), not min(mu_hat, ...). | One-sided-update defect. At slip onset L = 2*mu*G_eff, so the slip is a measurement of mu (times 0.9), not only an upper bound. |
| C3 | The zero-perturbation control becomes a hard gate G_Z, run FIRST. If it fails, stop: report "model defect", no H3 verdict. | P1 treated it as a side check; cycle 1 showed it can invalidate everything. |
| C4 | Sensitivity item "mu_prior {0.4, 1.1}" is replaced by memory-error half-width {ln 1.05, ln 1.15}. Added reference config "cycle-1 friction model" (fixed 0.75 prior + min update) to show the repair's effect; it is NOT counted in the robustness fraction. | mu_prior no longer exists. |
| C5 | Friction sensed at contact (NAT-only friction information) was considered and REJECTED: it would give NAT information that ART/VIS do not carry, confounding content with latency. All conditions share the same prior (C1). | Keeps the latency grid a pure latency comparison. |

Unchanged (explicitly): mass, mu ~ U(0.3, 1.2), crush limit c ~ U(1.6, 2.5), pulse model (Poisson(2), U(0.2,0.6)*m*g, 30/200/30 ms),
OU noise (gain 0.05, tau 100 ms), tau_m 40 ms, drop 10 mm, slip-event rule, L_fb hold/decay, all conditions (NAT 74 ms p 0.95; NOFB;
VIS tau_v {150,200,250} with s_vis 2 mm; ART delta in {-20,0,25,50,75,100,150,200,300} ms x p in {0.5,0.75,0.95}), SM grid 0..1.5,
N = 4000, bootstrap rules, G0, delta* definition and PASS band [50,150] ms, H3b rule, shuffled-feedback control, the other
sensitivity items, the Smith-predictor variant, the robustness criterion (>= 70% of sensitivity configurations), seed 20260926,
coder interpretations in code\DEVIATIONS.md (P1 items 1-16) unless they refer to mu_prior.

## 1. Why G_Z is now expected to pass (analytic, before code)
Only the ratio r = mu/mu_hat matters: with L = m*g, slip needs (1+SM)*r*(1+0.05*xi) < 1, crush needs (1+SM)*r*(1+0.05*xi) > c.
C1 gives r in [1/1.10, 1.10] = [0.909, 1.10]. Take SM = 0.2 (on the grid):
- Crush needs 1.2*1.10*(1+0.05*xi) > 1.6, i.e. xi > 4.24 (sd units) at the worst r AND c near 1.6. With ~40 independent OU samples per
  4-s trial, P(max xi > 4.24) ~ 40 * 1.1e-5 ~ 5e-4 per trial before the r and c restrictions, so F_crush << 0.01.
- Slip needs xi < -1.67 at the worst r. Deficits are then <= ~0.08*m*g for tens of ms (a <= 0.8 m/s^2); each excursion moves the
  object ~0.2-1 mm and v resets when slip stops. Expected summed displacement over 4 s ~1-3 mm << 10 mm, so drops are rare.
- NAT: a noise-trough slip sets mu_hat = 0.9*mu (r = 1.11); crush then needs xi > 4.0. Still << 0.01.
Prediction: F*_NOFB(K=0) <= 0.002 and F*_NAT(K=0) <= 0.002, both at SM_opt in {0.1, 0.2, 0.3}. (The cycle-1 fixed prior is the
reference config: it must reproduce F*_NOFB(K=0) ~ 0.50, otherwise the code differs from cycle 1.)
The +/-10% width is the widest round value for which this margin argument holds with c_min = 1.6: at +/-15% (sensitivity) crush needs
xi > 3.1 at the worst corner and F*(K=0) of ~0.5-2% is expected; that configuration is reported, not used for G_Z.
Caveat: the P1 pre-specified redesign (c ~ U(1.3, 2.0)) has c_min = 1.3 < 1.2*1.1, so its own zero-perturbation failure rate is
expected to be ~5-15%. If G0 fails and the redesign is run, its G_Z is computed and reported; if it fails, the redesign cannot
rescue H3 (see section 4).

## 2. Metrics and decision rule (same as P1 section 3, with G_Z added)
Order: G_Z (N = 4000, K = 0) -> G0 -> delta*, H3b -> controls -> sensitivity.
- G_Z PASS: F*_NOFB(K=0) <= 0.01 AND F*_NAT(K=0) <= 0.01 (point estimates; 95% bootstrap CI reported).
- PASS H3: G_Z and G0 hold and the delta* point estimate and 95% CI lie in [50, 150] ms; INCONCLUSIVE if the CI contains 50 or 150;
  FAIL otherwise. PASS H3b: F*_ART(100, 0.95) <= 0.8 * F*_VIS(200).
- Robust support additionally needs delta* in [50,150] in >= 70% of sensitivity configurations (reference config excluded).

## 3. Predictions (stated before any P1b code runs; informed by cycle 1)
- G_Z: PASS (F* <= 0.002 for NOFB and NAT). Confidence ~90%.
- Main run: F*_NOFB ~ 0.20 (plausible 0.12-0.35; the open-loop controller must hold SM ~ 0.6 to cover pulses up to +0.6*m*g and then
  crushes when (1+SM)*r*noise > c), F*_NAT ~ 0.13 (0.06-0.25). G0 ratio F*_NAT/F*_NOFB ~ 0.65, so G0 is predicted to FAIL
  (probability ~60%). Reason: time from slip onset to 10 mm is ~80-150 ms for the pulse sizes used, close to 74 ms + tau_m.
- If G0 holds: delta* ~ 30 ms (plausible 15-50 ms), i.e. H3 FAIL (below the band). P(H3 PASS) ~ 0.10.
- H3b: FAIL, ratio F*_ART(100)/F*_VIS(200) ~ 1.0 (0.9-1.05): both arrive after most drops are already decided.
- Shuffled control: R < 0.5 (PASS). Sensitivity: delta* in [50,150] in <= 3/19 configurations.
If these predictions hold, the finding is "in this task class, slip feedback is useful only within ~+30-50 ms of natural latency",
which is a hard (and negative) latency budget for ICMS slip feedback, not support for H3.

## 4. Abandonment
- G_Z fails -> stop; report a remaining model defect; no H3/H3b verdict; no further redesign in cycle 2.
- G0 fails -> run the P1 pre-specified redesign ONCE (with its G_Z reported). If G0 still fails or the redesign's G_Z fails, abandon H3
  in this model class: "open-loop margin with a memory prior suffices, or feedback cannot beat it; latency question not addressable
  with this task". No other parameter changes.

## 5. Null / control conditions (P1 section 7, unchanged, plus)
- NOFB null; shuffled-feedback control (must NOT retain >= 50% benefit); G_Z (hard gate); reference config (cycle-1 friction model) as
  a regression check that must reproduce cycle-1 F*_NOFB(K=0) = 0.498 +/- 0.03.

## 6. Outputs and budget
code\p1b_grip_latency.py (may import/reuse code\p1_grip_latency.py; numpy only, seed 20260926), code\results\p1b_grip_latency.json,
code\figures\p1b_R_vs_delta.png/.svg. < 10 min CPU per invocation, < 1 GB (cycle-1 main run took 194 s).
