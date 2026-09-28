# Neurobiologist bibliography: the biology an S1 ICMS encoder must mimic
Author role: neurobiologist (hive cycle 1, 2026-09-26). Format per HIVE.md.
"EF" = PubMed efetch abstract, URL pattern https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&rettype=abstract&retmode=text&id=<PMID>
"PMC" = full text HTML fetched from https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/ (text grepped for the facts quoted; not read cover to cover).
Grades: A replicated/independently confirmed; B single peer-reviewed study; C preprint/theory/chapter; D press.
All stimulation parameters below are QUOTED facts from published animal/human studies, never proposals. Any human application requires an IRB/FDA-approved clinical study.

---
## 1. Peripheral mechanoreceptive afferents (SA1, RA1, SA2, PC)

### [A] Densities of four mechanoreceptive unit types in human glabrous skin (Johansson & Vallbo, 1979) - DOI 10.1113/jphysiol.1979.sp012619 / PMID 439026
- Opened: EF id=439026 (abstract); PMC1281571 (only the abstract text is machine-readable; body is scanned) 
- Key facts: 334 low-threshold units, human median nerve microneurography. Four classes RA, PC, SA I, SA II. Overall density rises proximo-distally; relative density palm : main finger : fingertip = 1 : 1.6 : 4.2. The gradient is carried by RA and SA I (small, well-defined RFs); PC and SA II almost evenly distributed. Modelled absolute density: 241 units/cm2 at fingertip, 58 units/cm2 in palm.
- Relevance: sets the spatial sampling an encoder (and TouchSim) must reproduce; explains why fingertip representations dominate area 3b.
- Caveats: absolute densities are a model based on fibre counts; per-type absolute numbers are in the body (scanned), not verified by me -> per-type values UNVERIFIED here. Replicated by later work (used as TouchSim input).

### [A] Detection thresholds of afferents vs psychophysics (Johansson & Vallbo, 1979b) - DOI 10.1113/jphysiol.1979.sp013048 / PMID 536918
- Opened: EF id=536918 (abstract)
- Key facts: psychophysical indentation thresholds median 11.2 um (fingers/peripheral palm) vs 36.0 um (centre palm, creases). Afferent thresholds (128 units): PC 9.2 um, RA 13.8 um, SA I 56.5 um, SA II 33.1 um (medians). Detection can rest on one impulse in one RA unit.
- Relevance: single-spike sensitivity => near-threshold ICMS percepts may reflect very small activated populations; also bounds how "quiet" a biomimetic baseline must be.
- Caveats: human, small probe, specific stimulus waveform.

### [B] Stimulus-response functions of human SA units (Knibestol, 1975) - DOI 10.1113/jphysiol.1975.sp010835 / PMID 1127614
- Opened: EF id=1127614 (abstract)
- Key facts: 101 SA units; 88 SA-I (no response to lateral stretch), 13 SA-II (stretch-sensitive, often directional). SA-I no spontaneous discharge, irregular firing; SA-II mostly spontaneous, very regular. Conduction velocity SA-I 58.7 +/- 2.3 m/s, SA-II 45.3 +/- 3.6 m/s. Static response vs indentation: negatively accelerating, mean power-function exponent 0.66.
- Relevance: SA1 pressure coding is compressive (exponent < 1); SA2 carries skin-stretch (a proprioceptive cue) and is NOT in TouchSim.
- Caveats: only 2 SA-II units fitted for S-R functions.

