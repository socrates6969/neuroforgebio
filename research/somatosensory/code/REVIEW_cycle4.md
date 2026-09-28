# Independent code review, cycle 4 (P6). Verification gate. 2026-09-26
The reviewer did not modify any script, data file or result. The reviewer's checks are in code\review\check_p6.py, with stdout in
code\review\check_p6_output.txt. The digitisation was re-run from a scratch copy of the extraction script (output kept in the
session scratchpad, not in notes\data). Line numbers refer to code\p6_empirical_channels.py as reviewed.

| test | status | verdict as reported | reviewer view |
|---|---|---|---|
| P6 | CONFIRMED (code, numbers, formal label, substantive verdict). No bug | formal "not verifiable: code"; criteria 1-4 verify no level; K >= 5 NOT supported | Independent counts, K, N_eff, P_att, P_rel and JHU numbers match. C3 is a statistical false alarm, not a code error. The formal label is the correct literal application. The substantive outcome does not depend on C3. |

## (1) Fidelity to prereg\P6_empirical_channels.md
- Label rules (L49-83):
  - `tmap` maps Dk-prefixed tags to Dk, Pk-mcp and other palm tags to PALM, and dorsum non-digit tags to DORSUM_HAND. W maps to WRIST (DEVIATIONS 1).
  - R1 is palm first, and the dominant segment is palm if non-empty (L86-87).
  - R3 is strict: a single digit territory over all non-empty segments. Otherwise the electrode is MIXED, or HAND if it has only palm/dorsum-of-hand segments.
  - Ray mapping sends P{2..5}-mcp to Dk.
  - All of this is exactly prereg section 3.
- Estimands:
  - K_digit(m) (L97) and K_terr = K_digit + [n_PALM + n_DORSUM_HAND >= m] (L105) follow prereg 4a.
  - N_eff = N^2 / sum n_c^2 (L109), the bias-corrected form (L116) and soft Jaccard PR (L123) follow 4b.
  - The second-array gain G (L420) is correct.
- Attrition:
  - The exact DP (L142-151) is a Poisson-binomial over disjoint classes with q_k = 1 - BinomCDF(m-1; n_k, p). Level 6 runs over 6 classes (D1-D5 + HAND; DEVIATIONS 3).
  - MC uses 20,000 draws of independent survival.
- Relabelling (L449-478):
  - It picks exactly round(0.10 N) PF electrodes.
  - Each gets its dominant segment replaced, uniformly, by one of the 3 nearest other same-surface segments by table centroid.
  - Territory is recomputed from the new tag (R1).
  - This is prereg 5 with DEVIATIONS 4.
- Clustered loss (L590-608): per array, remove PF electrodes nearest a random wired site until ceil(0.38 n) are gone. Descriptive only, as specified.
- Ladder (L669-692):
  - The five criteria are exactly prereg section 6. Level 6 uses K_terr.
  - The MAJORITY label applies at 2/3.
  - A failed code control gives "not verifiable: code". No K* gives "not verifiable from open data".
- JHU secondary (L611-664):
  - Strict single-hue classes, m = 2, L <= 4.
  - Criterion 4 equals criterion 1 (DEVIATIONS 10).
  - JHU can only corroborate K*, never raise it.
- Minor, no effect on results:
  - JHU relabelling draws the 10% from ALL PF electrodes, including mixed ones, which then do not change. DEVIATIONS 10 states this.
  - The C1 shuffle "distance changed" check is pooled within-array (DEVIATIONS 7).

## (2) Independent recomputation from the CSVs (own code, no project imports)
- Wired / PF electrodes per participant: 64 / 62 for each of C1, P2 and P3.
- R1 counts per participant:

  | participant | R1 counts | K_digit m1/2/3 | K_terr(m2) |
  |---|---|---|---|
  | C1 | D1 8, D2 34, D3 13, D4 7 | 4/4/4 | 4 |
  | P2 | D1 9, D2 2, PALM 51 | 2/2/1 | 3 |
  | P3 | D1 5, D2 12, D3 23, D4 4, PALM 18 | 4/4/4 | 5 |

- R3 K(m2) is 4/1/3 and ray K(m2) is 4/4/4.
- N_eff,digit is 2.6732/1.4311/3.7033 and N_eff,seg is 5.1528/4.1156/6.2403. All equal the JSON.
- Per-array K(m2) lateral/medial is C1 2/3, P2 1/0 and P3 2/3, which gives G = 1 in all three.
- P_att(L; 0.62) was computed by enumerating all 2^5 survivor-class subsets (not the DP):

  | participant | L2 | L3 | L4 | L5 |
  |---|---|---|---|---|
  | C1 | 1.000000 | 0.999912 | 0.979690 | 0 |
  | P2 | 0.383404 | 0 | 0 | 0 |
  | P3 | 0.999998 | 0.988574 | 0.781745 | 0 |

- The maximum |enumeration - JSON exact| over 3 participants x 6 p x 5 L is 2.2e-16.
- P2 L2 = q_D1 x q_D2 = 0.997409 x 0.62^2 (0.3844).
- JHU strict counts are red 2, orange 14, yellow 5, green 6, mixed 35, which equals the JSON. P_att(0.62) L2/3/4 = 0.9985/0.9359/0.3449.
- Relabelling x = 0.10 was re-implemented independently (own neighbour table and RNG):

  | participant | L2 | L3 | L4 | JSON L2/3/4 |
  |---|---|---|---|---|
  | C1 | 1 | 1 | 1 | 1/1/1 |
  | P2 | 0.984 | 0.213 | 0.005 | 0.980/0.206/0.006 |
  | P3 | 1 | 1 | 1 | 1/1/1 |

  The P2 values agree within MC error.

