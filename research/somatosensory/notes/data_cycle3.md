# Data extraction, cycle 3 (data extractor: neurologist + neuroinformatics role), 2026-09-26

Scope: INPUTS ONLY, for blind pre-registration. I did not read code\RESULTS_* or code\REVIEW_*.
Open data only. No sign-ups. Every number below is QUOTED from an opened source unless marked DIGITISED
(read from a published figure; the method is stated) or ARITHMETIC (derived by me from quoted numbers).
CSV files: `notes\published-derived\` (listed at the end).

Access routes used:
- Europe PMC full text: `https://www.ebi.ac.uk/europepmc/webservices/rest/PMCxxxx/fullTextXML` (OA papers)
- Europe PMC supplementary files: `https://www.ebi.ac.uk/europepmc/webservices/rest/PMCxxxx/supplementaryFiles`
- NCBI PMC author manuscripts: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=NNNN`
- PMC figure images: `https://pmc.ncbi.nlm.nih.gov/articles/instance/NNNN/bin/<file>.jpg`
- GitHub: `https://github.com/CorticalBionics/StableAndPreciseICMS` (MIT license, code only)

---------------------------------------------------------------------------------------------------
## A) Spatial channel data for human S1 ICMS (for the PF-overlap / independent-channel model)

### A1. Greenspon et al. 2025, Nat Biomed Eng, "ICMS of somatosensory cortex evokes stable and precise tactile sensations" [B]
PMID 39643730, PMC12176618, DOI 10.1038/s41551-024-01299-z. Full text opened:
https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12176618/fullTextXML ; figures and ESM PDFs from .../supplementaryFiles.

**Data availability (quote):** "The de-identified data generated in this study are available from the data archive BRAIN
Initiative under the project code GU5A5IO8LRXE ( https://dabi.loni.usc.edu/dsi/GU5A5IO8LRXE ). Owing to participant privacy,
the data are available under restricted access, and access can be obtained on request to the study PIs..."
-> Per-electrode PF maps are **NOT openly available** (DABI, restricted, login). No "Source data" Excel exists in the ESM
(the ESM zip holds only figures + 2 PDFs: MOESM1 = Reporting summary style, MOESM2 = peer review file). I did not request access.
**Code availability:** GitHub repo above. It contains no data (README: "The data can be downloaded from DABI"), but it does contain
the **electrode layout of every S1 array** (HelperFunctions/LoadSubjectChannelMap.m) and the analysis constants (see A1.4).

A1.1 Array geometry (Methods, quote): "The two arrays (one medial and one lateral array) in Brodmann's area 1 of S1 were
2.4 mm x 4 mm with 60 1.5-mm-long electrode shanks wired in a chequerboard pattern such that 32 electrodes could be recorded
from or stimulated." Motor arrays: 4 x 4 mm, 100 shanks, 96 (C1, P3) or 88 (P2) wired.
Pitch 400 um: Hughes 2022 Methods (PMC10308851): "32 wired electrodes arranged on a 6 x 10 grid with a 400 um interelectrode
spacing, resulting in a device with an overall footprint of 2.4 x 4 mm". Fifer 2022 (PMC8865889) Methods: "32-channel stimulating
array (4 x 2.4 mm, 400-um pitch, custom population within 6 x 10 configuration...)". The Greenspon code multiplies grid distance
by 0.4 (Figure3_Somatotopy.m line 159: `ArrayDists{s,a} .* 0.4`).
-> 64 stimulating electrodes per Pitt/Chicago participant (2 arrays x 32).

A1.2 PF size (Fig 2e,f; quotes):
- "When summed over all electrodes, the area over which sensations were evoked above the 33% threshold was 12, 33 and 30 cm2 for
  C1, P2 and P3, respectively (palmar surface of 165 cm2, 7%, 20% and 18% of the whole hand, respectively; Fig. 2e)."
- "The size of individual PFs varied widely (median of 2.5 cm2, 5-95th percentiles 0.3-11.3 cm2) across electrodes and
  participants (Fig. 2f), with C1 reporting the smallest PFs and P2 the largest." Fig 2f legend: n = 62, 63 and 63 electrodes.
- Threshold rule: "we removed pixels reported on fewer than 33% of sessions for each electrode". "Electrodes for which no pixels met
  this threshold (25% for participants C1 and P2 and 58% for participant P3) were excluded from further analysis."
  (Note: the "n = 62, 63, 63" legend and the 25/25/58% exclusion are both quoted; how they reconcile is not stated. UNRESOLVED.)
- Mapping stimulus: "1-s-long ICMS pulse trains (100 Hz, 60 uA) to each electrode". Surveys every 1-3 months over ~800, 2,750 and
  750 days (C1, P2, P3).
- Per-electrode PF areas are NOT tabulated anywhere open. Only the pooled median/percentiles above.

A1.3 PF stability (Fig 2; quotes):
- Centroid distance from the first PF: no significant change for C1 and P3 (r = -0.03 and 0.12, P = 0.99 and 0.34); slight increase
  for P2 (r = 0.23, P < 0.01). "slopes tended to be extremely small (mean of 0.006 +/- 0.019)" [mm/day].
- "the mean Euclidean distance [single-day centroid to aggregate centroid] ranged from 3.5 to 8.7 mm (depending on the participant)."
- "Larger PFs tended to yield more variable centroids (r = 0.33, P < 0.01; Fig. 2h)".
- Within-day repeats (n = 8 and 7 electrodes, C1 and P2): "centroid distance: median of 3.5 mm, 25-75th percentiles 1.6-4.8 mm";
  within-day vs across-day distances "highly correlated (r = 0.68, P < 0.01) and statistically equivalent (paired t-test,
  t(15) = 0.1, P = 0.93)". => report noise, not drift, dominates PF variability.
