# RESULTS P6: empirical digit channels per 2 x 32 S1 array pair (cycle 4, coder-verifier)
Prereg: prereg\P6_empirical_channels.md (FIXED, not edited). Script: code\p6_empirical_channels.py (new; runtime 3.7 s, seed 20260926).
Outputs: code\results\p6_empirical_channels.json, code\results\p6_per_participant.csv; figures (png+svg) code\figures\
p6_counts_per_territory, p6_attrition, p6_channels_web. Interpretations: code\DEVIATIONS.md, P6 items 1-18 (pre-run), 19 (post-run).
Inputs are DIGITISED labels (Greenspon 2025 ED Fig 1; Fifer 2022 Fig 1C), grade B sources. Computational analysis only; not
stimulation settings. Any clinical claim requires an IRB/FDA-approved clinical study.

## Verdict (ladder, prereg section 6)
**Formal outcome: "not verifiable: code"**. Code control C3 (MC vs exact attrition) failed in 2 of 108 comparisons. DEVIATIONS 19
shows both are statistical false alarms of the 3-SE rule: brute force matches the exact values to 1e-15, and 1e6-draw MC agrees.
The rule is applied as written anyway.
**This does not change the result.** With criterion 5 ignored (criteria 1-4 only, DESCRIPTIVE), **no level is verified either**.
- Level 2 fails attrition in P2: P_att(2; 0.62) = 0.383.
- So the substantive outcome is "not verifiable from open data", with no conservative K.
- **"K >= 5" is NOT supported.** No participant reaches K_digit(m=2) = 5, and D5 is never a channel.

| L | K_obs C1/P2/P3 (R1, m=2) | crit 1 (3/3) | P_att(0.62) min [C1/P2/P3] | crit 2 | P_rel(0.10) min [C1/P2/P3] | crit 3 | K R3 C1/P2/P3 | crit 4 (>=2/3) | Label |
|---|---|---|---|---|---|---|---|---|---|
| 6 (K_terr) | 4/3/5 | no | 0 [0/0/0] | no | 0 | no | 4/2/4 | no | not verified |
| 5 | 4/2/4 | no | 0 [0/0/0] | no | 0 | no | 4/1/3 | no | not verified |
| 4 | 4/2/4 | no (2/3) | 0 [0.980/0/0.782] | no | 0.006 [1/0.006/1] | no | 4/1/3 | no | MAJORITY (not verified) |
| 3 | 4/2/4 | no (2/3) | 0 [1.000/0/0.989] | no | 0.206 [1/0.206/1] | no | 4/1/3 | yes | MAJORITY (not verified) |
| 2 | 4/2/4 | **yes** | **0.383** [1/0.383/1] | **no** | 0.980 | yes | 4/1/3 | yes | not verified |
Criterion 5 (C1 pass, C2 pass, C3 FAIL) = no at every level.

What limits the result is P2. Under R1 (palm first), 51 of its 62 PF electrodes are PALM (MCP pads). Only D1 (9 electrodes) and
D2 (2) are digit territories, and the D2 channel has exactly m = 2 electrodes. Its survival at p = 0.62 is 0.62^2 = 0.384.
Under ray mapping (P{k}-mcp -> Dk), P2 has K = 4. The palm-first rule therefore drives the P2 result (conditions table below).
C1 and P3 each hold K = 4 robustly: at p = 0.62, P_att(4) is 0.980 for C1 and 0.782 for P3. P3 is just under 0.8; it reaches 0.812
at p = 0.64.

## Per participant (R1, both arrays pooled; N_wired 64 each; N_PF 62/62/62)
| | C1 | P2 | P3 |
|---|---|---|---|
| n D1/D2/D3/D4/D5, PALM, DORSUM_HAND | 8/34/13/7/0, 0, 0 | 9/2/0/0/0, 51, 0 | 5/12/23/4/0, 18, 0 |
| K_digit m=1/2/3 | 4/4/4 | 2/2/1 | 4/4/4 |
| K_terr (m=2) | 4 | 3 | 5 |
| K_digit(m=2) under R2 / R3 / ray | 4 / 4 / 4 | 2 / 1 / 4 | 4 / 3 / 4 |
| Per array K_digit(m=2) lateral / medial; gain G | 2 / 3; G = 1 | 1 / 0; G = 1 | 2 / 3; G = 1 |
| N_eff,digit (bias-corr.) [boot 95% CI] | 2.67 (2.75) [2.02-3.30] | 1.43 (1.44) [1.18-1.74] | 3.70 (3.88) [2.91-4.22] |
| N_eff,seg (bias-corr.) [CI]; soft | 5.15 (5.53) [3.34-7.02]; 8.22 | 4.12 (4.34) [3.29-4.60]; 5.63 | 6.24 (6.83) [4.43-7.34]; 12.1 |
| Single-array N_eff,seg lat / med | 2.96 / 6.04 | 1.99 / 2.13 | 3.04 / 4.83 |
| Bootstrap K_digit(m=2) CI | 4-4 | 1-2 | 3-4 |
| P_att(L=2/3/4; p=0.62), exact | 1.000/1.000/0.980 | 0.383/0/0 | 1.000/0.989/0.782 |
| P_rel(L=2/3/4; x=0.10) | 1/1/1 | 0.980/0.206/0.006 | 1/1/1 |
| Joint p=0.62 + x=0.10 (L=2/3/4) | 1/1/0.978 | 0.583/0.047/0.001 | 1/0.989/0.798 |
| Clustered loss 38% (L=2/3/4) | 1/0.985/0.755 | 0.553/0/0 | 1/0.906/0.488 |

