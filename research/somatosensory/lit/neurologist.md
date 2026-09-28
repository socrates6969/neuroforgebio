# Neurologist bibliography: human ICMS of somatosensory cortex for BCI feedback
Author role: neurologist (hive cycle 1, 2026-09-26). Scope: HUMAN intracortical microstimulation (ICMS) of S1, plus the
few animal/theory papers that set the safety limits used in human trials.
Source access: PubMed E-utilities (esearch/esummary/efetch abstracts) and full text via Europe PMC REST
(`https://www.ebi.ac.uk/europepmc/webservices/rest/PMCxxxx/fullTextXML`) or NCBI efetch db=pmc
(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=xxxx`). Abstract URL pattern:
`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&rettype=abstract&retmode=text&id=<PMID>`.
Rules applied: stimulation parameters below are QUOTED facts from published, IRB/FDA-IDE-approved trials. They are not
proposed settings. Any clinical use requires an IRB/FDA-approved clinical study.
Grades: A = peer-reviewed and independently replicated; B = single peer-reviewed study (or one consortium);
C = preprint/theory; D = press. n = number of human participants.

Trial IDs seen: NCT01894802 (Pittsburgh/Chicago, "CRS"), NCT01964261 (Caltech/Rancho/USC), NCT03161067 (JHU/APL),
NCT00912041 (BrainGate, motor-only arrays), Case Western (ReHAB, Herring 2024).

---
## 1. Foundational percept papers

### [A] Intracortical microstimulation of human somatosensory cortex (Flesher, 2016) - DOI 10.1126/scitranslmed.aaf8083 / PMID 27738096
- Opened: PubMed abstract (efetch id=27738096); abstract only (no PMC full text available)
- Key facts: n=1 (long-term SCI). ICMS of the S1 hand area evoked sensations referred to locations on the hand, organized
  somatotopically. Many percepts had "naturalistic characteristics (including feelings of pressure)", were evoked "at low
  stimulation amplitudes", and "remain stable for months". Increasing amplitude graded perceived intensity.
- Relevance: first human demonstration; established location (by electrode) + intensity (by amplitude) coding.
- Caveats: n=1, abstract-only read; exact thresholds not verified from this source (see Hughes 2021 JNE, Greenspon 2026 for numbers).
  Grade A because the core findings (somatotopic hand percepts, amplitude-graded intensity) were replicated by Caltech
  (Armenta Salas 2018), JHU (Fifer 2022) and 5 Pitt/Chicago participants (Greenspon 2025/2026).

### [B] Proprioceptive and cutaneous sensations in humans elicited by ICMS (Armenta Salas, 2018) - DOI 10.7554/eLife.32904 / PMID 29633714
- Opened: Europe PMC full text PMC5896877
- Key facts: n=1 (participant FG, C5 SCI; Caltech). Two 48-channel stimulating arrays in S1 (plus 96-ch arrays in PMv and SMG).
  Pulses: biphasic, charge-balanced, cathodic-leading, 200 µs per phase, 53 µs interphase, 1 s trains. Exp 1: 20-100 µA at
  150 Hz: 46/96 electrodes (48%) produced at least one percept; 381 sensations in 1229 non-catch trials. Of 46 responsive
  electrodes: 32 upper arm, 18 forearm, 2 hand. Percepts described as cutaneous (e.g. "squeeze") or proprioceptive
  (e.g. "rightward movement"); proprioceptive reports skewed to higher amplitudes (p=0.039; N=79 proprioceptive vs 302
  cutaneous). Exp 2: 5 electrodes, 20-100 µA x 50-300 Hz. "Current amplitude, not frequency" differentiated modality on
  some sites.
- Relevance: the only human ICMS report of reproducible proprioceptive (movement) percepts -> proprioception open problem.
- Caveats: n=1; arrays mostly in arm (not hand) representation; percept modality self-report only; no functional proprioceptive task.

### [B] Intracortical somatosensory stimulation to elicit fingertip sensations (Fifer, 2022) - DOI 10.1212/WNL.0000000000013173 / PMID 34880087
- Opened: PubMed abstract (PMC8865889 full text not retrievable: restricted)
- Key facts: n=1 (JHU/APL, NCT03161067), arrays in finger areas of LEFT and RIGHT S1 using intraoperative mapping, 2-year
  period. Sensations in 8 fingers incl. fingertips, both hands; participant identified up to 7 finger-specific sites.
  Percept size on average 33% larger than a finger pad; size grew 21% as amplitude increased 20 -> 80 µA. Detection
  thresholds on a subset of electrodes: 9.2 to 35 µA.
- Relevance: bilateral / fingertip coverage; percept size vs amplitude.
- Caveats: n=1; threshold subset only.

### [A] Evoking stable and precise tactile sensations via multi-electrode ICMS (Greenspon, 2025) - DOI 10.1038/s41551-024-01299-z / PMID 39643730
- Opened: Europe PMC full text PMC12176618
- Key facts: n=3 (C1, P2, P3; arrays in Brodmann area 1). Projected fields (PFs) = focal hotspot with diffuse borders,
  somatotopic, stable over ~2 years (C1, P3) and ~7 years (P2); within-session PF change was equivalent to change over years.
  Survey stimulus 60 µA, 100 Hz, 1 s. PF size grew ~threefold (median 170%) from 40 -> 80 µA at 100 Hz, and median 129%
  from 50 -> 200 Hz at 60 µA. Amplitude JND (standard 60 µA, comparison 40-80 µA, 75% correct): median 13.5 µA
  (IQR 8.5-22.9 µA, n=35 electrodes); two outliers 60 and 106 µA. JND roughly follows Weber's law on average, variable across
  electrodes; lower-threshold electrodes had higher JNDs (r = -0.496). Biomimetic trains lowered JND (median 9.7 vs 16.6 µA
  linear, n=22). Discriminable levels between threshold and 100 µA cap: medians 8 (single, flat), 11 (biomimetic), 19.5
  (biomimetic multi-electrode quartets). "maximum safe stimulation level (100 µA)" stated as the constraint on dynamic
  range. Single electrodes "typically evoked only weak sensations"; overlapping multi-electrode PFs gave more localizable,
  intense sensations.
- Relevance: core quantitative source for intensity coding, dynamic range, PF stability; multi-electrode as fix for weak percepts.
- Caveats: 3 participants, one consortium; intensity scales self-reported. Grade A for "multi-electrode ICMS lowers
  per-electrode charge needed / raises intensity" because Caltech independently reports the same (Bjanes 2025).
  Precursor preprints: 10.1101/2023.02.18.528972 (PMC9949113, opened: states multi-channel biomimetic ICMS "doubles the dynamic
  range" and gives "nearly fivefold more discriminable levels of force" than single-channel linear) and 10.1101/2023.06.23.545425 (not opened).

### [B] Perception of microstimulation frequency in human S1 (Hughes, 2021) - DOI 10.7554/eLife.65128 / PMID 34313221
- Opened: Europe PMC full text PMC8376245
- Key facts: n=2 (P2, P3). Pulses cathodal-first, charge-balanced, 20-300 Hz, 2-100 µA. At 60 µA, 1 s, 20-300 Hz: amplitude
  and train duration always increased intensity; frequency effect electrode-dependent: on over half of tested electrodes,
  20-100 Hz felt MOST intense. Three k-means groups: low-, intermediate- (peak 40-100 Hz), high-frequency-preferring;
  neighbours tended to share group. At 20 µA (near threshold for most electrodes) 20 -> 100 Hz increased intensity for all
  groups. Quality: 20 Hz -> pressure, tapping, sparkle, touch; 100 Hz (IFP) -> buzzing, vibration, sharp; 300 Hz -> less
  pressure. Questionnaire included temperature (warm/cool) descriptors and 5-point naturalness scale. Data restricted to
  1 year in P2 "to minimize the impact of changes in perception".
- Relevance: frequency is not a monotonic intensity knob; per-electrode calibration needed.
- Caveats: n=2, deafferented cortex (reviewer note in the eLife record), self-selected intensity scales.

### [B] Effects of stimulus pulse rate on somatosensory adaptation (Hughes, 2022) - DOI 10.1016/j.brs.2022.05.021 / PMID 35671947
- Opened: NCBI efetch PMC10308851 (author manuscript full text)
- Key facts: n=1, ~1 year. Continuous high-frequency ICMS -> rapid intensity decrease; low frequency maintained longer; all
  continuous/burst protocols gave "complete sensation loss within 1 min". Intermittent paradigms (seconds between trains)
  never extinguished sensation over >3 min. Protocol limits quoted: max continuous train 15 s at 100 Hz or 5 s at 300 Hz;
  after 15 s stimulation an equal off period (50% duty cycle); 100 µA and 300 Hz caps "selected based on" NHP work;
  stimulator dropped pulses above 280 Hz.
- Relevance: sustained-contact encoding must be transient/intermittent; adaptation limits steady-state force feedback.
- Caveats: n=1.

### [B] Biomimetic stimulation patterns drive natural artificial touch (Hobbs, 2025) - DOI 10.1088/1741-2552/adc2d4 / PMID 40106898
- Opened: Europe PMC full text PMC13571258
- Key facts: n=3. Two-interval comparison against a real mechanical indentation on a sensate hand region. Single-electrode
  amplitude-modulated biomimetic ICMS judged more like indentation on 32% of electrodes; 4-electrode co-modulated
  amplitude+frequency biomimetic ICMS on 75% of electrode groups. Biomimetic trains needed less charge for intensity-matched
  sensation. Pulse: cathodal 200 µs, interphase 100 µs, half-amplitude anodal 400 µs.
- Relevance: operational naturalness metric (forced choice vs mechanical reference) usable in models.
- Caveats: requires residual sensation for the reference; 32% single-electrode = most electrodes did NOT improve.

### [B] Tactile edges and motion via patterned microstimulation (Valle, 2025) - DOI 10.1126/science.adq5978 / PMID 39818881
- Opened: NCBI efetch PMC11994950 (author manuscript full text)
- Key facts: n=2 (c1, c2). Simultaneous ICMS on 3 electrodes with aligned PFs evoked edges; orientation discrimination
  c1 81-89-84% (digits 1-3, n=150), c2 61-68% (n=75); asymptotic at 0.5 s (78%). Shapes: c1 82+/-9 to 72+/-8%, c2 50+/-14 to 48+/-8%.
  Curvature identified >75% once amplitude difference >20%. 3D objects via 9 electrodes: 79+/-11% (n=45). Motion
  direction: c1 76+/-14%, c2 78+/-15%; across digits c1 98+/-2%; train duration 50 ms -> 30%, 200 ms -> 72%; amplitude had
  no effect on direction. Overlapping trains fuse into one event; >0.5 s gap -> two events.
- Relevance: first human spatial pattern / motion coding beyond location+intensity; gives time constants for encoders.
- Caveats: n=2; large participant difference; lab task, not closed-loop dexterity metric.

### [B] Charge density of multi-channel ICMS modulates intensity and naturalness (Bjanes, 2025) - DOI 10.1088/1741-2552/ae1bd8 / PMID 41191971
- Opened: PubMed abstract only
- Key facts: n=1 (Caltech). Multi-channel ICMS evoked qualia distinct from single-channel, reduced minimum amplitude and
  per-electrode charge at detection threshold while increasing total charge; total delivered charge positively modulated
  intensity ("spatial integration"). 'Natural' descriptors: 100% multi-channel vs 85% single-channel (p<0.05).
- Relevance: independent (non-Pitt) replication of multi-electrode benefit.
- Caveats: n=1; numbers of electrodes/charges not read (abstract only).

### [B] Conveying tactile object characteristics through customized ICMS (Verbaarschot, 2025) - DOI 10.1038/s41467-025-58616-6 / PMID 40312384
- Opened: Europe PMC full text PMC12046030
- Key facts: n=3, participants self-tuned stimulation parameters (blinded) to create sensations for 5 virtual objects
  (spanning compliance, temperature, friction, moisture, texture). Parameter-based LDA predicted object at 34+/-12% (P2),
  37+/-15% (C1), 21+/-13% (P3, chance ~20%). Replay identification 36+/-16%, 37+/-13%, 22+/-9%. Reported qualities included
  "smooth", "warm", "dry", "rough"; one quote "It even has a sort of warmth to it." Paper lists prior descriptors
  "pressure", "tap", "warm", "squeeze", "pinch", "vibration", "blowing", "goosebumps".
- Relevance: only opened human source with "warm" descriptors; shows texture/temperature are at best weakly conveyable.
- Caveats: accuracies modestly above chance; visual context contributes; "warm" is a verbal descriptor, not a thermal percept test.

### [B] Subthreshold ICMS enhances tactile sensitivity (Osborn, 2025) - DOI 10.1016/j.brs.2025.03.021 / PMID 40216307
- Opened: PubMed abstract
- Key facts: n=1 (JHU, bilateral S1 arrays). Subthreshold ICMS reduced vibrotactile detection thresholds (median 1.5 dB);
  suprathreshold vibration raised ICMS thresholds (median 2.4 dB); effect decreased with distance between PF and vibration locus.
- Relevance: ICMS interacts with residual natural touch (incomplete SCI) -> models must include interaction terms.
- Caveats: n=1.

### [B] ICMS of human S1 induces natural perceptual biases (Greenspon, 2024) - DOI 10.1016/j.brs.2024.10.005 / PMID 39413869
- Opened: PubMed abstract
- Key facts: n=3. 2-interval amplitude discrimination shows time-order error: second stimulus typically overestimated;
  bias depends on amplitude sensitivity, first-stimulus amplitude/duration; longer inter-stimulus interval reduces effect.
- Relevance: history-dependent intensity -> encoder/psychometric models need a memory term.
- Caveats: psychophysics only.

---
## 2. Closed-loop / functional performance

### [B] A BCI that evokes tactile sensations improves robotic arm control (Flesher, 2021) - DOI 10.1126/science.abd0380 / PMID 34016775
- Opened: NCBI efetch PMC8715714 (author manuscript full text; supplement not opened)
- Key facts: n=1 (P2, 28 y at implant, C5 motor/C6 sensory ASIA B). Motor: 2 arrays, 88 wired electrodes in M1;
  sensory: 2 arrays, 32 wired electrodes in area 1. Robotic hand torque -> linear transform -> ICMS amplitude (index torque
  -> index electrodes; middle torque -> middle/ring/pinky electrodes). ARAT trial times median 20.9 s -> 10.2 s with ICMS
  (-51.2%, p<0.0001). Grasp phase (contact-to-liftoff) 13.3 s -> 4.6 s (-66%), 88% of improvement. Reach and transport
  phases -25% each. ARAT score median 21 (ICMS) vs 17 (no ICMS), p=0.029. <5 s ("able-bodied") trial achieved once in 108
  trials without ICMS; 14% of ICMS trials faster than fastest no-ICMS trial. Object transfer: 3.3+/-1.2 s -> 2.3+/-0.4 s
  per transfer in object zone (-30.3%, p=0.002); transfers per 2 min 15.8+/-3.8 -> 17.8+/-2.4 (p=0.050, n.s.). No change in
  number of successful trials. Improvement was immediate (no learning period).
- Relevance: the benchmark closed-loop effect size. Loop latency NOT reported in the main text (UNVERIFIED; may be in supplement).
- Caveats: n=1, blocked design (4 sessions each), unblinded; decoder-control check (sequence task) showed no advantage on ICMS days.

### [B] Artifact-free recordings in human bidirectional BCIs (Weiss, 2019) - DOI 10.1088/1741-2552/aae748 / PMID 30444217
- Opened: PubMed abstract
- Key facts: n=1. Sample-and-hold blanking triggered before each pulse + first-order 750 Hz high-pass Butterworth; spike
  detection in M1 resumes "as soon as 740 µs after each stimulus pulse". Without artifact rejection, objects moved in 2 min
  fell significantly (p<0.01); with it, no difference vs no-stimulation (p=0.621).
- Relevance: the per-pulse recording dead time (0.74 ms) is the only hard timing number for the bidirectional loop.
- Caveats: n=1; 5-DoF task.

### [B] ICMS of human S1 evokes task-dependent responses in motor cortex (Shelchkova, 2023) - DOI 10.1038/s41467-023-43140-2 / PMID 37949923
- Opened: Europe PMC full text PMC10638421
- Key facts: n=3. 60 µA, 100 Hz, 1 s S1 ICMS modulated a majority of M1 channels (single units confirmed, not artifact);
  some at short fixed (monosynaptic-like) latency, most variable. Sign/magnitude context-dependent across tasks. ICMS-evoked M1
  activity disrupted decoding of a virtual hand; disruption minimized by biomimetic (onset/offset-emphasizing) stimulation.
- Relevance: "write" contaminates "read" beyond electrical artifact -> decoder must model S1->M1 crosstalk.
- Caveats: n=3, one consortium.

### [B] ICMS feedback improves grasp force accuracy (Quick, 2020) - DOI 10.1109/EMBC44109.2020.9175926 / PMID 33018723
- Opened: NCBI efetch PMC7717497 (author manuscript)
- Key facts: n=1. ICMS feedback significantly reduced applied force error (p=0.022); visual feedback also (p<0.001); no
  significant effect on success rate (p=0.411); no significant difference between ICMS and sham-ICMS for any visual condition.
- Relevance: force-feedback benefit is small/fragile; sham control matters.
- Caveats: conference paper, n=1, mixed results -> weak evidence.

### [B] ICMS enables object identification (Osborn, 2021) - DOI 10.1109/EMBC46164.2021.9630450 / PMID 34892544
- Opened: PubMed abstract
- Key facts: n=1 (JHU). 3-choice virtual object ID without vision: 80% correct with sustained grip-force feedback; 76.7% with
  equal weighting of force and its derivative.
- Caveats: conference paper, n=1.

### [B] Perceived timing of vibration vs ICMS (Christie, 2022) - DOI 10.1016/j.brs.2022.05.015 / PMID 35644516
- Opened: PubMed abstract
- Key facts: n=1. Intensity-matched vibration perceived on average 48 ms faster than high-amplitude ICMS (reaction time);
  in temporal-order judgments, point of subjective simultaneity not different from zero.
- Relevance: perceptual latency penalty of ICMS ~tens of ms -> loop latency budget.
- Caveats: n=1.

### [B] Visual context affects perceived timing of ICMS (Rosenthal, 2025) - DOI 10.1152/jn.00518.2024 / PMID 41060788
- Opened: PubMed abstract
- Key facts: n=2 (Caltech, NCT01964261). Visual context and ICMS amplitude bias the qualitative experience; realistic visual
  scenes widen/shift the temporal binding window; peak consistently offset from zero (temporal misalignment); S1 encodes
  visual information related to ICMS.
- Caveats: n=2, case study.

### [C] ICMS vs peripheral nerve stimulation percepts (Hutchison, 2025, preprint) - DOI 10.1101/2025.08.20.25334094 / PMID 40894130
- Opened: PubMed abstract
- Key facts: n=1 (incomplete SCI, both ICMS and PNS). ICMS more localized and more qualitatively similar to natural touch;
  PNS higher intensity and more reliable. Naturalness ratings tracked other perceptual variables more than stimulation variables.
- Caveats: preprint, n=1.

### [B] Reconnecting the hand and arm to the brain (Herring, 2024) - DOI 10.1227/neu.0000000000002769 / PMID 37982637
- Opened: PubMed abstract
- Key facts: n=1 (27 y, AIS-B C3-C4). Six 64-channel intracortical arrays (M1, S1, IFG, AIP) + nine 16-channel nerve cuffs.
  S1 microstimulation produced repeatable individual-finger percepts; no operative complications.
- Relevance: largest single-person channel count found (384 intracortical channels); combined FES + ICMS architecture.
- Caveats: proof of concept, no quantitative sensory metrics in abstract.

### [B] Double neural bypass: restoring hand movement and sensation (Chandrasekaran, 2026) - DOI 10.1038/s41591-026-04498-0 / PMID 42463883
- Opened: PubMed abstract
- Key facts: n=1 (C4 sensory / C5 motor complete). iBCI + patterned spinal stimulation + activity-informed ICMS ("cortical
  mirroring"); significant persistent improvements in elbow flexion and wrist tactile sensation.
- Caveats: n=1; ICMS used for plasticity, not as a feedback channel; mechanisms unresolved.

---
## 3. Safety, longevity, charge limits

### [B] Long-term safety and efficacy of ICMS in humans (Greenspon, 2026) - DOI 10.1126/scitranslmed.aec3728 / PMID 42455900
- Opened: PubMed abstract (published version) + full text of the preprint version (medRxiv 10.1101/2025.08.11.25332271,
  PMID 40832410, Europe PMC PMC12363726)
- Key facts (published abstract): n=5, two Blackrock NeuroPort arrays each in hand area of BA1; implants 2-10 years;
  >168 million pulses over combined 27 implant-years, no serious adverse events, no direct negative effect on electrode
  health. Persistent sensations after offset: 3-25 events per participant. Thresholds rose ~3.5 µA/year; 64+/-13% of
  electrodes still functional (~21% decrease), 60% after 10 years in one participant. Quality and PF coverage consistent.
- Key facts (preprint full text; numbers differ slightly from the final version, e.g. 24 vs 27 years, 62+/-15% vs 64+/-13%):
  CereStim R96 stimulator; implant 26-122 months; 191-1357 sessions; 588 h stimulation; 1666 mC total charge. 53 ICMS-related
  AEs, all "persistent sensations"; ~1 per 22,000 trials; mostly <10 s, max ~9.5 min; never painful; more common after
  multi-electrode stimulation in 3/5 participants; interpreted as perceptual correlates of after-discharges ("not clinical
  seizures"). No seizures reported. Functional electrode = median threshold <100 µA over 6 months. Initial median
  thresholds 14.5-22.5 µA (4 participants), 61.5 µA (fifth). Threshold slope 3.54+/-11.52 µA/year. Monofilament thresholds
  unchanged. Quality reports reliable (r>0.81) in 3/5; naturalness stable or increasing, but decreased for P2 after year 8.
  Limits explored: 100 µA and 300 Hz; "no combination was found that reliably induced persistent sensations". Participants
  screened for seizure disorders.
- Relevance: the key human safety dataset. Grade B: single consortium (though 5 participants, 2 sites).
- Caveats: retrospective; all male; one array type (SIROF-tipped Utah/NeuroPort).

### [B] Neural stimulation and recording performance over 1500 days (Hughes, 2021) - DOI 10.1088/1741-2552/ac18ad / PMID 34320481
- Opened: NCBI efetch PMC8500669 (author manuscript)
- Key facts: n=1 (P2). SIROF-tipped stimulated S1 electrodes vs unstimulated Pt M1 electrodes. Arrays: 6x10 grid, 32 wired.
  Pulse: cathodal 200 µs, anodal 400 µs at half amplitude, 100 µs interphase; 20-300 Hz; 2-100 µA. Monthly suprathreshold
  survey typically 60 µA. Per-electrode limit: max 15 s at 100 Hz then equal off time. Detection threshold median 31.5 µA
  (day 100) -> 10.4 µA (day 1500), biggest change days 100-500. Recording quality declined on both, SIROF-sensory electrodes
  more likely to keep high-amplitude units. Cites McCreery: continuous 4 nC/phase (= 20 µA at 200 µs) caused neuron loss in cat cortex.
- Caveats: n=1; note opposite threshold trend to the 5-person average (Greenspon 2026) -> between-person variability.

### [B] Interim safety profile of BrainGate (Rubin, 2023) - DOI 10.1212/WNL.0000000000201707 / PMID 36639237
- Opened: PubMed abstract
- Key facts: n=14 (2004-2021), motor-cortex Utah arrays (no ICMS). Mean implant 872 days; 12,203 device-days; 68
  device-related AEs incl. 6 device-related SAEs; commonest = skin irritation at percutaneous pedestal; no explantations for
  safety, no intracranial infections, no deaths or permanent disability from device. Class IV evidence.
- Relevance: implant/pedestal risk baseline independent of stimulation.

### [B] Chronic ICMS effects on neural tissue and fine motor behavior (Rajan, 2015; NHP) - DOI 10.1088/1741-2560/12/6/066018 / PMID 26479701
- Opened: PubMed abstract
- Key facts: 3 rhesus macaques, S1 arrays, ICMS 4 h/day, 5 days/week, 6 months; 10-100 µA, 1 or 5 s trains, duty cycle 1/1 or
  1/3. Implantation caused damage; chronic ICMS had "no detectable additional effect"; no fine-motor impairment.
- Relevance: the NHP basis for the 100 µA human cap (Hughes 2022 states caps were selected from NHP work).

### [B] Chronic ICMS and the electrode-tissue interface (Chen, 2014; NHP) - DOI 10.1088/1741-2560/11/2/026004 / PMID 24503702
- Opened: PubMed abstract
- Key facts: 3 macaques, 4 h/day for 6 months; impedance and voltage excursion decay, stabilize after 10-12 weeks; decay
  depends on amplitude (and less on train duration); no fine motor deficit.

### [C] A model of safe levels for electrical stimulation (Shannon, 1992) - DOI 10.1109/10.126616 / PMID 1592409
- Opened: PubMed abstract only
- Key facts: model of damage vs stimulation level; proposes limits computed from charge and electrode position. The
  equation form (log(Q/A) = k - log(Q)) and k values are NOT stated in the abstract and were NOT verified from an opened
  source -> UNVERIFIED here. None of the opened human ICMS papers quoted a Shannon k or a charge density in µC/cm2; they
  quote per-phase amplitude/width caps (100 µA x 200 µs => 20 nC/phase, arithmetic) and "charge per phase" as the damage determinant.
- Grade C: theory/empirical model derived largely from macroelectrode data; applicability to microelectrodes contested (not verified here).

---
## 4. Frequency-discrimination context (not ICMS)

### [B] Functional frequency discrimination from cortical somatosensory stimulation (Kramer, 2019) - DOI 10.3389/fnins.2019.00832 / PMID 31440133
- Opened: PubMed abstract
- Key facts: n=3 epilepsy patients, SUBDURAL ECoG (not intracortical). Frequencies 20-100 Hz: reliable detection at and above
  40 Hz, lower limit ~20 Hz, JND estimated <10 Hz.
- Relevance: the Caltech/USC "Kramer/Lee" work found is surface stimulation; no Kramer ICMS percept paper found in PubMed.
- Caveats: different modality; do not pool with ICMS.

### [B] Reaction times to multi-electrode ICMS (Sombeck, 2020; NHP) - DOI 10.1088/1741-2552/ab5cf3 / PMID 31778982
- Opened: NCBI efetch PMC7189902 + abstract
- Key facts: monkeys, area 2. RT to single-electrode ICMS fell with current, frequency, train length; at 100 µA, 330 Hz most
  electrodes slower than mechanical cue, slightly faster than visual. >=480 µA spread over 16 electrodes gave RTs up to 20 ms
  FASTER than the mechanical cue.
- Relevance: multi-electrode ICMS can in principle beat natural latency; NHP only.

### [B] Roadmap for implanting arrays to evoke tactile sensations (Downey, 2024) - DOI 10.1002/hbm.70118 / PMID 39720868
- Opened: PubMed abstract
- Key facts: n=5 across 2 sites; presurgical fMRI/MEG mapping enabled ICMS percepts on at least the first four digits in all five.
- Relevance: targeting is a solved engineering step within this consortium.
