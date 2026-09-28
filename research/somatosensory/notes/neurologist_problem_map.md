# Neurologist problem map: human S1 ICMS for closed-loop BCI (cycle 1, 2026-09-26)
Sources: all entries in lit\neurologist.md (DOI/PMID there). Grades per HIVE.md. Parameters are quoted trial facts, not
settings. Anything that would need testing in people requires an IRB/FDA-approved clinical study.
Total evidence base: about 12 people with S1 ICMS arrays across 4 groups (Pitt/Chicago n=5, Caltech n>=2, JHU n=1,
Case Western n=1, plus the Feinstein n=1 bypass). Nearly every finding is n=1-5 and all participants are male.

## SOLVED (enough evidence for engineering assumptions)
| Claim | Grade | Numbers reported |
|---|---|---|
| ICMS of S1 hand area evokes somatotopic percepts on the hand/fingers, incl. fingertips | A | Flesher 2016; Fifer 2022 (8 fingers, 7 sites identifiable); Downey 2024 (>=4 digits in 5/5); Armenta Salas 2018 (arm) |
| Amplitude monotonically grades intensity | A | Flesher 2016; Hughes 2021; Greenspon 2025 |
| Detection thresholds are low, 10s of µA | A | 9.2-35 µA (Fifer); initial medians 14.5-22.5 µA in 4/5, 61.5 µA in 1 (Greenspon 2026 preprint); 31.5 -> 10.4 µA (Hughes JNE 2021) |
| Projected fields stable over years | B (one consortium, 3 people) | stable 2-7 y; within-session variability = across-year variability (Greenspon 2025) |
| Chronic ICMS within 100 µA / 300 Hz caps has no serious AEs up to 10 y | B | 5 people, 168 M pulses, 24-27 implant-years, 0 SAE, 53 persistent sensations (~1/22,000 trials), no seizures (Greenspon 2026) |
| Implant (Utah/NeuroPort) platform risk is acceptable | B | BrainGate 14 people, 12,203 device-days, 6 device-related SAEs, 0 explants (Rubin 2023) |
| Contact feedback improves a real BCI task | B (n=1) | ARAT trial time 20.9 -> 10.2 s; grasp phase 13.3 -> 4.6 s (Flesher 2021) |
| Stim artifact can be removed from M1 recordings | B | blanking + 750 Hz HPF, spikes back 740 µs after pulse; performance unchanged (Weiss 2019) |
| Multi-electrode ICMS gives stronger, more localizable, more "natural" percepts at lower per-electrode charge | A (Pitt/Chicago + Caltech) | discriminable levels 8 -> 19.5 (Greenspon 2025); natural descriptors 85% -> 100% (Bjanes 2025) |

## OPEN (with the quantitative limits the literature reports)
1. **Dynamic range / force resolution.** Single-electrode JND median 13.5 µA (IQR 8.5-22.9) between threshold and the 100 µA cap
   gives about 8 discriminable levels (up to 19.5 with biomimetic quartets). Contact forces "often exceed 1 N". Percepts from
   single electrodes are "typically weak". (B)
2. **Adaptation under sustained contact.** Continuous ICMS -> complete loss of sensation within 1 min; intermittent keeps it
   >3 min (Hughes 2022). No encoder has been shown to hold a steady-state grip percept for minutes. (B)
3. **Frequency is a non-monotonic, electrode-specific knob.** On >50% of electrodes 20-100 Hz feels most intense (Hughes 2021).
   A single frequency-to-intensity map cannot work; each electrode needs calibration. (B)
4. **Texture.** No human ICMS texture discrimination found. Closest are edges, shapes and motion (Valle 2025: orientation 61-89%,
   motion 76-98%), and object "feel" matched only slightly above chance (34-37% vs ~20% chance; Verbaarschot 2025). (B)
5. **Temperature.** No thermal percept study found. "Warm" appears only as a verbal descriptor (Verbaarschot 2025, Hughes
   2021 questionnaire). Area 1/3b arrays are unlikely targets for thermal channels (hypothesis, UNVERIFIED). Effectively OPEN, no data.
6. **Proprioception.** One person (Armenta Salas 2018): proprioceptive reports in 79 of 381 sensations, biased to higher amplitudes;
   arrays in the arm area. No functional proprioceptive closed-loop in humans. Area 3a/2 targeting has not been reported in humans. (B, n=1)
7. **Longevity / channel attrition.** Thresholds rise about 3.5 µA/year (SD 11.5), functional electrodes drop about 21-25%, and 54-60% of
   electrodes still work at 10 y in one person (Greenspon 2026). Direction differs between people (P2 thresholds fell over 1500 d).
   Recording quality declines on all arrays (Hughes 2021). (B)
8. **Channel count.** Typical: 32 wired stimulating electrodes per person (2x Utah in area 1, Flesher 2021); 2x48 channels at Caltech;
   max seen 6x64 intracortical channels total (Herring 2024, not all S1). Hand coverage is patchy (only >=4 digits guaranteed). (B)
9. **Loop latency.** No end-to-end sensor -> ICMS -> percept loop latency reported in the opened sources (Flesher 2021 main text
   has none; supplement not opened -> UNVERIFIED). Known pieces: recording blanking 0.74 ms/pulse; ICMS perceived about 48 ms slower
   than intensity-matched vibration in reaction time but simultaneous in TOJ (Christie 2022); motion direction needs about 200 ms trains
   (72% at 200 ms vs 30% at 50 ms, Valle 2025); NHP multi-electrode ICMS RT can be 20 ms faster than mechanical (Sombeck 2020).
   Visual-ICMS binding window is offset from zero (Rosenthal 2025). (B)
10. **Read/write interference beyond artifact.** S1 ICMS modulates M1 neurons in a context-dependent way and degrades decoding.
    Biomimetic onset/offset trains reduce this (Shelchkova 2023). (B)
11. **Per-user calibration burden.** Thresholds, JNDs (outliers 60-106 µA), frequency preference, quality reliability
    (r>0.81 in 3/5, not reliable in 2/5) and naturalness all vary by electrode and person. Some biases depend on history
    (time-order error, Greenspon 2024). No automated calibration method has been validated. (B)
12. **Naturalness metric.** Biomimetic trains are judged more like real indentation on 32% (single electrode) to 75% (4-electrode)
    of sites (Hobbs 2025). Naturalness seems "cognitively constructed" (Hutchison 2025, C). No standard scale exists.
13. **Safety margins are empirical, not mechanistic.** Caps (100 µA, 300 Hz, 200 µs cathodal phase = 20 nC/phase; 15 s on/15 s off
    at 100 Hz) come from NHP chronic studies (Rajan 2015, Chen 2014). Shannon-type k / µC/cm2 limits were not quoted in any
    opened human paper (UNVERIFIED). After-discharge (persistent sensation) risk rises with multi-electrode stimulation, which
    conflicts with open problem 1 (multi-electrode is the fix for dynamic range). (B)

## Where software/maths can contribute (no human work implied)
- Per-electrode psychometric models (threshold, Weber JND, frequency-group) fitted to published summary statistics. This could be a Bayesian
  calibration prior that reduces the number of calibration trials (simulate only).
- Encoder optimization under constraints: maximize discriminable levels subject to a per-electrode charge cap and an adaptation model
  (continuous -> extinction under 60 s).
- Survival model of electrode attrition (3.5 µA/y drift, about 21-25% loss) to forecast usable channels per year.
- Loop-latency budget model built from the pieces in item 9. Flag the missing end-to-end number as a gap.
- Decoder robustness to S1->M1 stimulation crosstalk (Shelchkova 2023), using public datasets only.
