# Numeric facts for models (each with citation DOI/PMID actually opened; exact as reported)

## neurologist
(Quoted human-trial facts only; not settings to apply. Full annotations: lit\neurologist.md. FT = full text opened, AB = abstract.)
- Pulse shape (Pitt/Chicago trial NCT01894802): cathodal-first, 200 µs cathodal, 100 µs interphase, 400 µs anodal at half amplitude;
  20-300 Hz; 2-100 µA. [Hughes 2021 JNE, 10.1088/1741-2552/ac18ad, PMID 34320481, FT; Hobbs 2025 PMID 40106898, FT]
- Caltech pulse: 200 µs/phase, 53 µs interphase, 1 s trains; tested 20-100 µA x 50-300 Hz (150 Hz in exp 1). [Armenta Salas 2018, PMID 29633714, FT]
- Caps used in humans: 100 µA, 300 Hz; max continuous 15 s @100 Hz or 5 s @300 Hz, then equal off time (50% duty). 100 µA x 200 µs
  = 20 nC/phase (arithmetic). No Shannon k or µC/cm2 value was quoted in any opened human paper (UNVERIFIED). [Hughes 2022 BrainStim, PMID 35671947, FT]
- Stimulator drops pulses above 280 Hz (CereStim). [Hughes 2022, FT]
- Cited cat-cortex damage level: continuous 4 nC/phase (= 20 µA @ 200 µs) produced neuron loss (McCreery, as cited in Hughes 2021 JNE; primary not opened).
- Detection thresholds: 9.2-35 µA (subset, JHU) [Fifer 2022, PMID 34880087, AB]; initial medians 14.5-22.5 µA in 4 of 5 people,
  61.5 µA in 1 [Greenspon decade preprint, PMID 40832410, FT]; median 31.5 µA at day 100 -> 10.4 µA at day 1500 (n=1) [Hughes 2021 JNE, FT].
- Threshold drift: +3.54 +/- 11.52 µA/year (mean +/- SD across electrodes, 5 people); functional electrode = median threshold < 100 µA;
  functional fraction 62+/-15% (preprint) / 64+/-13% (published) at end of follow-up; 54-60% at 10 y (one person); >75% at 1 y in 3/5.
  [Greenspon 2026 STM, PMID 42455900, AB; preprint FT]
- Persistent-sensation AEs: 53 over 5 people; ~1 per 22,000 trials; mostly <10 s, max ~9.5 min; 0 serious AEs; 0 seizures reported; 168 M pulses;
  588 h; 1666 mC total. [Greenspon preprint FT]
- Amplitude JND (standard 60 µA, 75% correct): median 13.5 µA, IQR 8.5-22.9 µA, n=35 electrodes (outliers 60, 106 µA);
  biomimetic 9.7 vs linear 16.6 µA (n=22). Weber's law holds on average. Threshold vs JND r = -0.496.
  Discriminable levels (threshold..100 µA): median 8 (single), 11 (biomimetic), 19.5 (biomimetic 4-electrode). [Greenspon 2025 NBE, PMID 39643730, FT]
- PF size: ~3x (median +170%) for 40 -> 80 µA @100 Hz; +129% for 50 -> 200 Hz @60 µA; percept size +21% for 20 -> 80 µA (JHU);
  percept ~33% larger than a finger pad. [Greenspon 2025 FT; Fifer 2022 AB]
- Frequency: on >50% of electrodes 20-100 Hz is MOST intense at 60 µA; 3 electrode groups (low/intermediate/high preferring);
  at 20 µA, 20 -> 100 Hz increases intensity on all groups. [Hughes 2021 eLife, PMID 34313221, FT]
- Adaptation: continuous ICMS -> complete percept loss within 1 min (all continuous/burst protocols); intermittent (1 s on/5 s off x50)
  never extinguished over >3 min. [Hughes 2022, FT]
- Responsive electrodes: 46/96 (48%) at 20-100 µA/150 Hz; proprioceptive 79 vs cutaneous 302 reports. [Armenta Salas 2018, FT]
- Electrode counts: 2 arrays x 32 wired S1 electrodes + 88 wired M1 electrodes (Pitt P2) [Flesher 2021, PMID 34016775, FT];
  2 x 48-ch S1 arrays (Caltech FG) [Armenta Salas 2018]; 6 x 64-ch intracortical arrays total, one person (Case) [Herring 2024, PMID 37982637, AB].
