# P5b: Independent spatial channels per 64-electrode S1 array pair, from measured somatotopy (H7', cycle 3)
Status: PRE-REGISTERED 2026-09-26 by mathematician (cycle 3). BLIND: fixed before any P5b code runs. I have NOT opened
code\RESULTS_*, code\REVIEW_*, code\results\* or any result line on BOARD.md. Computational only. Stimulation values are QUOTED
facts used as model inputs; they are not settings for any person.
Parent: prereg\P5_spatial_channel_capacity.md (NOT edited). P5b is a new test with a new generative model.

## 0. What I know before writing (disclosure)
- My own P5 predictions (N_eff ~6, FAIL vs 16). I do not know the P5 outcome.
- Queen's summary: "P5's N_eff is sensitive to the random centroid-scatter term and to the unreported inter-array distance;
  within-array analyses are preferred." This motivated three changes: (C1) scatter is modelled as a spatially CORRELATED map
  error fitted to the measured distance curve, with independent scatter as a pre-registered artefact control; (C2) the
  inter-array distance is BRACKETED, never chosen; (C3) the primary quantity is within-array.
- New inputs (notes\data_cycle3.md): exact wired maps, DIGITISED Greenspon Fig. 3e curve, pooled PF area quantiles, unions.

## 1. Question and estimand
How many effectively independent spatial (location) channels does a 2 x 32 wired-electrode S1 array pair give at the
PF-mapping stimulus (60 uA, 100 Hz, 1 s; Greenspon 2025 quoted), and under which condition on array placement?
- Per-array quantity: N_A = participation ratio of the PF overlap matrix of one array's electrodes with a PF.
- Pair bounds (inter-array distance unknown, NOT FOUND in any opened source, data_cycle3 A2):
  K_low  = N_eff of both arrays mapped onto the SAME skin territory (arrays "fully overlapping", section 3.6);
  K_high = N_eff with zero cross-array overlap (arrays "fully independent"; block-diagonal C, = 4/(1/N_A1 + 1/N_A2) exactly).
- Design estimand: K_design,low = 2.5th percentile of K_low over all draws POOLED over all defensible configurations (section 5);
  K_design,high likewise for K_high. Per-configuration 2.5th percentiles are used for robustness.

## 2. Inputs (all from notes\data_cycle3.md or opened sources; ASSUMPTIONs carry a sensitivity range)
| Input | Value | Source / label |
|---|---|---|
| Electrode positions | exact wired 32 of 60 sites per array, 400 um pitch, x_mm/y_mm columns | notes\published-derived\greenspon2025_S1_array_channel_maps.csv (Greenspon 2025 MIT code). Participants C1 = BCI02, P2 = CRS02, P3 = CRS07 (code mapping quoted in A1.6). BCI03/CRS08 used only in a geometry-only robustness row (identity UNVERIFIED) |
| Mean PF-centroid distance vs cortical distance (same-digit, within-array pairs) | 0.29/0.86/1.43/2.00/2.57/3.14/3.71 mm -> 3.1/6.0/8.0/11.8/18.2/24.1/26.6 mm, +/-1 mm; last point less reliable | DIGITISED Greenspon 2025 Fig 3e (CSV) |
| Correlation of those distances | pooled r = 0.69 (n = 5,892 pairs); each array r > 0.4 | Greenspon 2025 Fig 3e legend (quoted). How 5,892 pairs arise is UNRESOLVED (32 electrodes give 496 pairs/array); I read r = 0.69 as within-array pairs pooled over arrays |
| PF area (33% pixel threshold, 60 uA, 100 Hz) | median 2.5 cm2, 5th 0.3, 95th 11.3 | Greenspon 2025 Fig 2f (quoted). Model: two-piece log-normal matching all three quantiles: sigma_ln below median = ln(2.5/0.3)/1.645 = 1.289, above = ln(11.3/2.5)/1.645 = 0.917 [DERIVED], truncated to [0.05, 40] cm2 [ASSUMPTION]. Area independent of location [ASSUMPTION] |
| Unions (validation only) | C1 12, P2 33, P3 30 cm2 (palm 165 cm2) | Greenspon 2025 Fig 2e (quoted); read as union of PFs (as in P5) |
| Fraction of electrodes with a PF | f = 0.75 (C1, P2), 0.42 (P3) primary; f = 1.0 alternative | Greenspon 2025: 25/25/58% excluded (quoted); legend n = 62/63/63 conflicts (UNRESOLVED), so f = 1.0 is a sensitivity level. Excluded electrodes chosen uniformly at random [ASSUMPTION] |
| Digit territory on skin (for the same-digit restriction used by the data) | strips of width W across the digit axis, W in {15, 20, 25} mm, primary 20 | ASSUMPTION (Downey 2024 fMRI: D1-D5 peaks span ~18 mm of cortex in C1, ~4.5 mm per digit, used only to justify that one array rarely spans > 2-3 digits) |
| PF growth with amplitude (conditions, not configs) | area x (I/60)^gamma, gamma in {0.77, 1.43} | DERIVED from "170%" (1.7x per doubling) vs "threefold" (2.7x) wording, UNRESOLVED in the source, so both are used |
| Downey 2024 Supp. Table 1 digit coverage | per array, % electrodes with PF on each digit | notes\published-derived\downey2024_digit_coverage_by_array.csv; used only for a descriptive "which bound is closer" index (section 7) |

