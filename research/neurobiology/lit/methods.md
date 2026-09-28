# Methods literature: seizure-detection evaluation, leakage, baselines, CIs (role: methods-lit)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Compiled 2026-09-26 by methods-lit. Every entry was opened by me in this session. "Full text" = I read the relevant sections of the
full text; "abstract" = abstract only. Grades per HIVE.md: A = replicated, B = single peer-reviewed study, C = preprint/theory,
D = marketing. Numbers are quoted from the source; anything I could not confirm is marked UNVERIFIED.

---

## 1. CHB-MIT itself

### M1. Shoeb A, Guttag J. Application of Machine Learning to Epileptic Seizure Detection. ICML 2010 (Haifa). Grade B
- URL opened: https://icml.cc/Conferences/2010/papers/493.pdf (full text, 8 pages, via pdftotext). No DOI/PMID.
- Task: patient-specific onset detection (SVM, RBF kernel) on CHB-MIT.
- Features: filterbank energy (M = 2, 4 or 8 equal-bandwidth filters spanning 0.5-25 Hz) per channel on 2-s epochs, with
  W = 3 consecutive non-overlapping epochs stacked (6 s of context). Increasing W lowered false detections and raised latency.
- Training: seizure vectors from the first S seconds of K seizures plus non-seizure vectors from at least 24 h of non-seizure EEG.
- Data: 916 h of continuous scalp EEG at 256 Hz, 23 paediatric patients (Children's Hospital Boston) plus 1 adult (Beth Israel),
  173 test seizures. Data were cut into 1-h records.
- Protocol: **leave-one-record-out** cross-validation within each patient (median N_nonseizure-records = 33, median N_seizure-records = 5).
  Quote: leaving out epochs rather than hour-long records "leads to misleadingly good results by including in the training set feature
  vectors in close temporal proximity to those in the test data". This is the earliest CHB-MIT-specific statement of temporal leakage I found.
- Metrics (defined in §4.2): sensitivity = % of test seizures identified; "specificity" = false detections per 24 h;
  latency = delay from expert-marked EEG onset to detector declaration.
- Results: 96% of 173 test seizures detected; mean latency 4.6 s; 50% detected within 3 s, 71% within 5 s, 91% within 10 s;
  **median 2 false detections per 24 h** across 24 subjects; patient 13 had 20 false detections per 24 h; one patient-15 seizure
  had 55 s latency. With 1 training seizure: latency > 7 s and > 45% missed; with 3 training seizures: latency ~4 s and < 5% missed
  (curve from 5 randomly chosen patients).
- Caveats: leave-one-record-out trains on records recorded *after* the test record (non-causal; see M12). Event scoring rules
  (tolerances, merging) are not specified at SzCORE's level of detail. No CIs. Figures derived from a 5-patient subset.

### M2. Shoeb AH. Application of machine learning to epileptic seizure onset detection and treatment. PhD thesis, MIT, 2009. Grade B (thesis)
- URL opened: http://hdl.handle.net/1721.1/54669 (DSpace record, abstract only).
- Abstract: trained on >= 2 seizures, tested on **844 h** from **23** paediatric patients, detected **96% of 163** test seizures,
  median delay 3 s, median 2 false detections per 24 h.
- Caveat: the thesis numbers (844 h, 23 patients, 163 seizures) differ from the ICML paper (916 h, 24 patients, 173 seizures).
  The ICML version adds the adult patient. Cite the version whose numbers you use. PhysioNet asks users to cite this thesis.

### M3. Guttag J. CHB-MIT Scalp EEG Database, v1.0.0. PhysioNet, 2010. DOI 10.13026/C2K01R. Grade: dataset (primary source)
- URL opened: https://physionet.org/content/chbmit/1.0.0/ (full page).
- 22 subjects (5 male, ages 3-22; 17 female, ages 1.5-19) in **23 cases**; **chb21 is the same female subject as chb01, recorded 1.5 years later**.
  Case chb24 was added in December 2010 and is not in SUBJECT-INFO.
- 664 .edf files; RECORDS-WITH-SEIZURES lists **129** files with >= 1 seizure. 198 seizures in total ("182 seizures" in the original 23 cases).
- 256 Hz, 16-bit; mostly 23 EEG signals (24 or 26 in some); up to 5 dummy "-" channels; ECG in the last 36 chb04 files, VNS in the last 18 chb09 files.
- Files are usually 1 h (chb10: 2 h; chb04, 06, 07, 09, 23: 4 h); seizure files can be shorter. **Gaps between consecutive files**,
  usually <= 10 s "but occasionally there are much longer gaps". Surrogate dates preserve the time relationships within a case.
- License: Open Data Commons Attribution v1.0. Size 42.6 GB.
- Caveats: seizure counts differ between sources (PhysioNet 198; SzCORE Table 1: 198 seizures, 23 subjects, 982 h, 686 files; Pale 2023: 183 seizures,
  24 subjects, 982.9 h). The harness must count from the annotation files, not from the literature.

### M4. Goldberger AL et al. PhysioBank, PhysioToolkit, and PhysioNet. Circulation 2000;101(23):e215. DOI 10.1161/01.cir.101.23.e215, PMID 10851218. Grade B (resource paper)
- Opened: Europe PMC abstract.
- Describes PhysioBank (archive), PhysioToolkit (open-source software, including "the quantitative evaluation and comparison of analysis methods")
  and PhysioNet (free web access). It is the standard citation for any PhysioNet dataset.
- Caveat: it contains no CHB-MIT-specific content, because CHB-MIT dates from 2010.

---

## 2. Evaluation standards and scoring

### M5. Dan J, Pale U, Amirshahi A, ... Beniczky S, Atienza D, Ryvlin P. SzCORE: Seizure Community Open-Source Research Evaluation framework... Epilepsia 2025 (online 2024). DOI 10.1111/epi.18113, PMID 39292446, PMCID PMC12489712. Grade B (consensus framework; preprint arXiv 2402.13005)
- Opened: full text (Europe PMC XML), sections 2-4.
- **Personalized models**: time-series cross-validation (TSCV); train only on data acquired before the test data. In the benchmark,
  training starts with >= 5 h and >= 1 seizure, then the next hour is tested, 1 h is added to training, and so on. A subject qualifies
  only with >= 3 seizures and >= 1 h 30 min of data. CHB-MIT, Siena and SeizeIT qualify; TUH does not.
- **Subject-independent models**: leave-one-subject-out or K-fold over subjects, with subject independence guaranteed. Also a cross-dataset scenario.
- **Sample-based scoring** at 1 Hz. A label sample counts as seizure if the overlap exceeds 50%.
- **Event-based scoring**: any overlap is a TP; a hypothesis event that does not overlap a reference is an FP. Defaults:
  minimum overlap = any; **pre-ictal tolerance 30 s; post-ictal tolerance 60 s; merge events separated by < 90 s; split events > 5 min**.
- Metrics: sensitivity TP/(TP+FN); precision TP/(TP+FP); F1; **false alarms per day**. The framework explicitly **avoids TN-based
  metrics (specificity, accuracy)** because non-seizure events are ill-defined and, sample-wise, they give "extremely high" scores.
- Aggregation: per-subject scores, then the average over subjects. A model card and a reproducibility checklist are recommended (Fig. S4/S5).
- CHB-MIT exception: it provides only bipolar channels, so it cannot be converted to the unipolar 19-channel common-average montage and is analysed
  in its source bipolar montage.
- Caveat: the parameters are expert consensus, not empirically optimised. I did not open the supplementary benchmark results.

### M6. timescoring library (esl-epfl/epilepsy_performance_metrics), PyPI `timescoring` v0.0.7. Grade: software (C)
- Opened: README, `src/timescoring/scoring.py` source, LICENSE (raw GitHub, 2026-09-26). The repo was renamed (GitHub API "Moved Permanently").
- **License: MIT** ("Copyright (c) 2023 Embedded Systems Lab (ESL) - EPFL"). This resolves the UNVERIFIED licence item in NB2 RAPPORT.
  PyPI metadata carries no licence field.
- Defaults: `toleranceStart=30`, `toleranceEnd=60`, `minOverlap=0`, `maxEventDuration=300`, `minDurationBetweenEvents=90` (s).
  Sample scoring defaults to 1 Hz.
- Algorithm as coded:
  1. Resample both annotations to 10 Hz.
  2. Merge events < 90 s apart, in **both the reference and the hypothesis**.
  3. Split events longer than 300 s.
  4. Extend each reference event by -30/+60 s.
  5. TP when the relative overlap of the hypothesis with an extended reference is > minOverlap + 1e-6.
  6. FP = a hypothesis event that touches no TP-extended reference.
- F1 = 2TP/(2TP+FP+FN). `fpRate = FP / (numSamples/fs/3600/24)`, i.e. per 24 h of **total scored duration, including seizure time**.
  Sensitivity is NaN when there is no reference event; precision is NaN when there is no hypothesis event.
- Caveats: hypothesis merging means alarm bursts < 90 s apart count as one FP. Because splitting happens after merging, a merged
  run of alarms longer than 300 s is split into several events, which can each count as an FP. Pin the version, because v0.0.x
  may change behaviour.

### M7. Ziyabari S, Shah V, Golmohammadi M, Obeid I, Picone J. Objective evaluation metrics for automatic classification of EEG events. arXiv 1712.10107 (v3, 2019; J Neural Eng resubmission). Grade C (preprint)
- Opened: full text (arXiv PDF).
- Defines 5 metrics: **ATWV**, **DPALIGN**, **EPOCH** (sample the annotations at a fixed epoch; they use 0.25 s), **OVLP** (any-overlap) and
  **TAES** (time-aligned event scoring), plus inter-rater agreement (IRA, Cohen's kappa over EPOCH).
- OVLP: TP when a hypothesis overlaps the reference; FP when it overlaps none; duration is ignored; several hypothesis events on one reference
  "are not typically counted as FAs". Its one parameter is a guard band, set to 0 (some overlap required). OVLP is "a very permissive way of scoring,
  resulting in artificially high sensitivities".
- EPOCH "is inherently biased to weigh long seizure events more heavily".
- TAES: fractional TP/FN per event by overlap; FP <= 1 per event; worked example gives 0.71 TP, 0.29 FN, 0.14 FP.
- Clinicians: "a low false alarm rate, typically measured in units of the number of errors per 24 hours, is the single most important criterion".
  Systems must be compared at a comparable FA rate (DET curves), not at single operating points.
- Caveat: Table 2 numbers are garbled by PDF extraction, so I do not quote them.

### M8. Shah V, Obeid I, Picone J, Ekladious G, Iskander R, Roy Y. Validation of Temporal Scoring Metrics for Automatic Seizure Detection. IEEE SPMB 2020. DOI 10.1109/spmb50085.2020.9353631. Grade B (conference)
- Opened: full text (author docx at https://isip.piconepress.com/publications/conference_proceedings/2020/ieee_spmb/scoring/paper_v13.docx)
  and the abstract via OpenAlex.
- Neureka 2020 challenge: 19 teams, 16 scorable, TUSZ v1.5.1 (train 592 patients / dev 50; no patient overlap between sets), NEDC scoring v3.3.3.
  Ranking score P = sens - 2.5*fa - 7.5*nc/19 (TAES). Clinicians want "less than 1 per 24 hours".
- **The same system and data give very different numbers under different metrics**. For the baseline "nedc" system, eval set:
  - OVLP: sensitivity 42.96%, 11.45 FP/24 h.
  - TAES: 35.55%, 17.23 FP/24 h.
  - EPCH: 51.58%, **1,301.09 FP/24 h**.
  - DPAL: 42.96%, 11.77 FP/24 h.
- Caveat: TUSZ is owner-gated (not used here); the numbers are for illustration only.

### M9. Samanos C, Dan J, Atienza D. Benchmark of EEG-based seizure detection algorithms with SzCORE. IEEE EMBC 2025. DOI 10.1109/embc58623.2025.11254038, PMID 41336388. Grade B (conference)
- Opened: abstract (Europe PMC).
- 19 papers on patient-independent detection with public data matched the criteria; 3 were re-implemented. There were "notable discrepancies between reported
  performances and those obtained under standardized evaluation". Algorithms "tended to demonstrate high sensitivity (over 90%)" but "low
  precision (10-40%)". Clinical-relevance line: "high sensitivity (~70%) at the cost of a low precision (~14%)". Variability across datasets is "probably
  partially explained by the hourly rate of seizures".
- Caveat: the abstract gives two sensitivity figures (>90% and ~70%). The per-dataset (CHB-MIT) breakdown is UNVERIFIED because only the abstract was read.

### M10. Dan J, Shahbazinia A, Kechris C, Atienza D. Quantifying the Generalization Gap in Seizure Detection: A Large-Scale Empirical Benchmark via the SzCORE Challenge. arXiv 2505.18191v2; the PDF header says ICML 2026, PMLR 306. Grade B/C
- Opened: full text (arXiv v2 PDF).
- 28 algorithms were scored on a private held-out set: Filadelfia (Dianalund), 65 subjects, 398 seizures, 4,360 h, 18-98 h per subject, consensus labels from 3 neurophysiologists.
- Scoring used timescoring with the SzCORE defaults. Per-subject scores were averaged; **undefined precision (no detections) was set to 0**.
- Statistics: Friedman test, then Wilcoxon with Holm correction, Nemenyi test and Cliff's delta.
- Best result: **F1 32%, sensitivity 37%, precision 29%, 1.34 FP/day**. Top-5: sensitivity 30-58%, precision 19-29%, 1.34-14 FP/day.
  15/65 subjects (23%) had F1 = 0 for all top-5 algorithms. Hard seizures were shorter (median 48 s vs 118 s). Self-reported F1 was far above held-out F1 (Fig. 6).
- **CHB-MIT could not be scored** for the open-source submissions, because its bipolar montage does not fit the SzCORE input format. Datasets curated to
  contain more seizure time (TUSZ, Siena subsets) gave higher F1.

---

## 3. Leakage

### M11. Brookshire G et al. Data leakage in deep learning studies of translational EEG. Front Neurosci 2024;18:1373515. DOI 10.3389/fnins.2024.1373515, PMID 38765672, PMCID PMC11099244. Grade B
- Opened: full text (Europe PMC XML).
- Seizure experiment on **Siena** (not CHB-MIT): 47 seizures in ~128 h, **balanced** by taking non-seizure data from the start of each recording.
  - Segment-based holdout: accuracy **79.1% (78.8-79.4%)**.
  - Subject-based holdout: **65.1% (61.3-69.1%)**.
  - Wilcoxon T = 0.0, p = 0.0001.
- Alzheimer experiment: 99.8% segment-based vs 53.0% (43.1-64.8%) subject-based, i.e. chance.
- Literature survey: of 63 translational DNN-EEG papers, only **17 (27.0%)** unambiguously avoided subject leakage.
- Caveats: the classification is window-level, not event-level. The balanced sampling inflates accuracy (see M12).
  The CNN architectures were reused, with no model selection.

### M12. Pale U, Teijeiro T, Atienza D. Importance of methodological choices in data manipulation for validating epileptic seizure detection models. arXiv 2302.10672 (2023). Grade C (preprint; I believe it appeared at EMBC 2023, UNVERIFIED)
- Opened: full text. Random forest (100 trees) on **CHB-MIT**: 982.9 h, 183 seizures, 24 subjects, **0.32% ictal**, 7.6 +/- 5.8 seizures per subject,
  seizure length 58.6 +/- 65.0 s, 18 common bipolar channels. Post-processing used a 5-s moving average and merged seizures < 30 s apart.
- **Leave-one-seizure-out beat TSCV** by **3-7% event-level F1** (personalized). The authors call it "not a recommendation to use L1O"; it shows that
  "training on future data leads to overestimated performance".
- Balanced subsets gave event sensitivity ~100%. The full continuous data gave 80-95%. FA/day from subsets is linearly extrapolated and
  "data subsets should not be used to estimate the false alarm rate".
- Generalized (leave-one-subject-out) models performed worse on average than personalized models. Numbers are shown in figures only (not quoted).
- Recommends appending all fold predictions in time before scoring, reporting window size and step, and not shuffling.
- Caveat: the conclusion's "macro-averaging rather than micro-averaging" reads inconsistently with the appending advice in §5. The prereg must pick one explicitly.

### M13. Kapoor S, Narayanan A. Leakage and the reproducibility crisis in machine-learning-based science. Patterns 2023;4(9):100804. DOI 10.1016/j.patter.2023.100804, PMID 37720327, PMCID PMC10499856. Grade B (review + one case study)
- Opened: full text (Europe PMC XML).
- Leakage was found in **17 fields, affecting 294 papers**. Taxonomy of 8 types:
  - L1.1 no test set
  - **L1.2 pre-processing on train and test** (e.g. imputation or oversampling before the split)
  - **L1.3 feature selection on train and test**
  - L1.4 duplicates
  - L2 illegitimate features
  - **L3.1 temporal leakage** ("the test set should not contain any data from a date before the training set")
  - **L3.2 non-independence between train and test**
  - L3.3 sampling bias
- Proposes "model info sheets". In the civil-war case, once the errors were fixed, complex ML did not beat logistic regression.
- Caveat: it is not EEG-specific. Its value is as a checklist.

### M14. Shafiezadeh S, Duma GM, Mento G, et al. Methodological Issues in Evaluating ML Models for EEG Seizure Prediction: Good Cross-Validation Accuracy Does Not Guarantee Generalization to New Patients. Appl Sci 2023;13(7):4262. DOI 10.3390/app13074262. Grade B
- Opened: abstract only (via OpenAlex; mdpi.com returned 403).
- With XGBoost, randomized CV vs **leave-one-patient-out** dropped accuracy "from about 80% to 50%" on two datasets.
- Caveats: the task is *prediction*, not detection. The two datasets are UNVERIFIED (I believe one is CHB-MIT but did not confirm it). Only the first three authors were checked (Crossref).

### M15. Rukhsar S, Tiwari AK. Lightweight Convolution Transformer for Cross-patient Seizure Detection in Multi-channel EEG Signals. arXiv 2305.04325 (2023). Grade C. Included as an example of the reporting style the harness guards against, not as a benchmark
- Opened: abstract.
- Reports cross-patient **accuracy 96.31% and F1 96.32%** on CHB-MIT at 0.5-s segments.
- Caveat: segment-level accuracy/F1 near 96% implies a balanced segment set. It is not comparable with event-level F1 on continuous data
  (M10: 32% held-out). Whether its split was subject-disjoint is UNVERIFIED from the abstract. Do NOT cite it as a cross-patient CHB-MIT benchmark.

### M16. Roberts DR et al. Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. Ecography 2017 (online 2016). DOI 10.1111/ecog.02881. Grade B (review + simulations)
- Opened: abstract (OpenAlex).
- Random CV that ignores dependence gives "serious underestimation of predictive error". Block CV "is nearly universally more appropriate", but blocking can
  force extrapolation. This is the general justification for blocked, buffered splits in time.

---

## 4. Cross-patient vs patient-specific on CHB-MIT (synthesis; no new source)
- Patient-specific, event-level, continuous data: **~96% sensitivity, median 2 FD/24 h, median 3 s latency** (M1/M2). The protocol was leave-one-record-out,
  which is non-causal and inflates results relative to TSCV (by 3-7% event-F1 in M12).
- Cross-patient, event-level, **on CHB-MIT with SzCORE scoring: not found**. M10 could not score CHB-MIT at all (montage). Proxies:
  - window-level accuracy drop of 14 pp from segment to subject holdout on Siena (M11);
  - ~80% to ~50% accuracy under leave-one-patient-out for prediction (M14);
  - patient-independent standardized re-implementations at sensitivity ~70% / precision ~14% (M9);
  - held-out F1 of 32% on an independent EMU set (M10).
- **GAP**: a peer-reviewed, event-scored, subject-disjoint CHB-MIT number is missing. Our F2/F1 runs would produce one. Do not put a "typical"
  cross-patient CHB-MIT sensitivity into a prereg threshold without a source.

---

## 5. Simple validated baseline features

### M17. Esteller R, Echauz J, Tcheng T, Litt B, Pless B. Line length: an efficient feature for seizure onset detection. Proc 23rd IEEE EMBS 2001, pp. 1707-1710. DOI 10.1109/iembs.2001.1020545. Grade B
- Opened: abstract (OpenAlex) and the Crossref record.
- Tested on **intracranial** EEG: 1,215 h, 10 patients, 111 seizures (23 subclinical).
  Average delay **4.1 s**, **0.051 FP/h**, and 1 false negative (a subclinical seizure).
- Line length as usually defined: L = sum_k |x[k] - x[k-1]| over a window. The exact normalisation in the original is UNVERIFIED, because I did not read the full text.
- Caveat: iEEG, not scalp EEG. Onset-detector parameters were probably patient-tuned (UNVERIFIED).
- Related (abstract opened): Esteller 2004 EMBS (DOI 10.1109/iembs.2004.1404304) describes line length as "sensitive to variations in signal amplitude and frequency"
  and related to Katz fractal dimension and Teager energy.

### M18. Logesparan L, Rodriguez-Villegas E, Casson AJ. The impact of signal normalization on seizure detection using line length features. Med Biol Eng Comput 2015. DOI 10.1007/s11517-015-1303-x, PMID 25980503. Grade B
- Opened: abstract.
- Of 5 normalisation methods, AUC differed by **up to 52%**, and by up to 22% depending on raw-EEG vs feature normalisation. Best: **median decaying memory** (causal).
- Relevance: normalisation is a large, hidden degree of freedom. It must be fitted on training data only, or be causal, and it must be locked in the prereg.

### (Band power) Shoeb's filterbank energy (M1) is the validated band-power baseline on CHB-MIT: 0.5-25 Hz, 2-s epochs, 3-epoch stacking.
The NB2 F1 prereg uses 1-4/4-8/8-13/13-30/30-70 Hz band power + line length on 4-s windows. That band set is a plan choice, not a sourced one.
Note that Shoeb's detector used 0.5-25 Hz only.

---

## 6. CIs with few patients, and controls

### M19. Saravanan V, Berman GJ, Sober SJ. Application of the hierarchical bootstrap to multi-level data in neuroscience. NBDT 2020; PMID 33644783; preprint DOI 10.1101/819334. Grade B
- Opened: abstract (OpenAlex, preprint).
- Traditional tests on nested data gave "a false positive rate of over 45%" at nominal 5%. A hierarchical bootstrap applied level by level keeps the Type I error in bound
  and has more power than summarising.

### M20. Ren S et al. (full author list not checked). Nonparametric bootstrapping for hierarchical data. J Appl Stat 2010. DOI 10.1080/02664760903046102. Grade B
- Opened: abstract. Resample **the highest level (patients) with replacement**, and lower levels without replacement within each selected unit.
  This beats resampling at lower levels.

### M21. Field CA, Welsh AH. Bootstrapping clustered data. JRSS B 2007. DOI 10.1111/j.1467-9868.2007.00593.x. Grade B
- Opened: abstract. The **cluster bootstrap** gives consistent variance estimates under both the transformation and the random-effect model;
  the residual bootstrap only under the transformation model.

### M22. Cameron AC, Gelbach JB, Miller DL. Bootstrap-Based Improvements for Inference with Clustered Errors. Rev Econ Stat 2008;90(3):414. DOI 10.1162/rest.90.3.414. Grade A/B (widely replicated in econometrics; graded B here)
- Opened: abstract. Standard cluster-robust tests "can over-reject ... with few (five to thirty) clusters". A cluster bootstrap-t reduced 10% rejection to the nominal 5%.
- **Implication: with 2-4 patients (cycle 1), no patient-level bootstrap CI is trustworthy**. Report per-patient results and treat cross-patient CIs as descriptive only.

### M23. Clopper CJ, Pearson ES. The use of confidence or fiducial limits illustrated in the case of the binomial. Biometrika 1934;26(4):404. DOI 10.1093/biomet/26.4.404. Grade A (classical)
- Opened: metadata only (OpenAlex; no abstract). This is the exact binomial CI, already used in NB2 for "fraction of patients over chance".
  Within-patient seizures are not independent, so the interval is optimistic.

### M24. Ojala M, Garriga GC. Permutation Tests for Studying Classifier Performance. JMLR 2010;11. URL https://www.jmlr.org/papers/v11/ojala10a.html. Grade B
- Opened: abstract. Test 1 permutes labels to get the null for "classifier has found real class structure". Test 2 permutes features within class.
  This is the basis for the label-shuffle negative control. For time series, the permutation must respect dependence (a design choice, see harness spec).

### M25. Saito T, Rehmsmeier M. The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets. PLoS One 2015. DOI 10.1371/journal.pone.0118432. Grade B
- Opened: abstract. ROC plots on imbalanced data can be "deceptive" through misinterpreting specificity; PR plots reflect the fraction of true positives among
  positive predictions. CHB-MIT is 0.32% ictal (M12), so AUPRC must accompany AUROC, and the AUPRC chance level equals prevalence.

---

## 7. Reporting / provenance

### M26. Collins GS et al. TRIPOD+AI statement. BMJ 2024. DOI 10.1136/bmj-2023-078378. Grade A (consensus guideline)
- Opened: abstract. A 27-item checklist for prediction-model studies (regression or ML) that supersedes TRIPOD 2015. Use it as the reporting checklist in the evaluation card.

### M27. Mitchell M et al. Model Cards for Model Reporting. arXiv 1810.03993 (FAT* 2019). Grade C/B
- Opened: abstract. Model cards document intended use, evaluation conditions and disaggregated performance.
  SzCORE (M5) cites the model-card format for its seizure-detector card.

---

## Not found / not opened (do not cite until opened)
- The SzCORE Epilepsia supplementary benchmark tables (3 algorithms, including on CHB-MIT).
- The Esteller 2001 full text (exact line-length formula).
- The full text of M14, and the identity of its datasets.
- A peer-reviewed event-scored cross-patient CHB-MIT result (see §4 GAP).
