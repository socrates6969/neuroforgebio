# P6: Empirical (model-free) independent digit channels per 2 x 32 S1 array pair, computed directly from PF labels (cycle 4)
Status: PRE-REGISTERED 2026-09-26 by mathematician (cycle 4). BLIND: written before any channel count was computed by anyone I
know of. I have NOT opened code\RESULTS_*, code\REVIEW_*, code\results\* or any verdict line on notes\BOARD.md.
Computational only. This is not a stimulation protocol; no stimulation setting is proposed. Any clinical claim requires an
IRB/FDA-approved clinical study.
Parents (NOT edited): P5, P5b. The queen reports that both model-based estimates failed their validation gates, so P6 has
NO generative model. Every estimand is a deterministic function of the digitised labels.

## 0. Disclosure: what I looked at before writing
- notes\data_cycle3b.md in full, including section 4 (pairwise statistics, which are input data). Relevant numbers: the
  within-array all-pairs P(same dominant segment) = 0.418 pooled (per array 0.30-0.65), P(same digit) about 0.40-0.88 by
  distance, and C1 has about 12 thumb (D1) electrodes on the lateral array and 8 ring (D4) electrodes on the medial array
  (cross-check with Shelchkova 2023).
- CSV headers, and the SET of distinct label values (no counts, no tabulation by participant):
  - `digits` values include D1..D4, `D4|D5`, `D5|palm`, `palm`, `dorsum`;
  - palm-segment tags: D1d-d/D1d-p/D1p, D2..D4 d-d/d-p/m/p, P2-mcp..P5-mcp (**no D5 palm tag appears**);
  - dorsum tags: D1d, D1p, D2..D4 d/m/p, D5m, D5p, P-dr.
  This vocabulary alone means D5 can only enter through a dorsum label. That shapes my predictions (section 8), so I disclose it.
- notes\facts_for_models.md lines 14-16 (functional fraction), P5b (K_min = 5 justification).
- I did NOT compute any per-participant, per-digit or per-array count.

## 1. Question and design claim
How many independent digit-level channels does one 2 x 32-wired-electrode S1 array pair give, and under which conditions?
A "digit channel" = a digit territory with >= m electrodes whose dominant PF lies on that digit. Two electrodes per channel give
redundancy against attrition. Independence here means distinct dominant skin territory at the PF-mapping stimulus
(60 uA, 100 Hz, 1 s; Greenspon 2025, quoted). It does not mean proven perceptual independence (limitation, section 10).
K_min = 5 (one channel per digit), fixed in P5b section 6 and unchanged.

## 2. Data and participants
| Source | Participants / arrays | Role in P6 | Why |
|---|---|---|---|
| Greenspon 2025 Ext Data Fig 1 (`pf_per_electrode_greenspon2025.csv`) | C1, P2, P3; Medial + Lateral sensory array each | **PRIMARY (M = 3)** | Only source with digit identity AND segment identity per electrode; exactly one 2-array S1 pair per person, 32 wired each |
| Fifer 2022 Fig 1C (`pf_per_electrode_fifer2022.csv`) | JHU-1; left_array_A + left_array_B (the same-hemisphere pair); right array reported separately | SECONDARY, levels <= 4 only | Hue = finger, but hue-to-finger identity is unresolved and only 4 hue classes were extracted, so at most 4 distinct fingers can be counted. The count of distinct classes is invariant to which hue is which finger, so it is still a valid K_finger for L <= 4 |
| Armenta Salas 2018 Fig 2B | FG; 2 arrays (7x7, 48 wired) | EXCLUDED from K_digit; descriptive region-level N_eff only | Arm regions, no hand/digit labels; pitch assumed |
- Electrode unit: each wired electrode with has_PF = 1 (Greenspon) / status = PF (Fifer). Unwired electrodes are dropped.
  No-PF electrodes are never channels, but they are reported in the per-array denominators.
- Both arrays of a participant are pooled for "pair" estimands. Per-array values are reported descriptively.