- Closed-loop effect: ARAT trial time median 20.9 -> 10.2 s (-51.2%); grasp phase 13.3 -> 4.6 s (-66%); reach/transport -25%;
  object-zone time 3.3+/-1.2 -> 2.3+/-0.4 s; transfers/2 min 15.8+/-3.8 -> 17.8+/-2.4 (n.s.); ARAT 17 -> 21. n=1. [Flesher 2021, FT]
- Force-matching: ICMS reduced force error (p=0.022) but no success-rate effect; no difference vs sham. [Quick 2020, PMID 33018723, FT]
- Latency pieces (no end-to-end loop latency found, UNVERIFIED): recording blanking 740 µs after each pulse [Weiss 2019, PMID 30444217, AB];
  ICMS RT ~48 ms slower than intensity-matched vibration, TOJ PSS ~0 [Christie 2022, PMID 35644516, AB]; motion-direction accuracy 30% @50 ms
  vs 72% @200 ms trains, orientation asymptote 78% at 0.5 s; trains >0.5 s apart perceived as separate events [Valle 2025, PMID 39818881, FT];
  NHP: >=480 µA over 16 electrodes gives RT up to 20 ms faster than mechanical cue [Sombeck 2020, PMID 31778982, AB].
- Spatial patterning accuracies: edge orientation 61-89%; motion direction 76-78% (98% across digits, c1); 3D object ID 79% (n=45);
  curvature >75% once amplitude difference >20%. [Valle 2025, FT]
- Naturalness: biomimetic judged closer to real indentation on 32% of single electrodes, 75% of 4-electrode groups [Hobbs 2025, FT];
  'natural' descriptors 100% multi vs 85% single channel [Bjanes 2025, PMID 41191971, AB].
- Subthreshold ICMS lowers vibrotactile threshold by median 1.5 dB; suprathreshold vibration raises ICMS threshold by median 2.4 dB. [Osborn 2025, PMID 40216307, AB]
- NHP chronic-safety basis: 10-100 µA, 1 or 5 s trains, duty 1/1 or 1/3, 4 h/day, 5 d/week, 6 months, no added tissue damage.
  [Rajan 2015, PMID 26479701, AB]; impedance stabilizes after 10-12 weeks [Chen 2014, PMID 24503702, AB].