### [A] Afferent class proportions, RF sizes, frequency tuning (Delhaye, Long & Bensmaia, 2018 review) - DOI 10.1002/cphy.c170033 / PMID 30215864
- Opened: EF id=30215864; PMC6330897 (full text, grepped)
- Key facts: of tactile fibres from the hand, SA1 ~25% (RFs with multiple hot spots, mean ~10 mm2), RA ~40%, SA2 ~20% (mean RF 50 mm2), PC ~15% (large RFs). SA1 most sensitive below ~10 Hz (~5 Hz), PC peak ~250 Hz, RA intermediate. Area 3b hand RFs 10-60 mm2, smallest in L4; 94%-type centre-surround structure (see DiCarlo). 51% (3b) and 40% (area 1) of neurons show sustained (SA1-like) plus OFF (RA/PC-like) responses => convergence. Area 3a: mainly proprioceptive; hand RFs from single digit to whole hand; contains 15% of hand corticomotoneuronal cells. ~5% of area-1 neurons are Pacinian-like, rarer in 3b.
- Relevance: master reference for cortical-area roles; convergence means "one electrode = one afferent class" is false.
- Caveats: review; numbers are secondary citations (checked only as stated in review).

### [B] Texture: spatial + temporal codes across afferents (Weber et al., 2013) - DOI 10.1073/pnas.1305509110 / PMID 24082087
- Opened: EF id=24082087; PMC3800989 (full text, grepped)
- Key facts: 55 natural textures scanned on macaque fingertip. Spatial (SA1) mechanism accounts only for coarse textures; fine textures are conveyed by precise temporal spiking in RA/PC driven by skin vibrations (behaviourally relevant 50-800 Hz). SA1 respond weakly (<10 Hz) to most textures. 83% classification with 7 PC fibres; PC texture information peaks at ~2 ms temporal resolution. Spike patterns dilate/contract with speed: 89% accuracy after warping 120->80 mm/s, 62% for 40->80 mm/s.
- Relevance: the texture problem is fundamentally a ms-precision temporal code in RA/PC pathways.
- Caveats: macaque; single lab (but consistent with Long 2022, Harvey 2013 from same lab).

### [C] Touch is a team effort (Saal & Bensmaia, 2014 TINS review) - DOI 10.1016/j.tins.2014.08.012 / PMID 25257208
- Opened: EF id=25257208 (abstract)
- Key facts: most natural stimuli excite all afferent classes; most cortical neurons get convergent input from multiple classes; argues for functional (not submodality) grouping of cortical neurons.
- Relevance: an encoder should target functional cortical response types, not "SA1 electrodes" vs "RA electrodes".
- Caveats: review/opinion (graded C as synthesis; underlying data are B/A).

### [B] TouchSim: whole-hand afferent simulator (Saal et al., 2017) - DOI 10.1073/pnas.1704856114 / PMID 28652360
- Opened: EF id=28652360; PMC5514748 (full text, grepped)
- Key facts: SA1, RA, PC (no SA2) afferents tiled at measured densities; ~12,500 afferents on the palmar hand, just under 1,000 per fingertip, ~4,000 in the palm. IF models fitted on 1-1,000 Hz sinusoids/noise. Firing-rate fit: training R2 = 0.91 +/- 0.04 (sinusoids) and 0.92 +/- 0.11 (noise); validation (diharmonic) R2 = 0.85 +/- 0.08. LNP alternative: 0.66/0.84 training, 0.73 validation. Spike timing precision better than 8 ms for all models; PC sub-ms; SA1/RA 3-8 ms. SA1 rate linear in indentation depth; RA monotonic in indentation rate. Flutter evokes hundreds of spikes/s across SA1/RA populations; high-frequency vibration up to 100,000 spikes/s across PC population.
- Relevance: the reference front end for any biomimetic encoder (skin -> afferent spikes). Must be combined with an afferent->cortex stage.
- Caveats: validated against macaque data from the same lab; no SA2, no thermal, no proprioceptors; skin mechanics simplified.

### [B] Intensity coding in afferent populations (Muniak et al., 2007) - DOI 10.1523/JNEUROSCI.1486-07.2007 / PMID 17959811
- Opened: EF id=17959811 (abstract)
- Key facts: local population response (afferents under the probe) is logarithmic with amplitude; whole active population response is linear. Perceived intensity best explained by firing rate of afferents under/near the stimulus, weighted by afferent type.
- Relevance: pressure/intensity mapping should be compressive and localized -> sets the target transfer function for amplitude/frequency modulation.
- Caveats: macaque afferents + human psychophysics; vibratory stimuli.