- Centroid variability lies along a single axis (e.g. edge of finger, across a knuckle) (Ext Data Fig 2h).
- Report accuracy: "estimated centroids matched the reported centroids with submillimetre accuracy (median of 0.71 mm, Q1, Q3 = 0.52, 1.33 mm)".

A1.4 Cortical distance vs PF-centroid distance (Fig 3e; quotes):
- "restricting the analysis to pairs of electrodes with PFs on the same digit. We found that, as expected, PF centroid distance
  increased systematically with cortical distance (Fig. 3e). A 2 mm shift in cortex corresponded to a ~10 mm shift in the PF on
  the skin, on average."
- Legend: "Within digit, the distance between two PF centroids is significantly correlated with the distance between the electrodes
  across arrays (Pearson's correlation, n = 5,892 pairs, r = 0.69, P < 0.0001) and within each array (Pearson's correlation,
  r > 0.4, P < 0.0001, Holm-Bonferroni corrected)."
- From the released code (Figure3_Somatotopy.m, lines 150-200): x = grid distance x 0.4 mm; y = PF distance in pixels / 5 (so the code
  treats 5 px = 1 mm on the hand image; the paper text does not state this scale); 7 bins on [0, 4] mm; P3 lateral array excluded
  from the plot; only within-array pairs are plotted.
- **DIGITISED** mean curve (grey line), file `data\greenspon2025_fig3e_cortical_vs_PF_distance_DIGITISED.csv`:
  cortical 0.29 / 0.86 / 1.43 / 2.00 / 2.57 / 3.14 / 3.71 mm -> PF-centroid distance 3.1 / 6.0 / 8.0 / 11.8 / 18.2 / 24.1 / 26.6 mm.
  Method: axis calibration from tick marks (x: 36.7 px/mm; y: 2.97 px/mm), median grey-pixel row at each bin centre; +/-1 mm.
  The 2.0 mm point (11.8 mm) agrees with the stated "~10 mm". The curve is convex (slope ~5 mm/mm below 1.5 mm, ~11 mm/mm
  from 2-3 mm): ARITHMETIC from the digitised points.
- Digit classification: position along one optimal axis classifies digit "as well as the original position (2D)"; the axis is
  "approximately parallel to the local curvature of the central sulcus for five out of the six arrays". Accuracies are only plotted
  (Fig 3b,d, ~0.6-1.0 on the axis). NOT digitised.

A1.5 PF vs RF, amplitude/frequency, additivity:
- RFs larger than PFs (C1 P < 0.0001; P3 P = 0.0078). "The median proportion [of PF inside RF] was 1 for both with 25th percentiles of
  0.83 and 0.72 for C1 and P3". RFs span more hand regions than PFs (C1, P3, R1; P = 0.0035).
