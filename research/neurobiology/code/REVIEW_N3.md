# REVIEW: N3 power analysis + N3 harness validation on fresh subjects (independent code review, verification gate)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Reviewer: independent code reviewer, 2026-09-26.
Scope:
- **A.** code\n3_power\power_sim.py (SHA-256 06508ca5...5079e, equal to the JSON provenance), results\n3_power\power_sim.json and notes\n3_power.md.
- **B.** code\n3\*.py and code\run_n3.py, checked against prereg\N3_harness_validation_fresh.md (SHA-256 954e4abb...fc32b, equal to the lock card, both cards and run_n3.py).
  Reported material checked: code\RESULTS_N3.md, code\DEVIATIONS.md §N3 (N3-1 to N3-16), results\N3_*.json, results\rerun\N3_card.json and results\cards\.

Nothing in code\ (outside code\review\), results\, prereg\ or data\ was modified.
- The reviewer's checks are code\review\n3_*.py. Each writes a matching `*_out.json` and `*.log`.
- The checks used the venv and ran in 27 s, 40 s and 20 s. Peak RAM was < 0.6 GB (the N2 re-implementation measured 538 MB).
- The pytest suite was re-run with bytecode writing and the cache disabled: **83 passed**.

## Summary

| # | item | status |
|---|---|---|
| A1 | Literal Fisher on discrete p_up has size ~0 | **CONFIRMED** (independently) |
| A2 | Pooled ΣF1 conditional-randomisation statistic is exact (nominal size) | **CONFIRMED** (proof + two simulations) |
| A3 | Power: 4×4 needed for PL-A, 3×7-10 for PL-B; 0.59 / 0.31 at 2×4; window arm 0.96-1.00 | **CONFIRMED** within MC noise (reduced re-run) |
| A4 | "Reproduces N1b's real run" | **CONFIRMED with qualification.** The PL-A-hom match is partly calibration, not validation. |
| A5 | power_sim.py tie handling | **BUG (minor, no conclusion changes)**: float32 null vs float64 observed F1 in `combine` |
| B1 | Prereg lock before download and run; subject selection by the fixed rule; chb24 order by EDF header | **CONFIRMED** |
| B2 | Harness gates: V1-A, V2-A, PL-A trip, V1-E pooled, C3', PL-C, PL-B-code, PL-B specificity, locked-code hash identity | **CONFIRMED** (two notes, §B2) |
| B3 | N2 locked-model numbers chb23/chb24 (TP, FP, hours, FA/24 h, Garwood, AUROC) | **CONFIRMED** by an independent re-implementation |
| B4 | Verdicts: harness PASS, chb23 PASS, chb24 FAIL, overall INCONCLUSIVE | **CONFIRMED** |
| B5 | Determinism (rerun card identical); provenance (16 files SHA-verified) | **CONFIRMED** |

**Findings.**
- One BUG, in the power simulation only. It does not reach the N3 run, whose pooled code uses exact Fractions, and it does not change any N3 design decision.
- No finding puts an N3 verdict at risk.

## A. Power analysis

### A1 Literal Fisher size ~0: CONFIRMED (review\n3_power_reduced.py, part 1 and part 2)
- **Independent generic simulation.** This uses no power_sim code. Each replicate's F1 comes from TP ~ Bin(4, q), with a point mass at 0, and the observation and M = 999 nulls are i.i.d. (H0). There are 4,000 experiments, each 3 × 10 replicates.
  - Literal Fisher rejected **0 / 0 / 0** at α = 0.0025 / 0.0125 / 0.05.
- **Surrogate.** Pseudo-null, K = 4, S = 3, R = 10, 2,000 experiments: the literal Fisher is 0 / 0 / 0 again. This matches the published 0/6,000.
- **Mechanism.** Zero-TP replicates give p_up = 1 exactly, so the Fisher χ² is inflated towards acceptance.

