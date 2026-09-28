# Mathematician: candidate hypotheses (cycle 1, 2026-09-26)
Scope: computational/theoretical only. Stimulation parameters below are QUOTED from published studies
(sources in lit\mathematician.md) and used as simulation inputs. They are not settings for any person;
anything that would need testing in people requires an IRB/FDA-approved clinical study.
Notation: JND = just-noticeable difference (75% criterion); w = Weber fraction = JND / standard.

Ranking: combined score of (a) value to the program and the platform, (b) whether a CPU simulation can
support or refute it, (c) whether the result is NOT settled by the setup itself.

| Rank | ID | Short name | Prereg |
|---|---|---|---|
| 1 | H3 | Latency budget for ICMS grip-force feedback | prereg\P1_grip_latency_budget.md |
| 2 | H1 | Biomimetic vs linear encoding: event information per unit charge | prereg\P2_biomimetic_info_per_charge.md |
| 3 | H4 | Bayesian adaptive (psi) calibration vs staircase | prereg\P3_psi_vs_staircase_calibration.md |
| 4 | H2 | Channel capacity and multi-electrode pooling under Weber's law | prereg\P4_pooling_capacity.md |
| 5 | H6 | Sustained-charge cost to motor decoding | theory only |
| 6 | H5 | Proprioceptive ICMS + vision Kalman fusion | theory only (already largely shown in NHP) |

---------------------------------------------------------------------------------------------------
## H3. Grip-force feedback latency budget (rank 1)
Mechanism. Humans upgrade the grip/load force ratio 74 +/- 9 ms after a slip (Johansson & Westling 1987,
PMID 3582528). Artificial feedback adds delay: human ECoG surface stimulation of S1 gave median RTs of 254-528 ms
against 198-313 ms for touch (Caldwell 2019, PMID 30824821). In monkeys, multi-electrode ICMS gave RTs up to 20 ms
faster than a mechanical cue (Sombeck & Miller 2019, PMID 31778982). With unexpected load changes, the object can
slide out of the fingers before a delayed correction arrives. A controller can compensate with a bigger static
safety margin. With fragile objects this in turn raises the crush rate. Flesher 2021 notes their task had
"no penalty for grasping the objects too firmly".
Prediction (numbers). In a stochastic grip model (P1), define delta* as the largest added latency at which ICMS
feedback still keeps >= 50% of the benefit of natural feedback over no feedback, after optimising the safety
margin separately for each condition. Predicted delta* = 50-150 ms. ICMS at +100 ms should also cut failures by
>= 20% relative to vision-only feedback.
Falsification. delta* < 50 ms would mean that even the best published cortical-stimulation latencies lose most of
the benefit. delta* > 150 ms, or no finite delta*, would mean latency does not limit this task. Either way the
prediction fails.
Software test now. P1: numpy Monte Carlo of a 2-digit grasp with random friction, mass, load pulses, crush
limits, motor lag and noise, with the safety margin optimised per condition. Under 10 min on CPU.
Platform value: this yields a "latency budget" spec that a hardware maker can test its end-to-end
decode -> sensor -> stimulate pipeline against.

## H1. Biomimetic (transient + sustained) vs linear amplitude encoding (rank 2)
Mechanism. Natural afferent population activity peaks at contact onset and offset, with weak sustained responses
(Greenspon 2025 cites <10% during maintained contact). A biomimetic encoder a(t) = alpha*F + beta*|dF/dt|
(Greenspon 2025, PMC12176618) puts charge where events happen. Measured effects: median JND 9.7 uA for biomimetic vs
16.6 uA for linear, at 69 +/- 7% of the charge. Open question: is the gain in information about force CHANGES per unit
charge real under a noisy observer model with Weber noise? If so, does it depend on cortical adaptation to
sustained ICMS? The alternative: the biomimetic code only trades sustained-force information away.
Prediction (numbers). At matched total charge and with no adaptation, detection of +/-10-30% force steps within 200 ms
reaches d'_bio / d'_lin >= 1.3, and hold-force estimation RMSE degrades by <= 1.5x.
Falsification. The ratio is < 1.3, or the RMSE penalty is > 1.5x. An adaptation sweep reports whether any benefit
exists only when sustained ICMS responses adapt, which would make adaptation the unknown to measure.
Software test now. P2: synthetic grasp force trajectories, two encoders, a leaky-adaptation + Weber-noise observer
calibrated to the published 13.5 uA JND, and ROC analysis.

