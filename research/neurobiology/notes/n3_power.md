# N3 power analysis for the NC-P controls (synthetic only; before any N3 data are chosen or downloaded)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Mathematician/methodologist, hive cycle 2, 2026-09-26. Status: UNREVIEWED (HIVE rule 8). No EEG was read. No model output on any
new subject exists.
- Code: `code\n3_power\power_sim.py`, SHA-256 `06508ca5000f6bcf...5079e`.
- Output: `results\n3_power\power_sim.json` and `power_sim_stdout.txt`.
- Run: 284 s with 6 workers, well under 1 GB. Seed 20261001, stream 40. Python 3.12.10, numpy 2.5.3, scipy 1.18.1.
- Inputs used: synthetic label timelines and synthetic scores only. Calibration targets were taken from the N1b card on the burned
  subjects chb01/03/10.

Note: an earlier, unfinished draft by another instance exists at `code\power\n3_power.py` / `results\power\`. It is not used here
and has not been reviewed.

## 1. Answer in one paragraph

- **Why N1b failed.** The event arm failed mainly because of the **combination rule**, not the 4 seizures alone. Literal Fisher on the
  discrete p_up, which has a point mass at 1, rejected **0 of 6,000** honest pseudo-experiments even at α = 0.05. Its real size is
  about 0, so it wastes almost all of its power.
- **The better rule.** A **pooled conditional-randomisation statistic** (ΣF1 over retained replicates, with the null built by summing
  each replicate's own null draws index-wise) is exact. Its measured size is 0.0017-0.0025 at α = 0.0025, 0.010-0.015 at 0.0125 and
  0.046-0.054 at 0.05. It is the most powerful rule in every cell.
- **Even so, the event arm cannot reach 0.8 power at feasible N.** With the surrogate that reproduces N1b's real event behaviour,
  power ≥ 0.8 at α = 0.0025 (R = 10 replicates per subject) needs:
  - for the PL-A label leak: **4 subjects × 4 references**, or **2 subjects × ≥ 13 references**;
  - for the PL-B threshold leak: **≥ 3 subjects × ≥ 7-10 references**.
  - Fresh CHB-MIT subjects that the unchanged N2 code can run give at most 2 subjects with 4 test seizures each (§5). So the event arm
    **cannot** be the formal leak detector.
- **The window arm can be the gate.** It trips PL-A with power 0.96-1.00 at 2 subjects × 4 phantoms, and still ≥ 0.93 for a leak 3x
  weaker (T_A 0.65).
- **Proposal.** The **window arm (T_A) becomes the formal leak gate**. The event arm stays a **validity check** (it can fail the harness)
  but is **demoted to descriptive for power**. Threshold (PL-B-type) leaks are covered at code level: the F3 guard plus a mandatory
  violation test. They are not covered statistically.

## 2. The surrogate (what one simulated "fit" is)

**Layout and scores**
- Test allowed time H = max(2 h, 1.25 h × K), in 3,000-s segments. Training allowed time is 4 h (used for t_rm).
- K phantoms per replicate use CHB-MIT-like durations (27-101 s).
- The window latent has three parts:
  - a fast AR(1) component (ρ 0.90);
  - a slow AR(1) component (ρ 0.998, weight 0.4-0.8);
  - artifact bursts at 0.5-4 per hour (per subject, log-uniform), 10-120 s long, with amplitude 1.5-4 SD.
- Train→test non-stationarity has two sources:
  - a latent offset c ~ N(subject mean with SD 0.3, within-subject SD 0.5);
  - a burst-rate multiplier exp(N(0, 1.5)).
- Scores are p = expit(μ + σ·z).
  - **Saturated regime** (primary): μ ~ N(−9, 1.5), σ ~ U(2.5, 4). This is an over-confident LR fitted to phantom labels, as seen in N1b.
  - **Smooth regime** (sensitivity): μ ~ N(−1, 0.7), σ ~ U(0.7, 1.5).

**Downstream logic: the N1b/N2 pipeline, bit-checked in a self-test**
- The locked τ grid.
- 4-of-5 smoothing. Checked bit-equal against `nfharness.postprocess.hypothesis_mask`.
- 90-s merge and 300-s split, any-overlap TP with −30/+60 s, and FP as pieces touching no extended reference. Equal to
  `nfharness.scoring.reimpl_event_score` in 200/200 random cases.
- Label-free t_rm (1.323 events/h), and the ALWAYS/NEVER flags.
- Rank AUROC, equal to `nfharness.stats.auroc`.

**Sampler**
- Phantoms follow the sampler-S law: longest first, uniform on the valid (segment, onset) set, and gaps ≥ 300 s. This is implemented as
  exact vectorised rejection from a uniform superset.
- The observed and the M = 999 null placements come from the same sampler, so every p-value is exact.

**Planted leaks**
- **PL-A:** a latent shift δ·λ_subject·γ_phantom on the phantom windows. δ is calibrated so that the mean T_A = 0.775 (the N1b real
  PL-A mean).
  - "PL-A" uses γ ~ Gamma(shape 1).
  - "PL-A-hom" uses shape 20, an evenly spread leak. It is the harsher variant.
  - "PL-A-65" and "PL-A-60" are weaker leaks calibrated to T_A 0.65 and 0.60.
- **PL-B:** τ = argmax of the test-phantom F1 over the grid (ties go to the smallest τ). The p-value comes from the conditional null at that
  fixed h, as in N1b.

## 3. Calibration and validation against N1b (real card, K = 4, 3 subjects)

| quantity | N1b real | surrogate (saturated) | role |
|---|---|---|---|
| NC-P pooled phantom hit rate TP/N_ref | 17/120 = 0.14 | 0.16 | calibrated |
| NC-P FP per test hour | ~2.2 | 2.56 | calibrated |
| NC-P replicates with ≥ 20 events | 6/30 = 0.20 | 0.26 | calibrated |
| T_A replicate SD | 0.118 | 0.107 | calibrated |
| NC-P NEVER-ALARM fraction | 7/30 = 0.23 | 0.05 | **miss**: the surrogate is optimistic for Fisher (it retains more replicates) |
| t_rm = 0.99 flagged | 11/30 | 0.09 | miss (same direction) |
| PL-B: τ at the grid floor | 9/30 | 0.39 | calibrated |
| PL-B mean F1 | 0.136 | 0.124 | validation |
| **PL-B literal Fisher (3 × 10)** | **0.51** | median **0.37** (q10-q90 0.03-0.83); P(trip) 0.03 | **validation: reproduced** |
| **PL-A pooled hit rate** | **19/60 = 0.32** | PL-A 0.41; **PL-A-hom 0.31** | validation: PL-A-hom reproduces it |
| **PL-A literal Fisher T_E (3 × 5)** | **0.012** | PL-A-hom median 0.15 (q10-q90 2e-4-0.93), P(trip) **0.16**; PL-A P(trip) 0.71 | validation: the real value lies inside the PL-A-hom band |
| PL-A T_A | 0.775 | 0.73-0.75 | calibrated (δ) |

- The **smooth regime does NOT reproduce PL-B**: its literal Fisher median is 1.5e-5, against the real 0.51.
  - The reason is that graded scores give many distinct hypotheses across the τ grid, while the real phantom-trained model gives
    saturated scores. With saturated scores τ barely changes the alarm set, so choosing τ on test labels has almost nothing to exploit.
  - Primary conclusions therefore use the **saturated regime and PL-A-hom**. The smooth regime and plain PL-A are optimistic
    sensitivity cases.
- Under the validated surrogate, the N1b failure was the **likely** outcome, not bad luck: P(PL-A T_E trips) 0.16 and P(PL-B trips) 0.03.
  The N1b prereg had predicted 0.85 and 0.80.

## 4. Results (saturated regime; α = 0.0025 per test as in N1b, so the family of 4 tests is ≤ 0.01; α = 0.0125 in brackets)

**False-trip rate (size).** Honest fits, 6,000 pseudo-experiments (each observation replaced by one of its own null draws), 3 subjects × 10
replicates:

| rule | K = 4: α 0.0025 / 0.0125 / 0.05 | K = 10 | exact? |
|---|---|---|---|
| Fisher on p_up (N1b literal) | 0 / 0 / 0 | 0 / 0 / 0.0003 | valid, but its real size is ~0 (discreteness, mass at p = 1) |
| Fisher on Lancaster mid-p | 0.0002 / 0.003 / 0.013 | 0.0013 / 0.005 / 0.022 | not exact; here conservative |
| Fisher on random-tie-break p | 0.002 / 0.011 / 0.044 | 0.003 / 0.012 / 0.045 | exact up to the 1/(M+1) grid |
| **pooled ΣF1** | **0.002 / 0.012 / 0.051** | **0.0025 / 0.013 / 0.050** | **exact** |
| pooled ΣTP | 0.002 / 0.010 / 0.034 | 0.002 / 0.011 / 0.044 | exact (TP ties make it conservative) |

- The PL-B-τ null arm and the smooth regime give the same pattern.
- Window-arm Fisher on honest fits: 48 disjoint experiments, KS p 0.16, fraction below 0.05 = 0.04.
- **Every rule meets the ≤ 0.05 false-trip requirement.** The literal rule meets it only by never firing.

**Power, event arm, R = 10 replicates per subject, pooled ΣF1 (literal Fisher in parentheses).** K = references per replicate (= N_ref per
subject when phantoms mirror the real test seizures), S = subjects.

| leak | K | S = 1 | S = 2 | S = 3 | S = 4 | S = 6 |
|---|---|---|---|---|---|---|
| PL-A-hom (validated) | 4 | 0.29 (0.14) | 0.59 (0.25) | 0.72 (0.32) | **0.82** (0.39) | 0.95 (0.43) |
| PL-A-hom | 7 | 0.37 | 0.56 | 0.78 | **0.93** (0.59) | 0.99 (0.66) |
| PL-A-hom | 13 | 0.73 | **0.93** (0.80) | 0.99 | 1.00 | 1.00 |
| PL-A-hom | 20 | 0.44 | **0.86** (0.81) | 0.99 | 1.00 | 1.00 |
| PL-A (optimistic) | 4 | 0.67 | **0.95** (0.74) | 1.00 (0.89) | 1.00 | 1.00 |
| PL-B | 4 | 0.10 | 0.31 (0.02) | 0.50 | 0.65 | **0.91** (0.01) |
| PL-B | 7 | 0.31 | 0.61 | **0.85** (0.32) | 0.95 (0.49) | 0.99 |
| PL-B | 10 | 0.34 | 0.70 | **0.87** (0.47) | 0.95 (0.60) | 1.00 |
| PL-A-65 (T_A 0.65) | 4 | 0.14 | 0.18 | 0.30 | 0.35 | 0.53 |
| PL-A-65 | 10 | 0.24 | 0.48 | 0.64 | 0.76 | **0.91** |
| PL-A-60 (T_A 0.60) | 10 | 0.04 | 0.07 | 0.08 | 0.10 | 0.10 |
| PL-A-60 | 20 | 0.13 | 0.12 | 0.20 | 0.27 | 0.43 |

- With R = 5, as in N1b's PL-A arm, PL-A-hom at K = 4 is 0.16 / 0.30 / 0.47 / 0.56 / 0.79 for S = 1 / 2 / 3 / 4 / 6.
- At α = 0.0125 the event numbers rise by about 0.05-0.2 (JSON). This does not change any conclusion.
- The literal Fisher rule is dominated everywhere. Mid-p and random-tie Fisher sit between literal Fisher and the pooled rule.

**Power, window arm (T_A, Fisher on the continuous p_up).**

| leak | K = 4, S = 1 | K = 4, S = 2 | K = 4, S = 3 | K = 10, S = 2 |
|---|---|---|---|---|
| PL-A, R = 5 | 0.91 | **1.00** | 1.00 | 1.00 |
| PL-A-hom, R = 5 | 0.77 | **0.96** | 1.00 | 1.00 |
| PL-A-65, R = 10 | 0.81 | **0.93** | 1.00 | 1.00 |
| PL-A-60, R = 10 | 0.43 | 0.68 | 0.89 | 0.86 |

**Which leaks are detectable at the event level at all**
- **Label leaks that act through the scores (PL-A family).** They are detectable at the event level only when the leak is strong: T_A of
  at least ~0.73, with ≥ 4 subjects × 4 references or ≥ 2 subjects × ≥ 13.
  - For a leak at T_A 0.65 the event arm needs ≥ 6 × 10; at T_A 0.60 it is nearly blind (0.10 at 6 × 10 and 0.43 at 6 × 20, where the window arm has 1.00).
  - **The window arm detects every one of these leaks with much higher power at the same N.** The event arm adds no detection power
    for score-mediated leaks.
- **Threshold/post-processing leaks (PL-B family).** They do not change the scores, so the window arm is blind to them by construction.
  - The event arm is the only statistical detector, and it needs ≥ 3 subjects × ≥ 7 references (pooled rule), or ≥ 6 × 4.
  - In the saturated regime such a leak also barely inflates F1: 0.124 vs a null ~0.08-0.10. It is a real code defect, but a small one in effect.
- **Scorer/alarm leaks (PL-C).** They are covered by C3', which tripped in N1b. This is not re-simulated here.
- **Label-free leaks** (the normaliser fitted on test, C2b) are invisible to every label-randomisation control. They are covered by the F1 guard.

## 5. Feasibility, and the design consequence for N3

- **Coupled design.** With phantoms = real test seizures (K = N_ref), fresh CHB-MIT subjects the unchanged N2 code can run give K = 4.
  - The unchanged code needs the standard 23-label montage, ≥ 3 training seizures, ≥ 2 training files for the inner LOFO, and ≥ 4 test
    seizures.
  - Only 2 such subjects exist: chb23 (N_ref 4) and chb24 (N_ref 4, E3-relaxed); see the prereg.
  - At S = 2, K = 4, the event arm's power is 0.59 (PL-A-hom) and 0.31 (PL-B). **This is below 0.8, so the event arm cannot be the formal gate.**
- **Decoupled design (more phantoms than real seizures).** The null stays exact, because the phantoms are ours.
  - K = 13 at S = 2 would reach 0.93 for PL-A-hom. But the surrogate used ≈ 1.25 h of allowed test time per phantom, and chb23 and chb24
    have only 2.4 h and 0.97 h of allowed test time.
  - High phantom density was **not simulated**, so this route is not claimed.
- **Adopted for N3 (prereg §4).**
  - Formal leak gate: the window arm, with Fisher over R = 10 replicates per subject, both tails, α = 0.0025.
  - Mandatory planted leak: PL-A (25% of allowed test windows), which must trip T_A. Predicted power ≥ 0.96 at S = 2, K = 4.
  - Event arm: the **pooled ΣF1** statistic replaces literal Fisher. It stays on the **validity** side: p < 0.0025 in either tail fails the
    harness, and that false-FAIL rate is exact at ≤ 0.005.
  - Event-arm trips on PL-A and PL-B are **descriptive** (predicted P 0.3-0.6).
  - PL-B coverage is a code-level mandatory violation test instead.

## 6. Caveats (named, not hidden)

- **The surrogate is a model, not EEG.** It is calibrated on one real run (30 NC-P, 15 PL-A and 30 PL-B replicates on 3 burned subjects).
  It under-predicts degeneracy (NEVER 0.05 vs 0.23; t_rm saturation 0.09 vs 0.37). Both errors make event-arm power look better than it
  is, so the "event arm infeasible" conclusion is conservative in the right direction.
- **Pool resampling.** Power estimates come from resampling S of 24 simulated subjects × 10 fits (300 experiments per cell). The Monte Carlo SE is
  about 0.03 at p = 0.5, and some cells are non-monotone in K for that reason. Treat differences < 0.1 as noise.
- **δ calibration.** It was done on separate calibration subjects, so the pool T_A is 0.73-0.75 instead of 0.775. That is slightly harsher than N1b.
- **Allowed time.** chb24's test allowed time (0.97 h) and training allowed time (0.50 h) are below the simulated minimum of 2 h. Window-arm
  power for chb24 alone is therefore extrapolated. This is stated as a risk in the N3 prereg.
- **Sources.** No external source was used beyond the hive's own files. Every number above comes from `results\n3_power\power_sim.json`.