### [B] Tactile signals in object manipulation (Johansson & Flanagan, 2009 review) - DOI 10.1038/nrn2621 / PMID 19352402
- Opened: EF id=19352402 (abstract only; no numbers extracted)
- Key facts: contact events are encoded by tactile afferents and used by action-phase controllers to update motor output.
- Relevance: motivates onset/offset event signalling in closed loop.
- Caveats: review; abstract only.

## 2. Thermoreception

### [B] TRPM8 is the principal cold detector (Bautista et al., 2007) - DOI 10.1038/nature05910 / PMID 17538622
- Opened: EF id=17538622 (abstract)
- Key facts: TRPM8 activated by menthol or temperatures below ~26 C; TRPM8-/- mice have profoundly reduced cold responses and cold/warm discrimination deficits but still avoid <10 C surfaces.
- Relevance: cold is carried by a dedicated molecular/afferent channel, separate from mechanoreceptors.
- Caveats: mouse. TRPV1 (heat) paper not opened -> TRPV1 claims UNVERIFIED here.

### [B] Warm fibres in monkey glabrous skin (Darian-Smith et al., 1979) - DOI 10.1152/jn.1979.42.5.1297 / PMID 114608
- Opened: EF id=114608 (abstract)
- Key facts: 314 warm fibres; conduction velocity 1.2 +/- 0.5 m/s (unmyelinated). From 34 C baseline, warming pulses 0-8 C give peak rate 1.5-4.0 s after onset, then decay with time constant 5-12 s (independent of intensity); linear intensity function (ISI >= 60 s). >80% silent for skin >= 50 C. Receptor zone < 1 mm diameter; RF shaped by skin thermal conductivity. Suppression if ISI < 60 s.
- Relevance: thermal signals are slow (seconds) and adapt with 5-12 s time constants — a completely different time scale from touch.
- Caveats: monkey; the companion cold-fibre paper (PMID 4196271) has no abstract in PubMed -> not used.

### [B] Thermosensory activation of insular cortex (Craig et al., 2000) - DOI 10.1038/72131 / PMID 10649575
- Opened: EF id=10649575 (abstract)
- Key facts: PET in humans: graded cooling correlated with activity ONLY in the contralateral dorsal margin of middle/posterior insula; perceived thermal intensity correlated with right anterior insula / orbitofrontal cortex. Corresponds to the lamina I spinothalamocortical pathway.
- Relevance: primary thermal cortex is not S1 hand area.
- Caveats: PET, small n.

### [B] Operculo-insular segregation of touch, cold, warm, pain (Mazzola et al., 2012) - DOI 10.1016/j.neuroimage.2011.12.072 / PMID 22245639
- Opened: EF id=22245639 (abstract)
- Key facts: fMRI, 25 healthy volunteers. Posterior SII (OP1) activated by all stimulus types. Innocuous cooling activated contralateral OP1 and dorsal posterior/median insula; warm and heat-pain patterns differ; posterior granular insula (Ig) specific to pain.
- Relevance: independent (different group, different method) confirmation that thermal processing is operculo-insular.
- Caveats: fMRI; S1 not the focus.

### [B] Cellular coding of temperature in mouse cortex (Vestergaard et al., 2023) - DOI 10.1038/s41586-023-05705-5 / PMID 36755097
- Opened: EF id=36755097; PMC9946826 (full text, grepped)
- Key facts: widefield + 2-photon imaging, forepaw. S1 represents cool but not warm (10 C cooling 32->22 C gave reliable S1 responses, 10 C warming did not; only a tiny fraction of S1 neurons respond to warming, delayed/inconsistent). Posterior insula (pIC) has somatotopic cool AND warm; pIC inactivation profoundly impairs thermal perception. Warm responses in pIC delayed relative to cool. S1 and pIC receive parallel thermal streams (inactivating one does not abolish the other). Cool and touch spatially overlap in S1.
- Relevance: strongest cellular evidence that WARM is essentially absent from S1; COOL is present in S1 intermixed with touch.
- Caveats: mouse; primate S1 hand area not tested.

