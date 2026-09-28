# Evaluation card: N2-chbmit-433d818f305b

**RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance and clinical validation (IRB/ethics approval).**

**Verdict: not verifiable: code (harness not validated: N1 b failed)**

N2 counts only if N1 PASSES (all parts a-e). Parts known in this run: (a) PASS, (b) FAIL.

## Intended use / task
seizure DETECTION, patient-specific causal split (S2 variant, N2 §1); CHB-MIT bipolar, 22 unique channels of the 23-channel double-banana montage (duplicate T8-P8 dropped)

## Data

- dataset: CHB-MIT Scalp EEG Database v1.0.0, DOI 10.13026/C2K01R, ODC-By 1.0
- subjects: chb01, chb03, chb10 (chb01/chb21 same patient; chb21 not used)
- hours_scored_test: {'chb01': 3.6458333333333335, 'chb03': 8.0, 'chb10': 8.009444444444444}
- test_seizures_N_ref: {'chb01': 4, 'chb03': 4, 'chb10': 4}
- exclusions: none within the 29-file subset (see notes\data_subset.md for subset selection)

## Split

- scheme: causal: train through the file with the 3rd seizure; test = later files
- buffer B = 10 s
- split hash: `433d818f305ba2095ef854b1f7f8b594895ad070f5fc28584a5507bdc7d9f1e2` (prereg literal matched: True)
- split computed from manifest + per-file seizure counts before feature extraction (S7)

| subject | train files | test files |
|---|---|---|
| chb01 | chb01_01.edf, chb01_02.edf, chb01_03.edf, chb01_04.edf, chb01_05.edf, chb01_06.edf, chb01_15.edf | chb01_16.edf, chb01_18.edf, chb01_21.edf, chb01_26.edf |
| chb03 | chb03_01.edf, chb03_02.edf, chb03_03.edf | chb03_04.edf, chb03_05.edf, chb03_06.edf, chb03_07.edf, chb03_08.edf, chb03_34.edf, chb03_35.edf, chb03_36.edf |
| chb10 | chb10_12.edf, chb10_20.edf, chb10_27.edf | chb10_30.edf, chb10_31.edf, chb10_38.edf, chb10_89.edf |

## Model

- features: 132 = 22 ch x [log10 LL, log10 BP 1-4, 4-8, 8-13, 13-30, 30-55 Hz], 2-s windows, 1-s step
- normaliser: z-score fitted on training windows only (F1 guard)
- classifier: L2 logistic regression C=1, balanced weights, scipy L-BFGS-B gtol 1e-6 maxiter 1000
- postprocessing: causal 4-of-5, no minimum duration; timescoring merge 90 s / split 300 s
- threshold: tau* = smallest grid tau (0.05..0.99) with inner-LOFO train FA <= 12/24h
- config_sha256: b6775e9aad8958cfce6cbfe805674c55fd13b1c8969a8320b681edb451bd1e4f

## Metrics (per subject, summed over test files)

| subject | verdict | TP/N_ref | sens (CP 95%) | FP | FA/24h (Garwood 95%) | precision | F1 | median latency s | sample F1 | AUROC (file-bootstrap 95%) | AUPRC (prevalence) | tau* | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chb01 | INCONCLUSIVE | 4/4 | 1.00 [0.398, 1.000] | 5 | 32.9 [10.7, 76.8] | 0.44 | 0.62 | 3.0 | 0.85 | 0.984 [0.979, 0.991] | 0.748 (0.0252) | 0.05 | CI uninformative (N_ref = 4); FA on peri-ictal data only |
| chb03 | INCONCLUSIVE | 4/4 | 1.00 [0.398, 1.000] | 9 | 27.0 [12.3, 51.3] | 0.31 | 0.47 | 2.5 | 0.67 | 0.989 [0.977, 1.000] | 0.841 (0.0074) | 0.05 | CI uninformative (N_ref = 4) |
| chb10 | PASS | 4/4 | 1.00 [0.398, 1.000] | 0 | 0.0 [0.0, 11.1] | 1.00 | 1.00 | 2.0 | 0.96 | 0.975 [0.953, 0.998] | 0.925 (0.0095) | 0.06 | CI uninformative (N_ref = 4); FA on peri-ictal data only |

