# RESULTS P5b: independent spatial channels per 2 x 32 S1 array pair, from measured somatotopy (coder-verifier B, cycle 3)
Prereg: prereg\P5b_channels_measured_somatotopy.md (FIXED, not edited). Script: code\p5b_channels_measured.py (stages: --selftest,
--stage fit, --stage run, --stage posthoc). Seed 20260926. Outputs: results\p5b_fits.json, results\p5b_channels_measured.json,
results\p5b_posthoc_v1_reachability.json, results\p5b_*_stdout.txt; figures\p5b_K_bounds, p5b_calibration, p5b_K_vs_amplitude_web
(.png/.svg). Interpretations: DEVIATIONS.md section P5b (items 1-17 before results, item 18 post-hoc).
Runtime: fit 151 s, run 97 s, posthoc ~90 s; < 1 GB. A rerun reproduces the JSON exactly.
All numbers are MODEL outputs from published summary data. They are not stimulation settings for any person.

## Verdict: ABANDONED (prereg sections 4 and 9). Not VERIFIED.
- Gate, correlated model: 0/84 configurations are defensible.
  - V1 (curve) fails 84/84. Bin 3 fails in 82 of them: the simulated mean is ~10.9 mm against the digitised 8.0 +/- 2 mm.
  - V2 fails 42/84: every 1-D-map configuration, pooled r ~0.55 < 0.59.
  - V3 fails 28/84: every C1 configuration. C1's measured union is 12 cm2, below the gate's lower bound 0.7 x U_low = 19.2 cm2.
    The pooled PF-area model is too large for C1, who had the smallest PFs.
- The primary (C1+P2+P3 pooled, iso, W 20, disc) fails V1 and V3. V2 passes (r 0.738, per-array median 0.80).
- Independent-scatter control: the same gate counts (V1 84, V2 42, V3 28). This matches the prediction that it fails V1 or V2.
  - It does not enter the verdict.
  - Descriptively, its K_design differs from the correlated model's by 24% (low) and 31% (high). So the scatter model still matters.
- Post-hoc diagnostic (no verdict use):
  - A theta that meets V1 and V2 together DOES exist for corr/iso/W20 (g 6.6, sigma_f 24.9, l 11.5, sigma_n 1.7).
  - So the V1 failure comes partly from the pre-registered least-squares fit, not only from the model class.
  - At that theta, V3 still fails for C1 (17.1 > 12 cm2). ABANDONED therefore does not depend on the fitting issue.
  - K at that theta, descriptive: K_low 4.4 / 7.4 / 11.7 and K_high 8.4 / 12.5 / 18.4 (p2.5 / median / p97.5).
- Section 9 consequence: K is "not estimable from open data" under this model class. Pairwise PF overlap or per-electrode PF maps
  (DABI GU5A5IO8LRXE, restricted access) are needed.

## Numbers (DESCRIPTIVE ONLY: the gate failed; 60 uA; p2.5 / median / p97.5 of draws, bootstrap 95% CI)
| quantity | primary (1500 draws; N_A 3000) | all 84 configs pooled (27,600 draws) | prereg prediction |
|---|---|---|---|
| N_A (one array) | 4.33 / 7.11 / 11.30 (median CI 7.03-7.21) | 3.85 / 7.53 / 14.00 | median ~3.5 (2-6) -> higher |
| K_low (same territory) | 5.02 (CI 4.87-5.18) / 8.19 / 12.97 | 4.21 / 8.44 / 16.28 | median ~4.5 (2.5-7) -> higher |
| K_high (disjoint) | 9.58 (CI 9.25-9.77) / 14.03 / 20.08 | 8.81 / 14.70 / 23.44 | median ~7 (4-11) -> higher |
| K_design,low (pooled p2.5) | - | 4.21 (CI 4.17-4.26) | ~2.5 |
| K_design,high | - | 8.81 (CI 8.75-8.88) | ~4.5 |
- If the gate were ignored, the section-6 rule gives CONDITIONAL PASS. K_design,high 8.8 >= 5 and K_high p2.5 >= 5 in 84/84
  configurations. K_design,low 4.2 < 5, and K_low p2.5 >= 5 holds in only 30/84. This is NOT the verdict.