- "the size of the PF increased threefold as amplitude increased from 40 to 80 uA, with ICMS frequency fixed at 100 Hz (median
  (25-75th percentiles) of 170% (142-330%)...)"; "PF size grew systematically as frequency increased from 50 to 200 Hz, with amplitude
  fixed at 60 uA (median (25-75th percentiles) 129% (121-185%)...)"; size vs magnitude estimate r = 0.77.
  (Note: "threefold" and "170%" are both in the text; 170% is presumably the median size relative to 40 uA, i.e. 1.7x. UNRESOLVED wording.)
- Pairs: "the summed PFs were moderately predictive of the multi-electrode PF (mean r = 0.61; Fig. 4c)", additive model beats a
  random-pair null (KS D = 0.86, P < 0.0001), participant C1.
- Localization (C1, 60 uA): single-electrode ICMS "more often failed to elicit a localizable sensation (30% versus 0%) and when it did,
  participants often incorrectly localized the sensation (42% versus 7%)"; n = 128 single, 110 multi-electrode trials.
- Natural touch comparison (Discussion): "Contact transients evoke responses over a wide swath of cortex (spanning ~15 electrodes on
  the array)... Contact maintenance... (spanning ~2 electrodes)".

A1.6 Electrode layout file (open, from the GitHub code): `data\greenspon2025_S1_array_channel_maps.csv`
- 10 sensory arrays (5 participants x 2), each 10 rows x 6 columns, 32 wired positions in a chequerboard; x_mm, y_mm = col, row x 0.4.
- Participant codes: code maps BCI02 = C1, CRS02 = P2, CRS07 = P3 (Figure2/3 scripts: `SubjectIDs = {'BCI02','CRS02','CRS07'}`,
  `subj_str = {'C1','P2','P3'}`). BCI03 and CRS08 are also in the file (likely C2 and P4; the code does not state it, so UNVERIFIED).
- Array rotation angles (deg) are in the code (`ArrayRotations`). The **inter-array separation is not in the code or the paper**.
- Use: gives the exact geometry of which grid sites are wired, so a model can place the 32 electrodes exactly.

### A2. Array placement and inter-array separation (Pitt/Chicago)
- **Inter-array distance: NOT FOUND in any opened source** (Greenspon 2025, Hughes 2021 JNE, Hughes 2022, Flesher 2021, Downey 2024
  HBM + its supplements, Greenspon 2025 decade preprint, the GitHub code). Arrays were placed per participant from fMRI/MEG maps;
  the only spatial information is the images (Downey 2024 Fig 3; Greenspon 2025 Fig 1/Fig 3c). I did NOT estimate it.
- Downey et al. 2024 Hum Brain Mapp, "A Roadmap for Implanting Electrode Arrays..." [B], PMID 39720868, PMC11669040,
  full text: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11669040/fullTextXML (supplements: .../supplementaryFiles).
  - 5 participants (C1, C2, P2, P3, P4); "ICMS-evoked sensations localized to at least the first four digits of the hand".
  - Table 4 (quote header): "The distance (mm) along the medial-lateral axis from the hand-knob to the peak activity for each digit":
    C1 D1-D5 19.7, 10.3, 5.6, 4.1, 1.5; C2 16.2, 3.2, 6.2 (D1, D2, D4); P2 22.0, 11.8, 6.1 (D1, D2, D5); P3 15.3, 12.3, 10.9, 6.2
    (D1-D4); P4 19.9, 28.1, 15.7 (as listed). "the position of the sensory representations relative to the hand knob varied by up to
    25 mm along the mediolateral axis across participants".
    ARITHMETIC (C1 only, fMRI peaks): D1-to-D5 span 18.2 mm, i.e. ~4.5 mm per digit on average. Two 2.4 x 4 mm arrays cannot cover it.
  - "In all cases except for P4's medial motor array, we had 100% correspondence" (imaging-predicted digit evoked by >= 1 electrode).
  - "most projected fields on single electrodes were confined to a single segment or two adjacent segments, even when felt on
    multiple digits." No consistent relation between anterior-posterior electrode position and proximal-distal PF position.
  - Electrodes tested on average "10, 4, 54, 16, and 3 times in C1, C2, P2, P3, and P4".
  - **Supplementary Table 1** (percentage of electrodes per array with a PF on each digit; PFs can cover several digits; segments
    reported < 30% of the time were excluded) -> transcribed verbatim to `data\downey2024_digit_coverage_by_array.csv`.
    E.g. C1 medial D2/D3/D4 = 50/100/50%; C1 lateral D1/D2 = 28.6/92.9%; P2 medial D4/D5 = 100/100%.