## neurobiologist
(Full annotations: lit\neurobiologist.md. Animal/human stimulation values are reported facts, not settings.)
Afferents (periphery)
- Low-threshold mechanoreceptive unit density (human, modelled): fingertip 241 units/cm2, palm 58 units/cm2; relative density palm:finger:fingertip = 1:1.6:4.2; gradient carried by RA+SA1, PC+SA2 ~uniform. [A] PMID 439026
- Afferent indentation thresholds (medians, human): PC 9.2 um, RA 13.8 um, SA2 33.1 um, SA1 56.5 um; psychophysical 11.2 um (fingers) / 36.0 um (palm centre). One RA spike can suffice for detection. [A] PMID 536918
- Class shares of hand tactile fibres: SA1 ~25%, RA ~40%, SA2 ~20%, PC ~15%. RF: SA1 mean ~10 mm2 (multiple hotspots), SA2 mean 50 mm2, PC large. Frequency sensitivity: SA1 <~10 Hz (~5 Hz), RA intermediate, PC peak ~250 Hz. [A, review] PMID 30215864
- SA1 static rate vs indentation: negatively accelerating, mean power exponent 0.66; SA1 CV 58.7 +/- 2.3 m/s, SA2 CV 45.3 +/- 3.6 m/s; SA2 spontaneous + regular, SA1 no spontaneous. [B] PMID 1127614
- TouchSim: ~12,500 afferents (SA1/RA/PC) on palmar hand, <1,000 per fingertip, ~4,000 in palm. Rate fit R2 train 0.91 +/- 0.04 (sine) / 0.92 +/- 0.11 (noise); validation R2 0.85 +/- 0.08 (diharmonic). Timing precision <8 ms all classes; PC sub-ms; SA1/RA 3-8 ms. Population: flutter -> hundreds of spikes/s (SA1/RA pops); high-freq vibration -> up to 100,000 spikes/s (PC pop). No SA2, thermal or proprioceptors. [B] PMID 28652360
- Intensity: local afferent population response logarithmic in amplitude; whole-population response linear. [B] PMID 17959811
- Texture: relevant skin vibrations 50-800 Hz; SA1 respond <10 Hz to most textures; 7 PC fibres -> 83% classification of 55 textures; PC optimal temporal resolution ~2 ms; spike trains dilate with speed (warp 120->80 mm/s: 89%; 40->80 mm/s: 62%). [B] PMID 24082087
Thermal
- TRPM8 activated below ~26 C; TRPM8-/- mice still avoid <10 C. [B] PMID 17538622
- Warm fibres (monkey): CV 1.2 +/- 0.5 m/s; peak rate 1.5-4.0 s after warming onset; decay time constant 5-12 s; linear intensity 0-8 C from 34 C; RF focal zone <1 mm; >80% silent at >=50 C; suppression if ISI <60 s. [B] PMID 114608
- Mouse cortex: 10 C cooling (32->22 C) drives S1; 10 C warming does not (tiny fraction of S1 cells, delayed/inconsistent); posterior insula has somatotopic cool+warm; warm responses delayed vs cool. [B] PMID 36755097
Proprioception
- Human muscle spindle background mean rates ~10 Hz. [B, review] PMID 29668385
- S1 proprioceptive cells: 46/86 (53.5%) show movement-direction hysteresis in tonic (posture) activity; broad ~sinusoidal directional tuning. [B] PMID 7884459
- Area 2 ICMS during force perturbations: 5 uA no bias, 20 uA strong bias toward stimulated PD (monkey). [C, chapter] PMID 28035576
Cortex
- Skin-to-S1 response latency ~20 ms (macaque, indentation). Onset transient/sustained ratio mean >15x (range 2.2-42.4, median 12.0, 28 skin locations); offset/sustained mean >8x (range 0.76-35.0, median 6.0). Sustained activation confined to a fraction of a mm2 of cortex. [B] PMID 30668644
- Area 3b RFs: 94% single excitatory centre + 1-4 inhibitory flanks; ~half have near-balanced excitation/inhibition. [B] PMID 9502821
- S1 hand RFs 10-60 mm2 (smallest in L4); 51% (3b) / 40% (area 1) neurons show sustained + OFF responses (SA1 + RA/PC convergence); ~5% of area-1 neurons Pacinian-like. [A, review] PMID 30215864
- S1 encodes vibration frequency up to 800 Hz by phase-locking, not rate. [B] PMID 23667327
ICMS
- Near-threshold ICMS (4-9 uA) activates sparse cells hundreds of um from tip; 15-30 um tip move changes activated set; activation via axons in a volume tens of um wide. Stoney 1968 (second-hand via Histed): 10 uA -> 100 um, 100 uA -> 450 um radius. [B] PMID 19709632
- Model: somatic activation is predominantly antidromic at all amplitudes; initiation volume grows with amplitude, somatic volume ~constant, density rises. [C] PMID 34861412
- Monkey S1 ICMS amplitude JND ~30 uA, ~constant from 30-100 uA standards (no Weber law) -> ~2 discriminable steps; cathodal-first thresholds ~10 uA lower than anodal-first; thresholds rise below ~250 Hz; 3b = area 1 JNDs. [B] PMID 26504211
- Monkey ICMS frequency discriminable up to ~200 Hz (tested 10-400 Hz). [B] PMID 31879342
- Human S1 ICMS detection threshold median 31.5 uA (day 100) -> 10.4 uA (day 1500), n=1. [B] PMID 34320481
- Human percept descriptors (n=1, 381 reports): squeeze 24.9%, tap 17.3%, right movement 9.7%, vibration 8.1%, blowing 6.6%, forward movement 5.8%, pinch 5.5%. [B] PMID 29633714
- Biomimetic (onset/offset) ICMS judged more like indentation: 32% of single electrodes, 75% of 4-electrode groups; less charge for matched intensity; 'Less Warm' 19% of descriptors. n=3. [B] PMID 40106898
- Bidirectional BCI with ICMS: task time median 20.9 s -> 10.2 s (n=1). [B] PMID 34016775

