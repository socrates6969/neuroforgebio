# STATUS: somatosensory research program (queen), updated 2026-09-26 after cycle 4

## Bottom line
- One design recommendation has been written: DESIGN_RECOMMENDATION.md. It proposes an independent-channel architecture in which a channel is a measured PF territory
  with >= 2 electrodes. Plan for 2-4 digit channels plus palm per 2 x 32 S1 array pair.
- Its verified parts: pooling cannot replace spatial channels (P4); K >= 5 is not supported; channel count is placement/clustering-limited (P6).
- NOT verified: any guaranteed per-implant floor (P6 ladder verified no level), and perceptual independence of channels.
  Both need per-electrode PF areas (DABI, restricted; not accessed) or more implants.

## Cycle log (every test independently code-reviewed; code\REVIEW_cycle1-4.md)
| Cycle | Test | Verdict | Notes |
|---|---|---|---|
| 1 | P1 latency | UNTESTED (sanity gate failed) | structural model defect |
| 1 | P2 biomimetic | INCONCLUSIVE | degenerate metric; post hoc ~80% noise artifact |
| 1 | P3 psi calibration | FAIL 2/48 | |
| 1 | P4 pooling capacity | PASS | A non-blind; B/C robust |
| 2 | P1b latency v2 | ABANDONED | reactive hold compounds the margin |
| 2 | P2b biomimetic, variance controls | FAIL/ABANDONED | Weber-variance artifact confirmed |
| 2 | P3b threshold-only psi | FAIL, line closed | |
| 2 | P5 spatial channels (model) | INCONCLUSIVE, design use at risk | |
| 3 | P5b channels, measured somatotopy (blind) | ABANDONED (validation gate) | K not estimable by that model |
| 3 | P2c biomimetic, measured adaptation (blind) | FAIL (robust 10/10) | tau_a 13.2 s from Hughes 2022 |
| 3 | H3 latency | RETIRED (queen decision, theories.md) | no empirical anchor |
| 4 | P6 empirical channels (blind, model-free) | no level verified; K >= 5 not supported | K = 4/2/4; clustering p <= 0.007 |

Data added in cycles 3-4 (open only, no sign-ups): notes\data_cycle3.md and notes\data_cycle3b.md. The main addition is 318 digitised per-electrode PFs from
11 arrays, with the digitisation re-run by the reviewer.
Constraints respected: temperature and fine texture are out of scope (provisional); DABI was not accessed.

## Next options (need owner/lead choice)
1. Get the per-electrode PF areas (DABI access by the owner, or ask the authors). Then rerun P6 and a perceptual-independence test with the code as it stands.
2. Productise the P6 channel-count and attrition estimator as a platform feature (it is a reviewed prototype).
3. Neurobiology track (owner's top priority): proprioception via area 2/3a and the S1->M1 decoder crosstalk (H6), for which we need open data.

## Process lessons
- Unnamed sub-agents cannot message each other, so notes\BOARD.md is the blackboard. The handback fails, so reports land on BOARD.md.
- The review gate caught one over-claim (P2) and confirmed every verdict. Blind preregs (cycles 3-4) did not rescue any hypothesis.