- Hughes 2021 JNE [B], PMID 34320481, PMC8500669 (NIHMS author manuscript via efetch): participant P2: "Each electrode array consisted
  of 60 electrodes in a 6x10 grid, 32 of which were wired"; "On any given day, tactile sensations localized to the hand were elicited
  on 50-60 of the 64 electrodes with stimulation"; "Typically, 2 to 8 electrodes were removed from the test set each day" (high
  interphase voltage). High-amplitude recordings on "17+/-4 SIROF-sensory" electrodes on days 1400-1500.
- Flesher 2021 Science [B], PMID 34016775, PMC8715714 (author manuscript): "Two additional microelectrode arrays with 32 wired electrodes
  were implanted in area 1"; feedback used index-finger torque -> index-finger electrodes; middle-finger torque -> electrodes for
  middle, ring and pinky. No inter-array distance.
- Flesher 2016 STM [B], PMID 27738096: only the abstract was opened (no PMC copy). Abstract: stimulation sites "organized according to
  expected somatotopic principles"; percepts "remain stable for months". No numbers extracted.
- Greenspon et al. 2025 medRxiv "ICMS in humans: a decade of safety and efficacy" [C], PMID 40832410, PMC12363726 (preprint FT):
  5 participants; "62+/-15% of the electrodes still reliably evoke tactile sensations (~25% decrease in functional electrodes),
  including 55% of the electrodes after 10 years in one participant"; ">75% of electrodes for three of the five participants were
  functional one year after implantation" (functional = threshold < 100 uA); "somatotopic coverage remained largely unchanged due to
  spatially-redundant projected fields". Months implanted C1 56, C2 26, P2 122, P3 59, P4 27.

### A3. Demonstrated number of distinguishable locations / patterns
(For each: this is what was demonstrated, not a capacity bound.)
- Fifer et al. 2022 Neurology [B], PMID 34880087, PMC8865889 (PMC HTML https://pmc.ncbi.nlm.nih.gov/articles/PMC8865889/):
  JHU participant, 3 stimulating arrays (bilateral), 96 stimulating electrodes. "Stimulation evoked tactile sensations in 8 fingers,
  including fingertips, spanning both hands." Blinded identification of 5-7 digit-associated electrode sets (1-3 electrodes each) +
  null: "mean accuracy of 99.0% (i.e., 386 of 390 trials correct, including 78 of 80 in a block with 7-digit conditions and a
  no-stimulation condition)". PF "on average 33% larger than a finger pad"; size grew 21% from 20 to 80 uA.
  => >= 7 reliably distinguishable locations (+ null) demonstrated, with 3 arrays in 2 hemispheres.
- Greenspon 2025 (C1): bionic-hand digit localization; single vs multi-electrode (see A1.5). Categories were single digits or digit pairs;
  exact number of alternatives not stated in the text I extracted.
- Valle et al. 2025 Science "Tactile edges and motion..." [B], PMID 39818881, PMC11994950 (author manuscript via efetch; the Europe PMC
  endpoint returned HTTP 500). Participants c1, c2 (Pitt/Chicago arrays; "6x10 matrix electrodes ... covering 2.4x4.0mm").
  - Edge orientation (3 classes: along, across, none; 3-electrode edges): "c1: 81-89-84% on d1-d2-d3, n=150; c2: 61-68% on d2-d3, n=75";
    asymptote at 0.5 s duration (78%, n=225).
  - Shapes from two PFs: "c1: 82+/-9 - 72+/-8%, n=200, c2: 50+/-14 - 48+/-8%, n=120, for d2-d3" (5 shapes c1, 3 shapes c2).
  - Motion direction (4 directions, chance 25%): "c1: 76+/-14%, n=180, c2: 78+/-15%, n=60"; multi-digit "c1: 98+/-2%, n=120;
    c2: 75+/-14%, n=75". Duration effect: "50ms-30%, 200ms-72%, n=60".
  - Apparent motion only when trains were separated by 0 to 0.5 s; overlap -> single event at two locations; > 0.5 s -> two events.
  - Speed discrimination Weber fraction 0.56+/-0.09. Letters (T, L, C, O, I) on 3-6 adjacent PFs: 49+/-17% sequential vs 37+/-21%
    simultaneous (n=150). Object (pen/can/ball) from 9 electrodes: 79+/-11% (n=45).
  - "Participants would often report sensations of a continuous edge even when the individual electrode PFs were discontinuous".
