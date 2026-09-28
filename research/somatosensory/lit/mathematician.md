# Mathematician bibliography: encoding models, ICMS psychophysics, info theory, closed-loop control
Compiled 2026-09-26 by mathematician. Every entry was opened via PubMed E-utilities efetch
(https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&rettype=abstract&retmode=text&id=PMID)
and, where marked "full text", via NCBI PMC efetch (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=PMCID)
or Europe PMC (https://www.ebi.ac.uk/europepmc/webservices/rest/PMCID/fullTextXML). Numbers are copied as reported.
Grades per HIVE.md. I have graded single-lab results B even when they are classics, because I did not open the replications.

---------------------------------------------------------------------------------------------------
## 1. Afferent / encoding models

### [B] Simulating tactile signals from the whole hand with millisecond precision (Saal, 2017) - DOI 10.1073/pnas.1704856114 / PMID 28652360
- Opened: PubMed efetch 28652360; abstract (PMC5514748 full text not retrievable through efetch: metadata only)
- Key facts: TouchSim model: skin mechanics (stresses at receptors) then spiking model per fiber; tiles the whole palmar hand with receptors at known densities; simulated responses "closely match their measured counterparts, down to the precise timing of the evoked spikes".
- Relevance: ground-truth generator for "what the nerve would have sent" in biomimetic encoders (used by Okorokova 2018). Candidate reference simulator for prereg P2 in a later cycle (Python package; neuroinformatics to check install).
- Caveats: validated against monkey/human afferent recordings from literature; peripheral only (no cortical stage).

### [B] Predicting the timing of spikes evoked by tactile stimulation of the hand (Kim, Sripati, Bensmaia, 2010) - DOI 10.1152/jn.00187.2010 / PMID 20610784
- Opened: PubMed efetch; abstract
- Key facts: integrate-and-fire model predicts spike timing to arbitrary vibrations for three afferent types (SA1, RA, PC); accounts for rectification, frequency sensitivity, entrainment.
- Relevance: afferent-level encoder building block; motivates onset/offset (RA/PC) + sustained (SA1) decomposition used in H1.
- Caveats: vibratory stimuli; single lab.

### [B] A simple model of mechanotransduction in primate glabrous skin (Dong, 2013) - DOI 10.1152/jn.00395.2012 / PMID 23236001
- Opened: PubMed efetch; abstract
- Key facts: two-stage model (nonlinear transduction + generalized integrate-and-fire) with "at least one order of magnitude fewer parameters" than Kim 2010, saturating nonlinearity; predicts rate, timing, adaptation, threshold.
- Relevance: cheapest defensible afferent model for population simulation on a CPU budget.
- Caveats: single lab; no numbers in abstract.

### [B] Biomimetic encoding model for restoring touch in bionic hands through a nerve interface (Okorokova, He, Bensmaia, 2018) - DOI 10.1088/1741-2552/aae398 / PMID 30245482
- Opened: PubMed efetch; full text via NCBI PMC efetch PMC6324178
- Key facts: maps indentation depth, rate and acceleration to (i) population firing rate FR(t) and (ii) activated area A(t). Reconstruction of TouchSim aggregate responses: R^2 = 0.85, 0.87, 0.90 (FR; noise, sinusoids, steps) and 0.83, 0.61, 0.71 (area). On activities-of-daily-living sensor data: R^2 = 0.84. Proposes area -> pulse charge (recruitment), FR/area -> pulse frequency.
- Relevance: the canonical "biomimetic = depth + derivative terms" encoder; basis of H1 encoder family.
- Caveats: validated against a simulator (TouchSim), not against neural recordings; peripheral nerve target, not ICMS. Linear model loses accuracy at higher frequencies (authors).

### [B] A comprehensive model-based framework for optimal design of biomimetic patterns of electrical stimulation (Kumaravelu, 2020) - DOI 10.1088/1741-2552/abacd8 / PMID 32759488
- Opened: PubMed efetch; abstract
- Key facts: cortical hypercolumn model + genetic algorithm designs ICMS patterns matching recorded S1 (area 2 proprioceptive, area 1 cutaneous) activity; RNN encoder generalises; matched neurons "within 50 um of the electrode tip"; outperformed four previous linear/nonlinear mappings (in model space).
- Relevance: the only opened example of model-optimised ICMS encoding; shows the evaluation is in simulated neural space, not behaviour.
- Caveats: model-only; no behavioural validation.

### [B] Biomimetic approaches to bionic touch through a peripheral nerve interface (Saal & Bensmaia, 2015) - DOI 10.1016/j.neuropsychologia.2015.06.010 / PMID 26092769
- Opened: PubMed efetch; abstract. Review; blueprint for biomimetic codes. Relevance: framing. Caveat: review, no data.

---------------------------------------------------------------------------------------------------
## 2. Biomimetic stimulation: behavioural evidence

### [B] Biomimetic intraneural sensory feedback enhances naturalness, sensitivity and dexterity (Valle, 2018) - DOI 10.1016/j.neuron.2018.08.033 / PMID 30244887
- Opened: PubMed efetch; abstract
- Key facts: in trans-radial amputees (intraneural electrodes), biomimetic frequency modulation felt more natural; amplitude modulation gave better fine force identification; "hybrid" (biomimetic frequency + amplitude) gave both and improved gross dexterity and embodiment.
- Relevance: evidence that naturalness and discriminability can trade off; H1 must measure both information and cost, not just "biomimetic wins".
- Caveats: peripheral nerve, small n (abstract gives no n).

### [B] Biomimetic sensory feedback through peripheral nerve stimulation improves dexterous use of a bionic hand (George, 2019) - DOI 10.1126/scirobotics.aax2352 / PMID 33137773
- Opened: PubMed efetch; abstract
- Key facts: one participant, Utah Slanted arrays; with biomimetic feedback objects identified "significantly faster" than with intensity-only encoding; better grip-force precision with feedback.
- Caveats: n = 1 participant ("the participant"); peripheral.

### [B] Evoking stable and precise tactile sensations via multi-electrode ICMS of somatosensory cortex (Greenspon, 2025) - DOI 10.1038/s41551-024-01299-z / PMID 39643730 (preprint PMID 36824713)
- Opened: PubMed efetch; full text via Europe PMC fullTextXML PMC12176618
- Key facts (exact): 3 participants with cervical SCI. Amplitude discrimination: standard 60 uA, comparisons 40-80 uA, 75%-correct criterion; JND = half the difference between amplitudes at p = 0.25 and 0.75 of a fitted psychometric function; median JND 13.5 uA (n = 35 electrodes); JNDs same at 50 and 100 Hz. Discriminable levels between detection threshold and 100 uA (constant Weber fraction assumed): 2 to 14, median 7; native touch of a sensate hand: ~45-50 levels over 0-0.4 N. Biomimetic vs linear (peak-matched; biomimetic charge 69 +/- 7% of linear): median JND 9.7 vs 16.6 uA (IQR 7.7-16.1 vs 11.5-23.5 uA). Biomimetic amplitude: a(t) = alpha*F(t - dt) + beta*|df(t)|/dt. Multi-electrode (quartets): levels rose from 11 to 19.5; "nearly fivefold more discriminable levels" than single-electrode linear; discriminability "well expressed in terms of difference in total charge". Lower detection threshold correlated with higher JND (r = -0.496, P = 0.0024). Weber's law held on average, violated on some electrodes. Median projected field 2.5 cm^2.
- Relevance: the key quantitative anchor for H1, H2 (P2, P4).
- Caveats: n = 3; single consortium; biomimetic multi-electrode vs linear multi-electrode not fully compared.

### [B] ICMS of human S1 evokes task-dependent, spatially patterned responses in motor cortex (Shelchkova, 2023) - DOI 10.1038/s41467-023-43140-2 / PMID 37949923
- Opened: PubMed efetch; abstract
- Key facts: 3 participants; S1 ICMS activates M1 (some monosynaptic-latency responses); ICMS disrupted decoder performance; disruption "minimized using biomimetic stimulation, which emphasizes contact transients at the onset and offset of grasp, and reduces sustained stimulation".
- Relevance: second cost term for H1 (decoder interference scales with sustained charge) -> H6.

### [B] Restoring the sense of touch with a prosthetic hand through a brain interface (Tabot, 2013) - DOI 10.1073/pnas.1221113110 / PMID 24127595
- Opened: PubMed efetch; abstract. Key facts: monkeys; ICMS percepts localized and track pressure; performance equal for native vs prosthetic finger in a discrimination task; proposes phasic onset/offset ICMS. Caveat: NHP.

### [B] Tactile edges and motion via patterned microstimulation of human S1 (Valle, 2025) - DOI 10.1126/science.adq5978 / PMID 39818881
- Opened: PubMed efetch; abstract. Key facts: simultaneous multi-electrode ICMS with patterned projected fields evoked edges and shapes; spatiotemporal sequences evoked motion with controllable speed and direction. Relevance: spatial (multi-channel) coding as the route past single-channel intensity limits (H2). Caveat: no numbers in abstract.

---------------------------------------------------------------------------------------------------
## 3. ICMS psychophysics (inputs for channel-capacity and calibration models)

### [B] Behavioral assessment of sensitivity to ICMS of primate S1 (Kim, Callier, Tabot, Gaunt, Tenore, Bensmaia, 2015) - DOI 10.1073/pnas.1509265112 / PMID 26504211
- Opened: PubMed efetch; abstract only (PMC4679002: efetch returns metadata, not open-access XML)
- Key facts: detection depends on pulse width, frequency, amplitude, train duration; amplitude discriminability across the safe range and its dependence on frequency and duration (no numbers in abstract).
- Caveats: NHP. NUMBERS NOT EXTRACTED (full text not opened) -> request posted to neurobiologist.

### [B] The frequency of cortical microstimulation shapes artificial touch (Callier, 2020) - DOI 10.1073/pnas.1916453117 / PMID 31879342
- Opened: PubMed efetch; full text via Europe PMC PMC6969512
- Key facts (exact): monkeys discriminated ICMS frequency up to ~200 Hz (range tested 10-400 Hz); JNDs rose "from around 3 Hz for a 20-Hz standard to 95 Hz for the 200-Hz standard"; Weber fractions rose "from 0.15 to 0.5, between 50 and 100 Hz"; frequency effects on quality are electrode dependent.
- Relevance: frequency is a second, low-range-only channel dimension (H2).

### [B] Perception of microstimulation frequency in human somatosensory cortex (Hughes, 2021 eLife) - DOI 10.7554/eLife.65128 / PMID 34313221
- Opened: PubMed efetch; abstract. Key facts: 2 participants; amplitude and train duration raise intensity on all electrodes; frequency raises intensity on some electrodes and lowers it on others (three groups, spatially clustered). Relevance: frequency-intensity map is electrode-specific -> per-electrode calibration (H4).

### [B] Neural stimulation and recording performance in human sensorimotor cortex over 1500 days (Hughes, 2021 JNE) - DOI 10.1088/1741-2552/ac18ad / PMID 34320481
- Opened: PubMed efetch; abstract. Key facts: one participant; median ICMS detection threshold fell from 31.5 uA (day 100) to 10.4 uA (day 1500), largest change day 100-500. Relevance: threshold priors and drift for H4. Caveat: n = 1.

### [B] Intracortical microstimulation of human somatosensory cortex (Flesher, 2016) - DOI 10.1126/scitranslmed.aaf8083 / PMID 27738096
- Opened: PubMed efetch; abstract. Key facts: one participant; somatotopic hand percepts, many with pressure-like quality, low amplitudes, stable for months; amplitude grades intensity.

---------------------------------------------------------------------------------------------------
## 4. Closed-loop control, grasp and latency

### [B] A brain-computer interface that evokes tactile sensations improves robotic arm control (Flesher, 2021) - DOI 10.1126/science.abd0380 / PMID 34016775
- Opened: PubMed efetch; full text via NCBI PMC efetch PMC8715714 (author manuscript)
- Key facts: one participant; ARAT median trial time 20.9 -> 10.2 s with ICMS; grasp time cut by more than half, "accounting for 88% of the overall time reduction"; ICMS amplitude a linear transformation of robotic finger torque; authors note many objects rigid, "no penalty for grasping the objects too firmly".
- Relevance: benchmark effect size; motivates fragile-object (crush) term in H3. Caveat: n = 1.

### [B] Roles of glabrous skin receptors and sensorimotor memory in precision grip (Johansson & Westling, 1984) - DOI 10.1007/BF00237997 / PMID 6499981
- Opened: PubMed efetch; abstract. Key facts: grip force parallels load force with a small safety margin adapted to friction; friction info acts ~0.1 s after grip; slip-triggered adjustments at 0.06-0.08 s latency; depends on cutaneous input (anaesthesia).

### [B] Signals in tactile afferents eliciting adaptive motor responses during precision grip (Johansson & Westling, 1987) - DOI 10.1007/BF00236210 / PMID 3582528
- Opened: PubMed efetch; abstract. Key facts: slip -> force-ratio change latency 74 +/- 9 ms, about half the minimum latency of intended responses to cutaneous stimulation; tactile input alone can trigger the upgrade. Relevance: natural feedback latency for H3.

### [B] Factors influencing the force control during precision grip (Westling & Johansson, 1984) - DOI 10.1007/BF00238156 / PMID 6705863
- Opened: PubMed efetch; abstract. Key facts: safety margin = employed grip minus minimal grip preventing slip; depends on friction, weight and a subject-specific factor; relies on finger mechanoreceptors.

### [B] Coding and use of tactile signals from the fingertips in object manipulation (Johansson & Flanagan, 2009) - DOI 10.1038/nrn2621 / PMID 19352402
- Opened: PubMed efetch; abstract (review). Contact events encoded and used to monitor task phases -> event-detection metric in H1.

### [B] Direct stimulation of S1 results in slower reaction times than peripheral touch (Caldwell, 2019) - DOI 10.1038/s41598-019-38619-2 / PMID 30824821
- Opened: PubMed efetch; abstract. Key facts: 4 subjects, ECoG surface stimulation (not ICMS); median RT haptic 198-313 ms vs reliably perceived DCS 254 to 528 ms. Caveat: surface DCS, not intracortical.

### [B] Short reaction times to multi-electrode ICMS (Sombeck & Miller, 2019) - DOI 10.1088/1741-2552/ab5cf3 / PMID 31778982
- Opened: PubMed efetch; abstract. Key facts: monkeys, area 2; RT falls with current, frequency, train length; single electrode at 100 uA/330 Hz mostly slower than mechanical, slightly faster than visual cue; >= 480 uA spread over 16 electrodes gave RTs "as much as 20 ms faster than the mechanical cue". (Parameters quoted, not proposed.)

### [B] Comparing temporal aspects of visual, tactile and microstimulation feedback (Godlove, 2014) - DOI 10.1088/1741-2560/11/4/046025 / PMID 25028989
- Opened: PubMed efetch; abstract. Key facts: tactile cues faster than visual; ICMS in one monkey slower than both. No numbers in abstract.

### [C] Optimal feedback control as a theory of motor coordination (Todorov & Jordan, 2002) - DOI 10.1038/nn963 / PMID 12404008
- Opened: PubMed efetch; abstract. Stochastic optimal feedback control; corrections only in task-relevant dimensions. Theory framework for H3 (graded C as theory; experiments in paper not opened).

### [B] Brain-machine interface control algorithms (Shanechi, 2017 review) - DOI 10.1109/TNSRE.2016.2639501 / PMID 28113323; and Rapid control and feedback rates enhance neuroprosthetic control (Shanechi, 2017) - DOI 10.1038/ncomms13825 / PMID 28059065
- Opened: PubMed efetch; abstracts. BMI as closed-loop control system; in two monkeys higher control rate improved control even at fixed feedback rate, higher feedback rate helped further. Relevance: feedback rate/latency matter for H3.

### [C] Is the cerebellum a Smith predictor? (Miall, 1993) - DOI 10.1080/00222895.1993.9942050 / PMID 12581990
- Opened: PubMed efetch; abstract. Forward model + delay model to compensate feedback delays. Relevance: H3 sensitivity (a predictive controller reduces the latency penalty).

---------------------------------------------------------------------------------------------------
## 5. Cue integration, information theory, adaptive psychophysics

### [B] A learning-based approach to artificial sensory feedback leads to optimal integration (Dadarlat, O'Doherty, Sabes, 2015) - DOI 10.1038/nn.3883 / PMID 25420067
- Opened: PubMed efetch; full text via NCBI PMC efetch PMC4282864 (author manuscript)
- Key facts: two monkeys learned non-biomimetic 8-electrode ICMS encoding hand-to-target vector (direction by cosine-tuned pulse rates, distance by rate scaling); ICMS-only performance comparable to VIS trials at 15-25% dot coherence; VIS+ICMS variance matched minimum-variance integration predictions; visual weight moved 0 -> 1 with coherence.
- Relevance: H5 (Kalman fusion) is already supported in NHP; our value-add would be design, not discovery.

### [B] Humans integrate visual and haptic information in a statistically optimal fashion (Ernst & Banks, 2002) - DOI 10.1038/415429a / PMID 11807554
- Opened: PubMed efetch; abstract. MLE cue combination; weights inversely proportional to variance.

### [B] Bayesian integration in force estimation (Koerding, Ku, Wolpert, 2004) - DOI 10.1152/jn.00275.2004 / PMID 15190091
- Opened: PubMed efetch; abstract. Subjects combine priors over forces with sensory input; priors learnable.

### [B] Information theory and neural coding (Borst & Theunissen, 1999) - DOI 10.1038/14731 / PMID 10526332
- Opened: PubMed efetch; abstract (review). Methods for information in stimulus-response models; data then did not suggest a temporal code beyond rate+timing precision.

### [B] Periodicity and firing rate as candidate neural codes for vibrotactile frequency (Salinas, 2000) - DOI 10.1523/JNEUROSCI.20-14-05503.2000 / PMID 10884334
- Opened: PubMed efetch; abstract. S1 periodicity high but did not covary with single-trial performance; rate modulation did. Relevance: supports rate/intensity-based information accounting in H2.

### [B] Bayesian adaptive estimation of psychometric slope and threshold (Kontsevich & Tyler, 1999) - DOI 10.1016/s0042-6989(98)00285-5 / PMID 10492833
- Opened: PubMed efetch; abstract. Key facts: psi method picks the stimulus maximising expected information; threshold within 2 dB (23%) in < 30 trials for a typical 2AFC task; slope to same precision ~300 trials. Relevance: H4.

### [B] QUEST: a Bayesian adaptive psychometric method (Watson & Pelli, 1983) - DOI 10.3758/bf03202828 / PMID 6844102
- Opened: PubMed efetch; record has no abstract (title/citation only). Cited only as existence of the method.

### [B] Adaptive procedures in psychophysical research (Leek, 2001) - DOI 10.3758/bf03194543 / PMID 11800457
- Opened: PubMed efetch; abstract (review of three common adaptive methods, simulations + human data). Reference for staircase baseline in H4.

---------------------------------------------------------------------------------------------------
## Gaps (not found / not opened this cycle)
- Kim 2015 PNAS numeric JNDs/Weber fractions (full text not open via efetch). Neurobiologist asked on BOARD.
- A direct measurement of cortical adaptation time constant to sustained ICMS in humans (needed by P2; ASSUMPTION sweep used).
- Friction coefficient distributions for skin-object contact (P1 uses an ASSUMPTION range).
- Visuomotor latency for slip correction under vision only (P1 ASSUMPTION sweep).
- Texture information rates of natural afferents (needed to answer "is texture-level info reachable" in H2 quantitatively).

## Cycle 2 additions (opened 2026-09-26 by mathematician)
### [B] Finite element model of micromotion strain vs Utah array performance (Forrest, 2025) - PMID 41191976 / PMC12624975
- Opened: Europe PMC fullTextXML; full text. Key facts: "Each grid of electrodes had the same 400 um spacing"; shank length 1.5 mm; Pittsburgh "10 x 6 somatosensory arrays were SIROF ... coated". Relevance: array pitch for P5.
### Greenspon 2025 (PMC12176618) re-read for P5
- "A 2 mm shift in cortex corresponded to a ~10 mm shift in the PF on the skin, on average"; PF centroid distance vs electrode distance r = 0.69 (n = 5,892 pairs); "S1 arrays were wired in a chequerboard pattern"; union area "summed over all electrodes" above the 33% threshold 12, 33, 30 cm2 (C1, P2, P3) of a 165 cm2 palmar surface; PF median 2.5 cm2 (5-95th 0.3-11.3).
### Hughes 2021 JNE (PMC8500669) re-read via NCBI efetch db=pmc
- "Each electrode array consisted of 60 electrodes in a 6x10 grid, 32 of which were wired and functional" (S1).
### Johansson & Westling 1984 (PMID 6499981) abstract re-read
- "the more slippery the object the higher the grip force at any given load force"; ratio set "on the basis of a memory trace ... updating ... by tactile afferent information"; adjustments "about 0.1 s after the object was initially gripped"; slip-adjustment latency 0.06-0.08 s.
