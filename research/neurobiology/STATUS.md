# STATUS: neurobiology program (queen). Owner: Marius Carlsson. Updated 2026-09-26
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims (EU MDR 2017/745 Rule 11 / FDA SaMD; clinical use needs clearance and ethics approval).

## Cycle 1: COMPLETE (reviewed)
| Step | Output | Result |
|---|---|---|
| Literature and methods | lit\methods.md (27 graded entries), notes\harness_requirements.md, notes\facts.md | done |
| Data | CHB-MIT chb01/chb03/chb10: 29 EDFs, 35.7 h, 21 seizures, 1.51 GB, 53/53 SHA-256 verified (data\manifests\) | done. The 4th subject did not fit the 2 GB budget |
| Preregs | prereg\N1_harness_controls.md, prereg\N2_baseline_detection.md (locked blind) | done |
| Harness | code\nfharness\ + 54 pytest | built |
| N1 harness controls | (a) leak detection PASS; (b) negative controls FAIL; (c) determinism PASS; (d) 12/12 guards PASS; (e) scorer equivalence PASS | **N1 FAIL**, caused by a prereg design flaw in (b), not a code bug (review) |
| N2 baseline detection | per subject 4/4 test seizures; FA/24 h 32.9 / 27.0 / 0.0; AUROC 0.984 / 0.989 / 0.975 | **not verifiable** (harness not validated). The counterfactual rule verdict is INCONCLUSIVE (chb01, chb03 FA in the grey zone; chb10 PASS) |
| Review | code\REVIEW_N1_N2.md: leak-proofness, metrics (exact recompute), provenance CONFIRMED; no bug | done |

Verified and deliverable now: split engine, guards, leak meter, event scorer, CIs, provenance/evaluation card (PLATFORM_FEATURES.md 1-6).
Not verified: negative-control suite, baseline detector performance.

## Cycle 2 (2026-09-26): N1b done and reviewed; N3 PAUSED
| Step | Result |
|---|---|
| N1b redesigned negative controls (post-hoc, labelled) | **FAIL: controls powerless** in the event arm. Validity held: no leak detected, C3' exact null OK, N2 byte-identical. But planted leaks PL-A (event arm) and PL-B did not trip them. The window arm tripped PL-A (Fisher 3e-24). Review code\REVIEW_N1b.md: genuine, literal, no bug. |
| N2 | stays "not verifiable" on chb01/03/10 (final under the N2 and N1b rules) |
| N3 power analysis (synthetic only) | Literal Fisher on discrete p has size ~0, which explains the N1b failure. The event arm needs >= 4 subjects x 4 seizures (PL-A) or >= 3 x 7-10 (PL-B) for 0.8 power, which is infeasible here. The window arm has power 0.96-1.00 at 2 subjects x 4. notes\n3_power.md (reviewed later: CONFIRMED in code\REVIEW_N3.md) |
| N3 prereg (blind, fresh subjects chb23 + chb24) | Locked, SHA 954e4abb. Window arm = formal leak gate; event arm = validity only; mandatory select_tau violation test; the locked N2 model and rule re-run unchanged |
| Data decision | Option B: +0.549 GB, total ~2.06 GB (reported to lead) |
| Harness decision | MERGE: nf_eval is the canonical platform core; port the validated nfharness pieces; nfharness stays the reference oracle (notes\harness_decision_audit.md) |
| N3 run | PAUSED on owner request (RAM). See "Paused at" below |

## N3: COMPLETE and REVIEWED (resumed 2026-09-26; code\RESULTS_N3.md, code\REVIEW_N3.md)
- Harness validation on fresh subjects chb23/chb24 (blind prereg, locked before download): **PASS** on all 13 gates.
  The window-arm planted leak tripped (p 5.9e-16); the event arm is valid; C3'/PL-C/PL-B-code pass; the rerun is identical; 16/16 files SHA-verified.
- Locked N2 model (unchanged): chb23 **PASS** (4/4, FP 1 in 4.0 h); chb24 **FAIL** (4/4, FP 8 in 2.0 h, FA 96/24 h, Garwood 41-189). Overall **INCONCLUSIVE**.
  The chb23/24 test files are burned. A new model needs a new prereg on other open data.
- Power analysis CONFIRMED by independent review. One minor float32 tie-break bug in power_sim changes no conclusion.
- Follow-on: motor-readout (M1 done; M1b queued), then the harness merge + nf_eval review.