- Downey 2024: at least 4 digits per participant (A2).
- NOT FOUND: any explicit "number of independent channels" or information-theoretic channel count for human S1 ICMS.

---------------------------------------------------------------------------------------------------
## B) Adaptation to sustained ICMS (for the biomimetic-encoding model)

### B1. Hughes, Flesher, Gaunt 2022, Brain Stimul, "Effects of stimulus pulse rate on somatosensory adaptation in the human cortex" [B]
PMID 35671947, PMC10308851 (NIHMS author manuscript; full text via efetch; figures from PMC /bin/). One participant (P2: "A single
28-year-old male subject with a C5 motor/C6 sensory ASIA B spinal cord injury"). **No time constant or half-life is reported.**
Timescale: PERCEPTUAL, seconds to minutes.

Protocol numbers (quotes):
- Pulses: cathodal-first, 200 us cathodal, 400 us anodal at half amplitude; 20-300 Hz; 2-100 uA. CereStim C96.
  "Above 280 Hz, the stimulator occasionally dropped individual pulses".
- "The maximum stimulus train duration for continuous stimulation was 15 s at 100 Hz or 5 s at 300 Hz." After 15 s of stimulation,
  an equal time off (50% duty).
- Continuous: 20, 100, 300 Hz at 60 uA, single electrodes; "15 s of stimulation at 20 and 100 Hz and 5 s of stimulation at 300 Hz on
  5 electrodes for one trial each". Analog slider 0-1; "changed from baseline when ... below 0.95", "extinguished when ... less than 0.05".
- Burst: 100 Hz, 60 uA, 50% duty, bursts 100, 200, 500 ms; "60 s of stimulation for each of these burst parameters on 10 different
  electrodes for one trial each"; same number of pulses in 60 s.
- Intermittent: "1 s of stimulation at 60 uA followed by 5 s of no stimulation for 50 repetitions", then "1 s of stimulation followed by
  61 s without stimulation for another 5 repetitions"; verbal intensity after each train on a self-selected scale. Exp 1: 7 electrodes at
  100 Hz (2 sessions, Fig 3C); Exp 2: "Four electrodes were also tested four times at 20, 100, and 250 Hz."
- Detection threshold: 2AFC staircase (start 10 uA, 2 dB steps, stop after 5 reversals, 100 Hz), before/after "15 s on 15 s off ... at
  60 uA and 100 Hz for 240 s"; 12 electrodes.

Results (quotes):
- Continuous: "300 Hz stimulation resulted in the fastest change from baseline, with the median intensity falling to 69+/-30% of the
  baseline intensity after 5 s of stimulation. The median intensity remained unchanged from baseline after 5 s of stimulation at both
  20 Hz and 100 Hz. However, starting 7 s after stimulation onset, 100 Hz stimulation caused changes in percept intensity that fell to
  64+/-36% after 15 s of stimulation. Stimulation at 20 Hz had no effect on intensity during the 15 s stimulation window."
  Initial drop times differ by frequency (LME p = 8.1e-5; all pairwise p <= 0.0043).
  **DIGITISED** Fig 1C bars (initial adapt time, mean): 20 Hz 16.3 s (i.e. after the 15-s train ended = no change during stimulation),
  100 Hz 8.3 s, 300 Hz 3.9 s. Method: y ticks 0-16 s every 2 s (17.15 px/s), bar-top pixel row; +/-0.1 s.
  Motor-lag caveat (quote): the participant "began to move the slider within two seconds (mean 20 Hz = 1.37+/-0.54 s, mean 100 Hz =
  1.07+/-0.28 s, mean 300 Hz = 1.94+/-0.72 s)" after stimulation stopped, so "these times may overestimate the actual time it takes for
  adaptation to start occurring".