### [B] S1 needed for cooling perception in mice (Milenkovic et al., 2014) - DOI 10.1038/nn.3828 / PMID 25262494
- Opened: EF id=25262494 (abstract)
- Key facts: mice perceive small skin cooling; S1 neurons required for cooling perception; TRPM8 absence eliminates cold perception and S1 activation.
- Relevance: S1 does carry a behaviourally necessary cool signal (mouse).
- Caveats: mouse; abstract only.

### [B] ICMS percept "warmth" appears as an artefact quality in humans (Hobbs et al., 2025) - DOI 10.1088/1741-2552/adc2d4 / PMID 40106898
- Opened: EF id=40106898; PMC13571258 (full text, grepped)
- Key facts: see section 5; relevant here: participants compared ICMS to mechanical indentation; 'Less Warm' was one of the three most common descriptors (19%) of the biomimetic pattern vs the non-biomimetic one; mechanical indentation itself had no warmth. Quote: "more focal like an actual poke ... and less warm" (P2).
- Relevance: warmth reports from S1 ICMS exist but as a non-natural quality of linear trains, not as controllable temperature. No study found (in this pass) showing graded, controllable thermal percepts from S1 ICMS.
- Caveats: n = 3 humans; descriptor frequencies from supplementary tally.

## 3. Proprioception

### [A] The proprioceptive senses (Proske & Gandevia, 2012 review) - DOI 10.1152/physrev.00048.2011 / PMID 23073629
- Opened: EF id=23073629 (abstract)
- Key facts: receptors in skin, muscles, joints; limb position/movement coded by populations, not individual receptors; tendon organs and possibly spindles contribute to force/heaviness; motor areas can generate sensations of displacement without afferent input (experimental phantom).
- Relevance: position sense is a population/central-estimate construct; an encoder cannot copy "one receptor type".
- Caveats: review.

### [B] Human muscle spindles (Macefield & Knellwolf, 2018 review) - DOI 10.1152/jn.00071.2018 / PMID 29668385
- Opened: EF id=29668385 (abstract)
- Key facts: primary and secondary endings sensitive to length and velocity (primary more dynamic); fusimotor (gamma) control; human spindle background discharge related to stretch but low mean rates (~10 Hz); faithfully encode fascicle length passively, not straightforwardly during contraction.
- Relevance: afferent proprioceptive rates are low and contraction-dependent -> area 2/3a output, not spindles, is the practical encoding target.
- Caveats: review.

### [B] Proprioceptive activity in S1 during reaching (Prud'homme & Kalaska, 1994) - DOI 10.1152/jn.1994.72.5.2280 / PMID 7884459
- Opened: EF id=7884459 (abstract)
- Key facts: 254 S1 proprioceptive cells; broad, ~sinusoidal directional tuning; continuum phasic (movement) to tonic (posture); 46/86 (53.5%) show direction-dependent hysteresis; large active vs passive differences; most modulated by load direction.
- Relevance: position and movement signals are mixed in single S1 neurons with directional cosine tuning -> encoder target is population vector-like.
- Caveats: macaque.

### [B] Area 2 active vs passive movement (London & Miller, 2013) - DOI 10.1152/jn.00372.2012 / PMID 23274308
- Opened: EF id=23274308 (abstract)
- Key facts: area 2 neurons span active-only to passive-only; those responding to both have similar directional tuning; some fire before movement onset (efference copy).
- Relevance: area 2 mixes afferent and efference-copy signals — an ICMS encoder driven only by sensor data cannot reproduce the active-movement component.
- Caveats: macaque.