## 3. Label rules (fixed now)
Territory map of a segment tag s: prefix Dk -> "Dk" (k = 1..5); P2-mcp..P5-mcp -> "PALM"; P-dr -> "DORSUM_HAND"; empty -> none.
Tags merged in the digitisation (ulnar/radial halves) stay merged.
- **R1 (PRIMARY, "dominant surface = palm first")**: territory = map(palm_segment) if palm_segment is non-empty, else
  map(dors_segment). Dominant segment (for segment level) = palm_segment if non-empty, else dors_segment.
- R2 (liberal, descriptive): territory = the first digit territory among (map(palm), map(dors)); else PALM/DORSUM_HAND.
- R3 (strict, required robustness check): the electrode counts for digit Dk only if EVERY non-empty segment of the electrode
  maps to Dk. Otherwise it is "mixed" and is not counted for any digit.
- Ray-mapping sensitivity (descriptive): P{k}-mcp -> Dk instead of PALM.
- Fifer: an electrode counts for hue class h only if its hue set is exactly {h} (strict, analogous to R3). Multi-hue
  electrodes are "mixed". A liberal variant (first-listed hue) is descriptive.

## 4. Estimands (all computed per participant, pair = both arrays pooled)
(a) **K_digit(m)** = #{k in 1..5 : n_k >= m}, where n_k = number of electrodes with territory Dk. **Primary m = 2**; m = 1 and
    m = 3 are descriptive. K_terr(m) = K_digit(m) + [n_PALM + n_DORSUM_HAND >= m] (the "5 digits + palm" 6th territory).
    Also per array: K_digit^A(m), and the second-array gain G = K_pair - max_A K^A.
(b) **N_eff (participation ratio of the same-territory similarity matrix).** S_ij = 1 if electrodes i, j share a label, else 0,
    over the N PF electrodes. S is block-diagonal with all-ones blocks, so its eigenvalues are the class sizes n_c and
    PR = (tr S)^2 / sum_ij S_ij^2 = N^2 / sum_c n_c^2, the inverse Simpson index (Hill number of order 2). Computed at:
    - digit level (R1 territories, including PALM / DORSUM_HAND as classes): N_eff,digit;
    - segment level (R1 dominant segment tag): N_eff,seg;
    - soft variant (descriptive): S_ij = Jaccard of the two electrodes' sets {palm seg, dorsum seg}, PR = (tr S)^2 / ||S||_F^2.
    Also reported: the bias-corrected inverse Simpson N(N-1) / sum_c n_c(n_c-1).
(c) **Attrition.** Each PF electrode survives independently with probability p. Primary p = 0.62 (Greenspon 2026 STM
    preprint, 62 +/- 15%; published 64 +/- 13%; facts_for_models.md). Sensitivity p in {0.47, 0.54, 0.64, 0.75, 1.0}
    (0.47 = 62 - 15; 0.54 = the 10-year single-person lower value). Output: P_att(L) = P(K_digit(m=2) after loss >= L).
    - Exact computation: the digit classes are disjoint, so P(class k keeps >= m) = 1 - BinomCDF(m-1; n_k, p), and
      P(K >= L) follows exactly from a Poisson-binomial DP over the 5 classes.
    - Monte Carlo: 20,000 draws, seed 20260926. It must agree with the exact value within 3 MC standard errors (code check).
    - Clustered-loss sensitivity (descriptive, no verdict): on each array, remove electrodes in order of cortical distance from
      a uniformly random wired site until 38% of the PF electrodes are gone (2,000 draws).
    - ASSUMPTION: survival is independent of the PF label. The functional fraction is defined on all electrodes
      (threshold < 100 uA), not on PF electrodes.

## 5. Uncertainty
- **Bootstrap over electrodes** (10,000 resamples within participant, arrays pooled, seed 20260926), 95% percentile CI:
  - For N_eff: the standard bootstrap.
  - For K_digit: a class counts only if >= m DISTINCT original electrodes are drawn (duplicates must not create a redundant
    channel). Note: this is mathematically a random retention of about 63.2% of electrodes. So the K bootstrap is nearly the
    attrition test at p = 0.632. It is reported, but the attrition test is the binding one.