## (3) C3 failure: statistical false alarm, not a code error
- The exact values are independently confirmed to 2e-16 (above).
- The reviewer's own 1e6-draw MC gives:
  - P3 L2 p0.62: 0.999997 (exact 0.9999979).
  - JHU L4 p0.64: 0.37509 +/- 0.00048 (exact 0.37532).
- Exact false-alarm probabilities of the 3-SE rule (SE at the exact P, N = 20,000) for a CORRECT implementation:
  - Over the 108 comparisons the expected number of flags is 0.26.
  - P(>= 1 flag) is 0.23 and P(>= 2) is 0.027, treating the comparisons as independent (an approximation).
  - The single most likely flag of all 108 is exactly P3 L2 p0.62: P(flag) = 0.042, because one miss in 20,000 exceeds 3 SE when P = 0.9999979.
  - The JHU flag is 3.02 SE (one-sided tail 0.0013).
  - Two flags is unlucky (p about 0.03), but each is individually explained, and both vanish at 1e6 draws.
- Is the formal label "not verifiable: code" correct by the prereg's wording? YES, as a literal application:
  - Prereg 6.5 says "If any code control fails, NO level is verified ("not verifiable: code")".
  - C3 says "agreement within 3 SE for every participant, L and p".
- Nuance: the failure depends on two pre-run interpretations. DEVIATIONS 5 computes the SE at the exact P. DEVIATIONS 16 extends C3 to JHU.
  - With the conventional MC SE at p-hat, P3 would pass (0.96 SE), but JHU would still fail (3.001 SE).
  - Restricting C3 to the primary participants with the p-hat SE, C3 would pass, and the label would be "not verifiable from open data".
  - Both interpretations were fixed before the run, so applying them is legitimate.
- Prereg design weakness: a 3-SE rule over 108 correlated tests has a family-wise false-alarm rate of about 20-25%, and a normal SE is invalid at P near 1. Future gates should use an exact binomial interval with a multiplicity correction, or >= 1e6 draws. This is not a code bug.

## (4) P2 palm-first labelling and the digitisation
- R1 is applied correctly, and the prereg fixed it (section 3; the risk is disclosed in section 9).
  - P2 PALM electrodes (51) have palm tags P2-mcp 20, P3-mcp 1, P4-mcp 15 and P5-mcp 15.
  - Of these 51, 34 have NO dorsum label and 17 have a digit dorsum label (D2 15, D3 1, D5 1).
  - Only 1 P2 PF electrode has an empty palm segment.
- The R3 counts are consistent with this: HAND 34, MIXED 26, D2 2.
- So 34 of the 51 electrodes are pure MCP-pad PFs, which are non-digit under R1, R2 and R3 alike. Only ray mapping turns them into digits. The P2 shortfall is therefore not just an artefact of the palm-first rule.
- Ray mapping lifts P2 to K = 4 (D2 22, D4 15, D5 15, D1 9), as reported.
- Digitisation spot-check:
  - The CSV equals the committed extraction JSON in all 384 surface-cells (0 mismatches).
  - A fresh re-run of extract_greenspon2025_pf_segments.py (scratch copy, cached ED Fig 1 image and authors' code files) reproduces all 384 cell labels and the full segment table exactly. All 12 grid fits are 60/60 and no cell has a colour distance > 40. The P2 minimum margin is 14.2 and the median is 34.7.
  - The reviewer visually inspected an annotated crop of all four P2 array drawings (about 120 cells, including all 62 PF electrodes). Every label sits on a cell of uniform matching colour:
    - medial palm: pale green P5-mcp block, pale blue P4-mcp block, 1 red D2d-du;
    - lateral palm: pink P2-mcp, orange D1d-pu cluster, 1 lilac P3-mcp;
    - lateral dorsum: D2m/D2p reds plus 1 D3m;
    - medial dorsum: grey apart from 1 D5p.
  - What this validates: the read-out is exact and reproducible. What it cannot validate: the colour-to-segment identity rests on the authors' GetHandSegments.m palette, which the reviewer did not re-derive.
- Side note, not P6-relevant: the re-run prints "palmar hand area excl. wrist 127.0 cm2". data_cycle3b.md 2.1 quotes about 153 cm2 for the filled silhouette. These are different measures. Only the descriptive Null A uses segment areas.

## (5) Does the verdict follow?
- YES, "no level verified; K >= 5 not supported". Recomputed ladder, criteria 1, 2 and 4 only:
  - L5 and L4: crit 1 fails (P2 = 2) and crit 2 fails (min P_att 0).
  - L3: crit 1 and crit 2 fail.
  - L2: crit 1 passes and crit 4 passes (2/3), but crit 2 fails (P2 0.383 < 0.8).
- So no level is verified whatever C3 does. The formal label differs only in wording: "not verifiable: code" vs "not verifiable from open data".
- K >= 5 is unsupported under every labelling rule:
  - K_digit(m=2) is at most 4 in all participants under R1, R2, R3 and ray.
  - D5 is never a channel under R1.
- VERDICT-AT-RISK (interpretation only, not a bug): the absence of a conservative K (level 2 failing) rests on P2 under the pre-registered palm-first rule plus m = 2.
  - Under ray mapping, criteria 1-2 give K* = 3 at p = 0.62 (conditions table).
  - Report "no level verified" as R1-conditional. Do not report it as "the arrays give fewer than 2 channels".
  - C1 and P3 each hold K = 4 (P_att 0.98 / 0.78).