## 3. Generative model (numpy/scipy; seed 20260926)
3.1 Cortical frame: each array's 32 wired sites at (x_mm, y_mm), centred. Random in-plane orientation of the map axis per draw
    (uniform angle) [ASSUMPTION: the reference frame of the code's ArrayRotations is undocumented, so it is not used].
3.2 Skin centroid of electrode i: c_i = G(x_i) + f(x_i) + n_i, where
    - G is linear: G(x) = diag(g_u, g_v) R x. Primary: isotropic (g_v = g_u = g). Alternative "1-D map": g_v = 0 (Downey 2024: no
      consistent AP-electrode to proximal-distal-PF relation; Greenspon: one optimal axis classifies digit as well as 2-D).
    - f = 2-D Gaussian random field (independent u, v components), sd sigma_f, squared-exponential correlation length l
      (CORRELATED map error: nearby electrodes share it).
    - n_i ~ N(0, sigma_n^2 I2) independent (nugget).
3.3 Calibration (per map variant and per W): fit theta = (g, sigma_f, l, sigma_n) by minimising
    sum_b ((m_b - d_b)/s_b)^2 + ((r_sim - 0.69)/0.03)^2, where d_b are the 7 digitised means, s_b = 1 mm for bins 1-6 and 3 mm for
    bin 7, m_b is the simulated mean skin distance of SAME-DIGIT pairs (both centroids in the same u-strip of width W; strip
    phase uniform) in the same 7 cortical-distance bins (edges linspace(0, 4, 8) mm, as in the released code), r_sim is the
    pooled Pearson r over same-digit pairs. Common random numbers, 400 draws per evaluation, Nelder-Mead from 5 starts
    (bounds g in [0.5, 30] mm/mm, sigma_f in [0, 40] mm, l in [0.1, 20] mm, sigma_n in [0, 20] mm).
    Curve uncertainty: repeat the fit with d_b - 1 and d_b + 1 mm (3 curve levels).
3.4 Scatter-artefact CONTROL model "independent scatter": sigma_f = 0 (only g and sigma_n fitted, same objective).
3.5 PFs: discs of area A_i (two-piece log-normal) centred at c_i. Alternative shape: ellipses, aspect 2:1, long axis along v
    (along the digit) [ASSUMPTION; "centroid variability lies along a single axis", Ext Data Fig 2h, is the only shape hint].
    Unbounded skin plane (a hand boundary control is in section 8).
3.6 Pair bounds:
    - K_high: two arrays with independent field and nugget draws; cross-array overlaps set to 0.
    - K_low: array 2's wired sites placed in the SAME cortical frame as array 1 (same origin, same field realisation, independent
      nugget and area draws). This is the most-overlapping placement consistent with the fitted map.
    - Descriptive D-sweep (no verdict): array 2 offset by D in {0, 2, 4, 8, 16} mm along a random direction in one shared field
      covering both arrays. K(D) must be monotone within MC error and approach K_low (D = 0) and K_high (D = 16).
3.7 Overlap matrix C_ij = |P_i n P_j| / sqrt(A_i A_j) (closed-form lens area for discs; 0.25 mm raster for ellipses).
    N_eff = (tr C)^2 / sum_ij C_ij^2 over the electrodes with a PF.