### [B] Area 2 encodes whole-arm kinematics (Chowdhury, Glaser & Miller, 2020) - DOI 10.7554/eLife.48198 / PMID 31971510
- Opened: EF id=31971510 (abstract)
- Key facts: whole-arm model (not hand-only) predicts area 2 activity across workspaces; many neurons represent limb state differently in active vs passive movement.
- Relevance: proprioceptive encoder must be driven by whole-arm state, and must accept active/passive inconsistency.
- Caveats: macaque; abstract only.

### [B] Postural hand representations in sensorimotor cortex (Goodman et al., 2019) - DOI 10.1016/j.neuron.2019.09.004 / PMID 31668844
- Opened: EF id=31668844; PMC7172114 (full text, grepped)
- Key facts: during grasp, area 3a, area 2 and M1 neurons track time-varying multi-joint POSTURES of the whole hand (contrast: reaching -> velocity/speed of arm). Multi-joint GLMs beat single-joint GLMs in M1, 3a (t(30)=8.56) and area 2 (t(40)=5.67). Recorded n: 35 (3a), 59 (area 2), 290 (M1) task-modulated neurons.
- Relevance: hand proprioception encoder should map multi-joint posture synergies, not single joints.
- Caveats: modest 3a/area 2 sample sizes.

### [C] Proprioceptive ICMS in area 2 biases perceived perturbation direction (Tomlinson & Miller, 2016, book chapter) - DOI 10.1007/978-3-319-47313-0_20 / PMID 28035576
- Opened: PMC5452683 (full text, grepped)
- Key facts: ICMS in area 2 concurrent with force perturbations biased monkeys' reported direction toward the stimulated neurons' preferred direction; graded with current (5 uA no effect, 20 uA strong bias); 6 electrode sets produced PD-congruent bias; failures associated with PD instability over days. Bias not the result of training.
- Relevance: evidence that S1 ICMS can inject a directional kinematic signal that combines with natural proprioception.
- Caveats: chapter (not a primary peer-reviewed article), small n -> C.

### [B] Proprioceptive and cutaneous ICMS percepts in a human (Armenta Salas et al., 2018) - DOI 10.7554/eLife.32904 / PMID 29633714
- Opened: EF id=29633714; PMC5896877 (full text, grepped)
- Key facts: 1 tetraplegic participant, 2 arrays in S1; 381 reported sensations; top descriptors squeeze 24.9%, tap 17.3%, right movement 9.7%, vibration 8.1%, blowing 6.6%, forward movement 5.8%, pinch 5.5%. Proprioceptive percepts on multimodal electrodes associated with higher amplitudes irrespective of frequency. No warm/cool descriptors in the reported table.
- Relevance: human proof that S1 ICMS can evoke movement/position-like percepts.
- Caveats: n = 1; percepts not shown to be controllable kinematic variables.

## 4. Cortical coding in S1

### [A] Multiple body maps in S1 (Kaas et al., 1979) - DOI 10.1126/science.107591 / PMID 107591
- Opened: EF id=107591 (abstract)
- Key facts: two complete cutaneous body maps in areas 3b and 1; area 2 predominantly "deep" (proprioceptive) tissues; 3a a possible fourth map.
- Relevance: area-specific targeting determines percept modality (touch in 3b/1, deep/proprioception in 3a/2).
- Caveats: classic mapping; later widely confirmed (A).

### [B] Area 3b receptive-field structure (DiCarlo, Johnson & Hsiao, 1998) - DOI 10.1523/JNEUROSCI.18-07-02626.1998 / PMID 9502821
- Opened: EF id=9502821 (abstract)
- Key facts: 330 neurons, 247 with repeatable RFs; 94% have a single central excitatory region with 1-4 flanking inhibitory regions; half have nearly balanced excitation/inhibition; area 3b = local spatiotemporal filters.
- Relevance: electrically activating a 3b patch bypasses the surround inhibition that shapes natural spatial acuity.
- Caveats: macaque, fingerpads only.

