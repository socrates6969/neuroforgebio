# Design recommendation (cycle 4, 2026-09-26). Owner: Marius Carlsson. Status: see the "verified vs open" table

Computational and analytical work only, from published data. This is not a stimulation protocol. Any clinical use requires an
IRB/FDA-approved clinical study.

## The one recommendation
**Build feedback as an independent-channel architecture in which a "channel" is a distinct projected-field (PF) territory measured
per implant, not an electrode. Each channel needs >= 2 electrodes for redundancy. Plan for 2-4 digit-level channels (plus palm)
per 2 x 32-electrode S1 array pair, and do NOT plan for one channel per digit (5).** The number available is set by where the arrays
land in the somatotopic map, so it must be measured per person. The platform deliverable is a PF-mapping + channel-count + attrition
estimator (code\p6_empirical_channels.py, independently reviewed). It turns a user's PF map into an observed channel count and a probability
that each channel level survives electrode loss. It does NOT give a guaranteed floor (see "not verified" below) and does not establish perceptual independence.

## What is verified (pre-registered, independently code-reviewed, robust)
| Claim | Evidence | Test |
|---|---|---|
| Pooling electrodes onto one percept cannot reach natural force resolution on 64 electrodes (it would need 81 to ~5,800); capacity must come from spatially distinct channels | analytic + Monte Carlo + Blahut-Arimoto, reviewer re-derived | P4 B/C PASS |
| One channel per digit (K >= 5) is NOT supported by any open-data 2 x 32 implant, under every labelling rule | digitised PF maps, 3 participants, 186 electrodes | P6, reviewed |
| The channel count is limited by somatotopic clustering, not by electrode count: distinct-segment N_eff is 0.43-0.65 of a spatially random null in 3/3 participants (p <= 0.007) | P6 control C4 | P6, reviewed |
| Channel count depends on placement: observed digit channels are 4 / 2 / 4. P2's arrays map mostly to the palm (51/62 electrodes) | P6 | P6, reviewed |
| At 62% electrode survival (the published long-term functional fraction), 4 channels survive with P = 0.98 (C1) and 0.78 (P3); P2's 2 channels survive with P = 0.38 | exact attrition DP | P6, reviewed |
| Under measured perceptual adaptation (tau ~13 s, fit to Hughes 2022), biomimetic encoding has no model advantage in force-step detectability | 10/10 sensitivity rows | P2c, reviewed |
| Bayesian adaptive calibration does not save >= 30% trials vs a staircase (2-parameter or threshold-only) | 48-cell grids | P3, P3b, reviewed |

## What is NOT verified (open)
- **A guaranteed floor.** No level (not even 2) holds in 3/3 implants after attrition, so "every implant gives >= K channels" is not
  verified for any K. The fallback under the ray-mapping labelling rule is K = 3, but that result is rule-conditional.
- **Perceptual independence.** A distinct dominant territory is not proof that two channels can be told apart. PF areas and overlaps
  exist only in restricted data (DABI), and we did not sign up.
- **Model-based channel counts** (P5 ~14, P5b ~8-14) failed their validation gates, so they are not design values.
- **Loop latency budget:** retired (see theories.md); it needs a real end-to-end measurement.
- **Temperature and fine texture:** out of scope for S1 ICMS (provisional owner decision; biology grade B).

## Conditions under which the recommendation holds
- 2 x 32 wired electrodes in the S1 hand area, at 400 um pitch, placed as in the Pitt/Chicago trials (fMRI-targeted). Data: 3 participants,
  all male, grade-B sources, labels DIGITISED from published figures.
- Channel = dominant hand-segment territory; m = 2 electrodes per channel; independent electrode loss (clustered loss lowers C1's
  P(K >= 4) to 0.75 and P3's to 0.49).

## What would turn this into a verified positive number
Per-electrode PF areas/overlaps from more implants (DABI, or new open releases), or perceptual discrimination data between channels.
Then rerun P6 unchanged. The code and the decision ladder are already fixed.
