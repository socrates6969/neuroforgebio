# P5: How many effectively independent spatial channels do 64 S1 electrodes give? (H7, cycle 2)
Status: PRE-REGISTERED 2026-09-26 by mathematician (cycle 2). Fixed before any code is run. Theory/simulation on published summary
numbers. Stimulation values are QUOTED facts used as model inputs, not settings.

## 0. Changes vs original and why (new test, motivated by a cycle-1 result; POST-HOC in motivation)
P5 is a new prereg, not a revision. It exists because P4 (PASS) concluded that capacity must come from spatial channels, and its
control ASSUMED K = 1-16 fully independent channels (64 electrodes as 16 groups -> 39.9 bits/symbol vs 3.3 pooled). That independence
was never tested. The motivation is therefore post-hoc (I know P4's numbers), but I have NOT computed any P5 quantity; the predictions
below are blind with respect to P5's own outputs. Nothing in P4 is changed.

## 1. Hypothesis H7
With the published human array geometry, somatotopic gain and projected-field (PF) sizes, the PF overlap structure of 64 wired S1
electrodes supports N_eff >= 16 effectively independent spatial channels (the K = 16 used in P4's control).

## 2. Inputs (source opened by me this cycle unless noted)
- Array geometry: S1 arrays 6 x 10 grid, "60 electrodes ..., 32 of which were wired" (Hughes 2021 JNE, PMID 34320481, PMC8500669,
  full text via NCBI efetch); "S1 arrays were wired in a chequerboard pattern" (Greenspon 2025, PMID 39643730, PMC12176618, FT);
  "Each grid of electrodes had the same 400 um spacing", shank 1.5 mm, 10 x 6 SIROF S1 arrays in the Pittsburgh participants
  (Forrest 2025, PMID 41191976, PMC12624975, FT). Two S1 arrays = 64 wired electrodes (Flesher 2021, facts file; AUDIT row 9).
  Layout used: chequerboard = 30 sites per array; the 2 extra wired sites per array are placed at random non-chequerboard sites
  [ASSUMPTION: exact wiring map not opened]. Array centre-to-centre cortical separation D_arr: primary 5 mm, sensitivity {3, 8} mm
  [ASSUMPTION; not reported in the opened texts].
- Somatotopic gain: "A 2 mm shift in cortex corresponded to a ~10 mm shift in the PF on the skin, on average" -> g = 5 mm skin per mm
  cortex; PF-centroid distance vs electrode distance "r = 0.69" over n = 5,892 pairs (Greenspon 2025 FT). Isotropic gain [ASSUMPTION].
- PF size at the survey stimulus (60 uA, 100 Hz): "median of 2.5 cm2, 5-95th percentiles 0.3-11.3 cm2" (Greenspon 2025 FT).
  Model: log-normal, median 2.5 cm2, sigma_ln = 1.10 (mean of the two one-sided fits to the 5th/95th percentiles, 1.29 and 0.92),
  truncated to [0.1, 30] cm2 [DERIVED/ASSUMPTION]. PF area independent of location [ASSUMPTION]. PF shape = disc [ASSUMPTION;
  real PFs are "focal hotspot with diffuse borders"].
- PF growth with amplitude: PF size "threefold (median 170%)" from 40 -> 80 uA at 100 Hz (Greenspon 2025 FT; AUDIT row 17: +170% =
  2.7x). Power law area ~ I^1.43 [DERIVED: log2 2.7], used only for the amplitude sweep.
- Validation data: "When summed over all electrodes, the area over which sensations were evoked above the 33% threshold was 12, 33 and
  30 cm2 for C1, P2 and P3" (7-20% of a 165 cm2 palmar surface) (Greenspon 2025 FT). I read "summed over all electrodes" as the
  UNION of PFs (a sum of ~64 PFs of median 2.5 cm2 could not be 12 cm2) [INTERPRETATION].
- Cortical current spread (secondary analysis): Stoney 1968 as cited by Histed 2009 (PMID 19709632, verified second-hand in AUDIT
  row 64): 10 uA -> 100 um, 100 uA -> 450 um activation radius. Power law through both points: r(I) = 100 um * (I/10 uA)^0.653
  [DERIVED]. Alternative: Tehovnik 1996 (PMID 8815302, facts file, abstract) I = K r^2 with K in {100, 1000, 4000} uA/mm2.

## 3. Model and computations (numpy/scipy; seed 20260926; 500 Monte Carlo draws per configuration)
1. Place 64 electrodes (2 arrays) on the cortical plane. Skin centroid c_i = g * x_i + e_i, e_i ~ N(0, sigma_c^2 I2).
   sigma_c is calibrated ONCE (bisection, 2000 draws, primary D_arr) so that the mean Pearson r between electrode distance and centroid
   distance over all 2016 pairs equals 0.69. The same sigma_c is used for the D_arr sensitivity runs (not re-fitted), and a re-fitted
   variant is also reported.
2. PF_i = disc, area A_i ~ log-normal (above). Pairwise overlap: lens area |P_i n P_j| (closed form for two discs).
   Overlap matrix C_ij = |P_i n P_j| / sqrt(A_i A_j) (C_ii = 1). Unbounded skin plane [ASSUMPTION; a hand boundary would only increase
   overlap, so this favours PASS].
3. PRIMARY metric: participation ratio N_eff = (tr C)^2 / tr(C^2) = 64^2 / sum_ij C_ij^2 (1 <= N_eff <= 64).
   Secondary: packing number P_pack = size of a greedy maximal set of pairwise-disjoint PFs (smallest area first); union area U
   (Monte Carlo on a 0.5 mm raster).
4. Capacity consequence (descriptive): with K = floor(N_eff) groups of 64/K electrodes, total C = K * C(64/K) using P4's channel
   (w = 0.162, kappa = 0; reuse code\p4_pooling_capacity.py). This is still an UPPER bound because residual overlap is ignored.
5. Cortical-level N_eff (secondary): activation spheres of radius r(I) at each electrode tip, C_ij = sphere-overlap volume / sphere
   volume, same N_eff, for I in {20, 40, 60, 80, 100} uA and for the Tehovnik K values at 60 uA.
6. Amplitude sweep (perceptual): PF areas scaled by (I/60)^1.43 for I in {40, 60, 80, 100} uA.

## 4. Validation gate and decision rule
- Gate V1 (model consistent with data): median U over draws, primary configuration, in [6, 66] cm2 (0.5x the smallest to 2x the
  largest reported union). Gate V2: calibrated r = 0.69 reachable with sigma_c in [0, 50] mm. If V1 or V2 fails -> section 6.
- PASS H7: V1, V2 hold and the 2.5th percentile of N_eff over draws (primary: 60 uA, D_arr 5 mm) >= 16.
- FAIL: the 97.5th percentile of N_eff < 16. INCONCLUSIVE otherwise.
- Robustness: report N_eff for D_arr {3, 5, 8} mm x sigma_c {fitted, 0.5x, 2x} x amplitude {40, 60, 80, 100} uA. The verdict is
  "robust" only if the same PASS/FAIL holds in >= 70% of these 36 configurations.

## 5. Predictions (before any code runs)
- sigma_c fitted ~ 5-10 mm; U ~ 25 cm2 (V1 passes).
- Perceptual N_eff (primary) ~ 6 (plausible 3-12); P_pack ~ 6 (4-10). Verdict: FAIL, robustly (P(PASS) ~ 0.1).
  Reasoning: one array's centroids span only ~10 x 18 mm of skin (2.0 x 3.6 mm cortex x 5), while a median PF has a radius of ~9 mm,
  so PFs within an array overlap heavily; the two arrays add at most a few more channels.
- Cortical N_eff at 60 uA ~ 55-64 (nearest wired neighbours in a chequerboard are 566 um apart vs an activation radius of ~320 um),
  ~40 at 100 uA. So, if the prediction holds, the bottleneck is perceptual (PF size x somatotopic gain), not current spread.
- Capacity consequence: K ~ 6 groups -> total C well below P4's K = 16 value (39.9 bits/symbol); expected ~15-20 bits/symbol as an
  upper bound.

## 6. Abandonment
If V1 fails (model union outside [6, 66] cm2) for the primary and both D_arr alternatives, the disc/log-normal PF model does not
describe the published maps: abandon H7 in this model class and ask neurobiologist/neurologist (BOARD) for pairwise PF overlap data
(e.g. Greenspon 2025 Fig. 2 source data). No re-tuning of PF shape or size to pass V1.

## 7. Null / control conditions (each can fail)
- Tiny-PF control (all A_i = 0.001 cm2): N_eff >= 63. Identical-PF control (all centroids at 0, equal areas): N_eff = 1.00 +/- 1e-9.
- No-somatotopy null: centroids uniform on a 165 cm2 disc (whole palm), same areas. The somatotopic model must give a LOWER N_eff than
  this null; if not, the implementation is wrong.
- Area-shuffle control: permute areas across electrodes; N_eff must change by < 10% (checks that the result is not driven by one draw's
  area-location pairing).
- Closed-form lens area checked against the raster estimate (relative error < 1% for 100 random pairs).

## 8. Outputs and budget
code\p5_spatial_channels.py, code\results\p5_spatial_channels.json, code\figures\p5_neff_vs_amplitude.png/.svg. Pairwise closed form
over 2016 pairs x 500 draws x ~40 configurations is ~4e7 lens evaluations (seconds); rasters for U only on the primary. < 5 min, < 1 GB.
Limitation: overlap of PF LOCATION is a proxy for perceptual independence; electrodes with overlapping PFs can still differ in quality
(Armenta Salas 2018 descriptor spread, facts file), so N_eff measures independent locations, not all possible percept dimensions.