### [B] Rate + temporal multiplexing in S1 (Harvey et al., 2013) - DOI 10.1371/journal.pbio.1001558 / PMID 23667327
- Opened: EF id=23667327 (abstract)
- Key facts: vibratory amplitude encoded in S1 firing strength; frequency composition up to 800 Hz NOT in rates but in phase-locked responses of a subpopulation; spike timing shapes perception.
- Relevance: frequency/texture needs temporal patterning in cortex; ICMS pulse timing is the only lever.
- Caveats: macaque, single lab.

### [B] Texture in S1: high-dimensional population code (Lieber & Bensmaia, 2019) - DOI 10.1073/pnas.1818501116 / PMID 30718436
- Opened: EF id=30718436 (abstract)
- Key facts: texture identity in idiosyncratic responses across 3b/1/2 populations; continuum of fine vs coarse sensitivity tied to different afferent inputs; accounts for human texture perception.
- Relevance: a small number of electrodes cannot reproduce a high-dimensional idiosyncratic code.
- Caveats: macaque.

### [B] Speed-invariant texture in S1 (Lieber & Bensmaia, 2020) - DOI 10.1093/cercor/bhz305 / PMID 31813989
- Opened: EF id=31813989 (abstract)
- Key facts: cortical neurons have wider speed sensitivities than afferents; speed and texture more independent in cortex, explaining perceptual speed invariance.
- Relevance: encoder must decide whether to deliver afferent-like (speed-dependent) or cortex-like (speed-invariant) patterns.
- Caveats: macaque.

### [B] Precise temporal texture code in S1 (Long, Lieber & Bensmaia, 2022) - DOI 10.1038/s41467-022-28873-w / PMID 35288570
- Opened: EF id=35288570 (abstract)
- Key facts: texture-specific S1 spike patterns repeatable with millisecond precision; texture decodable from timing alone; rate+timing best; precision depends on submodality input and hierarchy; patterns dilate/contract with speed.
- Relevance: confirms (same lab) that the temporal code survives to cortex -> timing-precise ICMS is a necessary but unproven condition for texture.
- Caveats: macaque, same lab as Weber 2013.

### [B] Contact onset/offset transients dominate S1 (Callier, Suresh & Bensmaia, 2019) - DOI 10.1093/cercor/bhy337 / PMID 30668644
- Opened: EF id=30668644; PMC6917522 (full text, grepped)
- Key facts: Utah-array recordings, macaque. Onset transient on average >15x the sustained response (range 2.2-42.4, median 12.0; 28 skin locations, 4 arrays); offset transient >8x sustained (range 0.76-35.0, median 6.0). Latency ~20 ms after stimulus onset. During sustained contact activation is confined to a fraction of a mm2 around the hotzone electrode; recruitment during transients always dwarfs sustained. Palm cortex shows weaker sustained responses (fewer SA fibres). Behaviour matches neurometric performance of ONSET responses, underestimated by sustained.
- Relevance: the core biomimetic rule: large phasic onset/offset, small tonic hold; spatial spread larger during transients.
- Caveats: passive indentation, macaque.

## 5. ICMS biophysics and psychophysics

### [B] Sparse, distributed activation by microstimulation (Histed, Bonin & Reid, 2009) - DOI 10.1016/j.neuron.2009.07.016 / PMID 19709632
- Opened: EF id=19709632; PMC2874753 (full text, grepped)
- Key facts: 2-photon Ca imaging (mouse, cat, monkey). Near threshold (4-9 uA) activated cells lie hundreds of um from the tip, sparse, no strong bias toward the tip; more current fills in a sphere rather than extending it; moving the electrode 30 um (or 15 um) completely changes the activated set; blocking excitatory transmission had little effect => direct axonal activation in a volume tens of um in diameter. Cites Stoney et al. 1968 estimate: 10 uA -> 100 um radius, 100 uA -> 450 um radius.
- Relevance: ICMS activates a quasi-random sparse set via axons -> cannot address specific afferent-class-like neurons; percept quality depends on micro-position.
- Caveats: anaesthetized, calcium imaging temporal resolution; Stoney 1968 (PMID 5711137) has no abstract; its numbers are taken second-hand from Histed.