## H4. Model-based per-user calibration: psi method vs staircase (rank 3)
Mechanism. Every electrode needs a detection threshold (and ideally a JND) and these drift. The median human threshold
fell from 31.5 uA (day 100) to 10.4 uA (day 1500) (Hughes 2021, PMID 34320481). The psi method picks each trial to
maximise expected information and reaches threshold within 2 dB in < 30 2AFC trials (Kontsevich & Tyler 1999,
PMID 10492833). Staircases are simpler and robust to lapses.
Prediction. Across 48 simulated observer cells (threshold 10-50 uA, slope, lapse 0-10%), psi reaches 20% RMS
threshold error with >= 30% fewer trials than a 3-down-1-up staircase in >= 75% of cells. Bias stays <= 10% at
lapse <= 5%.
Falsification. Savings < 30% in more than 25% of cells, or bias > 10% at lapse <= 5% (model misspecification wins).
Software test now. P3. Platform value: "calibration minutes per array" is a direct product feature.

## H2. Channel capacity and multi-electrode pooling (rank 4)
Mechanism. If perceived intensity follows total injected charge with Weber noise (Greenspon: discriminability is
"well expressed in terms of difference in total charge"), then pooling M electrodes onto one percept adds only
ln(M)/ln(1+w) discriminable levels. The added information is log2 of that: a logarithmic gain in levels, and
roughly log-log in bits.
Prediction (numbers, computed analytically by me BEFORE writing P4, so this part is a consistency check rather
than a blind test). Single electrode 11 levels (biomimetic single-electrode median, n = 22, Greenspon Fig. 7e) and w = 0.162 predict 20.2 levels for quartets. The observed value is 19.5.
Over the reported JND IQR, reaching natural touch (45-50 levels) needs 81 to about 5800 pooled electrodes. Pooled
amplitude coding therefore cannot reach natural force resolution on a 64-channel array. Extra capacity has to come
from spatially independent channels (Valle 2025 edges/motion) and from a lower w (biomimetic).
Falsification. The pooled model without spatial summation (threshold scales with M) predicts no gain (11 levels) and
is refuted by 19.5. If the coder's Monte Carlo 2AFC simulation of the pooled observer does not reproduce the
analytic level count within 10%, the analytic formula is wrong.
Software test now. P4: analytic formula + Monte Carlo + Blahut-Arimoto capacity in bits/symbol.
Texture bound (ESTIMATE; answers neurobiologist's request on BOARD). There are two different questions:
(1) Identification information. Neurobiologist's fact (PMID 24082087, not opened by me): 7 PC fibres classify 55 textures at 83%.
    Fano's inequality gives I >= log2(55) - H_b(0.17) - 0.17*log2(54) = 4.1 bits per exploration. One electrode's ICMS channel
    offers about log2(11) = 3.5 bits in amplitude (biomimetic, Greenspon 2025). Frequency adds about 6.6 levels over 20-50 Hz at w = 0.15
    and about 3.4 levels over 50-200 Hz at w = 0.5 (Callier 2020 monkey Weber fractions), so roughly 10 levels = 3.3 bits.
    Frequency and amplitude are confounded on many electrodes (Callier 2020; Hughes 2021 eLife), so these bits do not simply add.
    Conclusion: about 4 bits of texture IDENTITY per exploration is within reach of a few electrodes, but only as an arbitrary,
    learned code (like Dadarlat 2015).
(2) Natural texture feel. This needs ms-precise spike timing up to 800 Hz (neurobiologist facts, PMIDs 24082087, 23667327).
    ICMS frequency is discriminable only to ~200 Hz (Callier 2020), and above ~100 Hz w reaches 0.5. On current evidence, a
    NATURAL texture code is not reachable with ICMS pulse timing. Grade: C (theory built from B-grade inputs). A proper test
    (a Blahut-Arimoto joint amplitude x frequency channel with a confound correlation rho) can be added to P4 in cycle 2.

## H6. Sustained-charge cost to motor decoding (rank 5, theory only)
Mechanism. S1 ICMS evokes M1 activity that disrupted decoding. Biomimetic stimulation, with less sustained
stimulation, minimised the disruption (Shelchkova 2023, PMID 37949923). Model: decoder error variance =
sigma_0^2 + k * (sustained charge rate). Under a fixed decode-error budget, this adds a second reason to prefer
transient codes on top of H1. Prediction: the optimal encoder in a joint (information - lambda*decoder disruption)
objective has beta/alpha rising with k. It is not preregistered because k is not available from the abstract. Next
cycle: ask neuroinformatics whether any public dataset lets us estimate k.

## H5. Proprioceptive ICMS as a low-dimensional cue fused with vision (rank 6, theory only)
Mechanism. MLE/Kalman fusion (Ernst & Banks 2002). Monkeys already integrated an 8-electrode non-biomimetic ICMS
vector signal with vision at minimum variance (Dadarlat 2015, PMID 25420067). Novelty here is low. A model would
only give design curves (fused variance vs ICMS cue variance and latency). A delayed cue needs a Smith-predictor or
Kalman prediction step (Miall 1993). This is deprioritised in favour of H3, which carries the same latency question in
a task where vision is weak (slip).