3.8 Secondary metrics (reported, no verdict): packing number (greedy maximal set with pairwise C_ij <= 0.1, smallest area
    first); union area U (0.25 mm raster).
3.9 Capacity consequence (descriptive only; does not move K_min): total C = K * C_P4(n_PF / K) with P4's channel
    (reuse code\p4_pooling_capacity.py; w = 0.162, kappa = 0) for K = floor(K_design,low) and floor(K_design,high).

## 4. Validation gate (model must reproduce the data or it is abandoned). Applied per configuration.
- V1 curve: simulated same-digit mean distance within +/- max(2 mm, 25%) of the digitised value in each of bins 1-6, and within
  +/- 40% in bin 7.
- V2 correlation: pooled r_sim in [0.59, 0.79], and the median per-array r > 0.40.
- V3 unions: for each of C1, P2, P3, measured U_p in [0.7 x median U_low(p), 1.3 x median U_high(p)]
  (U_low / U_high = union with arrays overlapping / independent; the bracket is required because the inter-array distance is unknown).
- V4 implementation check (not evidence, true by construction): simulated area quantiles within 5% of 2.5 / 0.3 / 11.3 cm2.
A configuration that fails V1, V2 or V3 is NOT defensible and is excluded from K_design and the robustness count (reported).
ABANDON (section 9) if the primary configuration fails, or if fewer than 50% of configurations pass.

## 5. Configurations (84 per scatter model)
participant geometry {C1, P2, P3} x map {isotropic, 1-D} x W {15, 20, 25} mm x PF shape {disc, ellipse} x
f {participant-specific, 1.0} at the central curve = 72 configurations; plus the off-centre curve levels {-1, +1 mm} crossed with
participant x map at (disc, W = 20, participant-specific f) = 12 rows; total 84.
Primary configuration: all three participants pooled (no participant favoured) at isotropic map, W = 20 mm, disc,
participant-specific f, central curve. Draws: 500 per configuration for discs,
100 for ellipses (raster). Correlated-scatter model = primary; independent-scatter model enters only if it passes the gate.
Amplitude CONDITIONS (reported separately, not in the robustness count): 60 uA (verdict), 40 and 80 uA via gamma in {0.77, 1.43}.

## 6. K_min (fixed now) and decision rule
K_min = 5. Justification: the design requirement is independent contact/force feedback for each of the 5 digits of one hand
at the same time (grasp involves all digits; Flesher 2021 already grouped fingers into 2 feedback channels; Fifer 2022 showed
>= 7 distinguishable locations with 96 electrodes across 2 hemispheres). Capacity alone is NOT the binding reason: in the P4
channel model any K >= 2 beats pooling. My ESTIMATE from the numbers quoted in P5 (K = 16 -> 39.9 bits, pooled 64 -> 3.3 bits;
approximation C(M) ~ log2(11 + 6.67 ln M) - 1.85 bits) is 5 x C(9.6) ~ 14 bits/symbol vs ~3.3 pooled, i.e. ~ +11 bits/symbol at K = 5
with 48 electrodes; the coder recomputes this exactly in 3.9, descriptively. K = 8 (segment-level, e.g. 4 fingers x 2 segments) is
reported as a secondary descriptive threshold with no verdict.
Verdict at 60 uA (all on defensible configurations; "robust" = the same call in >= 70% of them):
- PASS (unconditional): K_design,low >= 5 AND per-configuration 2.5th pct of K_low >= 5 in >= 70% of configurations.
- CONDITIONAL PASS: not PASS, but K_design,high >= 5 AND per-config 2.5th pct of K_high >= 5 in >= 70%.
  Recommendation then reads: ">= 5 independent channels holds ONLY if the two arrays map non-overlapping skin territories".
- FAIL: per-config 97.5th pct of K_high < 5 in >= 70% of configurations (even independent arrays cannot give 5).
- INCONCLUSIVE: otherwise.
- "VERIFIED" label requires: gate passed for the primary, >= 70% robustness, and no scatter-artefact flag (section 8).

## 7. Predictions (before any code runs)
- Fit: g ~ 5 mm/mm (4-8), sigma_f ~ 8 mm (4-14), l ~ 1.5 mm (0.5-3), sigma_n ~ 1.5 mm (0.5-3). Correlated model passes V1-V3.
- Independent-scatter control FAILS V1 or V2 (P ~ 0.8): with only white scatter, the intercept (3.1 mm at 0.29 mm) forces
  sigma_n <~ 2 mm, which makes r ~ 0.9 and a near-linear curve, not the convex 3 -> 27 mm curve.
