"""N3: harness validation on FRESH CHB-MIT subjects chb23/chb24 + the locked N2 model re-run (prereg\\N3_harness_validation_fresh.md).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.
Usage (prereg §3 order of work):
  python run_n3.py --phase synthetic --tmp DIR   # step 3: dry run on synthetic EDFs with the chb23/chb24 layout (stream 26)
  python run_n3.py --phase real                  # step 5: real run -> results\\N3_card.json, cards, figures
  python run_n3.py --phase real --rerun          # step 6: fresh-process rerun -> results\\rerun\\N3_card.json
  python run_n3.py --phase final                 # steps 2 + 6 + the §4/§5 verdicts -> results\\N3_verdict.json
nfharness, edf_reader.py, run_n2.py and n1b are imported UNCHANGED; their SHA-256 are checked before anything else.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import datetime as dt  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

CODE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CODE)
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
sys.path.insert(0, CODE)

import numpy as np  # noqa: E402
from scipy.stats import kstest  # noqa: E402

from nfharness import config as C  # noqa: E402
from nfharness.card import RUO, subject_figure, write_card  # noqa: E402
from nfharness.data import load_records, sha256_file, verify_inputs  # noqa: E402
from nfharness.errors import ThresholdSelectionError  # noqa: E402
from nfharness.features import FEATURE_NAMES, assert_whitelist, file_features  # noqa: E402
from nfharness.labels import LabelVault  # noqa: E402
from nfharness.pipeline import run_split, summarize  # noqa: E402
from nfharness.postprocess import TaggedScores, hypothesis_mask, select_tau  # noqa: E402
from nfharness.provenance import card_hash, code_hashes, dumps, environment, peak_rss_mb  # noqa: E402
from nfharness.scoring import Scorer, mask_events  # noqa: E402
from nfharness.splits import assert_split_hash, causal_splits, split_hash, split_string  # noqa: E402

import run_n2  # noqa: E402  (unchanged; subject_verdict = the N2 §4 decision rule)
from n1b.c3prime import c3_criteria, exact_distribution, file_counts, harness_mc  # noqa: E402
from n1b.ncp import EventArm, degeneracy, pvals  # noqa: E402
from n1b.segments import build_pseudo  # noqa: E402
from n1b.vault import DeferredScorer, OrderLog, sha_scores_hyps  # noqa: E402

import n3  # noqa: E402
from n3 import (ALLOWED_PREREG, ALPHA, EXPECTED_SPLIT_HASH_N3, FP_GRID_PREREG, K_C3MC, K_DRY, K_NULL, K_PLC,  # noqa: E402
                M_C, M_NULL, PL_A10_FRAC, R_LEAK, R_NCP, TEST_DURS_PREREG, n3_streams, pla_fraction, rng)
from n3.montage import assert_montage  # noqa: E402
from n3.pooled import f1_float, fisher, mid_p, null_draws_full, pooled_test  # noqa: E402
from n3.verdict import event_gate, fp_grid, harness_verdict, model_overall, pla_trips, window_gate  # noqa: E402

SUBJECTS = list(n3.SUBJECTS)
N3_PREREG = "N3_harness_validation_fresh.md"
N3_PREREG_SHA = "954e4abba139cde8d9a37e0ae43190416389315719d7d7451d26b394e87fc32b"   # results\cards\N3_prereg_lock.json
PREREG_LOCKED = {"N1_harness_controls.md": "27db9d27f5b6ac2e0f49826c6b3eb9625b8e1633434ae70cf62a7e10f09fc93b",
                 "N2_baseline_detection.md": "ed929ae0e5182827352928225cf40865a8bee5f6b5da089be5a6600e6678e21c",
                 "N1b_negative_controls_v2.md": "a67b251734d59097b0cd516162e054ecb72737f27344868a45b3c40f1d7fc4a6",
                 N3_PREREG: N3_PREREG_SHA}
PEAK_FLAG = "FA on peri-ictal data only"


# --------------------------------------------------------------------------------------------- hashes
def n3_code_hashes():
    files = sorted(glob.glob(os.path.join(CODE, "n3", "*.py"))) + [os.path.abspath(__file__)] + \
        sorted(glob.glob(os.path.join(CODE, "tests", "test_n3*.py")))
    return {os.path.relpath(f, CODE).replace("\\", "/"): sha256_file(f) for f in files}


def locked_code_check():
    """§1: nfharness/*.py + edf_reader.py + run_n2.py = results\\N2_run_card.json (17 files); n1b/*.py + run_n1b.py +
    tests/test_n1b.py = results\\N1b_card.json (the reviewed N1b code)."""
    with open(os.path.join(RES, "N2_run_card.json")) as fh:
        ref = json.load(fh)["provenance"]["code_sha256"]
    now = code_hashes(CODE, extra=[os.path.join(CODE, "run_n2.py")])
    mism = sorted(k for k in set(ref) | set(now) if ref.get(k) != now.get(k))
    with open(os.path.join(RES, "N1b_card.json")) as fh:
        ref_b = json.load(fh)["provenance"]["n1b_code_sha256"]
    now_b = {k: sha256_file(os.path.join(CODE, *k.split("/"))) for k in ref_b}
    mism_b = sorted(k for k in ref_b if ref_b[k] != now_b[k])
    return {"nfharness": {"n_files": len(now), "all_match_N2_run_card": not mism, "mismatches": mism, "sha256": now},
            "n1b": {"n_files": len(now_b), "all_match_N1b_card": not mism_b, "mismatches": mism_b, "sha256": now_b},
            "config_hash_literal": C.LOCKED_CONFIG_HASH_LITERAL,
            "config_hash_recomputed_equal": bool(C.LOCKED_CONFIG_HASH == C.LOCKED_CONFIG_HASH_LITERAL),
            "all_ok": bool(not mism and not mism_b and C.LOCKED_CONFIG_HASH == C.LOCKED_CONFIG_HASH_LITERAL)}


def prereg_hashes():
    return {n: sha256_file(os.path.join(ROOT, "prereg", n)) for n in PREREG_LOCKED}


# --------------------------------------------------------------------------------------------- preparation
def prepare(raw, subjects, real, stage_t, log):
    t = time.time()
    records, ann = load_records(raw, subjects)            # EDF headers (start time, duration) + summaries only
    montage = assert_montage([r.path for r in records])   # E1, header only, BEFORE any signal is read
    log.add("montage_E1_asserted", "files=%d" % len(montage))
    counts = {f: len(v) for f, v in ann.items()}
    splits = causal_splits(records, counts)
    shash = assert_split_hash(splits, EXPECTED_SPLIT_HASH_N3) if real else split_hash(splits)
    log.add("split_hash", shash)
    stage_t["records_split_s"] = time.time() - t
    t = time.time()
    assert_whitelist(FEATURE_NAMES)
    feats = {r.name: file_features(r) for r in records}
    stage_t["features_s"] = time.time() - t
    fhash = {f: hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest()[:16] for f, v in feats.items()}
    pseudo, table = {}, {}
    for si, s in enumerate(subjects):
        sp, pf = build_pseudo(splits[s], ann, feats, si)
        feats.update(pf)
        pseudo[s] = sp
        table[s] = {"train_allowed_h": sp.train_allowed_h, "test_allowed_h": sp.test_allowed_h,
                    "train_segments_s": [r.duration for r in sp.split.train],
                    "test_segments_s": [r.duration for r in sp.split.test],
                    "train_phantom_durations": [d for d, _, _ in sp.train_seizure_durations],
                    "test_phantom_durations": [d for d, _, _ in sp.test_seizure_durations],
                    "n_inner_lofo_groups": len(sp.groups)}
    return records, ann, splits, shash, feats, fhash, pseudo, table, montage


def table_check(table, subjects, real_names):
    ok = {}
    for s, rn in zip(subjects, real_names):
        a, t = ALLOWED_PREREG[rn], table[s]
        c = [round(t["train_allowed_h"], 2) == a["train_h"], round(t["test_allowed_h"], 2) == a["test_h"],
             sorted(t["test_segments_s"]) == sorted(a["test_segments_s"]),
             t["test_phantom_durations"] == TEST_DURS_PREREG[rn]]
        if "train_segments_s" in a:
            c.append(sorted(t["train_segments_s"]) == sorted(a["train_segments_s"]))
        ok[s] = bool(all(c))
    return ok


# --------------------------------------------------------------------------------------------- N2 model (steps i, vii)
def n2_fit(subjects, records, ann, splits, feats, log):
    """Step (i): locked N2 fit with a DeferredScorer (no test label read); s and h hashed and logged."""
    out = {}
    for s in subjects:
        sp = splits[s]
        subj = [r for r in records if r.subject == s]
        v = LabelVault(ann, {r.name: r.duration for r in subj}, protected_files=sp.test_names, name="N3-N2-" + s)
        res = run_split(sp, feats, v, [[r] for r in sp.train], purpose="N3 N2 locked model", scorer=DeferredScorer())
        sha = sha_scores_hyps(sp.test_names, res["p"], [res["hyp"]])
        log.add("N2_fit_scores_hyps_hashed", "%s tau=%r sha256=%s" % (s, res["tau"], sha))
        out[s] = {"res": res, "vault": v, "sha256_scores_hyps": sha}
    return out


def n2_score(prim, subjects, splits, log):
    """Step (vii): the harness Scorer reads the real test labels; N2 §3 metrics; N2 §4 rule."""
    rng_boot = C.rng(C.STREAM_BOOTSTRAP)
    metrics, grids = {}, {}
    for s in subjects:
        sp, res, v = splits[s], prim[s]["res"], prim[s]["vault"]
        sc = Scorer(v, "N3 N2 scoring (step vii)")
        res["per_file"] = {f: sc.score_file(f, res["hyp"][f]) for f in sp.test_names}
        res["ywin"] = {f: sc.ref_window_labels(f) for f in sp.test_names}
        m = summarize(res, sp.test, rng_boot)
        m["verdict"], m["flags"] = run_n2.subject_verdict(s, m)
        m["flags"].append(PEAK_FLAG)
        g = fp_grid(m["hours"])
        grids[s] = {"computed": list(g), "prereg": list(FP_GRID_PREREG.get(s, g)), "equal": list(g) == list(FP_GRID_PREREG.get(s, g))}
        m["fp_grid_meet_max_inconclusive_max"] = list(g)
        m["n_train_windows"], m["n_train_pos_windows"] = res["n_train_windows"], res["n_train_pos"]
        m["lr_converged_all_fits"], m["n_fits"] = res["converged_all"], res["n_fits"]
        m["N_ref_is_4"] = bool(m["n_ref"] == 4)
        metrics[s] = m
        log.add("N2_scored", "%s tp=%d fp=%d n_ref=%d verdict=%s" % (s, m["tp"], m["fp"], m["n_ref"], m["verdict"]))
    return metrics, grids


def plb_code_inprocess(prim, subjects, splits):
    """PL-B-code on the real N2 test scores: select_tau with test-tagged scores must raise ThresholdSelectionError."""
    out = {}
    for s in subjects:
        sp = splits[s]
        ts = TaggedScores("test", {f: prim[s]["res"]["p"][f] for f in sp.test_names}, {r.name: r.duration for r in sp.test})
        try:
            select_tau(ts, lambda masks: 0.0)
            out[s] = {"raised": False, "error": None}
        except ThresholdSelectionError as e:
            out[s] = {"raised": True, "error": "ThresholdSelectionError: %s" % e}
    return {"per_subject": out, "all_raised": bool(all(v["raised"] for v in out.values()))}


# --------------------------------------------------------------------------------------------- controls
def _replicate_nulls(ncp, pub, priv, key_prefix, M, extra_arm=None):
    """Re-create the stream-22 generator of the replicate and redo its null draws keeping integer counts; verify
    bit-identity with what n1b computed."""
    ts, durs = priv["ts"], priv["durs"]
    h_rm = {f: hypothesis_mask(priv["p"][f], pub["t_rm"], durs[f]) for f in ts.names}
    arms = {"rm": EventArm(ts, h_rm)}
    if extra_arm is not None:
        arms["plb"] = EventArm(ts, extra_arm)
    TA, cnt = null_draws_full(ts, arms, priv["te_len"], priv["te_order"], rng(*key_prefix, K_NULL, priv["si"], priv["rep"]), M)
    f1n = np.array([f1_float(*r) for r in cnt["rm"]])
    obs = arms["rm"].score(priv["pl_te"])
    ok = bool(np.array_equal(TA, priv["TAn"]) and float(f1n.mean()) == pub["E_rm"]["T_E_null_mean"]
              and pvals(pub["E_rm"]["T_E"], f1n) == (pub["E_rm"]["p_up"], pub["E_rm"]["p_lo"])
              and tuple(obs[1:]) == (pub["E_rm"]["tp"], pub["E_rm"]["fp"], pub["E_rm"]["n_ref"]))
    return cnt, ok, arms


def pooled_block(reps, nulls, deg_key):
    keep = [i for i, r in enumerate(reps) if not deg_key(r)]
    obs = [reps[i]["_obs"] for i in keep]
    arrs = [nulls[i] for i in keep]
    pf = pooled_test(obs, arrs, "F1")
    ptp = pooled_test(obs, arrs, "TP")
    mids = [mid_p(o, a) for o, a in zip(obs, arrs)]
    fm, nm = fisher(mids)
    return {"pooled_SigmaF1": pf, "pooled_SigmaTP_descriptive": ptp, "mid_p_fisher_up_descriptive": fm, "n_mid_p": nm,
            "n_retained": len(keep), "n_degenerate": len(reps) - len(keep),
            "n_degenerate_by_subject": {s: sum(1 for i, r in enumerate(reps) if r["subject"] == s and i not in keep)
                                        for s in sorted({r["subject"] for r in reps})}}


def controls_block(pseudo, feats, subjects, R, R_leak, key_prefix, M, stage_t, log):
    with n3_streams() as ncp:
        t = time.time()
        ncp_reps, ncp_nulls, plb_reps, plb_nulls, verify = [], [], [], [], []
        for s in subjects:
            for rep in range(R[s] if isinstance(R, dict) else R):
                pub, priv = ncp.run_replicate(pseudo[s], feats, rep, key_prefix=key_prefix, M=M)
                plb = ncp.planted_threshold_leak(priv, pub, allow_planted_leak=True, M=M)
                h_plb = {f: hypothesis_mask(priv["p"][f], plb["tau_test_optimal"], priv["durs"][f]) for f in priv["ts"].names}
                cnt, ok, arms = _replicate_nulls(ncp, pub, priv, key_prefix, M, extra_arm=h_plb)
                f1b = np.array([f1_float(*r) for r in cnt["plb"]])
                ok_b = bool(pvals(plb["T_E"], f1b) == (plb["p_up"], plb["p_lo"]))
                verify.append(ok and ok_b)
                pub["_obs"] = (pub["E_rm"]["tp"], pub["E_rm"]["fp"], pub["E_rm"]["n_ref"])
                plb["_obs"] = (plb["tp"], plb["fp"], plb["n_ref"])
                ncp_reps.append(pub)
                ncp_nulls.append(cnt["rm"].astype(np.int16))
                plb_reps.append(plb)
                plb_nulls.append(cnt["plb"].astype(np.int16))
                del priv
        log.add("NC-P_and_PL-B_done", "n=%d" % len(ncp_reps))
        stage_t["ncp_plb_s"] = time.time() - t
        leak = {}
        for name, frac, reps_range in (("PL-A", None, range(0, R_leak)), ("PL-A10", PL_A10_FRAC, range(R_leak, 2 * R_leak))):
            t = time.time()
            reps_, nulls_ = [], []
            for s in subjects:
                for rep in reps_range:
                    if frac is None:
                        pub, priv = ncp.run_replicate(pseudo[s], feats, rep, key_prefix=key_prefix, plant="PL-A",
                                                      allow_planted_leak=True, M=M)
                    else:
                        with pla_fraction(frac):
                            pub, priv = ncp.run_replicate(pseudo[s], feats, rep, key_prefix=key_prefix, plant="PL-A",
                                                          allow_planted_leak=True, M=M)
                    cnt, ok, _ = _replicate_nulls(ncp, pub, priv, key_prefix, M)
                    verify.append(ok)
                    pub["_obs"] = (pub["E_rm"]["tp"], pub["E_rm"]["fp"], pub["E_rm"]["n_ref"])
                    pub["plant_label"] = name
                    reps_.append(pub)
                    nulls_.append(cnt["rm"].astype(np.int16))
                    del priv
            leak[name] = (reps_, nulls_)
            log.add(name + "_done", "n=%d" % len(reps_))
            stage_t[name + "_s"] = time.time() - t
        agg = ncp.aggregate(ncp_reps)
        agg_a = ncp.aggregate(leak["PL-A"][0])
        agg_a10 = ncp.aggregate(leak["PL-A10"][0])
    deg_rm = lambda r: r["degeneracy_rm"]["degenerate"]  # noqa: E731
    ev = pooled_block(ncp_reps, ncp_nulls, deg_rm)
    ev_a = pooled_block(*leak["PL-A"], deg_rm)
    ev_a10 = pooled_block(*leak["PL-A10"], deg_rm)
    ev_b = pooled_block(plb_reps, plb_nulls, lambda r: r["degeneracy"]["degenerate"])
    fb_lit, nb = fisher([r["p_up"] for r in plb_reps if not r["degeneracy"]["degenerate"]])
    v1a, v2a = window_gate(agg["fisher"]["T_A_up"], agg["fisher"]["T_A_lo"], agg["n_window_flagged"], len(ncp_reps))
    v1e = event_gate(ev["pooled_SigmaF1"]["p_up"], ev["pooled_SigmaF1"]["p_lo"])
    spec_n = sum(bool(r["T_A_pvalues_identical_to_NCP"]) for r in plb_reps)
    strip = lambda L: [{k: v for k, v in r.items() if k != "_obs"} for r in L]  # noqa: E731
    return {
        "NC-P": {"aggregate_N1b": agg, "event_arm": ev, "V1-A": v1a, "V2-A": v2a, "V1-E": v1e,
                 "T_A_fisher_up": agg["fisher"]["T_A_up"], "T_A_fisher_lo": agg["fisher"]["T_A_lo"],
                 "T_A_replicate_mean": agg["T_A_mean"], "T_A_replicate_sd": agg["T_A_sd"],
                 "T_A_sd_by_subject": {s: float(np.std([r["T_A"] for r in ncp_reps if r["subject"] == s], ddof=1))
                                       for s in subjects if sum(r["subject"] == s for r in ncp_reps) > 1},
                 "literal_fisher_T_E_descriptive": {"up": agg["fisher"]["T_E_up"], "lo": agg["fisher"]["T_E_lo"],
                                                    "n": agg["fisher_n"]["T_E"]},
                 "replicates": strip(ncp_reps)},
        "PL-A": {"aggregate_N1b": agg_a, "event_arm_descriptive": ev_a, "fisher_T_A_up": agg_a["fisher"]["T_A_up"],
                 "trips_T_A": pla_trips(agg_a["fisher"]["T_A_up"]), "T_A_mean": agg_a["T_A_mean"],
                 "replicates": strip(leak["PL-A"][0])},
        "PL-A10_descriptive": {"aggregate_N1b": agg_a10, "event_arm": ev_a10, "fisher_T_A_up": agg_a10["fisher"]["T_A_up"],
                               "would_trip_T_A": pla_trips(agg_a10["fisher"]["T_A_up"]), "T_A_mean": agg_a10["T_A_mean"],
                               "replicates_used": "PL-A10 replicate indices %d..%d (stream 23 continued; DEVIATIONS N3-5)"
                               % (R_leak, 2 * R_leak - 1), "replicates": strip(leak["PL-A10"][0])},
        "PL-B_descriptive": {"event_arm": ev_b, "literal_fisher_up": fb_lit, "literal_fisher_n": nb,
                             "specificity_T_A_identical_n": spec_n, "specificity_n_total": len(plb_reps),
                             "specificity_holds": bool(spec_n == len(plb_reps)),
                             "tau_test_optimal_values": [r["tau_test_optimal"] for r in plb_reps],
                             "replicates": strip(plb_reps)},
        "null_recompute_bit_identical_to_n1b": {"n": len(verify), "all": bool(all(verify))},
        "_raw": (ncp_reps, ncp_nulls),     # popped by the callers; never written to a card
    }


def grouped_pooled(reps, nulls, group_size=10):
    """Dry run, DESCRIPTIVE (DEVIATIONS N3-8): the pooled SigmaF1 p over disjoint groups of replicates with the real-run
    shape (replicates g*10 .. g*10+9 of every subject pooled into one statistic)."""
    deg = lambda r: r["degeneracy_rm"]["degenerate"]  # noqa: E731
    n_g = max(r["replicate"] for r in reps) // group_size + 1
    out = []
    for g in range(n_g):
        idx = [i for i, r in enumerate(reps) if g * group_size <= r["replicate"] < (g + 1) * group_size]
        pb = pooled_block([reps[i] for i in idx], [nulls[i] for i in idx], deg)
        out.append({"group": g, "n_retained": pb["n_retained"], "p_up": pb["pooled_SigmaF1"]["p_up"],
                    "p_lo": pb["pooled_SigmaF1"]["p_lo"]})
    return out


def c3_block(prim, subjects, splits, key_prefix, M_C_, stage_t, log):
    t = time.time()
    scorers = {s: Scorer(prim[s]["vault"], "N3 C3prime") for s in subjects}
    files = [(s, f, np.asarray(prim[s]["res"]["hyp"][f], dtype=np.int8)) for s in subjects for f in splits[s].test_names]
    refs = {f: scorers[s]._ref(f) for s, f, _ in files}
    n_ref = sum(int(mask_events(refs[f])[0].size) for _, f, _ in files)
    ex, pmf = exact_distribution([file_counts(refs[f], h) for _, f, h in files], n_ref)
    stage_t["c3_exact_s"] = time.time() - t
    t = time.time()
    f1_mc, _ = harness_mc(files, scorers, rng(*key_prefix, K_C3MC, 0, 0), M_C_)
    crit = c3_criteria(f1_mc, ex)
    stage_t["c3_mc_s"] = time.time() - t
    log.add("C3prime_done", "")
    t = time.time()
    onset = {f: (int(mask_events(refs[f])[0][0]) if mask_events(refs[f])[0].size else None) for _, f, _ in files}
    f1_plc, n_forced = harness_mc(files, scorers, rng(*key_prefix, K_PLC, 0, 0), M_C_, plant="PL-C",
                                  allow_planted_leak=True, seizure_onset=onset)
    crit_c = c3_criteria(f1_plc, ex)
    stage_t["pl_c_s"] = time.time() - t
    log.add("PL-C_done", "")
    return {"n_files": len(files), "N_ref": n_ref, "H_hours": sum(h.size for _, _, h in files) / 3600.0, "exact": ex,
            "exact_pmf": pmf, "mc": crit, "PASS": bool(crit["crit_i"] and crit["crit_ii"]),
            "PL-C": {"mean_f1": float(f1_plc.mean()), "frac_above_q95": crit_c["frac_above_q95"], "bound_ii": crit_c["bound_ii"],
                     "n_forced_offsets": n_forced, "trip": bool(crit_c["frac_above_q95"] > crit_c["bound_ii"])},
            "_f1_mc": f1_mc, "_f1_plc": f1_plc}


# --------------------------------------------------------------------------------------------- phases
def _ks(ps):
    ps = [p for p in ps if p == p]
    if not ps:
        return None
    one = kstest(ps, "uniform", alternative="greater")
    two = kstest(ps, "uniform")
    frac = float(np.mean(np.asarray(ps) < 0.05))
    return {"n": len(ps), "ks_one_sided_super_uniform_p": float(one.pvalue), "ks_one_sided_D": float(one.statistic),
            "ks_two_sided_p_descriptive": float(two.pvalue), "frac_below_0.05": frac,
            "pass": bool(one.pvalue >= 0.01 and frac <= 0.08)}


def phase_synthetic(tmp, R_dry=50, M_C_=1000, keep_tmp=False):
    t0 = time.time()
    stage_t, log = {}, OrderLog()
    runtime = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "hostname": socket.gethostname()}
    code = locked_code_check()
    if not code["all_ok"]:
        raise SystemExit("locked code hash check failed: %s" % dumps(code)[:2000])
    from n3.synth import make_layout_dataset
    raw = os.path.join(tmp, "n3_synthetic")
    if os.path.exists(raw):
        shutil.rmtree(raw)
    os.makedirs(raw)
    t = time.time()
    subjects = make_layout_dataset(raw, os.path.join(ROOT, "notes", "data", "chbmit_inventory.csv"))
    stage_t["generate_s"] = time.time() - t
    inputs = {os.path.relpath(os.path.join(dp, f), raw).replace("\\", "/"): sha256_file(os.path.join(dp, f))
              for dp, _, fs in os.walk(raw) for f in sorted(fs)}
    records, ann, splits, shash, feats, fhash, pseudo, table, _ = prepare(raw, subjects, False, stage_t, log)
    split_str_real = split_string(splits).replace("syn23", "chb23").replace("syn24", "chb24")
    layout_ok = hashlib.sha256(split_str_real.encode()).hexdigest() == EXPECTED_SPLIT_HASH_N3
    tab_ok = table_check(table, subjects, SUBJECTS)
    key = (K_DRY,)
    blk = controls_block(pseudo, feats, subjects, R_dry, R_LEAK, key, M_NULL, stage_t, log)
    raw_reps, raw_nulls = blk.pop("_raw")
    grouped = grouped_pooled(raw_reps, raw_nulls)
    del raw_reps, raw_nulls
    reps = blk["NC-P"]["replicates"]
    ks_A_up = _ks([r["p_A_up"] for r in reps])
    ks_A_lo = _ks([r["p_A_lo"] for r in reps])
    keep = [r for r in reps if not r["degeneracy_rm"]["degenerate"]]
    ks_E_up = _ks([r["E_rm"]["p_up"] for r in keep])      # pooled SigmaF1 over ONE replicate = its exact p
    ks_E_lo = _ks([r["E_rm"]["p_lo"] for r in keep])
    t = time.time()
    prim = n2_fit(subjects, records, ann, splits, feats, log)
    c3 = c3_block(prim, subjects, splits, key, M_C_, stage_t, log)
    c3.pop("_f1_mc"), c3.pop("_f1_plc")
    stage_t["n2_c3_s"] = time.time() - t
    dry = {"a_T_A_up": ks_A_up, "a_T_A_lo": ks_A_lo, "a_pooled_SigmaF1_up_per_replicate": ks_E_up,
           "a_pooled_SigmaF1_lo_per_replicate": ks_E_lo, "b_PL-A_trips_T_A": blk["PL-A"]["trips_T_A"],
           "null_recompute_bit_identical": blk["null_recompute_bit_identical_to_n1b"]["all"],
           "descriptive_grouped_pooled_SigmaF1": grouped}
    dry["PASS"] = bool(all(x is not None and x["pass"] for x in (ks_A_up, ks_A_lo, ks_E_up, ks_E_lo))
                       and dry["b_PL-A_trips_T_A"] and dry["null_recompute_bit_identical"])
    runtime.update({"wall_s": time.time() - t0, "stage_s": stage_t, "peak_ram_mb": peak_rss_mb()})
    out = {"status_label": RUO + " SYNTHETIC DATA.", "dry_run": dry, "replicates_per_subject": R_dry, "R_leak": R_LEAK,
           "M_null": M_NULL, "table": table, "table_matches_prereg_layout": tab_ok, "layout_split_matches_prereg": layout_ok,
           "split_hash_synthetic": shash, "controls": blk, "C3prime_descriptive": c3,
           "provenance": {"seed": n3.SEED, "streams": "spawn_key=(26, k, subject_index, replicate); data (26, 0, si)",
                          "prereg_sha256": prereg_hashes(), "locked_code": code, "n3_code_sha256": n3_code_hashes(),
                          "environment": environment(), "input_sha256": inputs, "feature_sha256_16": fhash},
           "order_log": log.events, "runtime": runtime}
    with open(os.path.join(RES, "N3_synthetic.json"), "w", newline="\n") as fh:
        fh.write(dumps(out))
    try:
        from n3.figures import synthetic_figure
        synthetic_figure(out, os.path.join(FIG, "N3_synthetic_dryrun"))
    except Exception as e:
        print("figure failed:", repr(e))
    if not keep_tmp:
        shutil.rmtree(raw, ignore_errors=True)
    print(json.dumps({"dry_run": dry, "tab_ok": tab_ok, "layout_ok": layout_ok,
                      "NCP": {k: blk["NC-P"][k] for k in ("V1-A", "V2-A", "V1-E", "T_A_fisher_up", "T_A_fisher_lo")},
                      "pooled": blk["NC-P"]["event_arm"]["pooled_SigmaF1"], "PL-A": blk["PL-A"]["fisher_T_A_up"],
                      "wall_s": round(runtime["wall_s"], 1), "peak_mb": runtime["peak_ram_mb"],
                      "stage_s": {k: round(v, 1) for k, v in stage_t.items()}}, default=str))


def phase_real(rerun=False, R=R_NCP, R_leak=R_LEAK, M_C_=M_C, figures=True):
    t0 = time.time()
    stage_t, log = {}, OrderLog()
    runtime = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "hostname": socket.gethostname()}
    out_dir = os.path.join(RES, "rerun") if rerun else RES
    os.makedirs(out_dir, exist_ok=True)
    # §3 step 1: hashes of the preregs and the §1 code, snapshot of DEVIATIONS.md
    prereg = prereg_hashes()
    runtime["prereg_hashed_at_unix"] = time.time()
    prereg_ok = all(prereg[n] == v for n, v in PREREG_LOCKED.items())
    code = locked_code_check()
    if not (prereg_ok and code["all_ok"]):
        raise SystemExit("hash check failed: prereg %s code %s" % (prereg, code["nfharness"]["mismatches"] + code["n1b"]["mismatches"]))
    log.add("hashes_checked", "prereg N3 %s" % prereg[N3_PREREG][:16])
    dev_snap = os.path.join(out_dir, "N3_DEVIATIONS_snapshot.md")
    shutil.copyfile(os.path.join(CODE, "DEVIATIONS.md"), dev_snap)
    dev_sha = sha256_file(dev_snap)
    # §3 step 4: inputs verified against manifest + PhysioNet SHA256SUMS
    raw = os.path.join(ROOT, "data", "raw", "chbmit")
    t = time.time()
    man = os.path.join(ROOT, "data", "manifests", "chbmit_manifest.csv")
    inputs = verify_inputs(raw, man, os.path.join(raw, "_meta", "SHA256SUMS.txt"), subjects=set(SUBJECTS))
    stage_t["hash_inputs_s"] = time.time() - t
    log.add("inputs_verified", "n=%d" % len(inputs))
    runtime["first_annotation_parse_unix"] = time.time()
    records, ann, splits, shash, feats, fhash, pseudo, table, montage = prepare(raw, SUBJECTS, True, stage_t, log)
    tab_ok = table_check(table, SUBJECTS, SUBJECTS)
    # (i) locked N2 model: s, h hashed BEFORE any control reads a label
    t = time.time()
    prim = n2_fit(SUBJECTS, records, ann, splits, feats, log)
    stage_t["n2_fit_s"] = time.time() - t
    # (ii)-(iv) NC-P, PL-A (+PL-A10), PL-B
    blk = controls_block(pseudo, feats, SUBJECTS, R, R_leak, (), M_NULL, stage_t, log)
    blk.pop("_raw")
    # (v)-(vi) C3', PL-C
    c3 = c3_block(prim, SUBJECTS, splits, (), M_C_, stage_t, log)
    f1_mc, f1_plc = c3.pop("_f1_mc"), c3.pop("_f1_plc")
    plb_code = plb_code_inprocess(prim, SUBJECTS, splits)
    log.add("PL-B-code_inprocess", "all_raised=%s" % plb_code["all_raised"])
    # (vii) N2 scoring against the real test labels, last
    t = time.time()
    metrics, grids = n2_score(prim, SUBJECTS, splits, log)
    stage_t["n2_score_s"] = time.time() - t
    rule_verdict = model_overall([metrics[s]["verdict"] for s in SUBJECTS])
    tp = sum(metrics[s]["tp"] for s in SUBJECTS)
    fp = sum(metrics[s]["fp"] for s in SUBJECTS)
    nr = sum(metrics[s]["n_ref"] for s in SUBJECTS)
    c3["descriptive_model_pooled_f1"] = 2 * tp / (2 * tp + fp + (nr - tp))
    c3["descriptive_model_f1_above_q99"] = bool(c3["descriptive_model_pooled_f1"] > c3["exact"]["q99"])
    ncp = blk["NC-P"]
    gate = {"V1-A": ncp["V1-A"], "V2-A": ncp["V2-A"], "V1-E": ncp["V1-E"], "C3prime_i": c3["mc"]["crit_i"],
            "C3prime_ii": c3["mc"]["crit_ii"], "PL-A_trips_T_A": blk["PL-A"]["trips_T_A"],
            "PL-B-code_raises_inprocess": plb_code["all_raised"], "PL-C_trips": c3["PL-C"]["trip"],
            "PL-B_specificity": blk["PL-B_descriptive"]["specificity_holds"]}
    run_checks = {"hash_checks": bool(prereg_ok and code["all_ok"]), "montage_E1": True,
                  "segment_table_matches_prereg": bool(all(tab_ok.values())), "split_hash_matches_prereg": True,
                  "fp_grid_equals_prereg": bool(all(g["equal"] for g in grids.values())),
                  "N_ref_4_each": bool(all(metrics[s]["n_ref"] == 4 for s in SUBJECTS)),
                  "NC-P_order_ok": ncp["aggregate_N1b"]["all_order_ok"],
                  "null_recompute_bit_identical": blk["null_recompute_bit_identical_to_n1b"]["all"]}
    runtime["prereg_hash_precedes_first_annotation_parse"] = bool(runtime["prereg_hashed_at_unix"] < runtime["first_annotation_parse_unix"])
    runtime.update({"wall_s": time.time() - t0, "stage_s": stage_t, "peak_ram_mb": peak_rss_mb()})
    runtime["within_budget_15min_1.5GB"] = bool(runtime["wall_s"] < 900 and (runtime["peak_ram_mb"] or 0) < 1536)
    n2_per = {s: {k: v for k, v in metrics[s].items() if k != "per_file"} for s in SUBJECTS}
    card = {"status_label": RUO, "run_id": "N3-chbmit-%s" % shash[:12],
            "note": "Harness validation on fresh subjects chb23/chb24 (blind prereg) + the locked N2 model re-run unchanged. "
                    "Steps 2 (pytest) and 6 (rerun identity) and the final verdicts are computed by run_n3.py --phase final "
                    "-> results\\N3_verdict.json.",
            "data_decision_2.4": "B (cap raised; total raw data 2.062e9 bytes <= 2.10e9 abort limit)",
            "settings": {"R": R, "R_leak": R_leak, "M_null": M_NULL, "M_C": M_C_,
                         "fallbacks_used": [x for x, c_ in (("R=5", R != 10),) if c_]},
            "segment_table": table, "segment_table_matches_prereg": tab_ok, "montage_E1": montage and True,
            "split": {"string": split_string(splits), "hash": shash, "folds": {s: {"train": splits[s].train_names,
                                                                                     "test": splits[s].test_names} for s in SUBJECTS}},
            "N2_model": {"per_subject": n2_per, "decision_rule_overall": rule_verdict, "fp_grids": grids,
                         "sha256_scores_hyps_step_i": {s: prim[s]["sha256_scores_hyps"] for s in SUBJECTS}},
            "controls": blk, "C3prime": c3, "PL-B-code_inprocess": plb_code, "gate_items_real_run": gate,
            "run_checks": run_checks, "order_log": log.events,
            "provenance": {"prereg_sha256": prereg, "prereg_match_locked": prereg_ok, "locked_code": code,
                           "n3_code_sha256": n3_code_hashes(), "deviations_snapshot_sha256": dev_sha, "seed": n3.SEED,
                           "streams": {"20": "training phantoms (k, si, rep)", "21": "test phantoms", "22": "null draws",
                                       "23": "PL-A selection (PL-A reps 0-4, PL-A10 reps 5-9)", "24": "C3' MC (24,0,0)",
                                       "25": "PL-C (25,0,0)", "3": "N2 bootstraps (N2 stream, unchanged)"},
                           "input_sha256": inputs, "n_inputs_verified": len(inputs), "feature_sha256_16": fhash,
                           "environment": environment(),
                           "label_vaults_N2": {s: prim[s]["vault"].summary() for s in SUBJECTS},
                           "guard_calls": dict(sorted(C.GUARD_CALLS.items()))},
            "runtime": runtime}
    card["card_sha256_excl_runtime"] = None
    h = card_hash({k: v for k, v in card.items() if k != "card_sha256_excl_runtime"})
    card["card_sha256_excl_runtime"] = h
    with open(os.path.join(out_dir, "N3_card.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(card))
    if not rerun:
        write_subject_cards(card, metrics, prim, splits, figures)
        if figures:
            try:
                from n3.figures import real_figure
                real_figure(card, f1_mc, f1_plc, os.path.join(FIG, "N3_controls"))
            except Exception as e:
                print("figure failed:", repr(e))
    print(json.dumps({"card": h, "gate": gate, "run_checks": run_checks,
                      "T_A_fisher": [ncp["T_A_fisher_up"], ncp["T_A_fisher_lo"]],
                      "pooled": ncp["event_arm"]["pooled_SigmaF1"], "PL-A": blk["PL-A"]["fisher_T_A_up"],
                      "n2": {s: (metrics[s]["verdict"], metrics[s]["tp"], metrics[s]["n_ref"], metrics[s]["fp"],
                                 round(metrics[s]["window_auroc"], 4)) for s in SUBJECTS}, "n2_rule": rule_verdict,
                      "wall_s": round(runtime["wall_s"], 1), "peak_mb": runtime["peak_ram_mb"],
                      "stage_s": {k: round(v, 1) for k, v in stage_t.items()}}, default=str))


def write_subject_cards(card, metrics, prim, splits, figures):
    cards = os.path.join(RES, "cards")
    os.makedirs(cards, exist_ok=True)
    for s in SUBJECTS:
        m = dict(metrics[s])
        c = {"run_id": "N3-N2model-%s-%s" % (s, card["split"]["hash"][:12]),
             "verdict": "N2 decision rule, subject %s: %s (counts only if the N3 harness = PASS; see results\\N3_verdict.json)"
                        % (s, m["verdict"]),
             "verdict_note": "Locked N2 model and rule re-run unchanged on a fresh subject (prereg N3 §5). FP grid %s."
                             % m["fp_grid_meet_max_inconclusive_max"],
             "task": "seizure DETECTION, patient-specific causal split (N2 §1); CHB-MIT bipolar, 22 unique channels",
             "data": {"dataset": "CHB-MIT Scalp EEG Database v1.0.0, DOI 10.13026/C2K01R, ODC-By 1.0",
                      "subject": s + (" (no SUBJECT-INFO row; age/sex unknown; repeat-patient status UNVERIFIED)" if s == "chb24" else ""),
                      "hours_scored_test": m["hours"], "test_seizures_N_ref": m["n_ref"],
                      "files": "R2 subset: seizure-containing files only (prereg N3 §2.1); chb23/chb24 test files now BURNED"},
             "split": {"scheme": "causal: train through the file with the 3rd seizure; test = the next seizure files",
                       "buffer_s": C.BUFFER_S, "hash": card["split"]["hash"], "hash_matches_prereg": True,
                       "note": "split string of both subjects hashed (S7) before feature extraction",
                       "folds": {s: card["split"]["folds"][s]}},
             "model": {"config_sha256": C.LOCKED_CONFIG_HASH_LITERAL, "tau_rule": "smallest grid tau with inner-LOFO train FA <= 12/24h",
                       "tau_star": m["tau"]},
             "metrics": {s: m},
             "controls": {"N3 harness gate": "see results\\N3_card.json / N3_verdict.json"},
             "leakage_checklist": {"guards": "nfharness F1-F9/S7 unchanged; N3 gate = NC-P window arm + pooled event arm + C3' + planted leaks"},
             "provenance": {"prereg_sha256": card["provenance"]["prereg_sha256"], "split_hash": card["split"]["hash"],
                            "sha256_scores_hyps_step_i": prim[s]["sha256_scores_hyps"],
                            "label_vault": card["provenance"]["label_vaults_N2"][s]},
             "runtime": {}}
        write_card(c, os.path.join(cards, "%s_N3_card.json" % s), os.path.join(cards, "%s_N3_card.md" % s))
        if figures:
            sc = Scorer(prim[s]["vault"], "figure")
            sp = splits[s]
            subject_figure(s, m, prim[s]["res"]["p"], prim[s]["res"]["hyp"], {f: sc._ref(f) for f in sp.test_names},
                           prim[s]["res"]["tau"], os.path.join(FIG, "N3_card_%s" % s),
                           "N2 rule, subject verdict (counts only if N3 harness PASS)")


def phase_final():
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", os.path.join(CODE, "tests")],
                       capture_output=True, text=True, cwd=CODE)
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    npass = int(re.search(r"(\d+) passed", tail).group(1)) if re.search(r"(\d+) passed", tail) else 0
    nfail = sum(int(x) for x in re.findall(r"(\d+) (?:failed|error)", tail))
    tests = {"summary": tail, "passed": npass, "failed_or_error": nfail, "returncode": r.returncode,
             "PASS": bool(r.returncode == 0 and nfail == 0 and npass > 0)}
    r2 = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                         os.path.join(CODE, "tests", "test_n3.py") + "::test_PLB_code_select_tau_raises_on_test_tagged_scores"],
                        capture_output=True, text=True, cwd=CODE)
    plb_code_test = {"returncode": r2.returncode, "summary": (r2.stdout.strip().splitlines() or [""])[-1],
                     "PASS": r2.returncode == 0}
    h, cards = {}, {}
    for tag, base in (("run1", RES), ("run2", os.path.join(RES, "rerun"))):
        with open(os.path.join(base, "N3_card.json")) as fh:
            c = json.load(fh)
        stored = c.pop("card_sha256_excl_runtime", None)
        h[tag] = {"recomputed": card_hash(c), "stored": stored}
        cards[tag] = c
    identical = bool(h["run1"]["recomputed"] == h["run2"]["recomputed"] == h["run1"]["stored"] == h["run2"]["stored"])
    with open(os.path.join(RES, "N3_synthetic.json")) as fh:
        syn = json.load(fh)
    c1 = cards["run1"]
    g = c1["gate_items_real_run"]
    items = {"step2_pytest": tests["PASS"], "step3_dry_run": bool(syn["dry_run"]["PASS"]),
             "step5_real_run_complete": bool(all(c1["run_checks"].values())), "step6_rerun_identical": identical,
             "V1-A": g["V1-A"], "V2-A": g["V2-A"], "V1-E": g["V1-E"], "C3prime_i": g["C3prime_i"],
             "C3prime_ii": g["C3prime_ii"], "PL-A_trips_T_A": g["PL-A_trips_T_A"],
             "PL-B-code_raises": bool(plb_code_test["PASS"] and g["PL-B-code_raises_inprocess"]),
             "PL-C_trips": g["PL-C_trips"], "PL-B_specificity": g["PL-B_specificity"]}
    verdict, failed, flags = harness_verdict(items)
    n2 = c1["N2_model"]
    if verdict == "PASS":
        model = {"status": n2["decision_rule_overall"],
                 "label": "N2 locked model, confirmatory on fresh subjects; harness gate pre-registered blind"}
    else:
        model = {"status": "not verifiable: code", "decision_rule_counterfactual": n2["decision_rule_overall"],
                 "label": "N3 harness did not PASS (%s)" % ", ".join(failed)}
    model["per_subject"] = {s: {k: n2["per_subject"][s][k] for k in ("verdict", "tp", "n_ref", "fp", "hours", "fa_per_24h",
                                                                     "sens_ci_clopper_pearson", "fa_ci_garwood_per_24h",
                                                                     "window_auroc", "auroc_ci_block_bootstrap_files",
                                                                     "window_auprc", "tau", "latency_median", "flags")}
                            for s in SUBJECTS}
    out = {"status_label": RUO, "N3_harness_verdict": verdict, "failed_items": failed, "flags": flags, "gate_items": items,
           "tests": tests, "PL-B-code_pytest": plb_code_test, "rerun_identity": {"identical": identical, "hashes": h},
           "synthetic_dry_run": syn["dry_run"], "N2_model_test": model, "burned": "chb23 and chb24 test files are burned",
           "provenance": {"n3_code_sha256": n3_code_hashes(), "locked_code": locked_code_check(), "prereg_sha256": prereg_hashes()},
           "runtime": {"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "wall_s": time.time() - t0}}
    with open(os.path.join(RES, "N3_verdict.json"), "w", newline="\n") as fh:
        fh.write(dumps(out))
    print(json.dumps({"N3_harness": verdict, "failed": failed, "flags": flags, "model": model["status"], "tests": tail,
                      "rerun_identical": identical}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["synthetic", "real", "final"], required=True)
    ap.add_argument("--tmp", default=None)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--R", type=int, default=R_NCP)
    ap.add_argument("--R-dry", type=int, default=50)
    ap.add_argument("--MC", type=int, default=M_C)
    ap.add_argument("--keep-tmp", action="store_true")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    if a.phase == "synthetic":
        phase_synthetic(a.tmp, a.R_dry, a.MC, a.keep_tmp)
    elif a.phase == "real":
        phase_real(a.rerun, a.R, R_LEAK, a.MC, not a.no_figures)
    else:
        phase_final()
