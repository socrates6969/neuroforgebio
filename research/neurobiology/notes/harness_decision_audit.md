# Harness decision audit: nfharness vs nf_eval (canonical evaluation core)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Independent auditor, 2026-09-26.

Scope: `research\neurobiology\code\nfharness\` (with `code\tests\`, RESULTS/REVIEW N1_N2 and N1b) vs `nf_eval`
(branch `feature/research-algos`, commit 6d5f075, `services\workers\steps\eval_harness\` in worktree `C:\Users\mariu\neuro-worktrees\algos`).
Nothing in the worktree or nfharness was modified. `git status` in the worktree was clean before and after. nf_eval was run from a scratch copy.
Scripts: scratchpad `cmp_scorers.py` (output `cmp_out.json`) and `cmp2.py`.

## Recommendation

**A merge, with nf_eval as the canonical platform core.** Keep nf_eval's package, typed API, schema, CLI, NF-CJSON hashing, forecast and cluster statistics.
Port nfharness's verified pieces into it, and keep timescoring 0.0.7 as the reference oracle.

Why this way round:
- nf_eval is shaped like platform code. It is a packaged, typed, index-based API with no dataset coupling.
  It also has a JSON-schema evaluation card, a CLI, and prereg hashing that follows the repo spec (`docs/spec/hashing.md`).
  nfharness is research-script code, coupled to CHB-MIT, EDF files, 1-Hz masks and its own pipeline, features and model. It has no type hints and no package metadata.
- nfharness holds the validated evidence: real data (CHB-MIT) plus two independent reviews. nf_eval has no real-data validation and no review.
- The event scorers are numerically equal (see (2)), so choosing nf_eval as the core costs no correctness on the scorer, provided the oracle test below is ported with it.

**Port from nfharness into nf_eval, in priority order:**
1. **timescoring oracle test.** Port N1(e): the fixture X1-X12 plus 1,000 random pairs against timescoring 0.0.7, as a test dependency only.
   Also port the F9 version/parameter lock as a test assertion. nf_eval had never been run against timescoring before this audit.
2. **Garwood exact Poisson CI for FA/24 h** (`stats.garwood`). nf_eval has no FA interval.
3. **Detection latency** per TP event (`scoring.latencies`, verified on X12: +4 s / -15 s). nf_eval has none.
4. **Guards as named exceptions.** Port F1 (normaliser fit IDs), F3 (threshold selected on train-OOF only), F4 (window/boundary buffer), F6 (causal), F8 (test labels via a Scorer/LabelVault only), F9, S1, S5 and S7 (split hash equals the prereg literal).
   nf_eval covers only S1, S5 and part of F6 (`check_no_leakage`, `segment_random_split_for_leakage_control`), plus train-only recalibration.
5. **Leak meter (positive control).** Port the deliberately leaky split and normaliser, re-scored against the honest split (N1(a)).
   nf_eval exposes the leaky split but not the comparison. Also port the N1b planted-leak and phantom machinery as a control-suite module (clearly labelled: N1b was powerless in the event arm).
6. **Input provenance.** Port the SHA-256 of every input file checked against the source SHA256SUMS, plus package versions, BLAS threads, the seed stream map (`SeedSequence(20261001, spawn_key=(stream,...))`) and the byte-identical card rerun check.
7. **By-event and by-file bootstrap** (`bootstrap_indicators`, and the exact fast `block_bootstrap_auroc`). Offer them next to nf_eval's `cluster_bootstrap_ci`.
8. **The patient-identity map rule** (chb01 = chb21) as a required input to the patient-disjoint splits.

**Keep from nf_eval:**
- Patient K-fold, LOPO, and the chronological split with a guard.
- `check_no_leakage` (patient and time modes).
- Snyder chance (analytical and MC), the >= 7-day surrogate, sensitivity at fixed TiW.
- Brier, ECE, isotonic recalibration.
- Cluster bootstrap, BH-FDR, within-cluster permutation.
- The prereg lock and `verify_before_results`, `DEVIATIONS.md` handling, the card schema and the CLI.

## (1) Feature coverage

| Feature | nfharness | nf_eval |
|---|---|---|
| Patient-disjoint splits | S1 assert only (`assert_subject_disjoint`); cross-patient folds built in scripts | `patient_kfold` (seeded), `leave_one_patient_out`, checked by `check_no_leakage(mode="patient")` |
| Chronological/causal split | `causal_splits`: per subject, train up to and including the file with the n-th (3rd) seizure, test after; F6 assert; 10 s window buffer | `chronological_split`: cut at 60 % of each patient's span, 4 h guard, straddling or in-guard segments dropped; `check_no_leakage(mode="time")` |
| Split lock | S7: SHA-256 of the split string equals the prereg literal | none (the split is not hashed) |
| Random split | S5: raises unless `allow_random_split=True` | only `segment_random_split_for_leakage_control` |
| Leakage guards | F1-F9, S1, S5, S7 as named exceptions; call counters; 12/12 violations caught | `LeakageError` (patient/time overlap, duplicate or out-of-range index); train-only recalibration |
| Leak meter | yes (C2a/C2b; N1(a) PASS) | no |
| Event scoring | timescoring 0.0.7 itself (locked) + an independent re-implementation; 1-Hz integer masks | own continuous-time re-implementation; float-second events |
| Any-overlap, -30/+60, merge < 90 s, split > 300 s | yes (locked, F9) | yes (`SZCORE_DEFAULTS`, frozen dataclass; `min_overlap` can be changed) |
| FA denominator | the whole recording including seizure time (`len(mask)` s), as timescoring does | the same (`duration_s`, including seizure time); pooling is a micro-average |
| Sample scoring | timescoring SampleScoring | own implementation (equal, see (2)) |
| Latency | yes | no |
| Binomial CI | Clopper-Pearson (NaN if n = 0) | Clopper-Pearson (raises if n = 0); max difference 0 on all k <= n < 60 |
| FA CI | Garwood | none |
| Bootstrap | by event; by file within a subject (exact block AUROC), B = 10,000 | cluster bootstrap over any cluster id, n_boot = 2000, drops NaN replicates |
| BH-FDR | no | yes |
| Within-cluster permutation | no | yes |
| Snyder forecast metrics | no (detection only) | sensitivity at fixed TiW, Snyder Poisson chance (analytical Binomial(n, tiw) + MC), >= 7-day circular surrogate, fraction above chance with CP |
| Calibration | no | Brier, ECE (uniform and quantile), train-only isotonic |
| Prereg hashing | SHA-256 of the prereg files recorded before the first test-label read; config-hash literal | NF-CJSON canonical + domain tag `nf.prereg.v1`; exclusive-create lock; `verify_before_results` (ID, created_at, mtimes); DEVIATIONS helper |
| Provenance | input SHA-256 vs PhysioNet SHA256SUMS; code, prereg and config hashes; versions; BLAS threads; RAM; byte-identical card | `code_hash` (CRLF-normalised); no data-input hashing; no environment block |
| Card | JSON (hash excl. runtime) + Markdown + figure | JSON Schema `nf.evaluation-card/v1`, schema test, NOTICE |
| AUROC / AUPRC | both (AUPRC equals sklearn AP) | AUROC only (equal to nfharness, max difference 0) |

## (2) Numerical equivalence (run 2026-09-26, venv Python 3.12, timescoring 0.0.7)

| Test | timescoring vs nfharness (`event_score`) | vs nfharness re-impl | vs nf_eval `score_events` |
|---|---|---|---|
| Fixture X1-X12 (13 cases incl. X12a/b), TP/FP/N_ref/FA24h vs the hand values | 13/13 | 13/13 | 13/13 |
| 1,000 random pairs, N1(e) generator shape (integer s, 1-4 h) | 1000/1000 | 1000/1000 | 1000/1000 |
| 1,000 edge pairs (0.3-0.5 h files, events touching file start/end, gaps 89/90/91 s, lengths 299/300/301/600/601 s) | 1000/1000 | 1000/1000 | 1000/1000 |
| 1,000 random float-second events (ms resolution) | n/a (1 Hz only) | n/a | 1000/1000 |
| 1,000 events on a 0.1 s grid | n/a | n/a | 1000/1000 |
| Sample scoring, 1,000 random masks | (timescoring) | n/a | 1000/1000 vs nfharness `sample_score` |

**Mismatches found: 0 in random testing. Targeted probes found 2, both convention differences (neither is a bug):**
- **P1 (sub-0.1 s edge).** ref (1000, 1060), hyp (960.00, 970.04), 3600 s.
  timescoring gives TP 0 / FP 1, because at 10 Hz `round(970.04*10) = 9700` equals the extended start. nf_eval gives TP 1 / FP 0 (0.04 s of continuous overlap).
  Cause: nf_eval computes overlap in continuous time. Its docstring declares this deviation. It matters only when edges lie within 0.1 s of each other; 1-Hz outputs cannot trigger it.
- **P2 (non-integer duration).** duration 3600.5 s: nf_eval gives an FA denominator of 3600.5 s (23.997/24 h); timescoring uses numSamples/fs (3600 s, 24.0/24 h).
  Cause: the duration source. It matters only when duration is not a whole multiple of the label sample period.
- **P3 (overlapping or unsorted input events).** Equal on the probe. However, timescoring's merge assumes sorted, disjoint events (it sets `end = next.end`, not the max). nf_eval sorts and takes the max. nfharness cannot receive overlapping events (they arrive as masks).

The two nfharness scorers match timescoring exactly, which reproduces the N1(e) result independently. nf_eval's own tests are synthetic hand cases; none compares against timescoring.
Test suites: nfharness 68/68 pass. nf_eval 67/68 in the copy; the 1 failure is `test_canonical_copy_conforms_to_frozen_vectors`, because `spec/test-vectors` is outside the copied folder (a path issue, not a code failure).

## (3) Validation status

| Component | nfharness | nf_eval |
|---|---|---|
| Event/sample scorer | real CHB-MIT run + independent recompute (REVIEW N1_N2 item 2) + N1(e) fixture/1,000 pairs; re-confirmed here | synthetic only (K1/K2/property tests); equivalence to timescoring first shown by this audit (synthetic) |
| Splits + leak guards | real data, reviewer found no test-to-train path (item 1); 12/12 violations | synthetic only (property tests) |
| Leak meter | real data, N1(a) PASS (via ceiling clause) | n/a |
| CP / Garwood / bootstrap | real data, independently recomputed (item 2) | CP synthetic only; cluster bootstrap and BH synthetic only |
| Provenance / card determinism | real data, byte-identical reruns (N1(c), N1b), reviewed | synthetic tests only; prereg hashing checked against the repo's frozen spec vectors |
| Negative-control suite | **FAIL**: N1(b) was a design flaw; N1b was powerless in the event arm (reviewed, genuine). Not validated. | none |
| Forecast / Snyder / calibration | none | synthetic only. The Snyder chance is "our reading" from the abstract only (per its own docstring); not checked against the paper |
| Overall harness verdict | N1 FAIL, N1' FAIL, so "harness validated" is **not** claimable. Only the components marked VERIFIED in PLATFORM_FEATURES.md are verified; the next step is N3 | unvalidated, unreviewed (a single commit, 6d5f075, "synthetic data only") |

## (4) Dependencies, licensing, code quality

- **Dependencies.** nfharness needs numpy, scipy and timescoring 0.0.7 (MIT, (c) 2023 EPFL ESL). The script-level parts also use matplotlib.
  nf_eval needs numpy >= 2.1 and scipy >= 1.14, with Python pinned `==3.12.*`, and has no timescoring dependency. Keep timescoring as a test-only oracle. It is MIT, so attribution is required only if it is shipped.
- **Licensing.** Both are first-party and fall under the proprietary root LICENSE ((c) 2026 Marius Carlsson). nf_eval's pyproject has no license field; add one. There is no third-party code in either apart from timescoring.
  nf_eval's `_canonical.py` is a copy of the repo's own spec reference.
- **nf_eval code quality.** Good. It has type hints, frozen dataclasses, input validation, NaN serialised as null, seeded RNG everywhere (20261001), a documented algorithm in every module, and a JSON schema synced by a test.
  Minor issues:
  (i) `cluster_bootstrap_ci` loops in Python and is slow for large B;
  (ii) `auroc(scores, labels)` takes its arguments in the opposite order to nfharness `auroc(y, s)`, a porting hazard;
  (iii) `min_overlap` and the other parameters are adjustable, with no F9-style lock at use.
- **nfharness code quality.** Correct and reviewed, but not packaged. It has no type hints and uses module-level mutable state (`GUARD_CALLS`, the config literal).
  Its pieces are coupled to CHB-MIT specifics: the 1-Hz integer masks, the channel list and the `LabelVault` scorer key. Port the functions, not the modules.

## Convention conflicts to resolve (the owner decides; lock them in a platform prereg/spec)

1. **Time representation.** nfharness uses 1-Hz integer masks; nf_eval uses float-second events in continuous time. timescoring uses a 10 Hz grid, so edges < 0.1 s apart can differ (P1).
   Pick one: continuous time plus a documented deviation, or snapping to 10 Hz for exact timescoring parity.
2. **Recording duration / FA denominator source.** `len(mask)` vs `duration_s` float (P2). Both include seizure time (the timescoring convention). Keep that, and state it on the card, since the convention changes FA by about 100x.
3. **Causal split definition.** nfharness trains through the file with the n-th seizure, uses a file-level cut and a 10 s buffer, and hash-locks the split. nf_eval cuts at 60 % of the time span with a 4 h guard, drops segments and has no hash lock. These are different estimands.
4. **Resampling unit and B.** Event/file bootstrap B = 10,000 (np.percentile) vs cluster bootstrap n_boot = 2000 (np.quantile, NaN replicates dropped). There is also nfharness's few-cluster rule (pooled CIs are descriptive only with 3 subjects).
5. **Hash scheme.** Plain SHA-256 of files and strings plus `json.dumps(sort_keys)` for the card, vs NF-CJSON with a domain tag and CRLF normalisation. Adopt NF-CJSON, and re-express the split hash and card hash in it (existing N1/N2 literals then need a mapping note).
6. **Scorer parameter locking.** nfharness raises on any change (F9, and the version too). In nf_eval the parameters are overridable. Decide whether non-default parameters are allowed on cards, and if so, label them.
7. **Edge-case semantics.** Clopper-Pearson with n = 0 returns NaN vs raises; F1 with no events is NaN in both; latency is absent in nf_eval.
8. **Seeds.** Both use 20261001. nfharness spawns named `SeedSequence` streams (k = 0-16), while nf_eval passes the seed directly to each function. Unify on named streams so controls stay independent.
9. **Merge input contract.** timescoring requires sorted, disjoint events, while nf_eval accepts overlapping ones. Validate or normalise at the API boundary.
10. **Patient identity.** A chb01 = chb21-style identity map must feed `patient_ids` before any patient split.