- Within-array N_A (60 uA, correlated): median ~ 3.5 (plausible 2-6); P3 (f = 0.42) lowest (~2.5).
- K_low median ~ 4.5 (2.5-7); K_high median ~ 7 (4-11). K_design,low ~ 2.5; K_design,high ~ 4.5.
- Verdict: not unconditional PASS. Probabilities: PASS 0.10, CONDITIONAL PASS 0.35, INCONCLUSIVE 0.25, FAIL 0.30.
- 1-D map variant gives LOWER K than isotropic (centroids collapse onto a line). Ellipses give lower K than discs.
- 40 uA raises K by ~20-40%; 80 uA lowers it by ~20-40%.
- Descriptive Downey index (cosine similarity of the two arrays' digit-coverage vectors, per participant; e.g. C1 medial
  D2-D4 heavy vs lateral D1-D2 heavy) ~ 0.4-0.8, i.e. real placements lie between the bounds, closer to K_low for P2/P3.

## 8. Null and control conditions (each can fail)
- Scatter-artefact control: independent-scatter model (3.4). If it ALSO passes the gate and its K_design differs from the correlated
  model's by > 30%, raise the flag "scatter-model dependent": K_design is then the MIN of the two and "VERIFIED" is withheld.
- Field-shuffle control: permute the field values f(x_i) among electrodes (keeps marginals, destroys spatial correlation). N_A must
  RISE; report the ratio (this is the size of the "random scatter" inflation the queen flagged in P5).
- No-somatotopy null: centroids uniform on a 165 cm2 disc. Model N_A must be LOWER; otherwise the implementation is wrong.
- Tiny-PF control (A = 0.001 cm2): N_eff >= 0.98 n_PF. Identical-PF control: N_eff = 1.000 +/- 1e-9.
- Hand-boundary control: clip PFs to a 165 cm2 disc around the array's mean centroid; K must not increase.
- Lens area vs raster: relative error < 1% on 100 random pairs. Bound identity: K_high equals 4/(1/N_A1 + 1/N_A2) to 1e-9.
- D-sweep monotonicity (3.6).

## 9. Abandonment
If the primary configuration fails V1-V3, or < 50% of configurations pass: the linear-map + field + disc/ellipse PF class does not
describe the published maps; no re-tuning of PF size or shape to pass. Post to BOARD (-> neurologist, neuroinformatics): pairwise
PF overlap or per-electrode PF data (DABI GU5A5IO8LRXE, restricted) are needed. K is then reported as "not estimable from open data".

## 10. Why the result is not guaranteed by construction
- The scatter structure is not chosen by me: it is fitted to the measured curve and r, and the fit can fail the gate.
- The within-array K depends on how fast skin distance grows over 0-3.7 mm of cortex (the convex curve) relative to PF radius
  (median ~9 mm): the curve could make PFs within an array nearly disjoint at the far end (K up) or cluster them (K down).
- K_min = 5 was fixed from a functional requirement before any K was computed; the bracket bounds can land on either side.
- The independent-scatter control can pass the gate and flip K.

## 11. Outputs and budget
code\p5b_channels_measured.py, code\results\p5b_channels_measured.json, code\figures\p5b_K_bounds.png/.svg (K_low, N_A, K_high per
config; D-sweep). Fits: ~ 3 participants x 2 maps x 3 W x 3 curves x 2 scatter models x ~300 evaluations x 400 draws of <= 496 pairs:
~1e9 cheap distance ops, vectorised, ~2-4 min. Overlaps: discs closed form (2016 pairs x 500 draws x ~80 configs ~ 8e7 lens
evaluations), ellipses raster at 100 draws. Target < 10 min CPU, < 1 GB; if over budget, reduce ellipse draws to 50 first and
say so in code\DEVIATIONS.md. numpy/scipy only; seed 20260926.
Limitation: PF LOCATION overlap is a proxy for perceptual independence; overlapping PFs may still differ in quality, and
non-overlapping PFs may still interact (Greenspon 2025: summed PFs predict pairs only moderately, r = 0.61). K counts independent
locations at the mapping stimulus, not all percept dimensions.