- Burst: "Stimulation for 60 s caused a complete extinction of the evoked sensation on 26 of the 30 trials"; "mean drop time of
  13.2+/-1.6 s across paradigms (p = 0.76)"; extinction "500 ms paradigm ... at 26.1+/-2.6 s, while the 100 ms paradigm caused
  extinction at 39.1+/-3.8 s and the 200 ms paradigm caused extinction at 35.5+/-5.5 s (p = 0.016)".
  **DIGITISED** median time courses (Fig 2B, 1-s steps, 0-60 s): `data\hughes2022_fig2b_burst_DIGITISED.csv`.
  E.g. at 20 s: 0.64 / 0.48 / 0.46 (100/200/500-ms bursts); at 30 s: 0.52 / 0.34 / 0.01.
- Intermittent: "the mean intensity decreased to 43.5+/-10% of the initial intensity during the adaptation period and recovered back to
  72.6+/-7% of the initial intensity by the end of the recovery period"; "no electrodes ever became imperceptible"; two electrodes fell
  to "less than 6%"; two to "48-79%"; one "showed a slight increase". "changes in percept intensity driven by intermittent stimulation
  stabilized after approximately 100 s". Frequency (20/100/250 Hz) did not change intermittent adaptation or recovery (p >= 0.05).
  **DIGITISED** mean normalised intensity vs time (Fig 3B): `data\hughes2022_fig3b_intermittent_DIGITISED.csv` (42 resolvable points;
  e.g. t ~13 s 0.91, ~22 s 0.82, ~39 s 0.69, ~51 s 0.60, ~82 s 0.51, ~150 s 0.48, ~221 s 0.44, ~288 s 0.43; recovery 0.80 -> 0.73).
  Markers overlap (6 s spacing = 3.3 px), x uncertainty ~+/-3 s, y ~+/-0.01.
  The end values match the text (43.5%, 72.6%). No fit was done (left to the mathematician; any tau fitted from this is DERIVED).
- Detection: "mean threshold increase of 2.4+/-1.1 uA following continuous stimulation" (12 electrodes, p = 0.027).
- Discussion: "the only stimulus paradigm that did not cause adaptation was continuous stimulation at 20 Hz for 15 s".

### B2. Greenspon et al. 2024 Brain Stimul, "ICMS of human somatosensory cortex induces natural perceptual biases" [B]
PMID 39413869, PMC11887563 (author manuscript, efetch). 3 participants. Timescale: PERCEPTUAL, 0.5-5 s (inter-stimulus interval).
- Opposite sign from adaptation: a preceding stimulus ENHANCES the second one (time-order error). Trains 1 s, 50 Hz, standard 60 uA.
- "order effects were significantly reduced when the ISI was 5 seconds" (vs 1 s; signed rank Z = 2.71, p < 0.0066); 4 ISIs 0.5-5 s on
  a subset show "a similar trend". Recommendation (quote): "magnitude estimates should be performed using long inter-trial intervals
  (>3 seconds) to minimize the interactions between successive stimuli."
- Quote: "in magnitude estimation experiments we typically normalize all ratings within blocks to offset a global reduction in reported
  intensities caused by desensitization, though the degree to which this occurs is electrode dependent." No time constant given.

### B3. Neuronal adaptation / depression to ICMS (animal)
- Sombeck et al. 2022 J Neural Eng [B], PMID 35378515, PMC9142773 (author manuscript). Rhesus macaque (2 animals), Utah array (cortical area not checked by me).
  Timescale: NEURONAL, ms to seconds.
  - Single pulses: transsynaptic activity "as early as ~0.7 ms", "immediately followed by suppressed neural activity lasting 10-150 ms";
    "After trains, this long-lasting inhibition was replaced by increased firing rates for ~100 ms."
  - Fig 6 (0.2-s trains, 20/49/94/179 Hz): inhibition duration after trains up to ~250 ms at 94-179 Hz (read from plot, not digitised).
  - 4-s trains at 20, 40, 60 uA and 51, 80, 104, 131 Hz: firing rate in 50 ms bins fitted with a*exp(-b*x); "the evoked response decayed
    significantly faster with greater stimulation amplitude or frequency"; decayed "significantly faster for neurons recorded on the
    stimulated channel than on non-stimulated channels", while non-stimulated channels "were maintained throughout long trains".
    179 Hz was dropped for long trains "Because the recorded neural response decayed rapidly". The decay rates b are only in a
    figure I could not locate among the 7 PMC figure files: NOT extracted.
