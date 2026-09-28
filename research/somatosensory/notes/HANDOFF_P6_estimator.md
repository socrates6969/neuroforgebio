# Handoff: P6 channel estimator -> platform feature (research queen -> nfb-build-queen, 2026-09-26)

Source of truth: prereg\P6_empirical_channels.md (spec), code\p6_empirical_channels.py (reference impl, seed 20260926),
code\results\p6_empirical_channels.json + p6_per_participant.csv (golden values), code\REVIEW_cycle4.md (independent recompute),
code\DEVIATIONS.md section P6 (interpretations 1-19). Analysis tool only; not stimulation settings.

## Input format (per electrode)
participant, array, electrode, grid_row, grid_col, PF label(s) (dominant hand segment tag; see notes\published-derived\pf_per_electrode_greenspon2025.csv), wired/PF flag.
Territory mapping (rule R1 "palm first", primary): tag with a Dk prefix -> Dk; Pk-mcp and other palm tags -> PALM; dorsum non-digit tag -> DORSUM_HAND;
W -> WRIST. R2 is the liberal rule and R3 the strict one; the ray rule sends P{2..5}-mcp to Dk. Details: DEVIATIONS P6 item 1 and code L49-87.

## Maths
- K_digit(m) = #{k in D1..D5 : n_k >= m}, where n_k = electrodes in territory k (both arrays pooled). The primary m is 2.
- K_terr(m) = K_digit(m) + [n_PALM + n_DORSUM_HAND >= m].
- N_eff = N^2 / sum_c n_c^2 (participation ratio). Bias-corrected and soft-Jaccard forms: code L109-123.
- Attrition: each electrode survives independently with p. Per class q_k = 1 - BinomCDF(m-1; n_k, p).
  P(K >= L) is a Poisson-binomial tail over the classes (exact DP, code L142-151). Monte Carlo is a check only.
  NOTE: the MC-vs-exact 3-SE check gave 2/108 statistical false alarms (reviewer-confirmed). Golden tests should assert against the
  EXACT DP, not the MC.

## Golden values (R1, m = 2, p = 0.62)
| | C1 | P2 | P3 |
|---|---|---|---|
| n D1/D2/D3/D4/D5, PALM | 8/34/13/7/0, 0 | 9/2/0/0/0, 51 | 5/12/23/4/0, 18 |
| K_digit(m=2) | 4 | 2 | 4 |
| K_terr(m=2) | 4 | 3 | 5 |
| P_att(L=2/3/4), exact | 1.000/1.000/0.980 | 0.383/0/0 | 1.000/0.989/0.782 |
| N_eff,digit | 2.67 | 1.43 | 3.70 |
P2 check by hand: P(K >= 2) = P(D1 survives with >= 2) x P(D2 keeps both) = (1 - BinomCDF(1; 9, 0.62)) x 0.62^2 = 0.99740 x 0.3844
= 0.383404. The D2 term alone is 0.3844; the exact value is 0.383404 (corrected 2026-09-26 on nfb-build-queen's report). Full-precision values are in the JSON; the reviewer matched enumeration to 2e-16.
Planted-truth fixture (control C2): D1..D5 = (6,4,1,2,0), PALM = 3, m = 2 -> K_digit = 3, K_terr = 4, N_eff = 256/66.

## Caveats to carry into the product
- A distinct dominant territory does not mean perceptual independence (unverified).
- Survival is assumed independent. Clustered loss lowers P(K >= 4) (C1 0.755, P3 0.488).
- The result is rule-dependent: the ray mapping gives P2 K = 4.
