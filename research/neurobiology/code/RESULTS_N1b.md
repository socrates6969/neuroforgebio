# RESULTS: N1b negative controls v2 (POST-HOC redesign of N1(b)); CHB-MIT chb01, chb03, chb10

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Coder-verifier, cycle 2, 2026-09-26. Status: NOT YET REVIEWED (HIVE rule 8). Prereg: prereg\N1b_negative_controls_v2.md, SHA-256
a67b2517...c4a6, recorded in the card before any label was read. The N1 and N2 preregs match their locked hashes (27db9d27..., ed929ae0...).

## Verdict (strictly per prereg §5 and §6)

| item | verdict | basis |
|---|---|---|
| **N1b** | **FAIL (controls powerless in the event arm)** | Step 2 (the synthetic dry run) is not met, because PL-A did not trip on T_E. Step 3 is not met, because on real data **PL-A** (T_E) and **PL-B** did not trip. §4: "If any trip rule fails, N1b = FAIL (controls powerless), whatever the validity results." |
| **N1'** | **FAIL** | (a), (c), (d) and (e) are PASS (N1_verdict.json), but N1b is FAIL. |
| **N2** | **not verifiable: code** | §6: if N1b fails, N2 stays "not verifiable: code". Under N2 §8 this is final for chb01/03/10. The byte-identity check did pass: tau*, TP, FP, N_ref, H and AUROC are identical to N2_results.json. The locked-rule result would still be INCONCLUSIVE, but it is not reportable as a model result. |
| Abandonment (§7) | no N1c on these subjects | This failure is a DESIGN or power property, not a code bug. Harness validation moves to N3 (fresh subjects, blind prereg). |

Validity itself held: no leak was detected. NC-P V1 and V2 pass, C3' passes, the order log is correct in 30/30 replicates, and N2 is byte-identical.
What failed is **power**: two of the three planted leaks do not make the event-arm control fail.

## §5 steps

| step | result |
|---|---|
| 1 tests | pytest **68/68** pass: 54 N1/N2 tests plus 14 new tests in tests\test_n1b.py. The new tests cover the flag guard (every planted leak raises without `allow_planted_leak=True`), sampler S enumerating the valid set exactly on a hand fixture, the order log and PhantomVault access rules, the observational select_tau hook, the rank AUROC vs stats.auroc, the event arm vs timescoring, and the exact C3' pmf vs brute force. |
| 2 synthetic dry run (stream 16; 100 NC-P replicates; real layout) | KS of the pooled p_up(T_A) vs U(0,1): D 0.069, **p 0.70 (met)**. **PL-A did not trip**: Fisher up for T_A was 2.9e-21, but for T_E it was **0.25**. PL-B tripped (1.3e-9). C3' passed and PL-C tripped (both descriptive). One code-level fix was needed first (DEVIATIONS N1b-15, see below). |
| 3 real run | 385 s, 697 MB, within budget. No fallback was used (R 10, R_leak 5, M 999, M_C 1000). The run criteria are listed below. |
| 4 rerun | A fresh-process rerun gave a byte-identical card: SHA-256 **355d7d3020e1...e21d9** in both runs. |

## Real-run numbers vs prereg §8 predictions

