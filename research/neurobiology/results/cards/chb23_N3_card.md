# Evaluation card: N3-N2model-chb23-9320fa73c5e5

**RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance and clinical validation (IRB/ethics approval).**

**Verdict: N2 decision rule, subject chb23: PASS (counts only if the N3 harness = PASS; see results\N3_verdict.json)**

Locked N2 model and rule re-run unchanged on a fresh subject (prereg N3 §5). FP grid [4, 8].

## Intended use / task
seizure DETECTION, patient-specific causal split (N2 §1); CHB-MIT bipolar, 22 unique channels

## Data

- dataset: CHB-MIT Scalp EEG Database v1.0.0, DOI 10.13026/C2K01R, ODC-By 1.0
- subject: chb23
- hours_scored_test: 4.0072222222222225
- test_seizures_N_ref: 4
- files: R2 subset: seizure-containing files only (prereg N3 §2.1); chb23/chb24 test files now BURNED

## Split

- scheme: causal: train through the file with the 3rd seizure; test = the next seizure files
- buffer B = 10 s
- split hash: `9320fa73c5e52ce449f7257f47dda5fce87a25b53d812f51dbf6b21bc0397a19` (prereg literal matched: True)
- split string of both subjects hashed (S7) before feature extraction

| subject | train files | test files |
|---|---|---|
| chb23 | chb23_06.edf, chb23_08.edf | chb23_09.edf |

## Model

- config_sha256: b6775e9aad8958cfce6cbfe805674c55fd13b1c8969a8320b681edb451bd1e4f
- tau_rule: smallest grid tau with inner-LOFO train FA <= 12/24h
- tau_star: 0.05

## Metrics (per subject, summed over test files)

| subject | verdict | TP/N_ref | sens (CP 95%) | FP | FA/24h (Garwood 95%) | precision | F1 | median latency s | sample F1 | AUROC (file-bootstrap 95%) | AUPRC (prevalence) | tau* | flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chb23 | PASS | 4/4 | 1.00 [0.398, 1.000] | 1 | 6.0 [0.2, 33.4] | 0.80 | 0.89 | 5.0 | 0.78 | 0.993 [0.993, 0.993] | 0.765 (0.0166) | 0.05 | CI uninformative (N_ref = 4); FA on peri-ictal data only |

## Controls

- **N3 harness gate**: see results\N3_card.json / N3_verdict.json

## Leakage checklist (Kapoor et al.; evidence = harness guard / test)

- guards: nfharness F1-F9/S7 unchanged; N3 gate = NC-P window arm + pooled event arm + C3' + planted leaks

## Provenance

```
{
 "label_vault": {
  "chain_sha256": "dee2b338fdd3cac89aa120fa07a46dedc8bb02c1fc5f55a84a578b0ec8cb3893",
  "scorer_reads": 2,
  "vault": "N3-N2-chb23"
 },
 "prereg_sha256": {
  "N1_harness_controls.md": "27db9d27f5b6ac2e0f49826c6b3eb9625b8e1633434ae70cf62a7e10f09fc93b",
  "N1b_negative_controls_v2.md": "a67b251734d59097b0cd516162e054ecb72737f27344868a45b3c40f1d7fc4a6",
  "N2_baseline_detection.md": "ed929ae0e5182827352928225cf40865a8bee5f6b5da089be5a6600e6678e21c",
  "N3_harness_validation_fresh.md": "954e4abba139cde8d9a37e0ae43190416389315719d7d7451d26b394e87fc32b"
 },
 "sha256_scores_hyps_step_i": "09c453c8e3933282584590c40c8b6886502b5211a845ba0258fea7c52ab6f33a",
 "split_hash": "9320fa73c5e52ce449f7257f47dda5fce87a25b53d812f51dbf6b21bc0397a19"
}
```

## Runtime (excluded from the card hash)

```
{}
```

card SHA-256 (excluding runtime): `a8d29b8a00222b7c0d8daa37ce464cd0213eb6a1f4b1accc25b1055bd4fd9efb`