Cross-subject means (DESCRIPTIVE, 3 clusters; CI not valid inference): {'DESCRIPTIVE_mean_window_auroc': 0.9824975645247184, 'DESCRIPTIVE_mean_sensitivity': 1.0, 'note': '3 clusters; no across-subject CI is valid inference (CI2)'}

## Controls

- **N1a_positive_leak**: {  "ceiling_clause_used": true,  "mean_D": 0.013127631461017067,  "mean_E": 0.20614174341500516,  "mean_honest_auroc": 0.9824975645247184,  "n_subjects_D_positive": 3,  "per_subject": {   "chb01": {    "C2a_converged": true,    "C2a_n_test": 13004,    "C2a_n_train": 25310,    "C2b_minus_honest": 0.0015693907390827988,    "C2b_norm_leak_auroc": 0.9850933863077508,    "D": 0.01341639074081713,    "E": 0.1857011937127482,    "honest_auroc": 0.983523995568668,    "leak_auroc_C2a": 0.9969403863094851,    "p_train": 0.657   },   "chb03": {    "C2a_converged": true,    "C2a_n_test": 28682,    "C2a_n_train": 10907,    "C2b_minus_honest": 0.0001105800335371443,    "C2b_norm_leak_auroc": 0.9892555818160212,    "D": 0.010226198328543434,    "E": 0.05792722176202821,    "honest_auroc": 0.9891450017824841,    "leak_auroc_C2a": 0.9993712001110275,    "p_train": 0.273   },   "chb10": {    "C2a_converged": true,    "C2a_n_test": 28711,    "C2a_n_train": 21746,    "C2b_minus_honest": -0.0003311928934368602,    "C2b_norm_leak_auroc": 0.974492503329566,    "D": 0.01574030531369064,    "E": 0.37479681477023913,    "honest_auroc": 0.9748236962230029,    "leak_auroc_C2a": 0.9905640015366936,    "p_train": 0.429   }  },  "prediction": "honest mean 0.93, leaky 0.99, mean D +0.06, P(PASS)=0.75",  "verdict": "PASS" }
- **N1b_negative**: {  "C3_random_alarm": {   "crit3_f1_le_0.05": false,   "draws": 1000,   "mean_pooled_f1": 0.08124193597171774,   "mean_pooled_tp": 1.558,   "p95_pooled_f1": 0.16405405405405235  },  "NC1_iid_permutation": {   "crit1_auroc": true,   "crit2_sensitivity_vs_null": false,   "grand_mean_auroc": 0.4544826547066234,   "per_subject": {    "chb01": [     {      "auroc": 0.4474211584295699,      "converged": true,      "fp": 9,      "n_ref": 4,      "tau": 0.88,      "tp": 1     },     {      "auroc": 0.5401368610767948,      "converged": true,      "fp": 10,      "n_ref": 4,      "tau": 0.94,      "tp": 1     },     {      "auroc": 0.16720341845616737,      "converged": true,      "fp": 5,      "n_ref": 4,      "tau": 0.94,      "tp": 0     },     {      "auroc": 0.434660528311157,      "converged": true,      "fp": 7,      "n_ref": 4,      "tau": 0.89,      "tp": 1     },     {      "auroc": 0.7651013702642501,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.14196915547219907,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.93,      "tp": 0     },     {      "auroc": 0.27781097864882165,      "converged": true,      "fp": 2,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.29685129762914286,      "converged": true,      "fp": 7,      "n_ref": 4,      "tau": 0.93,      "tp": 0     },     {      "auroc": 0.6082678829996055,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.9,      "tp": 0     },     {      "auroc": 0.5453460383749578,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.99,      "tp": 0     }    ],    "chb03": [     {      "auroc": 0.6147234838982267,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.6348452539709785,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.27995150983006983,      "converged": true,      "fp": 65,      "n_ref": 4,      "tau": 0.05,      "tp": 3     },     {      "auroc": 0.4098906412981766,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.1927484254723583,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.4693983785996277,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.5529694865125369,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.35491288934074494,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.33770399540515206,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.6180243804217226,      "converged": true,      "fp": 90,      "n_ref": 4,      "tau": 0.05,      "tp": 4     }    ],    "chb10": [     {      "auroc": 0.471998230901477,      "converged": true,      "fp": 92,      "n_ref": 4,      "tau": 0.15,      "tp": 4     },     {      "auroc": 0.6158243246172651,      "converged": true,      "fp": 6,      "n_ref": 4,      "tau": 0.9,      "tp": 1     },     {      "auroc": 0.5711788299244965,      "converged": true,      "fp": 92,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.16186315114773986,      "converged": true,      "fp": 92,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.5188085367726086,      "converged": true,      "fp": 92,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.6738924951972541,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.9,      "tp": 2     },     {      "auroc": 0.2678339741056413,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.94,      "tp": 0     },     {      "auroc": 0.3177378935336704,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.86,      "tp": 0     },     {      "auroc": 0.782780817133165,      "converged": true,      "fp": 92,      "n_ref": 4,      "tau": 0.05,      "tp": 4     },     {      "auroc": 0.5626242534531221,      "converged": true,      "fp": 21,      "n_ref": 4,      "tau": 0.79,      "tp": 2     }    ]   },   "pooled_fp": 1404,   "pooled_nref": 120,   "pooled_sensitivity": 0.5583333333333333,   "pooled_tp": 67,   "replicates": 10,   "shift_null_sensitivity_mean": 0.5136583333333333,   "shift_null_tp_mean": 61.639,   "shift_null_tp_p99": 65.0,   "subject_mean_auroc": {    "chb01": 0.42247686896626657,    "chb03": 0.4465168444749594,    "chb10": 0.49445425067864407   }  },  "NC2_circular_shift": {   "crit1_auroc": false,   "crit2_sensitivity_vs_null": false,   "grand_mean_auroc": 0.352709048980686,   "per_subject": {    "chb01": [     {      "auroc": 0.08884135783951302,      "converged": true,      "fp": 5,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.1038027726532955,      "converged": true,      "fp": 7,      "n_ref": 4,      "tau": 0.9,      "tp": 0     },     {      "auroc": 0.16378614334745092,      "converged": true,      "fp": 9,      "n_ref": 4,      "tau": 0.99,      "tp": 1     },     {      "auroc": 0.06661643230526114,      "converged": true,      "fp": 12,      "n_ref": 4,      "tau": 0.8,      "tp": 0     },     {      "auroc": 0.1796265020113429,      "converged": true,      "fp": 7,      "n_ref": 4,      "tau": 0.94,      "tp": 0     },     {      "auroc": 0.17812490403898437,      "converged": true,      "fp": 2,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.14802019137874425,      "converged": true,      "fp": 5,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.04761981249512813,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.1053792497443008,      "converged": true,      "fp": 20,      "n_ref": 4,      "tau": 0.85,      "tp": 2     },     {      "auroc": 0.0789395982983307,      "converged": true,      "fp": 20,      "n_ref": 4,      "tau": 0.74,      "tp": 1     }    ],    "chb03": [     {      "auroc": 0.5290137251277447,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.97,      "tp": 0     },     {      "auroc": 0.5614813433328492,      "converged": true,      "fp": 14,      "n_ref": 4,      "tau": 0.68,      "tp": 1     },     {      "auroc": 0.5456891941851407,      "converged": true,      "fp": 30,      "n_ref": 4,      "tau": 0.98,      "tp": 2     },     {      "auroc": 0.2712829429473045,      "converged": true,      "fp": 12,      "n_ref": 4,      "tau": 0.99,      "tp": 2     },     {      "auroc": 0.3985545374123612,      "converged": true,      "fp": 3,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.5879162430516128,      "converged": true,      "fp": 4,      "n_ref": 4,      "tau": 0.92,      "tp": 1     },     {      "auroc": 0.8914151933665183,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.99,      "tp": 1     },     {      "auroc": 0.7739168108058149,      "converged": true,      "fp": 7,      "n_ref": 4,      "tau": 0.99,      "tp": 3     },     {      "auroc": 0.6932927433090827,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.2944648916645761,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.99,      "tp": 0     }    ],    "chb10": [     {      "auroc": 0.4467938360153929,      "converged": true,      "fp": 0,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.6750728348585266,      "converged": true,      "fp": 2,      "n_ref": 4,      "tau": 0.99,      "tp": 2     },     {      "auroc": 0.40078457569790693,      "converged": true,      "fp": 15,      "n_ref": 4,      "tau": 0.75,      "tp": 0     },     {      "auroc": 0.2091089333446724,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.19552399602825069,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.99,      "tp": 0     },     {      "auroc": 0.3748948347120424,      "converged": true,      "fp": 8,      "n_ref": 4,      "tau": 0.94,      "tp": 0     },     {      "auroc": 0.1611574101331429,      "converged": true,      "fp": 2,      "n_ref": 4,      "tau": 0.96,      "tp": 0     },     {      "auroc": 0.22520642155057535,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.99,      "tp": 1     },     {      "auroc": 0.5989331022422734,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.99,      "tp": 3     },     {      "auroc": 0.5860109355224389,      "converged": true,      "fp": 1,      "n_ref": 4,      "tau": 0.99,      "tp": 0     }    ]   },   "pooled_fp": 192,   "pooled_nref": 120,   "pooled_sensitivity": 0.16666666666666666,   "pooled_tp": 20,   "replicates": 10,   "shift_null_sensitivity_mean": 0.08209166666666667,   "shift_null_tp_mean": 9.851,   "shift_null_tp_p99": 15.009999999999991,   "subject_mean_auroc": {    "chb01": 0.11607569641123516,    "chb03": 0.5547027625203006,    "chb10": 0.38734868801052225   }  },  "prediction": "NC1/NC2 grand mean 0.50, null sensitivity ~0.04 (<= p99), random-alarm F1 ~0.01, P(PASS)=0.85",  "verdict": "FAIL" }
- **S-b_future_leak**: {  "leak_demonstrated": true,  "mean_dAUROC_future_minus_causal": 0.005977370980999486,  "mean_dF1_future_minus_causal": 0.14709995886466476,  "per_subject": {   "chb01": {    "auroc_causal": 0.983523995568668,    "auroc_future": 0.9979092899711586,    "f1_causal": 0.6153846153846154,    "f1_future": 0.7272727272727273,    "fp": 3,    "n_ref": 4,    "taus": [     0.24,     0.15,     0.05,     0.11    ],    "tp": 4   },   "chb03": {    "auroc_causal": 0.9891450017824841,    "auroc_future": 0.9949720744154112,    "f1_causal": 0.47058823529411764,    "f1_future": 1.0,    "fp": 0,    "n_ref": 4,    "taus": [     0.05,     0.05,     0.05,     0.05,     0.05,     0.05,     0.05,     0.05    ],    "tp": 4   },   "chb10": {    "auroc_causal": 0.9748236962230029,    "auroc_future": 0.9725434421305836,    "f1_causal": 1.0,    "f1_future": 0.8,    "fp": 2,    "n_ref": 4,    "taus": [     0.46,     0.5,     0.98,     0.05    ],    "tp": 4   }  } }
- **guard_calls_real_run**: {  "F1": 901,  "F2": 164,  "F3": 26713,  "F4": 1471,  "F5": 82,  "F6": 63,  "F7": 1,  "F8": 517,  "F9": 26566,  "S1": 3,  "S5": 3,  "S7": 1 }
- **N1c_rerun_identity**: evaluated by run_n1.py --final (compares this card with results\rerun\)
- **N1d_N1e**: see results\N1_cde_synthetic.json

