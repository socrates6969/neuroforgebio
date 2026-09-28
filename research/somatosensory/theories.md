# Theories and hypotheses: bidirectional closed-loop somatosensory feedback (queen-owned, cycle 1, 2026-09-26)

Computational and theoretical work only. Stimulation values are QUOTED from published trials as model inputs. They are
not settings for any person, and any human test requires an IRB/FDA-approved clinical study.
Sources: lit\*.md (graded, audited in lit\AUDIT.md). Full derivations: notes\mathematician_theories.md.
Status legend: SUPPORTED (a pre-registered sim passed and was independently reviewed), FALSIFIED (pre-registered FAIL),
UNTESTED-DEFECT (the test design was faulty, so there is no evidence either way), INCONCLUSIVE, THEORY (not yet testable).

| ID | Hypothesis | Mechanism | Predicted effect | Falsification test | Cycle-1 status |
|---|---|---|---|---|---|
| H2 | Pooled amplitude coding cannot reach natural force resolution; capacity must come from spatial channels | Perceived intensity tracks total charge with Weber noise (Greenspon 2025), so M pooled electrodes add ~ln M / ln(1+w) levels | 11 -> ~20 levels for quartets (19.5 observed); 81-5806 electrodes needed for natural (~45-50 levels) resolution; 64 electrodes give +1.5 bits/symbol from pooling vs ~+36 bits from 16 independent spatial groups (independence ASSUMED) | P4: analytic + Monte Carlo 2AFC + Blahut-Arimoto | SUPPORTED (P4 A/B/C PASS). Part A is non-blind and fragile under sensitivity; B is robust except at N(1)=14 and w=0.128 or with Weber violation. Spatial-independence assumption is untested (P5 queued) |
| H1 | Biomimetic (onset/offset transient + sustained) encoding gives more force-change information per unit charge than linear encoding | Natural S1 responses are dominated by transients (onset >15x sustained; Callier 2019); a(t)=alpha F + beta abs(dF/dt) puts charge on events | d'_bio/d'_lin >= 1.3 at matched charge, hold-force RMSE penalty <= 1.5x | P2: synthetic force traces, Weber-noise observer calibrated to the 13.5 uA JND, ROC | INCONCLUSIVE: the ratio metric was degenerate (d'_lin ~ 0.02). The post-hoc d'_bio 0.54 is ~80% a Weber-variance artifact (independent review: 0.10 under homoscedastic noise), so there is NO computational support yet. P2b redesign with variance-controlled arms |
| H3 | A latency budget exists: ICMS slip feedback keeps >= 50% of natural feedback's benefit up to +50-150 ms added delay | Human grip corrects slips in 74 +/- 9 ms (Johansson & Westling 1987); ICMS is perceived ~48 ms slower than vibration in RT (Christie 2022) | delta* in [50,150] ms; ICMS at +100 ms beats vision by >= 20% | P1: stochastic two-digit grasp with a per-condition optimised safety margin | UNTESTED-DEFECT: the model failed its own zero-perturbation sanity control (structural friction/crush window). Reported numbers (delta* 28 ms) are not evidence. Redesign P1b queued |
| H4 | Bayesian adaptive (psi) calibration saves >= 30% trials vs a 3-down-1-up staircase | Kontsevich & Tyler 1999 psi method | savings >= 30% in >= 75% of 48 observer cells | P3 | FALSIFIED (2/48 cells). A 2-parameter psi spends its trials on slope; at shallow slopes it is slower than the staircase. Calibration of a 64-electrode array costs ~5 h at 4 s/trial with either method (ESTIMATE from sim) |
| H5 | Proprioceptive ICMS as a low-dimensional cue fused with vision (Kalman/MLE) | Ernst & Banks 2002; Dadarlat 2015 (NHP, 8-electrode learned vector code) | minimum-variance fusion | none now (largely shown in NHP) | THEORY, deprioritised |
| H6 | Sustained ICMS charge disrupts the motor decoder; transient codes reduce it | S1 ICMS modulates M1; biomimetic trains reduce the disruption (Shelchkova 2023) | optimal beta/alpha rises with the disruption coefficient k | needs k from data | THEORY, needs a dataset |
| T-tex | A learned texture-IDENTITY code (~4 bits/exploration) is reachable; a natural texture FEEL is not | Fine texture needs ms timing at 50-800 Hz (Weber 2013); ICMS frequency is discriminable only to ~200 Hz (Callier 2020) and drives recruited axons synchronously (Histed 2009) | ID ~4.1 bits (Fano bound from 83% on 55 textures) vs ~3.5 bits/electrode amplitude | joint amplitude x frequency channel with confound (planned) | THEORY (grade C) |
| T-therm | Controllable warmth is not accessible via S1 ICMS; cool is uncertain | Warm pathway goes to posterior insula, and S1 carries cool but not warm (mouse, Vestergaard 2023) | no graded thermal percept from S1 arrays | literature only | THEORY (grade B, biology). Implication: thermal feedback needs another route (insula/operculum or non-neural skin display), outside this program's S1 scope |

## Status after cycle 4 (all reviewed)
- H2 / channel architecture: pooling limit VERIFIED (P4). Empirical channel count per 2 x 32 pair is 4/2/4; K >= 5 not supported; no floor verified (P6).
  Model-based counts (P5, P5b) were abandoned. See DESIGN_RECOMMENDATION.md.
- H1 biomimetic: FALSIFIED in our model class under measured adaptation (P2c robust FAIL). The human perceptual evidence stands separately.
- H4 calibration: FALSIFIED (P3, P3b); the line is closed.
- H3 latency: RETIRED (below).

## Decision in cycle 3 (queen, 2026-09-26): H3 latency budget is FORMALLY DROPPED from the design recommendation
Reasons:
1. Two model classes failed for model reasons, not latency reasons. P1 failed its own sanity gate (friction/crush window). P1b's
   reactive-hold rule compounds the safety margin, (1+SM)/0.9, so any delivered feedback raises crush failures (independently
   confirmed, code\REVIEW_cycle2.md). Even with the hold removed, G0 still fails (0.91). Any delta* we could produce would mostly
   reflect the controller we choose, which is an unconstrained modelling choice.
2. There is no empirical anchor. No opened source reports an end-to-end sensor -> ICMS -> percept loop latency (neurologist problem map #9), so
   a model-derived budget could not be validated against anything.
3. It is not needed for the converging recommendation (channel architecture), and a third redesign would drift toward tuning until it passes.
Status: H3 = RETIRED (not falsified). Open question for the platform: measure end-to-end loop latency on real systems.
Revisit only with a published latency measurement or a grip controller validated against human slip-response data.

## Decisions after cycle 1
- Kept: H2 (spatial channels are the lever), H1 (redesign with a well-posed metric), H3 (redesign the model; the latency question
  matters more than any other for the product spec, and the end-to-end loop latency is not reported anywhere we opened).
- Dropped: H4 in its pre-registered form. A threshold-only psi (P3b) is optional and would be a new, weaker, post-hoc-informed test.
- Added: P5 (how many effectively independent spatial channels 64 electrodes give, given projected-field overlap).
All cycle-2 preregs are post-hoc-informed redesigns and are labelled that way.