## Motor-readout cycle 1 (M1): COMPLETE and REVIEWED (motor-readout\code\RESULTS_M1.md, REVIEW_M1.md)
- Prereg M1 (blind, SHA 9eada9d7). Data: DANDI 000138 MC_Maze_Large, 001201 LINK (9 sessions over 0-730 d), EEGMMIDB subset; 730 MB, 131 files SHA-verified; all CC-BY/ODC-By, no sign-up.
- **Harness FAIL.** The PL-1 bar is analytically unreachable (max rise 0.035 vs bar 0.10), and the NC1 bits/s bar is mis-specified (coherence ignores sign/gain). Both are review-confirmed; there is no leak.
  So H1-H5 are "not verifiable: harness", and H6 was NOT TESTED (A4 budget cut).
- Exploratory (review reproduced to 1e-7, NOT verified):
  - GRU R2 0.812 > ridge 0.669 >> Kalman 0.286. The low KF follows from the prereg spec (20 ms, no lag); lag or 100 ms bins gives 0.38-0.45.
  - Bits/s (coherence bound, null-corrected): 31.9 / 25.6 / 13.3.
  - A day-0 decoder fails within +3 days on LINK (median retention rho -2.1 at >= 30 d). FA-Procrustes alignment is no better than re-z-scoring, and R2 is ~0 at >= 151 d.
- Next: M1b. Corrected controls plus a confirmatory test on FRESH data (e.g. MC_Maze_Medium/Small and unused LINK sessions), labelled post-hoc-informed. Then review, then THEORY.md.

## (historical) PAUSED (owner request to free memory; queen stopped 2026-09-26)
Lead-accepted decisions (recorded, not yet executed):
1. Harness: MERGE, with nf_eval (feature/research-algos) as the canonical platform core and nfharness as the reviewed golden oracle. Port the validated
   nfharness pieces into nf_eval (timescoring oracle test, Garwood, latency, the F1-F9/S7 guards, leak meter, input provenance, by-file bootstrap). The 10 conventions
   to lock are listed in notes\harness_decision_audit.md. nf_eval still needs an independent review (it is synthetic-only). PLATFORM_FEATURES.md is to be updated on resume.
2. N3 data: chb23 + chb24 (+0.549 GB, total ~2.06 GB); the cycle-1 raw files are kept for reviewers.
Workers: the N3 coder has stopped (state below); the N3 power/prereg mathematician finished. No agents are running.
Next on resume, in order:
 a) N3: finish the download and verify SHA; DEVIATIONS N3, tests and figures; synthetic dry run; real run; rerun; RESULTS_N3.md; independent review (including notes\n3_power.md and power_sim.py).
 b) Motor-readout track (QUEUED, not started; brief motor-readout\BRIEF.md). Mathematician covers theory (Shannon/Wolpaw ITR, decoders, latency and stability,
    nonstationarity) + a pre-registered test on an open motor dataset (e.g. NLB MC_Maze/DANDI; licence and size verified first; <= 1.5 GB), Kalman vs linear/Riemannian vs
    small RNN, through the leak-proof harness; then coder, independent review, THEORY.md. Decoding only.
 c) Harness merge work (after the N3 verdict), and the nf_eval review.
Power result, recorded as the lead asked: the event-arm negative controls need >= 4 subjects x 4 test seizures (PL-A) or >= 3 x 7-10 (PL-B) for power 0.8.
At 2 x 4 they reach 0.59 / 0.31. The window arm reaches 0.96-1.00 at 2 x 4.

## N3 run complete (2026-09-26, coder-verifier; historical note, SUPERSEDED: independently reviewed afterwards, see code\REVIEW_N3.md and the "N3: COMPLETE and REVIEWED" section)
- **N3 harness = PASS.** N2 locked model: chb23 PASS, chb24 FAIL (FP 8 in 2 h), so the overall result is **INCONCLUSIVE**.
- Run facts: rerun card identical (ce980b76...); pytest 83/83. Details are in code\RESULTS_N3.md.
- Next: independent review of N3 (including notes\n3_power.md and power_sim.py).

## Motor-readout M1b (2026-09-27): prereg LOCKED (c30873de); power-check run was cut off by an API error before its verdict; no fresh download. Idle pending the lead's Rust/Python decision and a bci-queen compute slot. bci-hive 002 confirmed no-overlap (read-only use of the motor data granted).