- Michelson et al. 2019 J Neurosci Res [B], PMID 30585651, PMC6469875 (author manuscript). Mouse S1 L2/3, GCaMP6s two-photon; 30 s
  continuous ICMS, 50 uA, 50 us/phase (mostly), 10-250 Hz. Timescale: NEURONAL (calcium), seconds.
  - "Activation Time" = time to reach half of the response energy over the 30-s train (15 s = no decay). "Activation Time was
    significantly greater in local somas than in distant somas for 30 Hz (10.9+/-0.4 vs 7.6+/-0.4 s), 50 Hz (9.8+/-0.6 vs 6.9+/-0.7 s),
    75 Hz (10.5+/-0.6 vs 6.4+/-0.7s), and 250 Hz (11.4+/-0.9 vs 5.7+/-1.5 s)". "At frequencies of 90 Hz or greater, there is a clear decrease
    in the number of activated neurons as the pulse train progresses." Steady-state neurons ~40 um closer to the electrode than onset neurons.
- Hughes & Kozai 2023 Brain Stimul [B], PMID 37244370, PMC10330928 (author manuscript). Mouse S1 and V1, GCaMP6s, 0-20 uA; Short (1 s on / 4 s
  off) and Long (30 s on / 15 s off) trains. Timescale: NEURONAL (calcium), 1 s to 30 s.
  - "most DCS [depression during continuous stimulation] occurred within the first 10 s"; rapid phase (0-10 s) depends on amplitude and
    frequency; slow phase (10-30 s) fitted as I(t) = k*I0*ln(t) + I0 with "k = -0.43+/-0.04" for all Long trains (k not different, p = 0.44).
  - Neuron classes (Short trains): "Rapidly Adapting" < 85% of max at 1 s; "Slowly Adapting" < 95%; non-adapting > 95%.
  - "Dynamic amplitude modulation reduced stimulation induced depression by 14.6 +/- 0.3% for Short and 36.1 +/- 0.6% for Long trains".
  - "calcium activity returned to baseline in less than 4 s for all trains". Neurons farther from the electrode depress faster.
- Hughes et al. 2025 iScience [B], PMID 40520112, PMC12167498 (abstract read; full text fetched but not mined): mouse V1, 30 s ICMS;
  excitatory activity "more likely to decrease", inhibitory "more likely to increase throughout the stimulation period".
- Suematsu et al. 2024 J Neural Eng [B], PMID 38537268 (abstract only): mouse V1; post-activation "depression" of calcium responses;
  depression prefers slightly higher frequencies than activation. No time constant in the abstract.
- Kumaravelu & Grill 2024 Brain Stimul [C, model], PMID 38492885 (abstract only): single-pulse excitation then prolonged inhibition
  (AHP + GABA-B); paired-pulse test excitation "decreased marginally ... for interpulse intervals (IPI) < 100 ms"; inhibition prolonged
  for IPIs < 50 ms; repetitive response declines at higher frequencies.

### B4. Natural S1 adaptation to sustained indentation
- Callier et al. 2019 Cereb Cortex "Neural Coding of Contact Events in Somatosensory Cortex" [B], PMID 30668644, PMC6917522
  (full text via PMC HTML). Macaque area 1, Utah arrays. Timescale: NEURONAL, ~20-400 ms.
  - "activity rose sharply, with a latency of about 20 ms after stimulus onset and remained high as long as the probe continued to move";
    transient/sustained ratio: transient = first 200 ms; sustained = 200-ms window starting 200 ms after the probe stopped. "more than
    15 times stronger ... (range: 2.2 to 42.4, median: 12.0 over 28 skin locations from 4 arrays)"; offset "more than 8 times stronger
    ... (range: 0.76 to 35.0, median 6.0)".
  - Sustained epoch defined as "the 300-ms period beginning 400 ms after stimulus onset (at which time the phasic response had subsided)".
    Ramp 200 ms at the largest indentation. => the phasic response subsides within ~400 ms of onset (as defined, not fitted).
  - During the sustained phase activation covers "a fraction of a square millimeter" around the hotzone electrode.
  - Population centroids converge on the reference within 40-50 ms.
  - **No adaptation time constant is reported.** Cited (not opened): afferent responses to a pre-indentation "decay away within 10-20 s,
    as does the resulting sensation" (Vega-Bermudez and Johnson 1999). Secondary, UNVERIFIED primary.