- **Digitisation relabelling**: a fraction x in {0.05, 0.10, 0.20} of PF electrodes, chosen at random, has its dominant
  segment replaced by a neighbouring segment.
  - Neighbour = uniform choice among the 3 nearest other segments of the same surface by segment-centroid distance (centroids
    from the segment table in `greenspon2025_ed1_extraction.json`, falling back to the CSV centroid columns). Neighbours can
    be on the same digit or an adjacent digit.
  - Territories are then recomputed under R1. 5,000 draws per x.
  - Output: P_rel(L, x) = P(K_digit(m=2) >= L). **x = 0.10 is binding**; 0.05 and 0.20 are reported.
  - Rationale: the colour margin is >= 14 RGB units, so pure colour errors should be rare. The larger error is
    "dominant segment" vs the authors' median-over-time rule; 10% is my stated guess, not a measurement.
- Joint attrition (p = 0.62) + relabelling (x = 0.10): reported, no verdict.

## 6. Decision rule and ladder (fixed now)
Ladder levels L in {6, 5, 4, 3, 2}. Level 6 uses K_terr (D1-D5 + palm/hand); levels <= 5 use K_digit (digits only).
Level L is VERIFIED if ALL of the following hold:
1. Observed K(m = 2, R1) >= L in **3 of 3** primary participants. A design claim must hold per implant; with M = 3, 2/3 is
   too weak to certify, so 2/3 only earns the label "MAJORITY (not verified)".
2. Attrition: min over participants of P_att(L; p = 0.62) >= 0.80 (exact value; MC as check).
3. Relabelling: min over participants of P_rel(L; x = 0.10) >= 0.80.
4. Definition robustness: under R3 (strict), K(m = 2) >= L in >= 2 of 3 participants.
5. Code controls pass (section 7, C1-C3). If any code control fails, NO level is verified ("not verifiable: code").