## neuroinformatics
- Recruitment follows the square of electrode–neuron distance. Excitability is 100–4000 µA/mm² at a 0.2 ms cathodal pulse. 10 µA directly activates "a few tenths to several thousands" of cell bodies (cat motor cortex). Tehovnik 1996, PMID 8815302, DOI 10.1016/0165-0270(95)00131-x (abstract).
- ICMS sparsely activates neurons "as far as millimeters away, even at low currents", via axons in a volume "tens of microns in diameter". Histed 2009, PMID 19709632 (abstract).
- Model: the volume where action potentials are initiated grows with amplitude; the volume of activated somata stays about constant while density rises; no direct soma/dendrite activation. Kumaravelu 2022, PMID 34861412 (abstract). Model: ModelDB 267691, 6410 neurons, 25 cell types (readme).
- Single-pulse ICMS gives short-latency excitation 0–25 ms, then inhibition 25–200 ms. Kumaravelu & Grill 2024, PMID 38492885, PMC11090107 (full text).
- Mouse cortex: fewer than 5% of neurons directly activated; amplitude raises density, not extent; more than 50% modulated at higher amplitudes; point-source model uses ρ = 5.8 Ω·m; direct-response windows are 5 µA 0.68 ms, 25 µA 1.14 ms, 50 µA 1.22 ms, 100 µA 1.47 ms. Hickman 2026, Cell Rep, PMID 42207642, PMC13404931 (full text). Data: DANDI 000774.
- TouchSim code constants (hsaal/touchsim constants.py): SA1/RA/PC densities are 10/25/10 (palm), 30/40/10 (finger), 70/140/25 (fingertip). Units are not stated (probably per cm², UNVERIFIED). Afferent depths are SA1 0.3, RA 1.6, PC 2.0 (units unstated). Internal sampling rate is 5000 Hz.

## mathematician
(Opened by mathematician; full annotations in lit\mathematician.md. Stimulation values are reported facts, not settings.)
- Greenspon 2025 NBE (PMID 39643730, FT PMC12176618): JND = half the difference between amplitudes at p = 0.25 and p = 0.75 (standard 60 uA, comparisons 40-80 uA); JND equal at 50 and 100 Hz;
  flat-train levels median 7 (range 2-14, n = 35); Fig. 7e levels median 8 (linear single, n = 22), 11 (biomimetic single, n = 22), 19.5 (biomimetic quartets, n = 8); natural touch ~45-50 levels over 0-0.4 N;
  biomimetic amplitude a(t) = alpha*F(t-dt) + beta*|df(t)|/dt; biomimetic charge = 69 +/- 7% of peak-matched linear.
- Callier 2020 PNAS (PMID 31879342, FT PMC6969512), monkey: frequency JND ~3 Hz at a 20 Hz standard to 95 Hz at a 200 Hz standard; Weber fraction 0.15 -> 0.5 between 50 and 100 Hz.
- Okorokova 2018 (PMID 30245482, FT PMC6324178): biomimetic model vs TouchSim aggregate firing rate R2 0.85/0.87/0.90 (noise/sine/steps); area R2 0.83/0.61/0.71; ADL R2 0.84.
- Johansson & Westling 1987 (PMID 3582528, AB): slip -> grip/load ratio change latency 74 +/- 9 ms. Johansson & Westling 1984 (PMID 6499981, AB): 0.06-0.08 s.
- Caldwell 2019 (PMID 30824821, AB): ECoG S1 surface stimulation (not ICMS) median RT 254-528 ms vs haptic 198-313 ms (4 subjects).
- Kontsevich & Tyler 1999 (PMID 10492833, AB): psi threshold within 2 dB (23%) in < 30 2AFC trials; slope to the same precision ~300 trials.
- Dadarlat 2015 (PMID 25420067, FT PMC4282864): 8-electrode ICMS vector code; ICMS-only performance comparable to vision at 15-25% coherence; VIS+ICMS matches minimum-variance integration.
- DERIVED (arithmetic, mine): JND 13.5 uA at 60 uA -> percept sd per stimulus sigma_p = JND/(0.6745*sqrt2) = 14.15 uA; Weber w = 0.225 (flat), 0.162 (biomimetic).

## ERRATA from the independent citation audit (queen, 2026-09-26; see lit\AUDIT.md rows 9, 23, 31, 42, 78)
- Flesher 2021: M1 had 2 arrays x 88 wired electrodes (176 in total), not 88. The S1 count of 2 x 32 = 64 is correct.
- Hughes 2022: "complete loss within 1 min" refers to 60-s BURST trains (26/30). Continuous 20 Hz trains showed no change within 15 s.
- Greenspon 2026: write "no serious AEs; all 53 AEs were persistent sensations", not "0 seizures reported". Cite the preprint (PMID 40832410) for AE counts.
- Greenspon 2025 numbers are grade B (one consortium, n=3), not A.
- The sigma_p derivation assumed a probit link. Greenspon fits a logistic (sigma ~14-16 uA).