- Primary by participant, N_A median: C1 7.6, P2 7.7, P3 6.2. P3 is lowest (f 0.42), as predicted.
- Primary packing (C <= 0.1), K_low set: 3 / 6 / 10. Unions (cm2, U_low median): C1 27.4, P2 26.1, P3 23.5.
- Factor medians (K_low / K_high):
  - map: iso 8.59 / 15.04 vs 1-D 8.19 / 14.26. 1-D is lower, as predicted, but only slightly.
  - shape: ellipse 8.74 / 15.38 vs disc 8.39 / 14.60. Ellipses come out HIGHER, against the prediction.
  - f: 1.0 gives 8.90 / 16.16 vs participant f 8.15 / 13.86.
- Amplitude conditions (pooled, change in the median vs 60 uA):
  - 40 uA: +17% (gamma 0.77) to +35% (gamma 1.43). Predicted +20-40%: matches.
  - 80 uA: -11% to -18%. Predicted -20-40%: a smaller drop than predicted.
  - At 80 uA with gamma 1.43, K_design,low is 3.7 and K_design,high is 7.7.
- Fits (central curve, W 20):
  - corr iso: g 7.6, sigma_f 5.3, l 1.25, sigma_n 0.004. Predicted g ~5, sigma_f ~8, l ~1.5 (in range); sigma_n ~1.5 (not in range, fitted ~0).
  - ind iso: g 7.1, sigma_n 3.3.
  - The 1-D map fits run to the bounds (sigma_f ~40, g 0.5-4.4).
- D-sweep (primary): K(D) medians 8.19 / 10.12 / 13.13 / 14.05 / 14.06 at D 0/2/4/8/16 mm.
  - It is monotone, K(0) = K_low exactly, and K(16)/K_high = 1.002.
  - The bracket closes by D ~ 8 mm of cortex. The real D is unreported.
- Downey cosine (similarity of the two arrays' digit coverage): C1 0.58, P2 0.73, P3 0.92 (C2 0.99, P4 0.24).
  - C1 and P2 are in the predicted 0.4-0.8. P3 is higher, i.e. closer to K_low.
- Geometry-only rows (BCI03 / CRS08, identity UNVERIFIED): K_low median 8.5 / 8.6, K_high 14.9 / 14.9.
- Capacity (3.9, descriptive, P4 channel, 48 PF electrodes):
  - K 4 gives 11.5 bits/symbol; K 5 gives 14.0; K 8 gives 21.2.
  - Pooled (K 1) gives 3.2. The mathematician's ~14 bits at K 5 is reproduced.

## Controls
| control | result | pass |
|---|---|---|
| field shuffle | N_A median rises by x1.11 | yes |
| no-somatotopy null | null N_A 20.5 > model 7.1 | yes |
| tiny PF | N_A and K_high medians 1.00 n_PF; the strict linear-map check is 1.00 in every draw; K_low median 0.71 n_PF | **NO** (K_low): co-located sites in the K_low placement plus the fitted nugget ~0 give coincident centroids. This is a property of the bound, not of the code (DEVIATIONS 18c) |
| identical PF | abs(N_eff - 1) < 1e-15 | yes |
| hand boundary (30 draws) | K_clip / K median 1.000 (N_A and K_low) | yes |
| lens vs raster (100 pairs) | max relative error 4e-5 | yes |
| bound identity K_high = 4/(1/N_A1 + 1/N_A2) | max error 7e-15 | yes |
| D-sweep monotone and approach | yes; ratio 1.002 | yes |
Self-tests all pass: V4 area quantiles 2.49 / 0.30 / 11.14 cm2 (within 5%), the ellipse affine map vs raster (0.08%), the union
raster, the field square root, exact pair statistics, and the decision-rule logic.

## What the whitepaper may say
- "Under a linear map plus a Gaussian-field model fitted to the published Greenspon 2025 curve, two 32-electrode S1 arrays give a
  descriptive bracket of ~8 (same territory) to ~14 (separate territories) PF-overlap channels at 60 uA. The pre-registered model
  did not pass its validation gate (curve shape and the C1 union), so no design value is claimed."
- Do NOT use 8 or 14 as a verified K. The robust qualitative points are:
  - the pair bound depends on array placement (a factor ~1.7);
  - the fitted 1-D and ellipse variants move K by < 10%;
  - the model PF area (pooled) overpredicts C1's union.
- Figure for the web: figures\p5b_K_vs_amplitude_web.png/.svg. It carries the "descriptive only / ABANDONED" subtitle and the model note.