Attrition sensitivity P_att(4), p = 0.47/0.54/0.62/0.64/0.75/1.0:
- C1: 0.866/0.939/0.980/0.985/0.998/1.
- P3: 0.493/0.639/0.782/0.812/0.934/1.
- P2: P_att(2) = 0.214/0.288/0.383/0.409/0.562/1.

## Controls
- **C1 label shuffle: PASS.** Invariants had max |diff| = 0 over 1,000 permutations x 3. The same-territory mean distance changed in
  100% of permutations. Observed values: 1.50, 1.66, 1.69 mm.
- **C2 planted truth: PASS.** K_digit = 3, K_terr = 4, N_eff = 3.878788 = 256/66. Exact P(K >= 3 | 0.62) equals brute force within 1e-12.
- **C3 MC vs exact: FAIL** in 2 of 108 comparisons: P3 L2 p0.62 (1 miss in 20,000 at P = 0.999998); JHU L4 p0.64 (3.03 SE).
  Both are false alarms, not code errors (DEVIATIONS 19).
- **Self-tests: 18/18 pass.** They cover label rules, the DP vs brute force on 600 random cases, the bootstrap distinct rule, soft = hard
  N_eff, and count aggregation.
- **C4 nulls, segment level: the expected result holds in 3/3.** Null B (pooled marginal): observed / null-median N_eff,seg is
  0.54 (p 0.0002), 0.43 (p < 1e-4) and 0.65 (p 0.007). Null A (area-proportional) gives ratios of 0.29, 0.23 and 0.35 (p < 1e-4).
  Somatotopic clustering, not the electrode count, limits the channel count.
- **C4, digit level vs Null B:** C1 0.72 (p 0.002), P2 0.38 (p < 1e-4), P3 0.99 (p 0.47; not clustered at digit level).

## "Under what conditions" (descriptive, criteria 1-2 only; K* per m x p x rule)
- R1: m=1 gives K* = 2 at p >= 0.62 (none below). m=2 gives K* = 2 only at p = 1.0. m=3 gives none.
- R2 (liberal): K* = 2 for all m and p, except m=1 (3 at p 0.62-0.75, 4 at p = 1).
- Ray mapping: m=2 gives K* = 3 at p <= 0.62 and 4 at p >= 0.75. m=1 gives 4. m=3 gives 2-4.
- Implication: for level 2, the verdict depends on two things. The first is the palm-first rule for P2's MCP-pad electrodes;
  this is a label-definition question, not a data-quality one. The second is the m = 2 redundancy.

## JHU secondary (left pair, strict single-hue, m = 2; L <= 4)
- Strict counts: red 2, orange 14, yellow 5, green 6, mixed 35 (N_PF 62). K_finger = 4 (liberal first-listed hue: 4).
- L4: P_att 0.345 FAIL; P_rel 0.895.
- L3 PASSES all JHU criteria: P_att 0.936, P_rel 1.0. L2 passes.
- Right array (descriptive): K_finger strict 2, liberal 3.
- There is no primary K*, so there is nothing to corroborate. JHU would support "3 channels" in an independent lab, but it cannot
  raise K* (prereg).
- Hue-to-finger identity and hue-ramp adjacency are UNVERIFIED (DEVIATIONS 10).

## Predictions vs observed (prereg section 8)
| Prediction | Observed | Hit? |
|---|---|---|
| K_digit(m=2) C1/P2/P3 = 3 (2-4) each | 4 / 2 / 4 | all in range, none = 3 |
| 0 of 3 with K >= 5 (P 0.85) | 0 of 3 | yes |
| D5 reaches m=2 in <= 1 participant | 0 (D5 absent under R1; R2 gives 1 e in P2; ray 15 in P2) | yes |
| K(m=1) exceeds K(m=2) by ~1 in >= 2 participants | 0 of 3 (equal in all) | no |
| N_eff,digit 2.5 (1.8-3.5) | 2.67 / 1.43 / 3.70 | 1 of 3 in range |
| N_eff,seg 5 (3-8) | 5.15 / 4.12 / 6.24 | yes |
| Single-array N_eff,seg ~2.4 | 1.99-6.04 (median 3.0) | higher |
| G >= 1 in >= 2 of 3 | G = 1 in 3 of 3 | yes |
| P_att(3) >= 0.8 in all (P 0.6); P_att(4) in all (P 0.2) | P2 fails both (0 / 0) | no / no (as expected at 0.8) |
| Relabelling changes K by <= 1 in >= 80% | 100% / 99.4% / 100% | yes |
| C4 seg below Null B median in 3/3, ratio 0.5-0.7 | 3/3; 0.54, 0.43, 0.65 | yes (P2 ratio below range) |
| Verified K*: not verifiable 0.10 | not verifiable | the 0.10 outcome |
| JHU K_finger 2-3 | 4 (passes L3) | higher |

## Caveats
- M = 3 participants with fMRI-targeted placement. All labels are digitised dominant segments, not PF areas.
- Survival is assumed independent of the label; clustered loss lowers P(K >= 4) to 0.75 in C1 and 0.49 in P3.
- There is no D5 palm tag in the digitised vocabulary, so K is possibly biased low at level 5 (prereg 9). It is flagged, not re-tuned.
- A distinct dominant territory does not mean proven perceptual independence.