**Reported claim** = the highest verified L, K* ("a 2 x 32 S1 array pair provides >= K* independent digit-level channels, each
backed by >= 2 electrodes, surviving loss to 62% functional electrodes"). Conditions attached to every claim:
- fMRI-guided placement over the hand area as in the Pitt/Chicago cohort;
- the PF-mapping stimulus;
- m = 2 redundancy;
- independent attrition.
- The design question "K >= 5" is **VERIFIED** only if K* >= 5.
- If K* in {2, 3, 4}: "K >= 5 NOT supported; verified conservative K = K*", plus the per-participant failing criterion.
- If level 2 fails: "not verifiable from open data" (no conservative number).
- JHU secondary: the same criteria 1-4 are applied to the left pair with K_finger (strict, m = 2), for L <= 4 only. It may
  CORROBORATE K* (reported as "replicated in an independent lab" if the JHU pair also reaches K*). It never raises K* and never
  lowers it; a JHU shortfall is reported as a caveat.
- "Under what conditions" table (descriptive, no verdict): K* recomputed for m in {1, 2, 3} x p in {0.47, 0.54, 0.62, 0.75, 1.0},
  under R1, R2 and ray-mapping. Plus the single-array K^A and the second-array gain G per participant.

## 7. Controls (each can fail)
- **C1 label shuffle within array (code test)**: permute the R1 labels among the PF electrodes of each array (1,000 permutations).
  - K_digit, K_terr and N_eff must be IDENTICAL to observed (|diff| < 1e-12), because they are permutation-invariant.
  - As a positive check that the shuffle actually happened, the mean cortical distance between same-territory pairs must
    change in >= 95% of the permutations.
  - Failure means the code uses positions or indices where it should not.
- **C2 planted truth**: a synthetic participant with class sizes D1..D5 = (6, 4, 1, 2, 0), PALM = 3, m = 2 must give K_digit = 3,
  K_terr = 4 and N_eff = 16^2/66 = 3.8788 exactly. The exact attrition P(K >= 3 | p = 0.62) must match an independent
  brute-force enumeration over survival counts to 1e-12.
- **C3 MC vs exact attrition**: agreement within 3 SE for every participant, L and p.
- **C4 spatially random null for N_eff (scientific, not a code test)**: N_eff depends only on the label multiset. So "spatially
  random" means each electrode lands on the hand independently of the others (no somatotopic clustering within an implant).
  - Null A (area-proportional): each of the participant's N PF electrodes is assigned a dominant segment independently, with
    probability proportional to segment area (the `*_segment_area_mm2` columns / segment table; palm and dorsum segments
    pooled, weighted by area).
  - Null B (pooled marginal): labels drawn i.i.d. from the pooled R1 label distribution of all 3 primary participants.
  - 10,000 draws each, at digit and segment level. Report the one-sided p = P(null N_eff <= observed) and the ratio
    observed / null median. The same nulls are reported for K_digit(m = 2) (descriptive).
  - Expected (section 8): observed N_eff < null (p < 0.05) at segment level in all 3 participants. This means somatotopic
    clustering, not electrode count, limits channels.
  - It FAILS (observed >= null median) if the implants sample the hand as broadly as random placement would. Then the channel
    limit is set by the number of PF electrodes and the label resolution, not by clustering.
  - Null A can also fail for a trivial reason: segment areas are unequal, so small fingertip segments are rare under Null A.
    That is why Null B is also reported.

## 8. Predictions (numbers fixed now)
| Quantity | Prediction (most likely; plausible range) |
|---|---|
| K_digit(m=2, R1), C1 | 3 (2-4) |
| K_digit(m=2, R1), P2 | 3 (2-4) |
| K_digit(m=2, R1), P3 | 3 (2-4) |
| Participants with K_digit(m=2) >= 5 | 0 of 3 (P = 0.85); 1 of 3 (0.12) |
| D5 as a channel | D5 reaches m = 2 in <= 1 participant (P = 0.8), because D5 exists only as a dorsum tag |
| K_digit(m = 1) | exceeds m = 2 by about 1 in >= 2 participants |
| N_eff,digit (R1) | 2.5 per participant (1.8-3.5) |
| N_eff,seg | 5 (3-8) per participant |
| Single-array N_eff,seg | about 2.4 (from 1/0.418) |
| Second-array gain G | >= 1 digit in >= 2 of 3 participants (the arrays target different digits, e.g. C1 lateral D1, medial D4) |
| Attrition, p = 0.62 | P_att(3) >= 0.8 in all participants (P = 0.6); P_att(4) >= 0.8 in all (P = 0.2) |
| Relabelling, x = 0.10 | changes K by <= 1 in >= 80% of draws |
| C4 | observed N_eff,seg below the Null B median in 3/3 (P = 0.75), with a ratio of about 0.5-0.7 |
| Verified K* | 5+: 0.05; 4: 0.20; 3: 0.40; 2: 0.25; not verifiable: 0.10 |
| JHU left pair K_finger(strict, m = 2) | 2-3 |

## 9. What can make this fail or mislead (known now)
- Dominant-label rule: R1 (palm first) may hide dorsum digits, especially D5. R2 is reported as the liberal bound.
  The verdict uses R1 plus the R3 check, so it is conservative.
- Palm-segment D5 tags do not appear in the digitised vocabulary. This could be a colour-merge artefact of the digitisation
  rather than biology. If so, K is biased low at level 5. Flag it in the results; it is not re-tuned.
- M = 3 participants, whose arrays were placed by fMRI targeting. The claim does not transfer to untargeted placement.
- Attrition independence is untested. The clustered-loss sensitivity shows its size.

## 10. Limitations
- A distinct dominant territory is not the same as perceptual independence. Overlapping PFs can still be discriminable, and
  distinct dominant labels can still co-activate other territories. Supporting evidence exists at the set level: Fifer 2022,
  blinded identification of 5-7 digit-associated electrode sets, 99.0% correct (quoted in data_cycle3.md).
- All labels are DIGITISED from figures. There are no per-electrode PF areas.
- C2 and P4 are not included (only low-resolution figures exist).

## 11. Outputs and budget
code\p6_empirical_channels.py -> code\results\p6_empirical_channels.json (and a CSV of per-participant tables).
numpy/scipy only, seed 20260926.
Cost: about 20k attrition draws + 5k x 3 relabelling draws + 10k bootstrap + 2 x 10k nulls + 1k shuffles, each over <= 64
labels. Well under 1 min; hard limit 5 min.
Any deviation goes to code\DEVIATIONS.md before results are read.