### [C] Stoney vs Histed reconciled by modelling (Kumaravelu et al., 2022) - DOI 10.1016/j.brs.2021.11.015 / PMID 34861412
- Opened: EF id=34861412 (abstract)
- Key facts: biophysical cortical-column model: at all amplitudes somatic activation is dominantly antidromic after axonal activation; no direct somatic/dendritic activation; AP-initiation volume grows with amplitude, somatic volume grows marginally, density within it rises.
- Relevance: axonal/antidromic recruitment is the mechanism an encoder works through.
- Caveats: computational model (C).

### [B] Monkey ICMS detection/discrimination (Kim et al., 2015) - DOI 10.1073/pnas.1509265112 / PMID 26504211
- Opened: EF id=26504211; PMC4679002 (full text, grepped)
- Key facts: macaque S1 (3b and 1) via chronic arrays. Wider pulses (50->400 us) lower detection threshold for 1-s 300-Hz trains; lowest current thresholds with long pulses and higher frequencies; thresholds rise as frequency drops below ~250 Hz. Amplitude discrimination 30-100 uA: JNDs roughly constant across standards (unlike Weber's law for natural stimuli); mean JNDs ~30 uA -> only ~2 discriminable amplitude steps between ~30 uA threshold and 100 uA. JNDs in 3b and area 1 indistinguishable. Cathodal-first thresholds ~10 uA lower than anodal-first.
- Relevance: single-electrode amplitude coding has very low information capacity -> need multi-electrode/population coding.
- Caveats: 2-3 monkeys; human JNDs differ (not covered here).

### [B] ICMS frequency shapes quality (Callier et al., 2020) - DOI 10.1073/pnas.1916453117 / PMID 31879342
- Opened: EF id=31879342 (abstract)
- Key facts: monkeys discriminate ICMS frequency 10-400 Hz consistently up to ~200 Hz; whether frequency changes quality (vs magnitude) is highly electrode dependent.
- Relevance: frequency is a second (quality) channel on some electrodes only.
- Caveats: macaque.

### [B] Long-term stability of ICMS sensitivity in monkeys (Callier et al., 2015) - DOI 10.1088/1741-2560/12/5/056010 / PMID 26291448
- Opened: EF id=26291448 (abstract)
- Key facts: detection performance stable over years, even on heavily stimulated electrodes.
- Relevance: percept stability.
- Caveats: detection only (not quality).

### [B] Biomimetic ICMS in monkeys: location, pressure, on/off (Tabot et al., 2013) - DOI 10.1073/pnas.1221113110 / PMID 24127595
- Opened: EF id=24127595 (abstract)
- Key facts: ICMS evokes percepts projected to a localized skin patch that track pressure; monkeys performed a tactile task equally well with native or prosthetic finger; proposes phasic ICMS at contact onset/offset mimicking S1 on/off responses.
- Relevance: origin of the onset/offset biomimetic scheme.
- Caveats: macaque; percept "location" inferred behaviourally.

## 6. Human ICMS: naturalness and stability

### [B] Human S1 ICMS (Flesher et al., 2016) - DOI 10.1126/scitranslmed.aaf8083 / PMID 27738096
- Opened: EF id=27738096 (abstract; full text not open-access)
- Key facts: 1 participant; hand percepts organized somatotopically; many naturalistic (pressure); low amplitudes; stable for months; amplitude grades intensity.
- Relevance: human baseline. Descriptor counts (incl. any warmth) UNVERIFIED (full text not opened).
- Caveats: n = 1.

### [B] Frequency perception in human S1 ICMS (Hughes et al., 2021) - DOI 10.7554/eLife.65128 / PMID 34313221
- Opened: EF id=34313221; PMC8376245 (full text, grepped)
- Key facts: 2 participants. Amplitude and train duration always raise intensity; frequency raises intensity on some electrodes and lowers it on others -> three electrode groups with distinct qualities (20 Hz: pressure, tapping, sparkle, touch; 100 Hz: buzzing, vibration, sharp on some groups; 300 Hz: less pressure). Neighbouring electrodes tend to share a group. Temperature (warm/cool) was among the descriptor options offered.
- Relevance: frequency-quality mapping is spatially organized -> an encoder needs per-electrode calibration, possibly related to underlying cortical response type.
- Caveats: n = 2.

### [B] 1500-day stimulation/recording stability in human S1 (Hughes et al., 2021 JNE) - DOI 10.1088/1741-2552/ac18ad / PMID 34320481
- Opened: EF id=34320481 (abstract)
- Key facts: detection thresholds decreased from median 31.5 uA at day 100 to 10.4 uA at day 1500 (largest change day 100-500); stimulated SIROF electrodes kept recording high-amplitude units more often than unstimulated platinum motor electrodes.
- Relevance: percept stability; sensitivity improved over time.
- Caveats: n = 1.

### [A] Stable, somatotopic projected fields over years (Greenspon et al., 2025) - DOI 10.1038/s41551-024-01299-z / PMID 39643730
- Opened: EF id=39643730; PMC12176618 (full text, grepped)
- Key facts: 3 participants, arrays in area 1; projected fields = focal hotspot with diffuse borders, somatotopic, stable over years (centroid drift r = -0.03 and 0.12, n.s., in 2 participants; slight increase r = 0.23 in the longest-implanted). Single electrodes typically evoke weak sensations; overlapping PFs from multiple electrodes produce more localizable, intense sensations.
- Relevance: location stability replicated across 3 people + monkey (Callier 2015) + Hughes 2021 -> graded A for "PF location is stable".
- Caveats: stability of quality/naturalness less studied than location.

### [B] Biomimetic ICMS feels more natural (Hobbs et al., 2025) - DOI 10.1088/1741-2552/adc2d4 / PMID 40106898
- Opened: EF id=40106898; PMC13571258 (full text, grepped)
- Key facts: 3 participants compared ICMS to residual-sensation mechanical indentation. Single-electrode amplitude-modulated (onset/offset) biomimetic ICMS judged more like indentation on 32% of electrodes; 4-electrode co-modulated amplitude+frequency pattern on 75% of electrode groups. Biomimetic trains needed less charge for matched intensity.
- Relevance: direct evidence that mimicking S1 onset/offset dynamics and spatial recruitment increases naturalness.
- Caveats: n = 3; forced-choice similarity, not absolute naturalness.

### [B] Edges and motion via patterned ICMS (Valle et al., 2025) - DOI 10.1126/science.adq5978 / PMID 39818881
- Opened: EF id=39818881 (abstract)
- Key facts: simultaneous multi-electrode ICMS with spatially patterned PFs evoked edges and arbitrary shapes; spatiotemporally sequenced ICMS evoked motion across the skin with controllable speed and direction.
- Relevance: spatial (3b-like) features are accessible via PF tiling.
- Caveats: participants with SCI; abstract only.

### [B] ICMS feedback halves grasp time (Flesher et al., 2021) - DOI 10.1126/science.abd0380 / PMID 34016775
- Opened: EF id=34016775 (abstract)
- Key facts: 1 participant; bidirectional BCI; ARAT-type trial time median 20.9 s -> 10.2 s with ICMS feedback, mostly less time spent grasping.
- Relevance: functional value of even non-natural contact/pressure feedback.
- Caveats: n = 1.

### [C] Restoring sensorimotor function via intracortical interfaces (Bensmaia & Miller, 2014 review) - DOI 10.1038/nrn3724 / PMID 24739786
- Opened: EF id=24739786 (abstract)
- Key facts: frames biomimetic vs adaptation-based (learned arbitrary mapping) approaches.
- Relevance: framing for encoder design choice.
- Caveats: review.