### B5. Summary of timescales (what each source measures)
| Source | Species | Measure | Timescale |
|---|---|---|---|
| Sombeck 2022 | NHP | post-pulse suppression 10-150 ms; post-train rebound ~100 ms; decay in 4-s trains | neuronal, 10 ms - s |
| Kumaravelu 2024 (model) | model | paired-pulse depression IPI < 100 ms | neuronal, < 100 ms |
| Callier 2019 | NHP | onset transient 12x sustained (median); phasic gone by ~400 ms | neuronal (natural), ~0.2-0.4 s |
| Michelson 2019 | mouse | half-energy time 5.7-11.4 s over 30 s trains | neuronal (Ca), s |
| Hughes & Kozai 2023 | mouse | rapid depression in first 10 s; slow ln(t) 10-30 s, k = -0.43 | neuronal (Ca), s |
| Greenspon 2024 | human | enhancement decays between ISI 1 s and 5 s | perceptual, s |
| Hughes 2022 continuous | human | onset of intensity drop 3.9 s (300 Hz), 8.3 s (100 Hz), none in 15 s (20 Hz) | perceptual, s |
| Hughes 2022 burst | human | drop 13.2 s; extinction 26-39 s | perceptual, 10s of s |
| Hughes 2022 intermittent | human | to 43.5% at 300 s, plateau ~100 s; recovery to 72.6% over 305 s | perceptual, minutes |
| Hughes 2022 detection | human | +2.4 uA threshold after 4 min 50% duty | perceptual, minutes |

---------------------------------------------------------------------------------------------------
## Not found / blocked
- Per-electrode PF maps, areas and centroids (Greenspon 2025): DABI restricted-access only. Not requested (no sign-up).
- Pairwise PF overlap (e.g. Jaccard / Dice) vs electrode distance: not reported anywhere open; only centroid distance (A1.4).
- Inter-array centre-to-centre distance for any Pitt/Chicago participant: not reported (images only).
- A count of "independent channels" for human S1 ICMS: not reported; only task-level demonstrations (A3).
- Any fitted time constant or half-life for perceptual ICMS adaptation in humans: not reported (Hughes 2022 gives onset times, extinction
  times and end-of-period levels only; digitised curves are provided for fitting).
- NHP perceptual ICMS adaptation time constants: none found in the Europe PMC searches ("intracortical microstimulation" AND
  (adaptation OR habituation) AND somatosensory: 208 hits, first 15 screened; microstimulation AND adaptation AND (magnitude estimation
  OR detection) AND primate/human: 410 hits, first 15 screened). Butovas & Schwarz 2003 (rat, PMID 12878710) not opened.
- Sombeck 2022 per-condition decay rates (in a figure not among the PMC figure files).

## Files written (notes\published-derived\)
- `greenspon2025_S1_array_channel_maps.csv`: exact 10x6 grid, wired positions, x/y mm (0.4 mm pitch), rotation; 10 S1 arrays (from the MIT code).
- `greenspon2025_fig3e_cortical_vs_PF_distance_DIGITISED.csv`: mean PF-centroid distance vs cortical distance (7 bins).
- `pf_summary_human_S1.csv`: all quoted PF / channel numbers with source and figure.
- `downey2024_digit_coverage_by_array.csv`: % electrodes per array with a PF on each digit (5 participants), transcribed from the supplement.
- `hughes2022_fig2b_burst_DIGITISED.csv`: median perceived intensity vs time, 3 burst paradigms, 0-60 s.
- `hughes2022_fig3b_intermittent_DIGITISED.csv`: mean normalised intensity vs time, intermittent adaptation + recovery.
