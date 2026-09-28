# Neurobiologist: mechanisms an S1-ICMS encoder must reproduce, per open problem
Sources: lit\neurobiologist.md (all PMIDs opened there). Computational/theoretical assessment only; any human test
requires an IRB/FDA-approved clinical study. Feasibility grades: evidence grade of the supporting data (A/B/C) +
verdict (PLAUSIBLE / PARTIAL / IMPLAUSIBLE via S1 ICMS alone).

## Cross-cutting constraint (applies to everything below)
ICMS does not address neurons by type. It activates axons within tens of um of the tip, producing a sparse,
quasi-random, antidromically driven set of somata spread over hundreds of um; a 15-30 um shift changes the set
(Histed 2009, PMID 19709632 [B]; model Kumaravelu 2022, PMID 34861412 [C]). Most S1 neurons already mix
SA1/RA/PC input (Saal & Bensmaia 2014, PMID 25257208; Delhaye 2018, PMID 30215864). So "stimulate the SA1 channel"
is not biologically available; the encoder can only control WHEN, WHERE (which electrode/projected field) and
HOW MUCH (amplitude/frequency) a local population fires.

## 1. Pressure / contact (baseline problem, most solved)
- Mechanism to reproduce: large phasic onset/offset transients (onset >15x, offset >8x sustained) with wide spatial
  recruitment, then a small, spatially focal tonic response graded by indentation depth; ~20 ms latency
  (Callier 2019, PMID 30668644 [B]); compressive intensity (log locally; SA1 exponent 0.66) (PMID 17959811, 1127614 [B]).
- S1 access: PLAUSIBLE. Human biomimetic onset/offset ICMS felt more like indentation (32% single electrodes, 75% of
  4-electrode groups) with less charge (Hobbs 2025, PMID 40106898 [B]); monkey precedent (Tabot 2013 [B]).
- Limitation: single-electrode amplitude gives ~2 discriminable steps (Kim 2015, PMID 26504211 [B]) -> intensity
  must be coded by recruiting more electrodes/overlapping PFs (Greenspon 2025 [A/B]).

## 2. Texture
- Mechanism: coarse texture = spatial SA1 pattern (3b-like); fine texture = ms-precise, texture-specific temporal
  spike patterns in RA/PC driven by 50-800 Hz skin vibrations, preserved in S1 with ms precision; speed dilates
  patterns; cortex becomes partly speed-invariant; texture identity is a high-dimensional idiosyncratic population code
  (Weber 2013; Harvey 2013; Lieber 2019/2020; Long 2022 [all B, one lab]).
- S1 access: PARTIAL / largely IMPLAUSIBLE for fine texture.
  * Coarse/spatial features (edges, shapes, motion across skin): PLAUSIBLE via PF tiling (Valle 2025 [B]).
  * Fine texture: requires (a) a subpopulation phase-locked up to hundreds of Hz and (b) idiosyncratic differences
    across many neurons. ICMS frequency is discriminable only up to ~200 Hz in monkeys (Callier 2020 [B]) and
    synchronously drives all recruited axons alike, so it cannot recreate neuron-specific patterns. Likely ceiling:
    a small set of discriminable "vibration-like" qualities (Hughes 2021 frequency groups [B]), not natural textures.
  * Open question for mathematician/coder: information-theoretic bound on texture channels given ~200 Hz ICMS limit
    and N electrodes (TouchSim -> S1 model needed).

## 3. Temperature
- Mechanism: dedicated thermal afferents (TRPM8 cold, warm C-fibres; seconds-scale dynamics, 5-12 s decay) project
  via lamina I to posterior insula; primate/human imaging places cooling in dorsal posterior insula/OP1
  (Craig 2000; Mazzola 2012 [B each, together A-level for "insula"]); mouse: S1 has COOL (needed for cool perception,
  Milenkovic 2014 [B]) but essentially no WARM; pIC has both (Vestergaard 2023 [B]).