## Leakage checklist (Kapoor et al.; evidence = harness guard / test)

- L1.1 no test set / test in training: train/test file-disjoint; F8 LabelVault (tests F8), F6 causal (tests F6)
- L1.2 preprocessing on train+test: F1 normaliser fit-ID guard (tests F1); C2b quantifies
- L1.3 feature selection / tuning on test: F2 config hash + inner-CV test-ID refusal; F3 tau from train_oof only
- L1.4 duplicates: windows never cross files (F4); duplicate T8-P8 channel dropped
- L2 illegitimate features: F7 whitelist of 132 signal features
- L3.1 temporal leakage: F6 causal split; S-b quantifies the non-causal alternative
- L3.2 non-independence train/test: F4 buffer B=10 s; S5 random window split forbidden (C2a quantifies)
- L3.3 sampling bias test distribution: continuous full test recordings (S6); no sub-sampling

## Provenance

```
{
 "code_sha256": {
  "edf_reader.py": "f5a62fb9a277b37bfa05a17bcfd5ff3f2ca2613907173c7774ada288d3c27ddf",
  "nfharness/__init__.py": "9efc7a844dc73e533957c92f644c38cd96df0851b52c58a7448e14a89df2937d",
  "nfharness/card.py": "83b6bedde5bfd01607b4d6f778f8d4739aa1e51f27631a38142ffa98b1f3ee2c",
  "nfharness/config.py": "dfca97f440fe098a5c966d245c4dc5401c745623e0383d3b40c5977263498632",
  "nfharness/data.py": "243c9db3912886620f82b955fd5f3cd03f17ac938b2ea0ad1be9313f38b5a9e0",
  "nfharness/errors.py": "7133afc13a2561096d54bb58c15463ccf07774868e5fc55fc15d883958c4b6aa",
  "nfharness/features.py": "29acae0789a5e5a297ad489d962ce26f81bdd38bb41c3e82074a6581ad96f32e",
  "nfharness/labels.py": "4679d0fabe44b4d313862321d9d2b3c7dd713370b2635563a321f35978f23a27",
  "nfharness/model.py": "08305ee1f64f8c7b237e6592bddbfa93e5b7b200e0bfe895e5e520a5094ca10a",
  "nfharness/pipeline.py": "76a2773a9e7bc94cb261d3a2acf3ca2261561bb60d3d0330886fba3ffebc202b",
  "nfharness/postprocess.py": "faa04421f2167935c72ed102c9c9e63750ad7775a56045212559e230e68244c9",
  "nfharness/provenance.py": "ade7554aa6990c5a27b27d171087c88dfb02378eb4a63a0279cf816302570b6b",
  "nfharness/scoring.py": "b23ed292bed2235e67cb09e7a7698f44ff2e16c6e16680ef4ec98e42bfffc1ef",
  "nfharness/splits.py": "1fcecb0af87f00709dc84a99fbc7f243444e342ff210031aae8e50660161ec29",
  "nfharness/stats.py": "5dc8cf597a76e5b5251cb6ba73139d7fd939d2eee37b8b2f8a7055464e3eb4ee",
  "nfharness/windows.py": "2898848e8984f84cef5ce637b6c810068e8a7db1b2e50e7eb62e7e67480cb36f",
  "run_n2.py": "964716ccb7e5ec2cb8a435895fc5239075093865640555cde87927157e8dd6b8"
 },
 "config_hash": "b6775e9aad8958cfce6cbfe805674c55fd13b1c8969a8320b681edb451bd1e4f",
 "deviations_sha256": "2767a6e7584fcefff36e55a1d9ad99cc8802de4a8b6c9e747acfea4afbbeaaec",
 "environment": {
  "blas_threads": {
   "MKL_NUM_THREADS": "1",
   "OMP_NUM_THREADS": "1",
   "OPENBLAS_NUM_THREADS": "1"
  },
  "machine": "AMD64",
  "packages": {
   "matplotlib": "3.11.2",
   "numpy": "2.5.3",
   "pytest": "8.4.2",
   "scipy": "1.18.1",
   "timescoring": "0.0.7"
  },
  "platform": "Windows-11-10.0.26200-SP0",
  "processor": "AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD",
  "python": "3.12.10"
 },
 "feature_sha256_16": {
  "chb01_01.edf": "70e08d2903664c5b",
  "chb01_02.edf": "8978bff57c8a3578",
  "chb01_03.edf": "c89b3c0e0fe98fd2",
  "chb01_04.edf": "a9a6698e4bf6217b",
  "chb01_05.edf": "3399af5453e353dc",
  "chb01_06.edf": "9bcdbee2b7b32bb0",
  "chb01_15.edf": "6ca947b50b5aa50a",
  "chb01_16.edf": "1c9ab0b71a72dd02",
  "chb01_18.edf": "1030b67af786a08a",
  "chb01_21.edf": "f49063ab05c4904d",
  "chb01_26.edf": "e0afe29317630e9f",
  "chb03_01.edf": "73106ba33d54c8f9",
  "chb03_02.edf": "9b5fe184a3462669",
  "chb03_03.edf": "79dfc2ba83ed062d",
  "chb03_04.edf": "b400474ea74d9fc9",
  "chb03_05.edf": "5d26aec8facf2427",
  "chb03_06.edf": "e400bf57880e94e1",
  "chb03_07.edf": "7dee6766560b24d5",
  "chb03_08.edf": "2f4a7c1ff5b554b0",
  "chb03_34.edf": "68a49b2f56cb9f09",
  "chb03_35.edf": "5b24c95fc6c5fc7d",
  "chb03_36.edf": "ce722806842a712f",
  "chb10_12.edf": "fe60a57212d6eed3",
  "chb10_20.edf": "6c4b2f0566872822",
  "chb10_27.edf": "87b4bfe79d5e0136",
  "chb10_30.edf": "48b6ef81e540310f",
  "chb10_31.edf": "66c777eb0be54a44",
  "chb10_38.edf": "419a40f0799900a2",
  "chb10_89.edf": "bce97104d93ea224"
 },
 "input_sha256": {
  "chb01/chb01-summary.txt": "77e86183845192d147c88a9bb4263c2b4a32e936c6236029770f86ca2ea023db",
  "chb01/chb01_01.edf": "92ec026f633dca94ee74c2e2b67cf9d58aa50da700b650a1696cf497dac073e3",
  "chb01/chb01_02.edf": "185bebea970f5dfac5b3044d04b9f7c4fa007b8c6bbea744e8b69f8b39d1f060",
  "chb01/chb01_03.edf": "4c4a95a9b4331aeaadadd538763eb2e735950d9aa615b85ee6246c784be8ae90",
  "chb01/chb01_03.edf.seizures": "eb521b5e1a521f70fb8224e4205f0826c5ade093f29765d057b5db4d6b6594ab",
  "chb01/chb01_04.edf": "d91d190b2362697fe2cdef922a593baabadcb12fde437bd8d50c01b084ca9030",
  "chb01/chb01_04.edf.seizures": "4881a6c210e5018a9d1756479ca80e38b034d2d6b0cc41ddd9eaeb60948a6adc",
  "chb01/chb01_05.edf": "935accfd943e9ab372e65e21fbfd1e93a5c84e32dc717b685548f3301cc2fd6e",
  "chb01/chb01_06.edf": "bfe5d1a037e7ecb14b01365a86c00dd7605ff2ad262ed272619053baa9ed44a6",
  "chb01/chb01_15.edf": "00157966600e41bec0754d189d4fb92b020b214cb7e559df1421c6dc29ee8eca",
  "chb01/chb01_15.edf.seizures": "91608b1905e50a08f9ed6c1583fcf2bbc1192dcd2bc64f9c4041098051f8658d",
  "chb01/chb01_16.edf": "6c90e98a1938c9c2308ac9777ba3221dc5811d93db4186ff09f50b9a4ee7c710",
  "chb01/chb01_16.edf.seizures": "28e68edfd7cd7d2645fd9bc92270dde0b36aac0b93143f84b0f83e8ff88ce731",
  "chb01/chb01_18.edf": "da6c386c78d6f8348b38886b90bf67e4dc2e6f26e5eb657c1920d612fc0651b5",
  "chb01/chb01_18.edf.seizures": "008166da5a7c5e6a9c437b6290b81d64f18edf41f4ac94411e96ccad1004b573",
  "chb01/chb01_21.edf": "ceb3e5c3e6d513ed8894d6d5d5fd4599c5650e98a1a1c960660b0031b720e559",
  "chb01/chb01_21.edf.seizures": "95f4e4bd5af60ebb22acfcfcff0afadaaa8aced95d6c4f2375e82e8cb0b93191",
  "chb01/chb01_26.edf": "c70832d28f4e2905e5f0179fdb7d5ec24c4f24006adf6a9905b60072a75cc630",
  "chb01/chb01_26.edf.seizures": "77450c22c744402033c34ee31f02321a36b8a5ff4f6d550165b8ffe9953f4040",
  "chb03/chb03-summary.txt": "8d74eb131a96959c7b2aec82215d232dc26c3012c4d98c2a1c5f5dac520f52b4",
  "chb03/chb03_01.edf": "74f1ebc1334c4d52a132513c8ecab03d15d5b8ecbd91c7fdc71346bf69797d02",
  "chb03/chb03_01.edf.seizures": "3f3600ed4f605ad17252a5595a3d7a8d00ee296500850d6266153b9d29e88c14",
  "chb03/chb03_02.edf": "de8bdcd1f1edd0da5b56d97056ddee16b95d98f6a9ee1d5759342f3cae6b8d22",
  "chb03/chb03_02.edf.seizures": "32bc5c2318d5425a18e8a50eb12a299896467aad18cacf95e4778307371940b1",
  "chb03/chb03_03.edf": "71311de31a52c67d4890aff2d94ef95cc347995aca9728f46ee47ff73af4bd8d",
  "chb03/chb03_03.edf.seizures": "d305dbccd624defd6016c39d58f3d64f9a861be2bb050f60e90595103fe00fb0",
  "chb03/chb03_04.edf": "631134f5bd08668085d498d2ea848630aa2238199c3240dccf3408fb3952157e",
  "chb03/chb03_04.edf.seizures": "c47ceaa39c8589b82128b03a5dcefe9c64bee96973655db5d05dc830f3b150cf",
  "chb03/chb03_05.edf": "6e400cf6457c5045d5783b188b9dd4362e267967f74d356f4f43923ccd7248ec",
  "chb03/chb03_06.edf": "c2ae9e30d316058e213691c45cdfc19630075b7d446e83bcb366df918816f315",
  "chb03/chb03_07.edf": "316a98d251bd6bebd2468f589437483ca93088e347edd611dea160eb708db366",
  "chb03/chb03_08.edf": "ac8b4aa61083add1199229c833c9db1be620450630d60e9db625b66212fba76b",
  "chb03/chb03_34.edf": "abbd5931fbed8cf0f890d7a87a6811036c4f8c137994570b2282c8297d4db3ed",
  "chb03/chb03_34.edf.seizures": "2c8b53f784b9f362b03ee6fec0d9c88c65c33c8f71716a85e696a2f97db7a06e",
  "chb03/chb03_35.edf": "b3eaa6fde574179ee0d61ce524d6ab443b5f540ef7294aff2177df3d58cd97dc",
  "chb03/chb03_35.edf.seizures": "0d254a27f6dacd4a6fe3fb60b719876c121b53ffce65339a71c673b96b09874b",
  "chb03/chb03_36.edf": "c8247c41e3902837d6c51510a7b80c39ec28f1c7785f17abb377d090c790b7cc",
  "chb03/chb03_36.edf.seizures": "e08034547c15851e9dee4bcacc1714508b6b348b7ae6c931d950d846f585604c",
  "chb10/chb10-summary.txt": "f63fbc9359c894a81f92ed126f0b813eb3cfc279f9a17b068ed3680abc575353",
  "chb10/chb10_12.edf": "1ef27c219149ded4633a5ee1e8468d300a84f5f6881cd3a45cf2152e8b15c62d",
  "chb10/chb10_12.edf.seizures": "2110bcd3ad691d8c03d46cf940afa9b41621c97d3c7093d222458c7095c0e699",
  "chb10/chb10_20.edf": "f3be2bdfdbb1525068a7d64ac1a1df8d5e18e8188aa574f8f9cfffc936691ced",
  "chb10/chb10_20.edf.seizures": "52c8ad1950b47d567bc65d0a3fdacee6e1c2772ad58bfbf756b021e38199e8aa",
  "chb10/chb10_27.edf": "854131336dca0e548e4cfb175d1b40edaa59a2bec3c17eb09991a31ae8959fb0",
  "chb10/chb10_27.edf.seizures": "4fec591229fe9564d35432e1d4aec0f6b43f10443ee586bbe4cacda9a5cab98f",
  "chb10/chb10_30.edf": "88f383c33fb37ac9bfa235edb9b3a07f8d33bc40033a47d2485f77aee2f63bff",
  "chb10/chb10_30.edf.seizures": "6fdfa6c83a2d6ae8ad5676bc39a8a0c3622098c31b38a482c2c753ab2498ef5e",
  "chb10/chb10_31.edf": "82fd895dd55765769b75b5415794348115e5967aa7e05d2a15af7700f87f20dc",
  "chb10/chb10_31.edf.seizures": "ebea4f44e18458c762abc4c08d476ad7833b10e20ed37089b77b6240b8f9fff4",
  "chb10/chb10_38.edf": "1a941b8f94b1f6272b90c49ec6defbaafa5c3ca1e996f610772c1b4488137016",
  "chb10/chb10_38.edf.seizures": "693ce5bc1bee753a02e017b253e92b4ded7a50803f5f4aae801260efff86f16d",
  "chb10/chb10_89.edf": "58534c515a35c37696ff041afe593254c5ab86a95d81873748c8a54eca8cf1c7",
  "chb10/chb10_89.edf.seizures": "fea69cb9df20123108c8680f272dc734635445298b245542cbb4d9e9b6595d88"
 },
 "label_vault_logs": {
  "chb01": {
   "chain_sha256": "4e55df4017c73fb5e7ae9eff66e79de6bd27d710b7d36fc6cfc16ac4e83782fe",
   "scorer_reads": 172,
   "vault": "N2-chb01"
  },
  "chb03": {
   "chain_sha256": "32289279bf631c2fd3bd1217fd68665924286354af48bbaf455d35fc3edde9a9",
   "scorer_reads": 264,
   "vault": "N2-chb03"
  },
  "chb10": {
   "chain_sha256": "b560a71641f530340623ea77b4ef652fe67eb1125779b0ecf948b8b91970f8e3",
   "scorer_reads": 172,
   "vault": "N2-chb10"
  }
 },
 "manifest_sha256": "d4fdc4084eab2ca652fb062bd93dcd5d68efd87590dd1efd14176ad24e5311f5",
 "n_inputs_verified": {
  "edf": 29,
  "seizures": 21,
  "summary": 3
 },
 "prereg_sha256": {
  "N1_harness_controls.md": "27db9d27f5b6ac2e0f49826c6b3eb9625b8e1633434ae70cf62a7e10f09fc93b",
  "N2_baseline_detection.md": "ed929ae0e5182827352928225cf40865a8bee5f6b5da089be5a6600e6678e21c"
 },
 "rng_streams": {
  "0": "leak split",
  "1": "iid label permutation",
  "2": "circular shift",
  "3": "bootstraps",
  "4": "chance-shift nulls then random-alarm draws",
  "5": "synthetic fixtures"
 },
 "seed": 20261001,
 "sha256sums_sha256": "f1698efeb9fef887e55cedf6eda13386d9a888db663aec48b2aa194b7b753d2b",
 "split_hash": "433d818f305ba2095ef854b1f7f8b594895ad070f5fc28584a5507bdc7d9f1e2"
}
```

## Runtime (excluded from the card hash)

```
{
 "first_test_label_read_unix": 1790441243.4861178,
 "hostname": "Marius",
 "peak_ram_mb": 695.5859375,
 "prereg_hash_precedes_first_label_read": true,
 "prereg_hashed_at_unix": 1790441207.8921878,
 "stage_s": {
  "features_s": 26.026124477386475,
  "hash_inputs_s": 1.1939373016357422,
  "n1a_s": 6.241813898086548,
  "n1b_s": 357.28953218460083,
  "n2_primary_s": 11.835246086120605,
  "s_a_s": 47.839762926101685,
  "s_b_s": 287.3906304836273
 },
 "started_utc": "2026-09-26T16:46:47.890180+00:00",
 "wall_s": 737.9243505001068
}
```

card SHA-256 (excluding runtime): `cf2913d8d71f839725a14ff6fa875189f2ecc68a5354b1ecc43aea5daef78e17`