### A2 Pooled ΣF1 is exact: CONFIRMED
- **Proof.** For each retained replicate r, the observation and its M null draws are i.i.d. given h. Retention depends on h only, and replicates are independent.
  - The columns j = 0..M of the matrix X[r, j] are therefore i.i.d. vectors, and so are their sums T_j = Σ_r X[r, j].
  - The rank p-value (1 + #{T_j ≥ T_0})/(M + 1) is valid; ties make it conservative only.
- **Simulations.**
  - Independent generic simulation: size **0.0020 / 0.0105 / 0.046** at α = 0.0025 / 0.0125 / 0.05.
  - Surrogate pseudo-null: 0.003 / 0.014 / 0.0525 (E arm) and 0.003 / 0.011 / 0.0465 (PL-B null arm).
  - Published: 0.0018-0.0025 / 0.010-0.015 / 0.046-0.054.
  - All agree within MC error (SE at 0.05 with n = 2,000 is 0.005).

### A3 Power numbers: CONFIRMED within Monte Carlo noise (reduced independent re-run)
**Design.** Saturated regime, K = 4, 12 subjects × 10 fits (published: 24), 300 experiments per cell, the published deltas, and different seeds.

| cell (pooled ΣF1, α 0.0025) | published | reviewer (reduced) |
|---|---|---|
| PL-A-hom event, 2×4, R = 10 | 0.59 | 0.62 |
| PL-A-hom event, 4×4, R = 10 | 0.82 | 0.82 |
| PL-A event, 2×4 | 0.95 | 0.91 |
| PL-B event, 2×4 | 0.31 | 0.21 |
| PL-B event, 4×4 | 0.65 | 0.72 |
| window arm, PL-A-hom, 2×4, R = 5 | 0.96 | 1.00 |
| window arm, PL-A, 2×4, R = 5 | 1.00 | 0.99 |

- **Surrogate diagnostics reproduce.** Honest hit rate 0.18 (published 0.16), T_A SD 0.112 (0.107), PL-A-hom hit rate 0.308 (0.31) and T_A 0.729 (0.73).
- The "3 × 7-10 for PL-B" and "≥ 4 × 4 for PL-A-hom" cells were read from power_sim.json. They equal notes\n3_power.md (0.85 / 0.87 and 0.82).
- **Conclusion.** The published conclusion holds under the reduced re-run: the event arm is under-powered at 2×4, and the window arm is near 1. The difference in the PL-B cell at 2×4 (0.21 vs 0.31) is within resampling noise for a 12-subject pool.

### A4 "Reproduces N1b's real run": CONFIRMED with qualification
- **PL-B.** The literal Fisher median is 0.37 published and 0.39 in the reviewer's run, against the real 0.51. With the A5 tie fix it is **0.47**, which is closer to the real value. The claim is supported.
- **PL-A.**
  - The "validation: PL-A-hom reproduces the 19/60 hit rate" is **not independent validation**. power_sim.py (comment at l. 580) and notes §2 say that the leak shape (γ shape 20) was chosen after a trial run, to bring the hit rate towards 0.32. So the hit-rate match is a calibration.
  - The genuinely out-of-sample check is the literal-Fisher band. The real 0.012 lies inside the PL-A-hom q10-q90 band (2e-4 to 0.93), which is a very wide band.
  - The notes already disclose the NEVER-alarm miss (0.05 vs 0.23).
- **Consequence for N3: none.** N3's formal leak gate is the window arm, and it tripped on real data at 5.9e-16. The event-arm power numbers are descriptive only.
- **Wording to fix in any report.** Say "PL-A-hom was chosen to match the N1b hit rate". Do not say "validated".

### A5 BUG (minor): float32 tie-breaking in power_sim.combine
- **Where.** `one_fit` stores the null F1 and T_A as **float32** (l. 277, 285, 297). `combine`/`p_up` compare them with the **float64** observation, using a 1e-12 tolerance (l. 303, 344-349).
- **Why it matters.** About 26% of the possible F1 fractions (for example 1/6 and 0.08) round DOWN in float32. When that happens, a null draw equal to the observation is counted as smaller, so p_up is too small.
- **Incidence.** In the reviewer's 120 honest fits, 7/120 observed F1 values were rounded down AND tied with ≥ 1 null draw, in both the E arm and the B arm.
- **What it affects.** The literal, mid-p and random-tie Fisher cells of the power tables, and the N1b-validation medians.
- **What it does not affect.**
  - The pooled ΣF1 power: identical with and without the fix in every re-run cell.
  - The size tables: the pseudo-null takes its observation from the float32 nulls themselves.
  - The window arm, where ties are negligible.
  - The N3 run: n3\pooled.py uses exact Fractions (unit-tested, and re-checked in B2e).
- **Magnitude.**
  - Literal Fisher power for PL-A-hom at 2×4: 0.28 → 0.25.
  - PL-B literal Fisher median: 0.39 → 0.47 (N1b validation) and 0.41 → 0.43 (2×4).
  - The bias favours literal Fisher, so the stated dominance of the pooled rule is, if anything, understated. No conclusion changes.
- **Fix, for any re-use.** Keep the nulls in float64, or cast the observation through float32 before comparing.

## B. N3

### B1 Lock, timeline and selection: CONFIRMED (review\n3_provenance_gates.py §1, §1b)

**Timeline (UTC)**
- The prereg mtime is 19:24:40. The lock card `written_utc` is 19:30:54.
- The first chb23/chb24 file on disk is 19:31:07 (chb23-summary.txt; annotations were already public in _meta since cycle 1).
- The first manifest download stamp is 19:53:38. The last EDF finished at 20:27:58.
- Real run 1 started at 20:28:14, and the rerun at 20:29:50.
- The prereg SHA-256 now equals the lock card, both run cards and the run_n3.py literal: 954e4abb.
- The n3 code was written at 19:31-19:58, during the download and before any signal was read. The dry run was at 20:07.
  DEVIATIONS §N3 is in the run snapshot, which is a byte prefix of the current DEVIATIONS.md; the only later addition is the appended run log.

**Selection**
- The reviewer re-applied §2.1 from notes\data\chbmit_inventory.csv with independent code:
  - seizure files ordered by EDF header date and time;
  - training up to the 3rd seizure;
  - test until N_ref = 4, with seizures < 90 s apart merged;
  - E0, E1 (labels = the chb01 standard 23), E2\*, E3\* and E5.
- **Only chb23 and chb24 are eligible.** Every other subject fails for the reason in the prereg §2.2 table. Some subjects fail extra rules as well; for example chb09 fails E1 and E2\*.
- The rebuilt split string hashes to **9320fa73...** (equal to the prereg), and the R2 bytes are 379,841,536 + 169,598,976.
- **chb24 header order:** chb24_01 16:26:28, chb24_03 18:26:39, chb24_04 19:26:46, chb24_06 21:27:00 (25.01.74).
  - Training = 01 + 03 (4 seizures). Test = 04 (3 references; gaps 291 and 307 s, both ≥ 90) + 06, so N_ref = 4.
  - The reviewer's EDF-header reader (in the B3 re-run) independently gives the same order and causal chronology.

### B2 Harness gates: CONFIRMED (review\n3_provenance_gates.py §2, §2e, §2h; code read)

**Recomputed from the card's replicate records**
- **V1-A.** Fisher over 20 replicates, none window-flagged: up **0.4693** and lo **0.2383**, bit-equal to the card. Both are ≥ 0.0025.
- **V2-A.** 0/20 window-flagged.
- **V1-E.**
  - The retained set is 18/20; the degenerate ones are chb23 r2 and chb24 r6, both never-alarm. The flags were decided from h before the draw (order logs OK).
  - T was recomputed from the per-replicate (TP, FP, N_ref) as the exact fraction **382141/183540**, equal to the card.
  - The pooled p_up is 0.779 and p_lo 0.222. Both are ≥ 0.0025, and p_up + p_lo ≥ 1.
- **PL-A.**
  - Fisher T_A up **5.88e-16** (10 replicates), equal to the card. It trips.
  - The leak is 874 of 3,496 allowed test windows on chb24, which is 25.0%.
- **PL-A10.** 3.10e-7, equal to the card. This item is descriptive.
- **C3'.**
  - **Independent exact enumeration** (review\n3_indep_n2.py): every circular offset of each of the 3 test files' hypothesis masks, the reviewer's own scorer, and an exact joint convolution.
  - It gives **μ\* = 690151047616081/5104034208000000**, the same fraction as the card. It also gives σ\* 0.096056, q95 = 4/13 and a\* 0.049260, all identical to the card.
  - (i) |0.13750 − 0.13522| = 0.0023 ≤ 0.0091. (ii) 0.049 ≤ 0.0698. PASS.
- **PL-C.** 0.419 > 0.0698, so it trips.
- **PL-B specificity.** The T_A p-values of the PL-B records equal NC-P's in 20/20.
- **PL-B-code.**
  - The pytest test calls the locked `nfharness.postprocess.select_tau` with the tags "test", "test_phantom", "train", "" and with an untagged dict. Each raises ThresholdSelectionError, and "train_oof" is accepted. The reviewer's re-run passes.
  - The in-process check on the real test scores also raised.

**Pooled implementation (§2e)**
- `n3.pooled.pooled_test` agrees with the reviewer's own exact-Fraction implementation in **60/60** random fixtures (18 replicates, M = 199).
- Its size under exchangeable H0 is 0.04 at 0.05 and 0.02 at 0.01 (400 experiments).

**Locked code**
- The 17 nfharness/edf_reader/run_n2 files equal results\N2_run_card.json, and every nfharness\*.py on disk is in that list.
- The 10 n1b/run_n1b/test_n1b files equal results\N1b_card.json.
- The n3 code on disk equals the n3_code_sha256 in both cards and in N3_verdict.json, so the code reviewed is the code that ran.

**Notes (no change to any verdict)**
- **(a) Dry run §3.3(a) is a reading (N3-8).**
  - The event-arm KS was applied to per-replicate p-values of the **47 retained** of 100 replicates, not ≥ 100. A single-replicate "pooled" p is simply n1b's exact p, so the dry run does not exercise the pooling code itself.
  - That code is covered by the unit tests, by the bit-identity check of the null recomputation against n1b, and by review §2e above. The grouped pooled p-values (0.89, 0.015, 0.16, 0.17, 0.88) are unremarkable.
- **(b) The PL-B specificity check is structurally near-tautological.** PL-B reuses the NC-P fit, so T_A cannot differ unless the code is broken. It is correct as specified.

### B3 N2 locked-model numbers: CONFIRMED (review\n3_indep_n2.py)

**Method.** The reviewer's own pipeline (code\review\indep_n2.py, from the N1/N2 review) imports nothing from nfharness, edf_reader, run_n2, n1b or n3:
- its own EDF reader and features;
- a Newton-IRLS logistic regression;
- the inner-LOFO τ scan and 4-of-5 smoothing;
- scoring by timescoring 0.0.7 AND by its own any-overlap scorer;
- Mann-Whitney AUROC;
- Garwood via gamma quantiles.

The split was written out from the prereg and hash-checked.

| subject | τ\* | TP/N_ref | FP (ts / own) | hours | FA/24 h | Garwood 95% /24 h | window AUROC | N2 rule |
|---|---|---|---|---|---|---|---|---|
| chb23 card | 0.05 | 4/4 | 1 | 4.00722 | 5.989 | [0.152, 33.37] | 0.993229 | PASS |
| chb23 reviewer | 0.05 | 4/4 | 1 / 1 | 4.00722 | 5.989 | [0.152, 33.37] | 0.993227 | PASS (grid 4, 8) |
| chb24 card | 0.99 | 4/4 | 8 | 2.000 | 96.0 | [41.45, 189.16] | 0.891194 | FAIL |
| chb24 reviewer | 0.99 | 4/4 | 8 / 8 | 2.000 | 96.0 | [41.45, 189.16] | 0.891193 | FAIL (grid 2, 5) |

- The training and test window counts match: chb23 17,826 / 177 positive / 14,425; chb24 7,195 / 100 / 7,198.
- The AUROC differences (≤ 2e-6) come from the different LR solver. They are the same size as in the N1/N2 review.
- **chb24 τ\* = 0.99 is the N2 §F3 fallback, not a bug.**
  - The train-OOF FA is 108/24 h at every τ from 0.05 upward and 120/24 h at 0.99, so no grid τ reaches ≤ 12/24 h.
  - The locked model therefore has no operating point on chb24 that meets the FA bar.
  - The chb24 FAIL is robust. It needs FP ≥ 6, and FP = 8. The Garwood lower bound, 41.4/24 h, is above 24/24 h.

### B4 Verdict strings: CONFIRMED
- **N3_verdict.json.** harness **PASS**; failed_items []; flags []; all 13 §4 items true (pytest 83/83, dry run PASS, run checks, rerun identity, and the 9 real-run gate items).
- **Model.** chb23 **PASS** (TP 4 ≥ 3 and FP 1 ≤ 4). chb24 **FAIL** (FP 8 > 5).
- **Overall.** The N2 rule for S = 2 gives **INCONCLUSIVE** (1 PASS, 1 FAIL). This is the correct literal application of prereg §5.
- **Label.** The harness passed, so the verdict counts under the label "N2 locked model, confirmatory on fresh subjects; harness gate pre-registered blind".
  - RESULTS_N3 correctly states that the confirmatory result is INCONCLUSIVE, not a PASS.

### B5 Determinism and provenance: CONFIRMED
- **Rerun.** The run 1 and rerun cards (fresh process, different start time) are **dict-equal excluding runtime**.
  - The reviewer's own canonical hash is 612f3768... for both.
  - The harness card_hash, recomputed, equals the stored value in both cards: **ce980b76...5fad22**.
- **Data.** 16/16 chb23/chb24 files, re-hashed now, equal the PhysioNet SHA256SUMS.txt entry, the card's input_sha256 and a manifest row marked verified = yes.
  - The files are 7 EDFs, 7 .seizures files and 2 summaries.
  - The byte total 549,440,512 EDF B equals the prereg, and the raw total is 2,062,274,867 B, under the 2.10e9 limit of decision B.
- **Budget.** Real run 86 s, peak 1,191 MB, which is within 15 min and 1.5 GB.

## Minor notes (no number changes)
- (i) The chb24 NC-P degeneracy prediction (4-9/10) missed (1/10). t_rm saturated in 8/20 replicates, but it rarely produced a never-alarm. RESULTS_N3 reports this honestly.
- (ii) PL-B's pooled event arm tripped (p 0.001) while literal Fisher did not (0.094). This is consistent with A1/A2 and is descriptive only.
- (iii) Caveats that remain valid and must stay in any report:
  - S = 2 and N_ref = 4 per subject, so the CP intervals are [0.40, 1.00];
  - FA is measured on peri-ictal data only;
  - chb24's repeat-patient status is UNVERIFIED, and it has no SUBJECT-INFO row;
  - the harness cannot see a label-free leak, such as a normaliser fitted on test data (F1 guard only).