- S1 access: IMPLAUSIBLE for controllable warm; UNCERTAIN (at best PARTIAL) for cool.
  * No study found in this pass showing graded, controllable thermal percepts from S1 ICMS. Human reports of
    "warm" occur as a non-natural quality of non-biomimetic trains (Hobbs 2025: 'Less Warm' 19% of comparisons) and
    warm/cool were offered descriptors in Hughes 2021 without reported thermal control.
  * Biology says thermal feedback would need posterior insula/operculum stimulation or peripheral/non-neural
    (e.g., skin thermal display on residual sensate skin) routes — outside S1 ICMS scope. Flag to queen.

## 4. Proprioception
- Mechanism: population code from spindles (length+velocity, low ~10 Hz rates, fusimotor-modulated), GTOs (force),
  joint receptors (extremes), SA2 skin stretch; in cortex, areas 3a and 2 carry multi-joint posture (hand) and
  whole-arm kinematics (reach), with cosine-like directional tuning, tonic posture + phasic movement components,
  hysteresis, and efference-copy (active != passive) (Proske 2012 [A]; Prud'homme 1994; London 2013;
  Chowdhury 2020; Goodman 2019 [B]).
- S1 access: PARTIAL.
  * Area 2 ICMS biases perceived perturbation direction toward the stimulated neurons' PD, graded with current
    (Tomlinson & Miller 2016 [C]); a human reported movement/position percepts (Armenta Salas 2018 [B], n=1).
  * Not shown: controllable, continuous joint-angle/posture percepts. Area 3a lies in the fundus of the central
    sulcus (Delhaye 2018) — hard for surface-inserted arrays (anatomical access issue; neurologist to confirm).
  * Active-movement signals include efference copy; a sensor-driven encoder can reproduce only the afferent part.

## 5. Naturalness
- Mechanism: natural touch = spatially structured (centre-surround 3b RFs, DiCarlo 1998 [B]) + temporally structured
  (transients, ms timing) + multi-submodality convergent activity in a large population; ICMS gives synchronous,
  sparse, axon-driven, surround-free activation.
- S1 access: PARTIAL, improving. Biomimetic transients + multi-electrode co-modulation measurably raise naturalness
  (Hobbs 2025 [B]); many single-electrode percepts are "tingle/buzz/vibration" (Hughes 2021 [B]).
  Frequency-quality groups cluster spatially -> per-electrode quality calibration is required.

## 6. Percept stability
- Mechanism: stability of the electrode-tissue interface and of the somatotopic map.
- S1 access: PLAUSIBLE — best supported claim. PF location stable over years in 3 humans (Greenspon 2025), thresholds
  stable or improving (31.5 -> 10.4 uA over 1500 days, Hughes 2021 JNE), detection stable for years in monkeys
  (Callier 2015). Combined grade A for LOCATION stability; quality/naturalness stability less studied (B/UNVERIFIED).

## Summary table
| Problem | Biological mechanism | S1 ICMS access | Grade |
|---|---|---|---|
| Pressure/contact | onset/offset transients + focal tonic, compressive | PLAUSIBLE | B (human n=3 + monkey) |
| Coarse spatial/edges/motion | 3b spatial RFs, somatotopy | PLAUSIBLE | B |
| Fine texture | ms temporal patterns up to 800 Hz, high-dim idiosyncratic pop code | LARGELY IMPLAUSIBLE | B |
| Cool | TRPM8 -> S1 (mouse) + pIC | UNCERTAIN | B (mouse only) |
| Warm | warm C-fibres -> posterior insula, absent from S1 | IMPLAUSIBLE | B (converging A for insula) |
| Proprioception | 3a/2 posture + kinematics, efference copy | PARTIAL (bias/direction, not continuous posture) | B/C |
| Naturalness | spatiotemporal + convergent pop activity | PARTIAL, improving with biomimicry | B |
| Stability (location) | interface + map stability | PLAUSIBLE | A |
