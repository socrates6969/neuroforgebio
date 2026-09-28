"""N1b: negative controls v2 (prereg\\N1b_negative_controls_v2.md, POST-HOC redesign of N1 part (b)).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims.
Usage (order of work, prereg §5):
  python run_n1b.py --phase synthetic --tmp DIR   # dry run on synthetic EDFs (real layout): KS uniformity, PL-A trip
  python run_n1b.py --phase real                  # real run -> results\\N1b_card.json (+ figure)
  python run_n1b.py --phase real --rerun          # fresh-process rerun -> results\\rerun\\N1b_card.json
  python run_n1b.py --phase final                 # pytest + rerun identity + N1' and N2 status -> results\\N1b_verdict.json
nfharness is imported UNCHANGED; its file hashes are checked against results\\N2_run_card.json before anything else.
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
from nfharness.data import load_records, sha256_file, verify_inputs  # noqa: E402
from nfharness.features import FEATURE_NAMES, assert_whitelist, file_features  # noqa: E402
from nfharness.labels import LabelVault  # noqa: E402
from nfharness.pipeline import run_split, summarize  # noqa: E402
from nfharness.provenance import card_hash, code_hashes, dumps, environment, peak_rss_mb  # noqa: E402
from nfharness.scoring import Scorer, mask_events  # noqa: E402
from nfharness.splits import assert_split_hash, causal_splits, split_hash  # noqa: E402

from n1b import K_C3MC, K_PLC, K_SYN  # noqa: E402
from n1b import rng as nrng  # noqa: E402
from n1b.c3prime import c3_criteria, exact_distribution, file_counts, harness_mc  # noqa: E402
from n1b.ncp import ALPHA_FISHER, M_NULL, aggregate, fisher, planted_threshold_leak, run_replicate  # noqa: E402
from n1b.segments import build_pseudo  # noqa: E402
from n1b.synth import make_layout_dataset  # noqa: E402

SUBJECTS = ["chb01", "chb03", "chb10"]
PREREG_LOCKED = {"N1_harness_controls.md": "27db9d27f5b6ac2e0f49826c6b3eb9625b8e1633434ae70cf62a7e10f09fc93b",
                 "N2_baseline_detection.md": "ed929ae0e5182827352928225cf40865a8bee5f6b5da089be5a6600e6678e21c"}
N1B_PREREG = "N1b_negative_controls_v2.md"
# prereg §2.1 table (train allowed h, segments, test allowed h, segments) and §2.2 durations (file order)
TABLE = {"chb01": (5.81, 9, 2.11, 6), "chb03": (1.81, 4, 6.27, 12), "chb10": (4.90, 4, 6.27, 8)}
DURS = {"chb01": ([40, 27, 40], [51, 90, 93, 101]), "chb03": ([52, 65, 69], [52, 47, 64, 53]),
        "chb10": ([35, 70, 65], [58, 76, 89, 54])}
N2_KEYS = ("tau", "tp", "fp", "n_ref", "hours", "window_auroc")
RUO = ("RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or "
       "treatment decisions may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical "
       "use requires regulatory clearance and clinical validation (IRB/ethics approval).")


def n1b_code_hashes():
    files = sorted(glob.glob(os.path.join(CODE, "n1b", "*.py"))) + [os.path.abspath(__file__)] + \
        sorted(glob.glob(os.path.join(CODE, "tests", "test_n1b*.py")))
    return {os.path.relpath(f, CODE).replace("\\", "/"): sha256_file(f) for f in files}


def harness_hash_check():
    """nfharness/*.py, edf_reader.py, run_n2.py must equal results\\N2_run_card.json (prereg §1, §6)."""
    with open(os.path.join(RES, "N2_run_card.json")) as fh:
        ref = json.load(fh)["provenance"]["code_sha256"]
    now = code_hashes(CODE, extra=[os.path.join(CODE, "run_n2.py")])
    mism = sorted(k for k in set(ref) | set(now) if ref.get(k) != now.get(k))
    return {"n_files": len(now), "all_match_N2_run_card": not mism, "mismatches": mism, "sha256": now}


# --------------------------------------------------------------------------------------------- shared preparation
def prepare(raw, subjects, real, stage_t):
    t = time.time()
    records, ann = load_records(raw, subjects)
    counts = {f: len(v) for f, v in ann.items()}
    splits = causal_splits(records, counts)
    shash = assert_split_hash(splits, C.EXPECTED_SPLIT_HASH) if real else split_hash(splits)
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
        table[s] = {"train_allowed_h": sp.train_allowed_h, "train_segments": sp.n_train_segments,
                    "test_allowed_h": sp.test_allowed_h, "test_segments": sp.n_test_segments,
                    "train_phantom_durations": [d for d, _, _ in sp.train_seizure_durations],
                    "test_phantom_durations": [d for d, _, _ in sp.test_seizure_durations],
                    "min_segment_s": min(r.duration for r in sp.split.train + sp.split.test)}
    return records, ann, splits, shash, feats, fhash, pseudo, table


def table_check(table, subjects, real_names):
    ok = {}
    for s, rn in zip(subjects, real_names):
        a = TABLE[rn]
        t = table[s]
        ok[s] = bool(round(t["train_allowed_h"], 2) == a[0] and t["train_segments"] == a[1] and
                     round(t["test_allowed_h"], 2) == a[2] and t["test_segments"] == a[3] and
                     t["train_phantom_durations"] == DURS[rn][0] and t["test_phantom_durations"] == DURS[rn][1])
    return ok


def n2_primary(subjects, records, ann, splits, feats):
    """N2 primary recomputed with the unchanged code (as run_n2.py)."""
    out = {}
    for s in subjects:
        sp = splits[s]
        subj = [r for r in records if r.subject == s]
        v = LabelVault(ann, {r.name: r.duration for r in subj}, protected_files=sp.test_names, name="N2-" + s)
        res = run_split(sp, feats, v, [[r] for r in sp.train], purpose="N2 primary")
        m = summarize(res, sp.test)
        out[s] = {"res": res, "metrics": m, "vault": v}
    return out


def n2_identity(prim, subjects):
    with open(os.path.join(RES, "N2_results.json")) as fh:
        old = json.load(fh)["per_subject"]
    per, ok = {}, True
    for s in subjects:
        new = {k: prim[s]["metrics"][k] for k in N2_KEYS}
        ref = {k: old[s][k] for k in N2_KEYS}
        same = dumps(new) == dumps(ref) and all(repr(new[k]) == repr(ref[k]) for k in N2_KEYS)
        per[s] = {"recomputed": new, "N2_results_json": ref, "byte_identical": bool(same)}
        ok &= same
    return {"per_subject": per, "all_identical": bool(ok)}


def run_ncp_block(pseudo, feats, subjects, R, R_leak, key_prefix, stage_t, M=M_NULL):
    t = time.time()
    ncp, privs = [], []
    for s in subjects:
        for rep in range(R[s] if isinstance(R, dict) else R):
            pub, priv = run_replicate(pseudo[s], feats, rep, key_prefix=key_prefix, M=M)
            ncp.append(pub)
            privs.append(priv)
    stage_t["ncp_s"] = time.time() - t
    t = time.time()
    pla = []
    for s in subjects:
        for rep in range(R_leak):
            pub, _ = run_replicate(pseudo[s], feats, rep, key_prefix=key_prefix, plant="PL-A", allow_planted_leak=True, M=M)
            pla.append(pub)
    stage_t["pl_a_s"] = time.time() - t
    t = time.time()
    plb = [planted_threshold_leak(pv, pb, allow_planted_leak=True, M=M) for pv, pb in zip(privs, ncp)]
    stage_t["pl_b_s"] = time.time() - t
    agg = aggregate(ncp)
    agg_a = aggregate(pla)
    keep_b = [r for r in plb if not r["degeneracy"]["degenerate"]]
    fb_up, nb = fisher([r["p_up"] for r in keep_b])
    spec = all(r["T_A_pvalues_identical_to_NCP"] for r in plb)
    trips = {"PL-A": {"fisher_T_A_up": agg_a["fisher"]["T_A_up"], "fisher_T_E_up": agg_a["fisher"]["T_E_up"],
                      "n_retained_T_E": agg_a["fisher_n"]["T_E"],
                      "trip": bool(agg_a["fisher"]["T_A_up"] < ALPHA_FISHER and agg_a["fisher"]["T_E_up"] < ALPHA_FISHER)},
             "PL-B": {"fisher_T_E_up": fb_up, "n_retained": nb, "n_degenerate": len(plb) - len(keep_b),
                      "specificity_T_A_identical": bool(spec),
                      "T_E_mean": float(np.mean([r["T_E"] for r in plb])),
                      "pooled_tp_fp_nref": [sum(r["tp"] for r in plb), sum(r["fp"] for r in plb), sum(r["n_ref"] for r in plb)],
                      "tau_test_optimal_values": [r["tau_test_optimal"] for r in plb],
                      "trip": bool(fb_up == fb_up and fb_up < ALPHA_FISHER and spec)}}
    return {"NC-P": {"aggregate": agg, "replicates": ncp}, "PL-A": {"aggregate": agg_a, "replicates": pla},
            "PL-B": {"replicates": plb}, "trips": trips}


def run_c3_block(prim, subjects, splits, key_prefix, M_C, stage_t):
    t = time.time()
    scorers = {s: Scorer(prim[s]["vault"], "N1b C3prime") for s in subjects}
    files = [(s, f, np.asarray(prim[s]["res"]["hyp"][f], dtype=np.int8)) for s in subjects for f in splits[s].test_names]
    refs = {f: scorers[s]._ref(f) for s, f, _ in files}
    counters = [file_counts(refs[f], h) for _, f, h in files]
    n_ref = sum(int(mask_events(refs[f])[0].size) for _, f, _ in files)
    ex, pmf = exact_distribution(counters, n_ref)
    stage_t["c3_exact_s"] = time.time() - t
    t = time.time()
    f1_mc, _ = harness_mc(files, scorers, nrng(*key_prefix, K_C3MC, 0, 0), M_C)
    crit = c3_criteria(f1_mc, ex)
    stage_t["c3_mc_s"] = time.time() - t
    t = time.time()
    onset = {f: (int(mask_events(refs[f])[0][0]) if mask_events(refs[f])[0].size else None) for _, f, _ in files}
    f1_plc, n_forced = harness_mc(files, scorers, nrng(*key_prefix, K_PLC, 0, 0), M_C, plant="PL-C",
                                  allow_planted_leak=True, seizure_onset=onset)
    crit_c = c3_criteria(f1_plc, ex)
    stage_t["pl_c_s"] = time.time() - t
    tp = sum(prim[s]["metrics"]["tp"] for s in subjects)
    fp = sum(prim[s]["metrics"]["fp"] for s in subjects)
    nr = sum(prim[s]["metrics"]["n_ref"] for s in subjects)
    model_f1 = 2 * tp / (2 * tp + fp + (nr - tp))
    return {"n_files": len(files), "N_ref": n_ref, "H_hours": sum(h.size for _, _, h in files) / 3600.0,
            "exact": ex, "exact_pmf": pmf, "mc": crit, "PASS": bool(crit["crit_i"] and crit["crit_ii"]),
            "PL-C": {"mean_f1": float(f1_plc.mean()), "frac_above_q95": crit_c["frac_above_q95"],
                     "bound_ii": crit_c["bound_ii"], "n_forced_offsets": n_forced,
                     "trip": bool(crit_c["frac_above_q95"] > crit_c["bound_ii"])},
            "descriptive_model_pooled_f1": model_f1, "descriptive_model_f1_above_q99": bool(model_f1 > ex["q99"]),
            "_f1_mc": f1_mc, "_f1_plc": f1_plc}


# --------------------------------------------------------------------------------------------- phases
def phase_synthetic(tmp, R_total=100, R_leak=5, M_C=1000, keep_tmp=False):
    t0 = time.time()
    stage_t = {}
    runtime = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "hostname": socket.gethostname()}
    prereg = {n: sha256_file(os.path.join(ROOT, "prereg", n)) for n in list(PREREG_LOCKED) + [N1B_PREREG]}
    raw = os.path.join(tmp, "n1b_synthetic")
    if os.path.exists(raw):
        shutil.rmtree(raw)
    os.makedirs(raw)
    t = time.time()
    subjects = make_layout_dataset(raw, os.path.join(ROOT, "notes", "data", "chbmit_selection.csv"))
    stage_t["generate_s"] = time.time() - t
    inputs = {os.path.relpath(os.path.join(dp, f), raw).replace("\\", "/"): sha256_file(os.path.join(dp, f))
              for dp, _, fs in os.walk(raw) for f in sorted(fs)}
    records, ann, splits, shash, feats, fhash, pseudo, table = prepare(raw, subjects, False, stage_t)
    tab_ok = table_check(table, subjects, SUBJECTS)
    base, extra = divmod(R_total, len(subjects))
    R = {s: base + (1 if i < extra else 0) for i, s in enumerate(subjects)}
    key = (K_SYN,)
    blk = run_ncp_block(pseudo, feats, subjects, R, R_leak, key, stage_t)
    pA = [r["p_A_up"] for r in blk["NC-P"]["replicates"]]
    ks = kstest(pA, "uniform")
    pE = [r["E_rm"]["p_up"] for r in blk["NC-P"]["replicates"] if not r["degeneracy_rm"]["degenerate"]]
    ksE = kstest(pE, "uniform") if pE else None
    t = time.time()
    prim = n2_primary(subjects, records, ann, splits, feats)
    stage_t["n2_primary_s"] = time.time() - t
    c3 = run_c3_block(prim, subjects, splits, key, M_C, stage_t)
    f1_mc, f1_plc = c3.pop("_f1_mc"), c3.pop("_f1_plc")
    dry = {"KS_T_A_p_up": {"n": len(pA), "statistic": float(ks.statistic), "pvalue": float(ks.pvalue),
                           "pass_ge_0.01": bool(ks.pvalue >= 0.01)},
           "KS_T_E_p_up_descriptive": None if ksE is None else {"n": len(pE), "statistic": float(ksE.statistic),
                                                                "pvalue": float(ksE.pvalue)},
           "PL-A_trips": blk["trips"]["PL-A"]["trip"],
           "PASS": bool(ks.pvalue >= 0.01 and blk["trips"]["PL-A"]["trip"])}
    runtime.update({"wall_s": time.time() - t0, "stage_s": stage_t, "peak_ram_mb": peak_rss_mb()})
    out = {"status_label": RUO + " SYNTHETIC DATA.", "dry_run": dry, "replicates_per_subject": R, "R_leak": R_leak,
           "M_null": M_NULL, "table": table, "table_matches_prereg_layout": tab_ok, "split_hash": shash,
           "NC-P": blk["NC-P"], "PL-A": blk["PL-A"], "PL-B": blk["PL-B"], "trips": blk["trips"],
           "C3prime_descriptive": c3,
           "n2_primary_synthetic": {s: {k: prim[s]["metrics"][k] for k in N2_KEYS} for s in subjects},
           "provenance": {"seed": C.SEED, "streams": "spawn_key=(16, k, subject_index, replicate); data (16, 0, si)",
                          "prereg_sha256": prereg, "harness": harness_hash_check(), "n1b_code_sha256": n1b_code_hashes(),
                          "environment": environment(), "input_sha256": inputs, "feature_sha256_16": fhash},
           "runtime": runtime}
    with open(os.path.join(RES, "N1b_synthetic.json"), "w", newline="\n") as fh:
        fh.write(dumps(out))
    try:
        from n1b.figures import synthetic_figure
        synthetic_figure(out, f1_mc, os.path.join(FIG, "N1b_synthetic_dryrun"))
    except Exception as e:  # figure failure must not hide results
        print("figure failed:", repr(e))
    if not keep_tmp:
        shutil.rmtree(raw, ignore_errors=True)
    print(json.dumps({"dry_run": dry, "V1": blk["NC-P"]["aggregate"]["V1"], "V2": blk["NC-P"]["aggregate"]["V2"],
                      "fisher": blk["NC-P"]["aggregate"]["fisher"], "trips": {k: v["trip"] for k, v in blk["trips"].items()},
                      "c3": [c3["PASS"], c3["PL-C"]["trip"]], "table_ok": tab_ok, "wall_s": round(runtime["wall_s"], 1),
                      "peak_mb": runtime["peak_ram_mb"], "stage_s": {k: round(v, 1) for k, v in stage_t.items()}}))


def phase_real(rerun=False, R=10, R_leak=5, M_C=1000, figures=True):
    t0 = time.time()
    stage_t = {}
    runtime = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "hostname": socket.gethostname()}
    out_dir = os.path.join(RES, "rerun") if rerun else RES
    os.makedirs(out_dir, exist_ok=True)
    # 1. prereg hashes BEFORE any label is read (the N1b card records the N1b prereg SHA-256)
    prereg = {n: sha256_file(os.path.join(ROOT, "prereg", n)) for n in list(PREREG_LOCKED) + [N1B_PREREG]}
    runtime["prereg_hashed_at_unix"] = time.time()
    prereg_ok = all(prereg[n] == v for n, v in PREREG_LOCKED.items())
    harness = harness_hash_check()
    if not (prereg_ok and harness["all_match_N2_run_card"]):
        raise SystemExit("hash check failed: prereg %s harness %s" % (prereg_ok, harness["mismatches"]))
    # 2. snapshot DEVIATIONS.md (review note 5(i))
    dev_src = os.path.join(CODE, "DEVIATIONS.md")
    dev_snap = os.path.join(out_dir, "N1b_DEVIATIONS_snapshot.md")
    shutil.copyfile(dev_src, dev_snap)
    dev_sha = sha256_file(dev_snap)
    # 3. inputs
    raw = os.path.join(ROOT, "data", "raw", "chbmit")
    t = time.time()
    man = os.path.join(ROOT, "data", "manifests", "chbmit_manifest.csv")
    inputs = verify_inputs(raw, man, os.path.join(raw, "_meta", "SHA256SUMS.txt"), subjects=set(SUBJECTS))
    stage_t["hash_inputs_s"] = time.time() - t
    runtime["first_annotation_parse_unix"] = time.time()
    records, ann, splits, shash, feats, fhash, pseudo, table = prepare(raw, SUBJECTS, True, stage_t)
    tab_ok = table_check(table, SUBJECTS, SUBJECTS)
    # 4. N2 identity recompute
    t = time.time()
    prim = n2_primary(SUBJECTS, records, ann, splits, feats)
    ident = n2_identity(prim, SUBJECTS)
    stage_t["n2_identity_s"] = time.time() - t
    # 5. NC-P, PL-A, PL-B
    blk = run_ncp_block(pseudo, feats, SUBJECTS, R, R_leak, (), stage_t)
    # 6. C3', PL-C
    c3 = run_c3_block(prim, SUBJECTS, splits, (), M_C, stage_t)
    f1_mc, f1_plc = c3.pop("_f1_mc"), c3.pop("_f1_plc")
    agg = blk["NC-P"]["aggregate"]
    trips = dict(blk["trips"])
    trips["PL-C"] = c3["PL-C"]
    run_ok = {"hash_checks": bool(prereg_ok and harness["all_match_N2_run_card"]),
              "segment_table_matches_prereg": bool(all(tab_ok.values())),
              "N2_identity_byte_identical": ident["all_identical"],
              "NC-P_V1": agg["V1"], "NC-P_V2": agg["V2"], "NC-P_order_ok": agg["all_order_ok"],
              "C3prime_i": c3["mc"]["crit_i"], "C3prime_ii": c3["mc"]["crit_ii"],
              "PL-A_trip": trips["PL-A"]["trip"], "PL-B_trip": trips["PL-B"]["trip"], "PL-C_trip": trips["PL-C"]["trip"]}
    first_reads = [v.first_scorer_read_time for v in [prim[s]["vault"] for s in SUBJECTS] if v.first_scorer_read_time]
    runtime["first_scorer_read_unix"] = min(first_reads) if first_reads else None
    runtime["prereg_hash_precedes_first_annotation_parse"] = bool(runtime["prereg_hashed_at_unix"] < runtime["first_annotation_parse_unix"])
    runtime.update({"wall_s": time.time() - t0, "stage_s": stage_t, "peak_ram_mb": peak_rss_mb()})
    runtime["within_budget_15min_1.5GB"] = bool(runtime["wall_s"] < 900 and (runtime["peak_ram_mb"] or 0) < 1536)
    card = {"status_label": RUO, "run_id": "N1b-chbmit-%s" % shash[:12],
            "note": "POST-HOC redesign of N1(b); not blind. Replaces only N1(b). Step 4 (rerun identity) and step 1 "
                    "(pytest) are evaluated by run_n1b.py --phase final -> results\\N1b_verdict.json.",
            "settings": {"R": R, "R_leak": R_leak, "M_null": M_NULL, "M_C": M_C, "fallbacks_used": [x for x, c in (("M_C=500", M_C != 1000), ("R=5", R != 10), ("R_leak=3", R_leak != 5)) if c]},
            "segment_table": table, "segment_table_matches_prereg": tab_ok,
            "N2_identity": ident, "NC-P": blk["NC-P"], "PL-A": blk["PL-A"], "PL-B": blk["PL-B"], "C3prime": c3,
            "trips": trips, "run_criteria": run_ok, "run_criteria_all_true": bool(all(run_ok.values())),
            "provenance": {"prereg_sha256": prereg, "prereg_N1_N2_match_locked": prereg_ok, "harness_hash_check": harness,
                           "n1b_code_sha256": n1b_code_hashes(), "deviations_snapshot_sha256": dev_sha,
                           "seed": C.SEED, "streams": {"10": "training phantoms (k, si, rep)", "11": "test phantoms",
                                                       "12": "null placements", "13": "PL-A window selection",
                                                       "14": "C3' MC (14,0,0)", "15": "PL-C (15,0,0)"},
                           "split_hash": shash, "input_sha256": inputs, "n_inputs_verified": len(inputs),
                           "feature_sha256_16": fhash, "environment": environment(),
                           "label_vaults_N2_identity": {s: prim[s]["vault"].summary() for s in SUBJECTS}},
            "runtime": runtime}
    card["card_sha256_excl_runtime"] = None
    h = card_hash({k: v for k, v in card.items() if k != "card_sha256_excl_runtime"})
    card["card_sha256_excl_runtime"] = h
    with open(os.path.join(out_dir, "N1b_card.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(card))
    if figures and not rerun:
        try:
            from n1b.figures import real_figure
            real_figure(card, f1_mc, f1_plc, os.path.join(FIG, "N1b_controls"))
        except Exception as e:
            print("figure failed:", repr(e))
    print(json.dumps({"card": h, "run_criteria": run_ok, "fisher": agg["fisher"], "n_deg": agg["n_degenerate_event_arm"],
                      "n_wflag": agg["n_window_flagged"], "trips": {k: v["trip"] for k, v in trips.items()},
                      "c3": {k: c3["mc"][k] for k in ("mean_mc", "frac_above_q95", "bound_ii")},
                      "mu_star": c3["exact"]["mu_star"], "q95": c3["exact"]["q95"],
                      "wall_s": round(runtime["wall_s"], 1), "peak_mb": runtime["peak_ram_mb"],
                      "stage_s": {k: round(v, 1) for k, v in stage_t.items()}}))


def phase_final():
    t0 = time.time()
    r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", os.path.join(CODE, "tests")],
                       capture_output=True, text=True, cwd=CODE)
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    npass = int(re.search(r"(\d+) passed", tail).group(1)) if re.search(r"(\d+) passed", tail) else 0
    nfail = sum(int(x) for x in re.findall(r"(\d+) (?:failed|error)", tail))
    tests = {"summary": tail, "passed": npass, "failed_or_error": nfail, "returncode": r.returncode,
             "PASS": bool(r.returncode == 0 and nfail == 0 and npass > 0)}
    h = {}
    cards = {}
    for tag, base in (("run1", RES), ("run2", os.path.join(RES, "rerun"))):
        with open(os.path.join(base, "N1b_card.json")) as fh:
            c = json.load(fh)
        stored = c.pop("card_sha256_excl_runtime", None)
        h[tag] = {"recomputed": card_hash(c), "stored": stored}
        cards[tag] = c
    identical = bool(h["run1"]["recomputed"] == h["run2"]["recomputed"] == h["run1"]["stored"] == h["run2"]["stored"])
    with open(os.path.join(RES, "N1b_synthetic.json")) as fh:
        syn = json.load(fh)
    with open(os.path.join(RES, "N1_verdict.json")) as fh:
        n1 = json.load(fh)
    c1 = cards["run1"]
    steps = {"1_tests": tests["PASS"], "2_synthetic_dry_run": bool(syn["dry_run"]["PASS"]),
             "3_real_run_criteria": bool(c1["run_criteria_all_true"]), "4_rerun_byte_identical": identical}
    n1b_pass = bool(all(steps.values()))
    parts = {k: n1["parts"][k] for k in ("a", "c", "d", "e")}
    parts["N1b"] = "PASS" if n1b_pass else "FAIL"
    n1p = "PASS" if all(v == "PASS" for v in parts.values()) else "FAIL"
    with open(os.path.join(RES, "N2_results.json")) as fh:
        n2 = json.load(fh)
    if n1p == "PASS" and c1["N2_identity"]["all_identical"]:
        n2_status = {"status": n2["n2_decision_rule_verdict"],
                     "label": "N2 locked-rule verdict; harness gate re-validated post hoc (N1b)",
                     "per_subject": {s: {"verdict": n2["per_subject"][s]["verdict"], "tp": n2["per_subject"][s]["tp"],
                                         "n_ref": n2["per_subject"][s]["n_ref"], "fp": n2["per_subject"][s]["fp"]}
                                     for s in SUBJECTS}}
    else:
        n2_status = {"status": "not verifiable: code", "label": "N1b FAILED or N2 identity differs; final for chb01/03/10 (N2 §8)"}
    out = {"status_label": RUO, "N1b_verdict": parts["N1b"], "N1prime_verdict": n1p, "N1prime_parts": parts,
           "steps": steps, "tests": tests, "rerun_identity": {"identical": identical, "hashes": h},
           "run_criteria": c1["run_criteria"], "synthetic_dry_run": syn["dry_run"], "N2": n2_status,
           "provenance": {"n1b_code_sha256": n1b_code_hashes(), "harness_hash_check": harness_hash_check(),
                          "prereg_sha256": {n: sha256_file(os.path.join(ROOT, "prereg", n)) for n in list(PREREG_LOCKED) + [N1B_PREREG]}},
           "runtime": {"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "wall_s": time.time() - t0}}
    with open(os.path.join(RES, "N1b_verdict.json"), "w", newline="\n") as fh:
        fh.write(dumps(out))
    print(json.dumps({"N1b": parts["N1b"], "N1prime": n1p, "steps": steps, "N2": n2_status["status"], "tests": tail}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["synthetic", "real", "final"], required=True)
    ap.add_argument("--tmp", default=None)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--R", type=int, default=10)
    ap.add_argument("--R-leak", type=int, default=5)
    ap.add_argument("--MC", type=int, default=1000)
    ap.add_argument("--R-total-synthetic", type=int, default=100)
    ap.add_argument("--keep-tmp", action="store_true")
    a = ap.parse_args()
    if a.phase == "synthetic":
        phase_synthetic(a.tmp, a.R_total_synthetic, a.R_leak, a.MC, a.keep_tmp)
    elif a.phase == "real":
        phase_real(a.rerun, a.R, a.R_leak, a.MC)
    else:
        phase_final()