| quantity | result | prediction | hit? |
|---|---|---|---|
| Hash checks | 15 nfharness/*.py + edf_reader.py + run_n2.py (17 files) = N2 run card. **nfharness was not modified.** | - | yes |
| §2.1 segment table | exact (5.81/9, 2.11/6; 1.81/4, 6.27/12; 4.90/4, 6.27/8) | - | yes |
| N2 identity | byte-identical in all 3 subjects (chb01 tau 0.05, TP 4, FP 5, AUROC 0.983523995568668; chb03 0.05/4/9; chb10 0.06/4/0) | P = 0.97 | yes |
| NC-P T_A | mean **0.475**, replicate SD 0.118; subject means 0.493 / 0.476 / 0.456; null mean 0.4998 | 0.50, SD ~0.15, subject means 0.40-0.60 | yes |
| NC-P Fisher | T_A up 0.840 / lo **0.0186**; T_E up 0.995 / lo 1.000. All >= 0.0025, so **V1 PASS** | ~U(0,1) | yes |
| NC-P t_rm | 0.37-0.98 in 18/30; **0.99 flagged in 11/30** (one replicate at 0.05) | 0.6-0.95 mostly; flag <= 3/30 | **no** |
| NC-P T_E | pooled phantom F1 **0.075** (TP 17, FP 319, N_ref 120); mean of the replicate null means 0.050 | ~0.05 (0.02-0.09) | yes |
| Degenerate (event arm) | **7/30** NEVER-ALARM, 0 ALWAYS-ALARM; 0/30 window-flagged. So **V2 PASS** (limits 10 and 3) | 0-3 of 30 | no (but V2 holds) |
| Locked-rule arm (descriptive) | tau* >= 0.5 in 29/30 (22/30 at 0.99); NEVER-ALARM 8/30 (27%); Fisher up 0.995 | tau* >= 0.5; NEVER 30-60% | mostly |
| **PL-A** | T_A mean 0.775 (subject means 0.718 / 0.810 / 0.796), Fisher up **3.3e-24** (trips). T_E mean 0.163 (pooled TP 19, FP 80, N_ref 60), 4/15 NEVER-ALARM, Fisher up **0.012** (**not < 0.0025**) | AUROC 0.90 (0.75-0.99); F1 ~0.4 (0.15-0.8); P(trip T_E) 0.85 | **no (T_E)** |
| **PL-B** | tau(test-optimal) spread over 0.05-0.99; T_E mean 0.136 (pooled TP 49, FP 750, N_ref 120); 0/30 degenerate; Fisher up **0.51** (**no trip**); specificity check: T_A p-values identical to NC-P in 30/30 | F1 ~0.2 (0.1-0.35); P(trip) 0.80 | **no** |
| C3' exact | mu* **0.08205** (exact fraction), sigma* 0.0572, q95 **6/37 = 0.162**, a* 0.0483, q99 8/37 = 0.216, P(F1 <= 0.05) 0.19 | mu* 0.082 +/- 0.003; q95 0.16-0.20 | yes |
| C3' harness MC (1,000, timescoring) | mean 0.0846: \|diff\| 0.0026 <= 0.0054 **(i) met**; above q95 0.059 <= 0.0686 **(ii) met** | P(PASS) 0.95 | yes |
| PL-C | mean F1 0.224; above q95 **0.673** > 0.0686, so it **trips** (3,100 forced offsets) | mean ~0.20; fraction ~0.4 (>= 0.25) | yes |
| Descriptive | N2 model pooled F1 0.632 > q99 0.216 | - | - |
| **N1b overall** | **FAIL** | P(PASS) = 0.6. The named main risks were PL-B power and PL-A power on T_E, and those are exactly what failed. | - |

## Why the event arm is powerless (for the methodologist; the mechanism is verified only as far as stated)

- **PL-A.** The leak works in the window arm: AUROC 0.50 rises to 0.77. The leaked windows are correctly aligned; in a scratch diagnostic, leaked positive windows scored 0.508 vs 0.410 for negatives.
  - However, only 25% of the phantom windows, scattered at random, are in training. The 4-of-5 smoothing, combined with a rate-matched tau near the grid top (1.3 events/h), rarely turns this into an alarm on a phantom.
  - Pooled TP was 19/60. There were 4/15 NEVER-ALARM replicates, and every p = 1 from a zero-TP replicate dilutes Fisher.
- **PL-B.** Maximising F1 over tau on the test phantoms mostly picks low tau (many FP) or a lucky high tau. With N_ref = 4 per subject, the conditional null at that same h has almost as much mass at the achieved F1, so the p-values are about U(0,1) (Fisher 0.51).
  - In other words, the exact conditional test of T_E given h cannot detect a leak that acts only through the choice of h among many poor hypotheses when there are only 4 references.
- **t_rm saturation.** 11/30 replicates hit 0.99 because the train-OOF rate never fell to 1.323/h. The phantom-trained model has no signal, so its high scores come in bursts.
- In the synthetic dry run the same PL-A T_E weakness appeared on white-noise features. That is why DEVIATIONS records it as a power property and not a code bug.

## Deviations (code\DEVIATIONS.md, section N1b)

- N1b-1 to N1b-14: INTERPRETATIONS, written before the dry run and the real run.
  - The unchanged run_split is used with its existing `scorer=` parameter (a DeferredScorer), plus an observational select_tau hook that captures the train-OOF scores.
  - PL-A is planted in the data as 1-window training pseudo-records.
  - Streams and pairing, exact C3' with integer convolution, and 100 dry-run replicates in total.
- **N1b-15, DEVIATION found in the dry run.** Sampler S could put all training phantoms in one training file, and the harness LR then raised "need both classes" in a LOFO fold.
  - Fix: the training-phantom draw is redrawn until the phantoms span >= 2 training files. This was needed once on the real data.
  - Test phantoms and nulls are unaffected, so exactness holds. No harness file was changed.
- DEVIATIONS.md was snapshotted into results\N1b_DEVIATIONS_snapshot.md at the start of each run (hash 42dc7765... in both runs). The run log was appended only afterwards.

## Files

- Code (new): code\n1b\ (segments, sampler, vault, ncp, c3prime, synth, figures), code\run_n1b.py, code\tests\test_n1b.py.
- Results: results\N1b_card.json (real run 1), results\rerun\N1b_card.json, results\N1b_synthetic.json, results\N1b_verdict.json, results\N1b_DEVIATIONS_snapshot.md.
- Figures: figures\N1b_controls.png/.svg (real run), figures\N1b_synthetic_dryrun.png/.svg.
- Environment: Python 3.12.10, numpy 2.5.3, scipy 1.18.1, timescoring 0.0.7, BLAS threads = 1, seed 20261001, streams k = 10-16. Nothing was installed.
