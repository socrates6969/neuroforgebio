# Citation audit: somatosensory hive (cycle 1)
Auditor: citation-auditor (independent), 2026-09-26. Scope: notes\facts_for_models.md (all four sections) and the
load-bearing claims in lit\neurologist.md, lit\neurobiologist.md, lit\mathematician.md. The auditor did not edit other agents' files.

Method. Every source below was re-opened by the auditor, not taken from the agents' notes.
- PubMed efetch abstracts: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&rettype=abstract&retmode=text&id=...`
  (49 PMIDs) and esummary (47 more PMIDs, checked for author, year, journal and DOI).
- Full text: Europe PMC `.../rest/PMCxxxx/fullTextXML` (PMC12176618, PMC12363726, PMC8376245, PMC13571258, PMC5896877, PMC9946826,
  PMC11090107, PMC6969512, PMC6324178, PMC4282864, PMC13404931, PMC8865889, PMC6330897, PMC5452683); NCBI efetch db=pmc
  (PMC8715714, PMC8500669, PMC10308851, PMC11994950, PMC2874753, PMC7717497); PMC article HTML (PMC6917522, PMC5514748,
  PMC4679002, PMC3800989). GitHub raw files: hsaal/touchsim `constants.py` and `classes.py`.
- Verdicts: VERIFIED = the number is in the opened source as stated. MINOR-ERROR = the number is essentially right but the wording,
  attribution, count or grade needs a correction (stated). WRONG = contradicted by the source. UNVERIFIABLE = the auditor could not open a source that contains it.

## Summary
- Citation integrity: all 96 PMIDs checked resolve to the stated paper (first author, year, journal and DOI match).
  **No fabricated or mis-resolved citations were found.**
- Counts over the 81 audited entries (many rows bundle several numbers): **VERIFIED 74, MINOR-ERROR 5, WRONG 0, UNVERIFIABLE 2.**
- Corrections needed before any whitepaper use: rows 9, 23, 31, 42 and 78 (the MINOR-ERROR rows).

## Table

| # | Claim (as written by the hive) | Source | Verdict | Note |
|---|---|---|---|---|
| 1 | Flesher 2021 = Science 372:831, bidirectional BCI, n=1 | PMID 34016775, PMC8715714 | VERIFIED | Authors, year, journal and DOI match. |
| 2 | ARAT trial time median 20.9 -> 10.2 s (-51.2%) | Flesher 2021 FT | VERIFIED | "decreased by 51.2%, from a median of 20.9 s to 10.2 s" (p<0.0001). |
| 3 | Grasp phase 13.3 -> 4.6 s (-66%), 88% of the improvement | Flesher 2021 FT | VERIFIED | Exact. |
| 4 | Reach and transport phases -25% | Flesher 2021 FT | VERIFIED | "both decreased by 25%". |
| 5 | Object zone 3.3+/-1.2 -> 2.3+/-0.4 s (-30.3%, p=0.002) | Flesher 2021 FT | VERIFIED | Exact. |
| 6 | Transfers per 2 min 15.8+/-3.8 -> 17.8+/-2.4, n.s. (p=0.050) | Flesher 2021 FT | VERIFIED | Exact. |
| 7 | ARAT score median 17 -> 21 (p=0.029) | Flesher 2021 FT | VERIFIED | Exact. |
| 8 | <5 s trial once in 108 without ICMS; 14% of ICMS trials faster than the fastest no-ICMS trial | Flesher 2021 FT | VERIFIED | Also: a score of 3 was reached 15 times with ICMS. |
| 9 | "2 arrays x 32 wired S1 electrodes + 88 wired M1 electrodes" (facts, neurologist) | Flesher 2021 FT; Hughes 2021 JNE FT | MINOR-ERROR | The 88 is **per array**. Hughes 2021: "Each electrode array consisted of 88 wired electrodes" (2 M1 arrays = 176 wired M1 electrodes). S1 = 2 x 32 = 64, correct. |
| 10 | Greenspon 2025 = Nat Biomed Eng 9:935, n=3 | PMID 39643730, PMC12176618 | VERIFIED | Match. |
| 11 | JND task: standard 60 uA, comparisons 40-80 uA, 75% correct | Greenspon 2025 FT | VERIFIED | Exact. |
| 12 | Median JND 13.5 uA, IQR 8.5-22.9, n=35; outliers 60 and 106 uA | Greenspon 2025 FT | VERIFIED | Exact (Fig. 6b legend). |
| 13 | Biomimetic JND 9.7 vs linear 16.6 uA (n=22) | Greenspon 2025 FT | VERIFIED | IQRs 7.7-16.1 and 11.5-23.5 are also correct. |
| 14 | Threshold vs JND r = -0.496 (P=0.0024) | Greenspon 2025 FT | VERIFIED | Exact. |
| 15 | Discriminable levels: flat median 7 (2-14); 8 / 11 / 19.5 (linear single, biomimetic single, biomimetic quartets; n=22, 22, 8) | Greenspon 2025 FT | VERIFIED | Exact. "Nearly fivefold more discriminable levels" and "doubled the dynamic range" are also in the published body. |
| 16 | Weber's law holds on average | Greenspon 2025 FT | VERIFIED | Tested only on a subset with 50 vs 70 uA standards (+/-16 uA); violated on some electrodes. Keep that caveat. |
| 17 | PF size ~3x (median +170%) for 40 -> 80 uA; +129% for 50 -> 200 Hz | Greenspon 2025 FT | VERIFIED | The paper says "threefold" and a median of 170%. Note that +170% = 2.7x; quote the median, not "3x". |
| 18 | Natural touch ~45-50 levels over 0-0.4 N | Greenspon 2025 FT | VERIFIED | Uses Weber fraction 1.083 and a detection threshold of 0.05 mm (Methods). |
| 19 | Biomimetic charge = 69 +/- 7% of peak-matched linear | Greenspon 2025 FT | VERIFIED | Exact. |
| 20 | JND = half the distance between p=0.25 and p=0.75; JND equal at 50 and 100 Hz | Greenspon 2025 FT | VERIFIED | Exact. The psychometric fit is **logistic** (see row 78). |
| 21 | a(t) = alpha*F(t-dt) + beta*abs(dF)/dt; median PF 2.5 cm2 | Greenspon 2025 FT | VERIFIED | The formula is in Methods. PF median 2.5 cm2 (5-95th percentiles 0.3-11.3). |
| 22 | Percept ~33% larger than a finger pad; +21% for 20 -> 80 uA; thresholds 9.2-35 uA | Fifer 2022, PMID 34880087 (abstract + PMC8865889 FT) | VERIFIED | These numbers come from Fifer, not from Greenspon; the combined citation in the facts line is ambiguous. The neurologist wrote that the FT was restricted, but it is retrievable and confirms the numbers. |
| 23 | Greenspon 2025 graded [A] (neurologist, neurobiologist) | HIVE.md grade rules | MINOR-ERROR | JND, levels and PF numbers come from one consortium with n=3 and have not been independently replicated. Grade **B** for these numbers (as the mathematician does). Only the qualitative "multi-electrode helps" claim has partial independent support (Bjanes 2025). |
| 24 | Greenspon 2026 = Sci Transl Med 18:eaec3728 (2026); preprint = medRxiv 2025.08.11.25332271 | PMIDs 42455900, 40832410 | VERIFIED | Both resolve. The published version is paywalled, so only its abstract was read. |
| 25 | >168 M pulses; no serious AEs; 27 implant-years (published) vs 24 (preprint) | Greenspon 2026 AB; preprint FT | VERIFIED | Exact. |
| 26 | Threshold drift ~3.5 uA/yr; 3.54 +/- 11.52 uA/yr | Abstract; preprint FT | VERIFIED | The +/- figure is from the preprint only. |
| 27 | Functional electrodes 64+/-13% (published) / 62+/-15% (preprint); 60% / 55% / 54% at 10 y | Abstract; preprint FT | VERIFIED | Published abstract 60%; preprint abstract 55%; preprint body 54% (P2). |
| 28 | >75% functional at 1 y in 3/5 participants; functional = median threshold <100 uA over 6 months | Preprint FT | VERIFIED | Exact. |
| 29 | 53 persistent-sensation AEs (3-25 per participant), ~1 per 22,000 trials, mostly <10 s, max ~9.5 min | Preprint FT | VERIFIED | Exact. Also: never painful; more common after multi-electrode stimulation in 3/5 participants. |
| 30 | 588 h stimulation, 1666 mC total; initial median thresholds 14.5-22.5 uA (4 participants), 61.5 uA (1) | Preprint FT | VERIFIED | Exact. |
| 31 | "0 seizures reported" / "No seizures reported" (facts, neurologist) | Preprint FT | MINOR-ERROR | The paper does not say this in these words. It says: no serious AEs; all 53 ICMS-related AEs were persistent sensations; afterdischarges "are not clinical seizures"; participants were screened for seizure disorders. Rephrase to "no serious AEs; all 53 ICMS-related AEs were persistent sensations". |
| 32 | The preprint body numbers (rows 26-30) also hold in the final STM paper | STM 2026 full text | UNVERIFIABLE | Paywalled. The abstract already differs from the preprint (27 vs 24 years, 64 vs 62%), so cite the preprint for body numbers or re-check them against the STM text. |
| 33 | Hughes 2021 JNE = J Neural Eng 18(4), 1500 days, n=1 | PMID 34320481, PMC8500669 | VERIFIED | Match. |
| 34 | Pulse: cathodal 200 us, 100 us interphase, anodal 400 us at half amplitude; 20-300 Hz; 2-100 uA | Hughes 2021 JNE FT; Hobbs 2025 FT | VERIFIED | Exact in both papers. |
| 35 | Detection threshold 31.5 uA (day 100) -> 10.4 uA (day 1500) | Hughes 2021 JNE AB+FT | VERIFIED | IQRs 22.8-49.6 and 7.4-16.6. |
| 36 | McCreery: continuous 4 nC/phase (=20 uA x 200 us) caused neuron loss in cat cortex | Hughes 2021 JNE FT (secondary) | VERIFIED | Verified **as cited by Hughes** only; the McCreery primary was not opened. Keep the "as cited" wording. |
| 37 | Hughes 2021 eLife: at 60 uA, 20-100 Hz was MOST intense on over half of electrodes; 3 groups; at 20 uA, 20 -> 100 Hz raised intensity in all groups | PMID 34313221, PMC8376245 | VERIFIED | Exact ("on over half of the tested electrodes"). |
| 38 | Caps: 15 s continuous at 100 Hz or 5 s at 300 Hz, then equal off time (50% duty); 100 uA / 300 Hz from NHP work | Hughes 2022, PMID 35671947, PMC10308851 | VERIFIED | Exact. |
| 39 | Stimulator drops pulses above 280 Hz | Hughes 2022 FT | VERIFIED | The paper says "occasionally dropped individual pulses" (a CereStim). |
| 40 | Intermittent 1 s on / 5 s off x50 never extinguished the sensation over >3 min | Hughes 2022 AB+FT | VERIFIED | Exact. |
| 41 | 100 uA x 200 us = 20 nC/phase | Arithmetic; Armenta Salas FT | VERIFIED | Armenta Salas states "maximum charge delivered per phase was 20 nC". |
| 42 | "Continuous ICMS -> complete percept loss within 1 min (all continuous/burst protocols)" (facts, neurologist; reused in mathematician preregs as "adaptation <1 min") | Hughes 2022 FT | MINOR-ERROR | Continuous trains were tested only for 15 s (20 or 100 Hz) or 5 s (300 Hz): intensity fell at 100/300 Hz, and **20 Hz showed no change in 15 s**. Complete extinction came from **60-s, 100 Hz burst-modulated trains** (26 of 30 trials; mean drop onset 13.2 s). Say: "continuous high-frequency ICMS adapts within seconds; 60-s burst-modulated 100 Hz trains extinguished the percept within 1 min on 26/30 trials." |
| 43 | Hobbs 2025: biomimetic more indentation-like on 32% of single electrodes, 75% of 4-electrode groups; less charge; n=3 | PMID 40106898, PMC13571258 | VERIFIED | Also: no significant difference for 57% of single electrodes. |
| 44 | 'Less Warm' 19% of descriptors | Hobbs 2025 FT | VERIFIED | Tied with 'Dynamics' 19%; 'Poke' 12%. |
| 45 | Valle 2025: edge orientation 61-89%; asymptote 78% at 0.5 s | PMID 39818881, PMC11994950 | VERIFIED | c1 81-89-84%, c2 61-68%; 78% (n=225). |
| 46 | Motion direction 76/78%; 98% across digits (c1); 30% at 50 ms vs 72% at 200 ms | Valle 2025 FT | VERIFIED | Exact. |
| 47 | 3D object ID 79% (n=45); curvature >75% once the amplitude difference exceeds 20% | Valle 2025 FT | VERIFIED | Exact. |
| 48 | Trains >0.5 s apart are perceived as separate events | Valle 2025 FT | VERIFIED | "typically"; motion is perceived only at 0-0.5 s separations. |
| 49 | Armenta Salas 2018: 200 us/phase, 53 us interphase, 1 s; 20-100 uA; 150 Hz (exp 1), 50-300 Hz (exp 2) | PMID 29633714, PMC5896877 | VERIFIED | Exact. |
| 50 | 46/96 electrodes responsive (48%); 381 reports; proprioceptive 79 vs cutaneous 302 | Armenta Salas FT | VERIFIED | Exact. |
| 51 | Descriptors: squeeze 24.9%, tap 17.3%, right movement 9.7%, vibration 8.1%, blowing 6.6%, forward 5.8%, pinch 5.5% | Armenta Salas FT Table 1 | VERIFIED | Exact. |
| 52 | Two 48-ch S1 arrays (Caltech) | Armenta Salas FT | VERIFIED | Exact. |
| 53 | Christie 2022: vibration perceived 48 ms faster than intensity-matched ICMS; TOJ PSS ~0; n=1 | PMID 35644516 AB | VERIFIED | Exact. |
| 54 | Callier 2019: S1 latency ~20 ms; onset/sustained mean >15x (2.2-42.4, median 12.0, 28 locations); offset >8x (0.76-35.0, median 6.0); sustained activation in a fraction of a mm2 | PMID 30668644 (Cereb Cortex 2019), PMC6917522 FT | VERIFIED | Exact. |
| 55 | TouchSim: ~12,500 afferents; <1,000 per fingertip; ~4,000 in palm | PMID 28652360, PMC5514748 FT | VERIFIED | "each fingertip contains just under 1,000 fibers ... palm contains only 4,000". |
| 56 | Rate fit R2 0.91+/-0.04 (sine), 0.92+/-0.11 (noise); validation 0.85+/-0.08 | TouchSim FT | VERIFIED | Exact. |
| 57 | Timing precision <8 ms for all classes; PC sub-ms; SA1/RA 3-8 ms | TouchSim FT | VERIFIED | Exact. |
| 58 | Flutter -> hundreds of spikes/s; high-frequency vibration -> up to 100,000 spikes/s (PC); no SA2 | TouchSim FT | VERIFIED | SA2 is explicitly excluded (macaques lack SA2). No thermal or proprioceptive afferents are modelled (scope). |
| 59 | TouchSim constants: SA1/RA/PC densities 10/25/10 (palm), 30/40/10 (finger), 70/140/25 (tip); depths 0.3/1.6/2.0; 5000 Hz | GitHub hsaal/touchsim | VERIFIED | Densities and depths are in `constants.py`. The 5000 Hz resampling is in `classes.py` (lines 251-253), not in `constants.py`. |
| 60 | Kim 2015: monkey ICMS JND ~30 uA, ~constant for 30-100 uA standards (no Weber) -> ~2 steps | PMID 26504211, PMC4679002 FT | VERIFIED | "mean JNDs hover around 30 uA ... only two perceptually discriminable steps". |
| 61 | Cathodal-first thresholds ~10 uA lower than anodal-first | Kim 2015 FT | VERIFIED | "differ on average by ~10 uA". |
| 62 | Thresholds rise below ~250 Hz; JNDs in 3b equal those in area 1 | Kim 2015 FT | VERIFIED | Thresholds fall with frequency and level off at 250 Hz; 3b = area 1 (t(30)=0.400). |
| 63 | Histed 2009: near threshold (4-9 uA), sparse cells hundreds of um away; a 15-30 um tip move changes the set; axonal volume tens of um | PMID 19709632, PMC2874753 FT | VERIFIED | A 30 um move "almost completely eliminated overlap" (radius ~15 um). Cat/mouse cortex, not S1. |
| 64 | Stoney 1968 via Histed: 10 uA -> 100 um, 100 uA -> 450 um | Histed FT (secondary) | VERIFIED | Second-hand, as labelled. |
| 65 | Weber 2013: 7 PC fibres -> 83% of 55 textures; PC optimal resolution 2 ms; warp 89% (120->80) / 62% (40->80); SA1 <10 Hz; 50-800 Hz | PMID 24082087, PMC3800989 FT | VERIFIED | The 50-800 Hz range is attributed by Weber to prior behavioural work (refs 7-10). |
| 66 | Vestergaard 2023: cooling drives S1, warming barely does (tiny fraction, delayed); pIC codes cool+warm somatotopically; 10 C steps from 32 C | PMID 36755097, PMC9946826 FT | VERIFIED | Also: pIC cool latency ~80 ms vs warm ~320 ms (useful for models). Mouse. |
| 67 | Darian-Smith 1979 warm fibres: CV 1.2+/-0.5 m/s; peak 1.5-4 s; tau 5-12 s; linear 0-8 C from 34 C; RF <1 mm; >80% silent at >=50 C; suppression at ISI <60 s | PMID 114608 AB | VERIFIED | The ">80% silent" figure is at a base of 39 C with pulses to >=50 C. |
| 68 | Johansson & Vallbo 1979a: 241 u/cm2 tip, 58 palm; 1:1.6:4.2; RA+SA1 carry the gradient | PMID 439026 AB | VERIFIED | Absolute densities are model-based (as labelled). |
| 69 | Johansson & Vallbo 1979b: PC 9.2, RA 13.8, SA2 33.1, SA1 56.5 um; psychophysics 11.2 / 36.0 um; one RA impulse can suffice | PMID 536918 AB | VERIFIED | Exact. |
| 70 | Johansson & Westling 1987: slip -> ratio change 74+/-9 ms; 1984: 0.06-0.08 s | PMIDs 3582528, 6499981 AB | VERIFIED | Exact. |
| 71 | Weiss 2019: recording resumes 740 us after each pulse | PMID 30444217 AB | VERIFIED | Exact. |
| 72 | Sombeck: >=480 uA over 16 electrodes -> RT up to 20 ms faster than mechanical | PMID 31778982 AB | VERIFIED | J Neural Eng, epub Dec 2019, vol 17 (2020); the hive files label it both 2019 and 2020 (cosmetic). |
| 73 | Quick 2020: force error reduced (p=0.022); success rate n.s. (p=0.411); ICMS = sham | PMID 33018723, PMC7717497 FT | VERIFIED | Exact. EMBC conference paper. |
| 74 | Osborn 2025 1.5 dB / 2.4 dB; Bjanes 2025 100% vs 85% 'natural'; Herring 2024 6 x 64-ch arrays | PMIDs 40216307, 41191971, 37982637 AB | VERIFIED | Exact. |
| 75 | Rajan 2015 NHP: 10-100 uA, 1 or 5 s, duty 1/1 or 1/3, 4 h/d, 5 d/wk, 6 mo, no added damage; Chen 2014 impedance stabilises after 10-12 wk | PMIDs 26479701, 24503702 AB | VERIFIED | Exact. |
| 76 | Callier 2020: frequency JND ~3 Hz at 20 Hz -> 95 Hz at 200 Hz; Weber 0.15 -> 0.5 between 50 and 100 Hz; discriminable to ~200 Hz | PMID 31879342, PMC6969512 FT | VERIFIED | Exact. |
| 77 | Okorokova 2018 R2 0.85/0.87/0.90 (rate), 0.83/0.61/0.71 (area), ADL 0.84; Kontsevich & Tyler 2 dB in <30 trials, slope ~300; Dadarlat 8-electrode ICMS ~ vision at 15-25% coherence; Caldwell 254-528 vs 198-313 ms | PMIDs 30245482 FT, 10492833 AB, 25420067 FT, 30824821 AB | VERIFIED | Dadarlat: 15-25% is monkey D; monkey F matched 15%. |
| 78 | DERIVED sigma_p = JND/(0.6745*sqrt2) = 14.15 uA (mathematician) | Greenspon 2025 Methods | MINOR-ERROR | The arithmetic is right, but it assumes a cumulative-Gaussian psychometric. Greenspon fits a **logistic** (JND = ln3/c). Moment-matching a logistic gives sigma_p ~= 1.167 x JND = 15.8 uA. Label it "Gaussian approximation; 14-16 uA depending on link function". |
| 79 | Neurobiology secondary facts: Delhaye 2018 (SA1 25%, RA 40%, SA2 20%, PC 15%; SA1 RF ~10 mm2; 51%/40% sustained+OFF; ~5% Pacinian-like in area 1); Knibestol 1975 (exponent 0.66; CV 58.7/45.3; SA1 no spontaneous firing); Muniak 2007 (log local / linear population); Bautista 2007 (<~26 C; avoid <10 C); Macefield ~10 Hz; Prud'homme 46/86 (53.5%); Tomlinson 5 uA no effect / 20 uA strong bias; DiCarlo 94% + 1-4 inhibitory sides, half balanced; Harvey 800 Hz phase-locking | PMIDs 30215864 (PMC6330897 FT), 1127614, 17959811, 17538622, 29668385, 7884459, 28035576 (PMC5452683 FT), 9502821, 23667327 | VERIFIED | Tomlinson: the 20 uA was delivered on 4 electrodes at once. DiCarlo: 94% of the 247 well-fitted RFs. |
| 80 | Neuroinformatics: Tehovnik 1996 (100-4000 uA/mm2; few tenths to thousands of cells at 10 uA); Kumaravelu 2022 (antidromic, volume vs density); Kumaravelu & Grill 2024 (0-25 ms excitation, 25-200 ms inhibition); Hickman 2026 (<5% activated, >50% modulated, rho 5.8 Ohm*m, windows 0.68/1.14/1.22/1.47 ms) | PMIDs 8815302, 34861412 AB; 38492885 (PMC11090107 FT); 42207642 (PMC13404931 FT) | VERIFIED | Exact. Kumaravelu & Grill state 0-25 / 25-200 ms as background from prior literature, not as a new model result. |
| U2 | Flesher 2021 end-to-end loop latency; Shannon k / uC/cm2 for human ICMS | n/a | UNVERIFIABLE | The hive already flags both as UNVERIFIED; the auditor also found neither in the opened texts. Do not put a number in the whitepaper. |

Verdict tally: 81 entries (rows 1-80 plus U2). MINOR-ERROR: rows 9, 23, 31, 42 and 78 (5). UNVERIFIABLE: rows 32 and U2 (2). VERIFIED: the other 74. WRONG: 0.

## Citations resolved by esummary only (existence check, content not audited)
27738096 Flesher 2016 STM; 40312384 Verbaarschot 2025; 39413869 Greenspon 2024; 37949923 Shelchkova 2023; 34892544 Osborn 2021;
41060788 Rosenthal 2025; 40894130 Hutchison 2025 (medRxiv); 42463883 Chandrasekaran 2026 Nat Med; 36639237 Rubin 2023; 1592409 Shannon 1992;
31440133 Kramer 2019; 39720868 Downey 2024; 25257208; 19352402; 10649575; 22245639; 25262494; 23073629; 23274308; 31971510; 31668844;
107591; 30718436; 31813989; 35288570; 26291448; 24127595; 24739786; 20610784; 23236001; 32759488; 26092769; 30244887; 33137773;
36824713; 6705863; 25028989; 12404008; 28113323; 28059065; 12581990; 11807554; 15190091; 10526332; 10884334; 6844102; 11800457.
For all of them the first author, year, journal and DOI match the hive's header lines.

## Advice for the whitepaper
- The safest headline numbers (VERIFIED from full text) are: Flesher 20.9 -> 10.2 s; Greenspon 2025 JND 13.5 uA and levels 8/11/19.5
  vs ~45-50 for natural touch; Hobbs 32%/75%; Callier onset >15x; the Greenspon 2026 abstract numbers (168 M pulses, 0 SAE,
  ~3.5 uA/yr, 64+/-13%).
- Cite the preprint (PMID 40832410) explicitly for AE counts and rates until the STM full text is checked.
- Everything above is n=1 to n=5 from one or two consortia. Present it as B-grade human evidence, not A.
