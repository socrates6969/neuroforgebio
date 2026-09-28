# REVIEW: N1b negative controls v2 (independent code review, verification gate)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Reviewer: independent code reviewer, 2026-09-26.
Scope: code\n1b\*.py and code\run_n1b.py, checked against prereg\N1b_negative_controls_v2.md (SHA-256 a67b2517...c4a6, the same as in the card).
Reported material checked: code\RESULTS_N1b.md, code\DEVIATIONS.md §N1b (including N1b-15), results\N1b_*.json and results\rerun\N1b_card.json.
Nothing in code\, results\ or prereg\ was modified. The reviewer's checks are code\review\n1b_*.py, and each writes a matching `*_out.json` and `*.log`.
Every check used the venv, ran in under 4 min and stayed under 700 MB peak. Planted-leak variants were patched in memory only.

## Summary

| # | item | status |
|---|---|---|
| 1a | Sampler S (exact enumeration, ictal-excluded, longest first, 300-s gap, ±30/60 tolerance) | **CONFIRMED** |
| 1b | PhantomVault access rules, order log (hash of s and h -> draw -> seal -> score) | **CONFIRMED** |
| 1c | Conditional-randomisation p-values (M = 999), Fisher combination, V1 and V2 | **CONFIRMED** |
| 1d | Rate-matched tau t_rm and the degeneracy flags (label-free, decided before the draw) | **CONFIRMED** |
| 1e | C3' exact enumeration, harness MC criteria (i) and (ii), PL-C | **CONFIRMED** |
| 1f | PL-A (25% of allowed test windows, with phantom labels, put into training and the normaliser fit; alignment); PL-B; PL-C | **CONFIRMED**, as specified |
| 2 | Is the "controls powerless" FAIL genuine? | **CONFIRMED genuine.** The FAIL is robust to every alternative reading tested. One design-level cause is documented: Fisher over discrete p-values with a point mass at p = 1 is very conservative. |
| 3 | nfharness unmodified; N2 byte-identical; card rerun identity | **CONFIRMED** |
| 4 | Verdict strings (N1b FAIL, N1' FAIL, N2 "not verifiable: code", no N1c) | **CONFIRMED** as the literal application |

No BUG was found. No finding puts the verdict at risk. Two notes follow (§5), and neither changes a number.

## 1. Fidelity

### 1a Sampler S: CONFIRMED (review\n1b_sampler_indep.py)
- **Method.** The check is an independent re-implementation built from notes\data\chbmit_selection.csv only. It does not use nfharness or the n1b code.
  - The causal split is rebuilt, and [on - 600, off + 900) is excluded, clipped to the file.
  - Validity is tested per integer onset by brute force.
  - Placement is longest first, with ties broken by (file order, seizure index). The valid (segment, onset) list is enumerated and `rng.integers(0, n)` picks one entry.
- **Table.** The §2.1 table is reproduced exactly: 5.81/9, 2.11/6; 1.81/4, 6.27/12; 4.90/4, 6.27/8. The durations also match.
- **Same draws.** On the same SeedSequence streams, the re-implementation gives placements identical to n1b.sampler in all 30 real replicates. This holds for:
  - stream 10 (training phantoms, with the N1b-15 condition);
  - stream 11 (test phantoms);
  - the first 50 stream-12 null placements of each replicate.
- **Exclusion.** No drawn phantom, tolerance included, touches excluded time or leaves its segment: 0 violations.
- **Exact enumeration.** The valid set is enumerated exactly, not by rejection. For example, the first test phantom has 6,461 / 20,857 / 21,133 valid pairs. The code made no empty-set redraws (card: null/test redraws 0).

### 1b PhantomVault and order: CONFIRMED (code read + review\n1b_card_recompute.py)
- **Training reads** go to a harness `LabelVault`. It holds only the training phantoms, and every test pseudo-record is a protected file (vault.py:209-211).
- **Scorer reads before `seal_test_phantoms`** raise `TestLabelAccessError` (vault.py:240-241). `release_test_labels` and every plant need `allow_planted_leak=True`.
- **No test-label read during the fit.** `run_split` gets a `DeferredScorer`, which returns None, so no test label is read inside the fit.
- **Captured tau.** The captured `select_tau` output is checked against `res["tau"]` (ncp.py:235).
- **Order log.** All 30 NC-P logs have the same sequence: draw_train_phantoms -> fit_run_split -> hash_scores_hyps -> degeneracy_decided -> draw_test_phantoms -> seal_test_phantoms -> score_observed -> null_draws.

### 1c p-values and Fisher: CONFIRMED
- **Formulas.** p_up = (1 + #{null >= obs})/1000 and p_lo uses <= (ncp.py:70-72). Each null placement is drawn afresh from the unconditioned sampler S on stream 12.
- **Observed statistics.**
  - Observed T_A is asserted equal to `nfharness.stats.auroc` with the Scorer's window labels.
  - Observed T_E is asserted equal to timescoring on every replicate.
- **Recomputed from the replicate records**, all bit-equal to the card:
  - NC-P Fisher: A up 0.8400, A lo 0.01858, E up 0.9954, E lo 0.99998. There are 23 retained replicates and 7 degenerate ones.
  - PL-A: A up 3.28e-24, E up 0.01218 (11 retained).
  - PL-B: 0.5129 (30 retained).
- **Sanity.**
  - Every p lies on the k/1000 grid, and p_up + p_lo >= 1.001.
  - Every zero-TP replicate has p_up = 1 exactly.
  - V1 and V2 were recomputed. The V2 limits are scaled by n/30 (N1b-8), which is a no-op here.

### 1d t_rm and degeneracy: CONFIRMED
- **t_rm.** It is the smallest grid tau at which the train-OOF events, after the 90-s merge and 300-s split, fall to <= 1.323/h of allowed training time. This is label-free.
  - If no tau qualifies, t_rm = 0.99 and the replicate is flagged. That happened in 11/30 NC-P replicates and 0/15 PL-A replicates.
- **ALWAYS/NEVER flags.** They are computed from h over the allowed test seconds before the test phantoms are drawn. The recomputed flags agree with coverage and n_events in all replicates.

### 1e C3' and PL-C: CONFIRMED (review\n1b_c3_pmf.py)
- **Exact pmf.** The card's pmf has mass 1, and its mean equals mu* = 0.0820475 (an exact fraction). The re-derived sigma*, q95 = 6/37 and a* = 0.04831 match the card.
- **Criteria.** (i) |0.08465 - 0.08205| = 0.0026 <= 0.0054. (ii) 0.059 <= 0.06865. PL-C: 0.673 > 0.06865, so it trips.
- **Agreement with the N1 review's independent enumeration** (c3_analytic): P(F1 <= 0.05) = 0.1903 here vs 0.1908 there, and the MC mean is 0.0826.
- **PL-C offset.** The offset (onset - first alarm start) mod T, applied with `np.roll`, puts the first alarm run on the seizure onset, as §4 requires.

### 1f Planted leaks: CONFIRMED as specified (review\n1b_pla_alt.py, n1b_card_recompute.py, n1b_plb_ties.py)
- **PL-A is real and correctly aligned.**
  - The reviewer reproduced PL-A chb01 r0 with the unchanged code. sha256(s, h) ab27dd97..., T_A 0.74485, p_A 0.003, t_rm 0.89 and p_E 0.065 are identical to the card.
  - All 1,898 leaked windows (floor(0.25 x 7,595) allowed test windows, 90 of them phantom-positive) were checked. For each one:
    - its feature row equals the ORIGINAL file's window at offset a + i;
    - its label equals the phantom window label recomputed from the drawn test phantoms;
    - 0 mismatches.
  - In all 15 PL-A replicates, the counts differ from the paired NC-P replicate by exactly the leak: training windows by n_leak and training positives by n_leak_positive.
  - The leaked windows form 24.9% of the phantom-positive windows on average. They are in every inner-CV fold and in the normaliser fit (they are not in any LOFO group), and they remain in test scoring.
- **PL-B.** tau = argmax over the grid of the test-phantom F1, with ties going to the smallest tau. The reviewer's reproduction matched the card's tau in 30/30 replicates. The T_A p-values are identical to NC-P in 30/30.

## 2. Is "controls powerless" genuine? CONFIRMED genuine

| sensitivity (NOT the prereg rule) | real PL-A T_E | real PL-B | synthetic PL-A T_E | real NC-P T_E up / lo |
|---|---|---|---|---|
| literal (prereg) | 0.0122 | 0.513 | 0.255 | 0.995 / 1.000 |
| Fisher including degenerate replicates as p = 1 | 0.114 | - | 0.679 | - |
| locked-rule tau arm | 0.149 | - | 0.814 | 0.995 |
| Lancaster mid-p in Fisher | **0.00041** | 0.049 | 0.011 | 0.52 / 0.79 |
| Stouffer | 0.9999 | - | 1.0 | - |
| PL-B ties -> largest tau (§4 gives no tie rule; 14/30 replicates have ties) | - | 0.288 | - | - |
| PL-A reading R2: "25% of the phantom-POSITIVE test windows" (real run, 15 replicates) | 0.491 (T_A 6.99e-10) | - | - | - |

- **N1b-15.** It conditions only the TRAINING phantoms on spanning >= 2 training files. Without it the unchanged harness raises "need both classes", so the literal alternative is a crash, not a more powerful control.
  - The test phantoms and the nulls are unaffected (§1a, identical draws), so exactness holds.
  - It has no pathway to the PL-A or PL-B signal. It was needed once (train_lofo redraws = 1).
- **Smoothing (4-of-5) and the tau grid.** Both are locked N2 objects that §1 says must not change.
  - The grid ceiling does not bind in PL-A: t_rm lies in 0.84-0.99, and 0/15 replicates are flagged.
  - In PL-B, 5/30 fits give F1 = 0 at every grid tau. The phantom-trained model's scores never produce a hit, so the choice of tau has nothing to exploit. This is a property of the data and the design.
- **Fisher handling of p = 1.** This is the one design-level source of lost power.
  - The p-values are exactly valid but discrete. Zero-TP replicates give p = 1 exactly, in 14/23 retained NC-P replicates and 64/77 synthetic ones.
  - As a result, the Fisher test is far below its nominal size: NC-P E up is 0.995 and the synthetic value is 1.0, where U(0,1) is expected.
  - With a mid-p, the real PL-A T_E would trip (4.1e-4).
  - However, (i) the prereg defines p_up explicitly with >=, so mid-p is not a literal reading. (ii) Even under mid-p, **PL-B (0.049) and the synthetic dry-run PL-A (0.011) still do not trip**, so N1b is FAIL under every variant.
  - For N3: combine the event arm with a test built for discrete p-values (for example, an exact pooled statistic summed over replicates, randomised per replicate) instead of Fisher on conservative p-values. This has to be preregistered blind.
- **Mechanism, confirmed only as far as stated.** The PL-A leak is real: T_A rises from 0.50 to 0.77, and alignment is verified. It rarely becomes a TP event, however, because the linear L2 model gets only 25% of the phantom windows, and 4/15 replicates never alarm at t_rm. The coder's "power property, not a code bug" diagnosis is consistent with everything above.

## 3. Hashes and identity: CONFIRMED (review\n1b_card_recompute.py)
- **nfharness.** The current SHA-256 of nfharness\*.py (15), edf_reader.py and run_n2.py (17 files) equals results\N2_run_card.json with 0 mismatches. The card's harness block also equals it. nfharness is unmodified.
- **N2 identity.** The card's N2 recompute equals results\N2_results.json by repr for tau, TP, FP, N_ref, hours and window AUROC in all 3 subjects.
  - The reviewer's in-process reproduction of all 30 NC-P fits matched the card's sha256(s, h) 30/30.
- **Card identity.** The card SHA-256 recomputed for run 1 and for the rerun equals the stored value in both cards: 355d7d30...21d9.
- **Code and prereg hashes.**
  - The n1b code hashes now equal the card and the synthetic card, so the code that ran is the code reviewed.
  - The prereg hashes now equal both cards.
  - The DEVIATIONS snapshot hash equals the card, and the snapshot already contains N1b-15, the pre-run disclosure.

## 4. Verdict: CONFIRMED as the literal application
- §5 step 2 is not met: the synthetic PL-A T_E Fisher is 0.255. §5 step 3 is not met: PL-A T_E is 0.0122 >= 0.0025 and PL-B is 0.513.
- §4 then says: "If any trip rule fails, N1b = FAIL (controls powerless)". So **N1b = FAIL**, and N1' = FAIL.
- §6 then says **N2 = "not verifiable: code"**, which is final for chb01/03/10 (N2 §8).
- §7: a DESIGN or power failure means no N1c on these subjects, and validation moves to N3.
- The validity side held and is correctly reported as not detecting a leak:
  - V1 and V2 PASS;
  - C3' (i) and (ii) PASS;
  - PL-C trips;
  - order, rerun and N2 identity PASS.
- **Report wording.** "no leak was detected" must not be read as "the harness is shown leak-free". The event-arm controls were shown to lack power, so their silence is uninformative.

## 5. Minor notes (no number changes)
- (i) RESULTS_N1b says PL-A "4/15 NEVER-ALARM". This is correct. In addition, 3 of the 11 retained PL-A replicates have zero TP, so p = 1.
- (ii) NC-P T_A lower-tail Fisher = 0.0186 (mean AUROC 0.475) passes V1 but is the closest to its bound. This is descriptive, and something to watch in N3.
- (iii) N1b-15 departs from the literal "only redraw rule" of §2.2. It was disclosed before the real run, is exactness-preserving and is judged acceptable.
