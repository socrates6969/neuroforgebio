# Independent code review, cycle 2 (P1b, P2b, P3b, P5). Verification gate. 2026-09-26
The reviewer did not modify any script or result. The reviewer's checks are in code\review\check_{p1b,p2b,p3b,p5}.py, with
stdout in code\review\check_*_output.txt. Line numbers refer to the scripts as reviewed.

| test | status | verdict as reported | reviewer view |
|---|---|---|---|
| P1b | CONFIRMED (code and H3 ABANDONED). The H3b FAIL is uninformative | H3 ABANDONED, H3b FAIL | The crush diagnosis is right, and the reviewer derived it analytically: the delivered grip is (1+SM)/0.9 times the grip at slip, so the safety margin compounds. Removing the hold alone still does not make G0 pass. |
| P2b | CONFIRMED | ABANDONED (formal); the decision rule gives FAIL | An independent build of the arms reproduces Delta and V to 4 decimals. Under FV the residual variance cue is small (d' 0.05), so FAIL is conservative. |
| P3b | CONFIRMED | FAIL; the stop-line rule is triggered | An independent 1-D psi, with explicit entropy and its own RNG, agrees within MC noise. The rule recounts match. |
| P5 | CONFIRMED (code and INCONCLUSIVE / not robust). DESIGN USE AT RISK | INCONCLUSIVE, not robust | An independent N_eff reproduces the primary result and all 18 configurations checked, with the same class in 18/18. The N_eff ~14 (K = 14, 35.6 bits) depends on the random-scatter term. Pure somatotopy gives 9.6 (FAIL), and so does a sigma_c fitted within arrays. |

## P1b grip latency v2 (p1b_grip_latency_v2.py)
Fidelity:
- C1 memory prior is mu*exp(u*ln1.10), with u drawn from a separate stream: L29-36 and L58-61.
- C2 replace update: L106-107 with muc = 0.9 L/(2 Geff) at L145, which matches the prereg exactly.
- The L_fb max/hold/decay rule is unchanged from P1: L110 and L117-118.
- G_Z runs first (L372) and gates the rest (L380-386).
- The reference regression is at L376-378. The G0 rule is at L337.
- The redesign runs once and its G_Z is reported (L403-424). The abandonment rule is at L417-424.
- H3b: L354-360. The sensitivity list swaps mu_prior for memory ±5/15% plus the Smith predictor (L438-447). The robustness count excludes the baseline and reference rows (L472).
- Self-tests cover bit-identity with cycle 1 in the reference config, CRN, the exact delay and whether replace can raise mu_hat.

Consistency:
- Every number in RESULTS_P1b_P2b.md matches p1b_grip_latency.json:
  - G_Z 0.00125/0.00025.
  - ref 0.498.
  - G0 ratio 1.49 (boot 0/1000).
  - redesign G_Z 0.1065/0.0365 and G0 0.99.
  - H3b 1.25 (1.23-1.28).
- The sensitivity file matches too: 0/19 configurations, and G_Z fails for c U(1.3,2.0) and for noise 0.1.

Crush diagnosis (check_p1b.py, using the coder's simulate() at N = 1000):
- CONFIRMED: at SM_opt 0.7, failure among trials with >= 1 delivered detection is 1.000 (crush 0.93) for NAT, and also for ART+100.
- It is also 1.000 at SM 0.6 and 1.0. At SM 0.2 it is 0.68 and at SM 0.4 it is 0.84, so "100%" holds only for SM >= ~0.6.
- Analytic mechanism (reviewer): at slip, L(t_s) = 2 mu Geff(t_s). After delivery the new command is (1+SM) L(t_s)/(2 mu_hat) = (1+SM) Geff(t_s)/0.9.
  - The grip that was already carrying the margin gets multiplied by (1+SM)/0.9 again.
  - Crush is certain (noise-free) when (1+SM)^2/(0.99 c) > 1. For all c <= 2.5 that means SM >= 0.573.
- Knock-outs (reviewer patches, not prereg arms):
  - Removing the L_fb hold gives F*_NAT 0.366 vs NOFB 0.401 (ratio 0.91).
  - Disabling only the mu update gives a ratio of 1.38.
  - Disabling both gives 1.00.
- So the hold rule is the main cause. But fixing it alone still leaves G0 failing (0.91 >> 0.5). Tell the mathematician before any P1c.

Interpretation risk:
- F*_ART(+100) = F*_NAT = F*_SHUF = 0.593 exactly. Under this mechanism, failure = P(any detected slip) + P(fail | none), which does not depend on latency.
- So H3b FAIL (ART worse than vision, 1.25) is an artefact of the hold rule. VIS delivers less often (only after a 2 mm slip). Do not cite H3b as evidence about ICMS vs vision.
- As in cycle 1, the JSON H3_verdict string (L423-424) carries the canned "open-loop margin with a memory prior suffices". That is false: F*_NOFB = 0.40.
  - Use the RESULTS wording: "H3 untested: delivered feedback raises failures via the reactive-hold rule".

## P2b biomimetic d' difference (p2b_biomimetic_ddprime.py)
Fidelity:
- Delta = d'_bio - d'_lin, each a max over D1/D2: L91-92.
- Paired episode bootstrap with the detector re-chosen per resample: L103-118.
- R0 gate: L246-253.
- FV (L45-50): rbar = mean of r over contact samples (a > 0), with a constant sd sqrt(nT)(w rbar + sigma0) on contact samples.
  - The reviewer verified that the contact mask a > 0 equals F > 0.02 for BOTH encoders (A_THR > 0), so the "non-contact samples keep Weber sd" branch never touches a metric window.
- HS (L28-36, L43-44): the per-sample sd is 141.5. A reviewer MC of the 1-s-train 2AFC JND gives 13.41 (target 13.5).
- V = 1 - Delta_FV/Delta_W: L132 and L148.
- The rule and HS downgrade (L135-157) follow section 2.
- Abandonment and rerun on U(0.3,0.6): L255-273.
- Controls: L281-298. Probe: L122-127.

Independent check (check_p2b.py):
- The reviewer built the noise arms from the prereg text, with their own AUC (rankdata) and their own d'. The result reproduces the JSON to 4 decimals:
  - Delta W/FV/HS 0.5252/0.1121/0.0550.
  - V_FV 0.7865, V_HS 0.8953.
  - probe d' 0.4889.
- The mean rbar is matched: 60.31 (bio) vs 60.26 (lin).
- NEW: a variance-only probe under FV noise gives d'_bio 0.053 (AUC 0.515). This is a small residual cue from sd differences between episodes. It inflates d'_bio,FV, so the true mean-signal Delta is even smaller than 0.112. That strengthens FAIL.

Consistency and precedence:
- The JSON verdict is ABANDONED, because the FV best AUCs 0.536/0.505 and then 0.536/0.511 are both < 0.55. The coder applied section 5 over section 2, which is a defensible reading.
- Both labels lead to the same scientific statement: H1 is not supported, and the "biomimetic advantage" is ~80-90% Weber-variance artefact.
- Note that "not measurable" is slightly strong. d'_bio,FV = 0.13 (CI 0.09-0.17) is measurably non-zero, just far below 0.30.
- Recommended whitepaper line: "FAIL by the decision rule (V_FV 0.79); formally ABANDONED at the AUC floor".
- The tau_ad <= 0.3 s sweep is exploratory and post-hoc. It needs a blind prereg.

## P3b threshold-only psi (p3b_psi_threshold_only.py)
Fidelity:
- 1-D grid: 200 log-spaced alpha in [2,200], B = beta_a, lam = 0.02, the same candidates as P3 (L34-46).
- The oracle uses the true beta per cell (L63).
- The estimate is exp(E ln theta75(alpha, beta_a, 0.02)), and the error is against the TRUE observer's theta75 (L65). That is correct: slope misspecification shows up as bias.
- Uniform prior in ln alpha comes from p3.run_psi. The entropy closed form was checked vs brute force at 4e-15.
- The staircase is bit-identical to P3 (asserted, L141-153, L230-231).
- Control rule: L234-247, where >= 36 cells = 75%. Stop-line rule: oracle < 24 (L246).

Independent check (check_p3b.py):
- The reviewer's 1-D psi uses explicit per-outcome posteriors and their own RNG, with 300 runs.
- Bias at N = 60 agrees within MC noise:

  | cell | reviewer | coder |
  |---|---|---|
  | (20,3,.02) | -0.006 | -0.004 |
  | (20,1.5,.02) | +0.196 | +0.180 |
  | (10,1.5,.05) | +0.246 | +0.256 |
  | (50,6,0) | -0.124 | -0.129 |
  | (31.5,3,.10) | +0.238 | +0.193 |
  | oracle (20,1.5,.02) N_req | 78.6 | 75.6 |

- N_req is fragile where the bias sits near the RMSE target. For (50,6,0) A the reviewer gets 19.6 against the coder's 38.2, because the bias -0.12 against the target 0.18 makes the crossing flat. The oracle's beta = 3 count (2 vs A's 4 on the same model) shows the same noise.
- This cannot move 5/48 to 36/48, or 9/48 (oracle) to 24/48.
- A recount from the JSON gives savings 5, bias failures 20, oracle 9 (stop-line TRIGGERED) and control 24/48 (not triggered). All match.

## P5 spatial channel capacity (p5_spatial_capacity.py)
Fidelity:
- Layout: 6 x 10 at 0.4 mm, chequerboard (r+c even) plus 2 random odd sites per array, re-drawn per draw (L48-65).
  - The arrays are separated along the short axis (L68-72; an ASSUMPTION, since orientation is not reported).
  - The reviewer's long-axis variant with re-fitted sigma_c gives the same N_eff (14.2), so orientation does not matter.
- Scatter: c = 5x + N(0, sigma_c^2 I). sigma_c comes from bisection on the mean per-draw Pearson r over all 2016 pairs, with CRN (L188-212).
  - Reviewer re-fit: 6.56 vs 6.54 mm.
- PF areas: log-normal (median 2.5 cm2, sigma 1.10) with inverse-CDF truncation to [0.1,30] cm2 (L75-79). sigma = mean(1.289, 0.917), as the prereg derives.
- Lens: closed form (L95-108). The reviewer's segment-formula version matches it and matches MC.
- C_ij = lens/sqrt(A_i A_j) with C_ii = 1 (L116-124). N_eff = 64^2 / sum C^2 (L111-113), which is exactly the prereg's participation ratio.
- Cortical (L131-134, L476-484): the equal-sphere lens volume pi(4r+d)(2r-d)^2/12 over the sphere volume is correct (MC 0.2416 vs closed form 0.2417).
  - r(I) = 0.1 (I/10)^0.653 mm, and Tehovnik r = sqrt(60/K). This is as specified.
- Gates and rule: L387, L409-417, L229-234. The robustness grid of 36 uses a >= 70% criterion (L422-437).
- The capacity step reuses P4 (L237-244). K = 16 gives 39.9, which matches P4.

Independent re-implementation (check_p5.py):
- Written from the prereg only, with its own layout, rejection-sampled areas, segment-formula lens, own seeds and MC union.
- Primary: median 14.31, p2.5 11.49, p97.5 17.17, INCONCLUSIVE. The coder has 14.24/11.60/17.50.
- 18 robustness configurations (D 3/5/8 x sigma x0.5/1/2 x I 40/100) agree within ~0.3 N_eff, with the same PASS/FAIL/INCONCLUSIVE class in 18/18.
- Union median 44.8 vs 44.3 cm2. Null 45.5 vs 45.4.
- Cortical N_eff matches to 0.1: Stoney 64.0/62.9/55.4 and Tehovnik 30.3/63.9.
- No bug.

Tiny-PF control failure:
- The diagnosis is CONFIRMED: at sigma_c = 0 the minimum is 64.000, and with the fitted sigma_c the reviewer sees 2.6% of draws < 63 (coder 2.8%).
- It is a prereg design flaw, not a code bug. ONE fully coincident pair gives N_eff = 4096/66 = 62.06 < 63, and random Gaussian scatter produces ~0.46 such near-coincidences per draw.
- It does not invalidate the other controls: identical-PF, null, shuffle and lens all pass.

Why the design recommendation must NOT rest on "N_eff ~14 / K = 14 / 35.6 bits" (reviewer sensitivities, not prereg):
- About a third of N_eff comes from the random-scatter term, not from somatotopy.
  - With sigma_c = 0 (pure 5 mm/mm somatotopy), N_eff = 9.6 (8.3-11.2): FAIL.
  - With sigma_c x0.5, N_eff is 11.0: FAIL.
- sigma_c depends on which pairs carry r = 0.69. Across all 2016 pairs (the prereg reading) sigma_c is 6.5 mm, but the cross-array pairs dominate the distance variance.
  - Fitting r = 0.69 on within-array pairs only gives sigma_c 2.9 mm and N_eff 10.7 (9.0-12.7): FAIL.
  - At the coder's sigma_c, the within-array r is only 0.31.
  - Greenspon's n = 5,892 is close to 3 x 2016 = 6,048, which fits the all-pairs reading. The reviewer did NOT open the paper, so this is UNVERIFIED. A second reason for caution is that the observed r includes centroid measurement noise, which the model counts as real spread.
- The model union is 44 cm2, above all three reported unions (12/33/30). Even sigma_c x0.25 still gives 37 cm2, so the PF-area model, not the scatter, sets the union. V1 is a loose gate.
- A split-normal area model that hits the reported p5/p95 (0.30/11.2 cm2) gives N_eff 15.0 (11.8-18.9): INCONCLUSIVE, a small effect.
- Bottom line for P5: the verdict INCONCLUSIVE (not robust) is correct. The defensible statement is "N_eff between ~10 (somatotopy alone) and ~15-22 (with fitted scatter / wide array spacing); P4's K = 16 is NOT supported as a design value".
  - The RESULTS line "P4's K = 16 figure is roughly the right order" is too generous.
  - Use K ~ 10-14 (upper bound ~24-36 bits/symbol, still ignoring residual overlap).
  - The perceptual (not current-spread) bottleneck is robust: cortical N_eff is 55-64 in both implementations.

## Bottom line for the queen
- No coding bug changes any pre-registered verdict in P1b, P2b, P3b or P5.
- Before anything reaches the whitepaper:
  - P1b: remove "open-loop margin suffices"; do not cite H3b; the crush mechanism is margin compounding ((1+SM)/0.9 on the grip at slip).
  - P2b: cite FAIL (Weber-variance artefact, V 0.79-0.90) with ABANDONED as the formal label.
  - P3b: the stop-line rule is valid.
  - P5: report INCONCLUSIVE, and do NOT use N_eff 14 or 16 as a design figure without the sigma_c caveat (somatotopy alone gives ~10).
