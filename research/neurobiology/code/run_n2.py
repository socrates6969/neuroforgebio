"""N2 baseline detection run (+ the real-data parts of N1: (a) leak controls, (b) negative controls, (c) hashes).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Usage:
  python run_n2.py                       # real CHB-MIT run, outputs results\\N2_*.json, results\\N1_ab.json, cards, figures
  python run_n2.py --rerun               # second fresh-process run for N1 (c): writes results\\rerun\\ only
  python run_n2.py --synthetic DIR --out DIR2 [--replicates R]   # same pipeline on synthetic EDFs (N1 c on synthetic)
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import datetime as dt  # noqa: E402
import json  # noqa: E402
import socket  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

CODE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

import numpy as np  # noqa: E402

from nfharness import config as C  # noqa: E402
from nfharness import stats  # noqa: E402
from nfharness.card import RUO, subject_figure, write_card  # noqa: E402
from nfharness.data import load_records, sha256_file, verify_inputs  # noqa: E402
from nfharness.features import FEATURE_NAMES, assert_whitelist, file_features  # noqa: E402
from nfharness.labels import LabelVault  # noqa: E402
from nfharness.pipeline import leak_normaliser, leak_random_split, pooled_f1, run_split, summarize  # noqa: E402
from nfharness.provenance import card_hash, code_hashes, dumps, environment, peak_rss_mb  # noqa: E402
from nfharness.scoring import Scorer, reimpl_event_score  # noqa: E402
from nfharness.splits import Split, assert_split_hash, causal_splits, split_hash, split_string  # noqa: E402

SUBJECTS = ["chb01", "chb03", "chb10"]
P_LEAK = {"chb01": 0.657, "chb03": 0.273, "chb10": 0.429}       # N1 (a), literal prereg values
FP_GRID = {"chb01": (3, 8), "chb03": (8, 14), "chb10": (8, 14)}  # (meets-bar max FP, inconclusive max FP), N2 §4
PEAK_FLAG = {"chb01": "FA on peri-ictal data only", "chb10": "FA on peri-ictal data only"}
N_NULL = 1000


def subject_verdict(s, m):
    flags = []
    if m["n_ref"] < 10:
        flags.append("CI uninformative (N_ref = %d)" % m["n_ref"])
    if m["n_ref"] != 4:
        flags.append("HARNESS FLAG: N_ref != 4")
    if s in PEAK_FLAG:
        flags.append(PEAK_FLAG[s])
    if m["n_ref"] < 3 or not m["scores_complete"]:
        return "INCONCLUSIVE", flags
    tp, fp = m["tp"], m["fp"]
    fmeet, finc = FP_GRID.get(s, (int(np.floor(m["hours"])), None))
    if finc is None:  # synthetic subjects: generic rule (meets: FA <= 24/24h; FAIL: Garwood lower > 24/24h)
        finc = max([k for k in range(0, 200) if stats.garwood(k)[0] <= m["hours"]])
    sens_meet = tp >= 3
    sens_fail = tp <= 1
    fp_meet = fp <= fmeet
    fp_fail = fp > finc
    if sens_fail or fp_fail:
        return "FAIL", flags
    if sens_meet and fp_meet:
        return "PASS", flags
    return "INCONCLUSIVE", flags


def overall(vs):
    n_pass = sum(v == "PASS" for v in vs)
    n_fail = sum(v == "FAIL" for v in vs)
    if n_pass >= 2 and n_fail == 0:
        return "PASS"
    if n_fail >= 2:
        return "FAIL"
    return "INCONCLUSIVE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--rerun", action="store_true")
    ap.add_argument("--replicates", type=int, default=10)
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    t_start = time.time()
    runtime = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "hostname": socket.gethostname()}
    stage_t = {}

    synthetic = a.synthetic is not None
    if synthetic:
        raw = a.synthetic
        subjects = sorted(d for d in os.listdir(raw) if os.path.isdir(os.path.join(raw, d)))
        out = a.out
    else:
        raw = os.path.join(ROOT, "data", "raw", "chbmit")
        subjects = SUBJECTS
        out = os.path.join(ROOT, "results", "rerun") if a.rerun else os.path.join(ROOT, "results")
    os.makedirs(out, exist_ok=True)
    cards_dir = os.path.join(out, "cards")
    os.makedirs(cards_dir, exist_ok=True)

    # ---- provenance first: prereg hashes BEFORE any label access
    prereg = {n: sha256_file(os.path.join(ROOT, "prereg", n)) for n in ("N1_harness_controls.md", "N2_baseline_detection.md")}
    runtime["prereg_hashed_at_unix"] = time.time()
    prov = {"prereg_sha256": prereg, "seed": C.SEED,
            "rng_streams": {"0": "leak split", "1": "iid label permutation", "2": "circular shift", "3": "bootstraps",
                            "4": "chance-shift nulls then random-alarm draws", "5": "synthetic fixtures"},
            "environment": environment(), "config_hash": C.LOCKED_CONFIG_HASH_LITERAL,
            "code_sha256": code_hashes(CODE, extra=[os.path.abspath(__file__)]),
            "deviations_sha256": sha256_file(os.path.join(CODE, "DEVIATIONS.md")) if os.path.exists(os.path.join(CODE, "DEVIATIONS.md")) else None}
    if not synthetic:
        man = os.path.join(ROOT, "data", "manifests", "chbmit_manifest.csv")
        sums = os.path.join(raw, "_meta", "SHA256SUMS.txt")
        t = time.time()
        prov["input_sha256"] = verify_inputs(raw, man, sums, subjects=set(subjects))
        prov["n_inputs_verified"] = {"edf": sum(k.endswith(".edf") for k in prov["input_sha256"]),
                                     "seizures": sum(k.endswith(".seizures") for k in prov["input_sha256"]),
                                     "summary": sum(k.endswith("-summary.txt") for k in prov["input_sha256"])}
        prov["manifest_sha256"] = sha256_file(man)
        prov["sha256sums_sha256"] = sha256_file(sums)
        stage_t["hash_inputs_s"] = time.time() - t
    else:
        prov["input_sha256"] = {os.path.relpath(os.path.join(dp, f), raw).replace("\\", "/"): sha256_file(os.path.join(dp, f))
                                for dp, _, fs in os.walk(raw) for f in sorted(fs)}

    records, ann = load_records(raw, subjects)
    recmap = {r.name: r for r in records}
    counts = {f: len(v) for f, v in ann.items()}
    splits = causal_splits(records, counts)
    if synthetic:
        shash = split_hash(splits)
        hash_ok = "n/a (synthetic)"
    else:
        shash = assert_split_hash(splits, C.EXPECTED_SPLIT_HASH)
        hash_ok = True
    durations = {r.name: r.duration for r in records}

    # ---- features (stream one EDF at a time)
    t = time.time()
    assert_whitelist(FEATURE_NAMES)
    feats = {}
    for r in records:
        feats[r.name] = file_features(r)
    stage_t["features_s"] = time.time() - t
    fhash = {f: __import__("hashlib").sha256(np.ascontiguousarray(v).tobytes()).hexdigest()[:16] for f, v in feats.items()}

    rng_boot = C.rng(C.STREAM_BOOTSTRAP)

    # ---- N2 primary
    t = time.time()
    primary, metrics, vaults = {}, {}, {}
    for s in subjects:
        sp = splits[s]
        subj_recs = [r for r in records if r.subject == s]
        v = LabelVault(ann, {r.name: r.duration for r in subj_recs}, protected_files=sp.test_names, name="N2-" + s)
        res = run_split(sp, feats, v, [[r] for r in sp.train], purpose="N2 primary")
        primary[s] = res
        m = summarize(res, sp.test, rng_boot)
        m["verdict"], m["flags"] = subject_verdict(s, m)
        m["n_train_windows"], m["n_train_pos_windows"] = res["n_train_windows"], res["n_train_pos"]
        m["n_buffer_dropped_windows"] = res["n_buffer_dropped"]
        m["lr_converged_all_fits"], m["n_fits"] = res["converged_all"], res["n_fits"]
        m["honest_train_window_fraction"] = res["n_train_windows"] / (res["n_train_windows"] + res["n_buffer_dropped"] + m["n_test_windows"])
        metrics[s] = m
        vaults[s] = v
    n2_verdict = overall([metrics[s]["verdict"] for s in subjects])
    stage_t["n2_primary_s"] = time.time() - t

    # ---- N1 (a) leak controls
    t = time.time()
    rng_leak = C.rng(C.STREAM_LEAK_SPLIT)
    n1a = {}
    for s in subjects:
        subj_recs = [r for r in records if r.subject == s]
        p_s = P_LEAK.get(s, round(metrics[s]["honest_train_window_fraction"], 3))
        c2a = leak_random_split(subj_recs, feats, {f: ann[f] for f in durations if recmap[f].subject == s}, p_s, rng_leak)
        c2b = leak_normaliser(splits[s], feats, vaults[s])
        h = metrics[s]["window_auroc"]
        n1a[s] = {"p_train": p_s, "honest_auroc": h, "leak_auroc_C2a": c2a["auroc"], "D": c2a["auroc"] - h,
                  "E": (1 - c2a["auroc"]) / (1 - h) if h < 1 else float("nan"), "C2b_norm_leak_auroc": c2b["auroc"],
                  "C2b_minus_honest": c2b["auroc"] - h, "C2a_n_train": c2a["n_train"], "C2a_n_test": c2a["n_test"],
                  "C2a_converged": c2a["converged"]}
    meanD = float(np.mean([n1a[s]["D"] for s in subjects]))
    meanH = float(np.mean([n1a[s]["honest_auroc"] for s in subjects]))
    meanE = float(np.mean([n1a[s]["E"] for s in subjects]))
    npos = sum(n1a[s]["D"] > 0 for s in subjects)
    a_pass = bool(((meanD >= 0.05) or (meanH >= 0.95 and meanE <= 0.50)) and npos >= 2)
    n1a_summary = {"per_subject": n1a, "mean_D": meanD, "mean_honest_auroc": meanH, "mean_E": meanE,
                   "n_subjects_D_positive": npos, "ceiling_clause_used": bool(meanD < 0.05 and meanH >= 0.95),
                   "verdict": "PASS" if a_pass else "FAIL",
                   "prediction": "honest mean 0.93, leaky 0.99, mean D +0.06, P(PASS)=0.75"}
    stage_t["n1a_s"] = time.time() - t

    # ---- N1 (b) negative controls
    t = time.time()
    R = a.replicates
    rng_null = C.rng(C.STREAM_CHANCE_NULL)
    n1b = {}
    for mode, stream in (("nc1_perm", C.STREAM_IID_PERM), ("nc2_shift", C.STREAM_CIRC_SHIFT)):
        g = C.rng(stream)
        per = {}
        obs_tp, null_tp = 0, np.zeros(N_NULL, dtype=np.int64)
        tp_all = fp_all = nref_all = 0
        for s in subjects:
            sp = splits[s]
            per[s] = []
            for rep in range(R):
                res = run_split(sp, feats, vaults[s], [[r] for r in sp.train], label_mode=mode, rng=g,
                                purpose="N1b-" + mode)
                y = np.concatenate([res["ywin"][f] for f in sp.test_names])
                sc = np.concatenate([res["p"][f] for f in sp.test_names])
                tp = sum(v["tp"] for v in res["per_file"].values())
                fp = sum(v["fp"] for v in res["per_file"].values())
                nref = sum(v["n_ref"] for v in res["per_file"].values())
                tp_all += tp
                fp_all += fp
                nref_all += nref
                obs_tp += tp
                scorer = Scorer(vaults[s], "N1b-chance-null")
                for r in sp.test:
                    offs = rng_null.integers(0, r.duration, size=N_NULL)
                    if res["per_file"][r.name]["n_ref"] > 0:
                        null_tp += scorer.shifted_tp(r.name, res["hyp"][r.name], offs)
                per[s].append({"auroc": stats.auroc(y, sc), "tp": tp, "fp": fp, "n_ref": nref, "tau": res["tau"],
                               "converged": res["converged_all"]})
        aucs = {s: [x["auroc"] for x in per[s]] for s in subjects}
        grand = float(np.mean([v for s in subjects for v in aucs[s]]))
        subj_means = {s: float(np.mean(aucs[s])) for s in subjects}
        p99 = float(np.percentile(null_tp, 99))
        crit1 = bool(0.45 <= grand <= 0.55 and all(0.35 <= v <= 0.65 for v in subj_means.values()))
        crit2 = bool(obs_tp <= p99)
        n1b[mode] = {"replicates": R, "per_subject": per, "grand_mean_auroc": grand, "subject_mean_auroc": subj_means,
                     "pooled_tp": obs_tp, "pooled_nref": nref_all, "pooled_fp": fp_all,
                     "pooled_sensitivity": obs_tp / nref_all if nref_all else float("nan"),
                     "shift_null_tp_p99": p99, "shift_null_tp_mean": float(null_tp.mean()),
                     "shift_null_sensitivity_mean": float(null_tp.mean() / nref_all) if nref_all else float("nan"),
                     "crit1_auroc": crit1, "crit2_sensitivity_vs_null": crit2}
    # C3 random-alarm control on the N2 model's own hypotheses (circular shifts, stream 4 continued)
    f1s, tps = [], []
    scorers = {s: Scorer(vaults[s], "N1b-C3-random-alarm") for s in subjects}
    for _ in range(N_NULL):
        TP = FP = NR = 0
        for s in subjects:
            for r in splits[s].test:
                o = int(rng_null.integers(0, r.duration))
                e = reimpl_event_score(scorers[s]._ref(r.name), np.roll(primary[s]["hyp"][r.name], o))
                TP, FP, NR = TP + e["tp"], FP + e["fp"], NR + e["n_ref"]
        f = pooled_f1(TP, FP, NR)
        f1s.append(0.0 if f != f else f)
        tps.append(TP)
    c3 = {"draws": N_NULL, "mean_pooled_f1": float(np.mean(f1s)), "p95_pooled_f1": float(np.percentile(f1s, 95)),
          "mean_pooled_tp": float(np.mean(tps)), "crit3_f1_le_0.05": bool(np.mean(f1s) <= 0.05)}
    b_pass = bool(all(n1b[m]["crit1_auroc"] and n1b[m]["crit2_sensitivity_vs_null"] for m in n1b) and c3["crit3_f1_le_0.05"])
    n1b_summary = {"NC1_iid_permutation": n1b["nc1_perm"], "NC2_circular_shift": n1b["nc2_shift"], "C3_random_alarm": c3,
                   "verdict": "PASS" if b_pass else "FAIL",
                   "prediction": "NC1/NC2 grand mean 0.50, null sensitivity ~0.04 (<= p99), random-alarm F1 ~0.01, P(PASS)=0.85"}
    stage_t["n1b_s"] = time.time() - t

    # ---- S-a cross-patient (descriptive)
    t = time.time()
    s_a = {}
    for held in subjects:
        tr = [r for r in records if r.subject != held]
        te = [r for r in records if r.subject == held]
        sp = Split("cross_patient", tr, te, label="LOSO-" + held)
        v = LabelVault(ann, durations, protected_files=[r.name for r in te], name="S-a-" + held)
        groups = [[r for r in tr if r.subject == g] for g in subjects if g != held]
        res = run_split(sp, feats, v, groups, purpose="S-a")
        m = summarize(res, te)
        s_a[held] = {k: m[k] for k in ("tp", "n_ref", "fp", "hours", "sensitivity", "fa_per_24h", "precision", "f1",
                                       "window_auroc", "window_auprc", "prevalence", "tau", "latency_median")}
    stage_t["s_a_s"] = time.time() - t

    # ---- S-b future-leak variant (non-causal, Shoeb-style)
    t = time.time()
    s_b = {}
    for s in subjects:
        subj = sorted([r for r in records if r.subject == s], key=lambda r: r.t_start)
        comb = {"p": {}, "hyp": {}, "per_file": {}, "ywin": {}, "tau": []}
        for f in splits[s].test:
            tr = [r for r in subj if r.name != f.name]
            sp = Split("future_leak", tr, [f], label="S-b-" + f.name)
            v = LabelVault(ann, {r.name: r.duration for r in subj}, protected_files=[f.name], name="S-b-" + f.name)
            res = run_split(sp, feats, v, [[r] for r in tr], purpose="S-b")
            for k in ("p", "hyp", "per_file", "ywin"):
                comb[k].update(res[k])
            comb["tau"].append(res["tau"])
        m = summarize(comb, splits[s].test)
        s_b[s] = {"auroc_future": m["window_auroc"], "f1_future": m["f1"], "tp": m["tp"], "fp": m["fp"], "n_ref": m["n_ref"],
                  "taus": comb["tau"], "auroc_causal": metrics[s]["window_auroc"], "f1_causal": metrics[s]["f1"]}
    dA = float(np.mean([s_b[s]["auroc_future"] - s_b[s]["auroc_causal"] for s in subjects]))
    dF = float(np.mean([s_b[s]["f1_future"] - s_b[s]["f1_causal"] for s in subjects]))
    s_b_summary = {"per_subject": s_b, "mean_dAUROC_future_minus_causal": dA, "mean_dF1_future_minus_causal": dF,
                   "leak_demonstrated": bool(dA > 0 or dF > 0)}
    stage_t["s_b_s"] = time.time() - t

    # ---- guard registry + vault logs
    guards = dict(sorted(C.GUARD_CALLS.items()))
    vault_logs = {s: vaults[s].summary() for s in subjects}
    first_read = min(v.first_scorer_read_time for v in vaults.values() if v.first_scorer_read_time)
    runtime["first_test_label_read_unix"] = first_read
    runtime["prereg_hash_precedes_first_label_read"] = bool(runtime["prereg_hashed_at_unix"] < first_read)

    known_n1_fail = [k for k, ok in (("a", a_pass), ("b", b_pass)) if not ok]
    if not s_b_summary["leak_demonstrated"]:
        known_n1_fail.append("S-b leak demonstration")
    n2_status = n2_verdict if not known_n1_fail else "not verifiable: code (harness not validated: N1 %s failed)" % ",".join(known_n1_fail)

    # ---- per-subject evaluation cards + run card
    split_note = "split computed from manifest + per-file seizure counts before feature extraction (S7)"
    common = {
        "status_label": RUO, "task": "seizure DETECTION, patient-specific causal split (S2 variant, N2 §1); CHB-MIT bipolar, "
        "22 unique channels of the 23-channel double-banana montage (duplicate T8-P8 dropped)",
        "data": {"dataset": "CHB-MIT Scalp EEG Database v1.0.0, DOI 10.13026/C2K01R, ODC-By 1.0" if not synthetic else "SYNTHETIC",
                 "subjects": ", ".join(subjects) + (" (chb01/chb21 same patient; chb21 not used)" if not synthetic else ""),
                 "hours_scored_test": {s: metrics[s]["hours"] for s in subjects},
                 "test_seizures_N_ref": {s: metrics[s]["n_ref"] for s in subjects},
                 "exclusions": "none within the 29-file subset (see notes\\data_subset.md for subset selection)"},
        "split": {"scheme": "causal: train through the file with the 3rd seizure; test = later files", "buffer_s": C.BUFFER_S,
                  "hash": shash, "hash_matches_prereg": hash_ok, "note": split_note,
                  "folds": {s: {"train": splits[s].train_names, "test": splits[s].test_names} for s in subjects}},
        "model": {"features": "132 = 22 ch x [log10 LL, log10 BP 1-4, 4-8, 8-13, 13-30, 30-55 Hz], 2-s windows, 1-s step",
                  "normaliser": "z-score fitted on training windows only (F1 guard)",
                  "classifier": "L2 logistic regression C=1, balanced weights, scipy L-BFGS-B gtol 1e-6 maxiter 1000",
                  "postprocessing": "causal 4-of-5, no minimum duration; timescoring merge 90 s / split 300 s",
                  "threshold": "tau* = smallest grid tau (0.05..0.99) with inner-LOFO train FA <= 12/24h",
                  "config_sha256": C.LOCKED_CONFIG_HASH_LITERAL},
    }
    leak_check = {
        "L1.1 no test set / test in training": "train/test file-disjoint; F8 LabelVault (tests F8), F6 causal (tests F6)",
        "L1.2 preprocessing on train+test": "F1 normaliser fit-ID guard (tests F1); C2b quantifies",
        "L1.3 feature selection / tuning on test": "F2 config hash + inner-CV test-ID refusal; F3 tau from train_oof only",
        "L1.4 duplicates": "windows never cross files (F4); duplicate T8-P8 channel dropped",
        "L2 illegitimate features": "F7 whitelist of 132 signal features",
        "L3.1 temporal leakage": "F6 causal split; S-b quantifies the non-causal alternative",
        "L3.2 non-independence train/test": "F4 buffer B=10 s; S5 random window split forbidden (C2a quantifies)",
        "L3.3 sampling bias test distribution": "continuous full test recordings (S6); no sub-sampling",
    }
    controls = {"N1a_positive_leak": n1a_summary, "N1b_negative": {k: v for k, v in n1b_summary.items()},
                "S-b_future_leak": s_b_summary, "guard_calls_real_run": guards,
                "N1c_rerun_identity": "evaluated by run_n1.py --final (compares this card with results\\rerun\\)",
                "N1d_N1e": "see results\\N1_cde_synthetic.json"}
    runtime["wall_s"] = time.time() - t_start
    runtime["stage_s"] = stage_t
    runtime["peak_ram_mb"] = peak_rss_mb()

    run_card = dict(common)
    run_card.update({"run_id": "N2-%s-%s" % ("synthetic" if synthetic else "chbmit", shash[:12]),
                     "verdict": n2_status, "n2_decision_rule_verdict": n2_verdict,
                     "verdict_note": "N2 counts only if N1 PASSES (all parts a-e). Parts known in this run: (a) %s, (b) %s." % (
                         n1a_summary["verdict"], n1b_summary["verdict"]),
                     "metrics": metrics, "cross_subject": {
                         "DESCRIPTIVE_mean_window_auroc": float(np.mean([metrics[s]["window_auroc"] for s in subjects])),
                         "DESCRIPTIVE_mean_sensitivity": float(np.mean([metrics[s]["sensitivity"] for s in subjects])),
                         "note": "3 clusters; no across-subject CI is valid inference (CI2)"},
                     "secondary_S-a_cross_patient": s_a, "controls": controls, "leakage_checklist": leak_check,
                     "provenance": dict(prov, split_hash=shash, feature_sha256_16=fhash, label_vault_logs=vault_logs),
                     "runtime": runtime})
    h_run = write_card(run_card, os.path.join(out, "N2_run_card.json"), os.path.join(cards_dir, "N2_run_card.md"))
    sub_hashes = {}
    for s in subjects:
        c = dict(common)
        c["split"] = dict(common["split"], folds={s: common["split"]["folds"][s]})
        c.update({"run_id": "N2-%s-%s" % (s, shash[:12]), "verdict": "%s (subject %s: %s)" % (n2_status, s, metrics[s]["verdict"]),
                  "verdict_note": "Subject-level decision-rule verdict: %s. Overall N2: %s." % (metrics[s]["verdict"], n2_status),
                  "metrics": {s: metrics[s]}, "controls": {"N1a": n1a[s], "NC1_mean_auroc": n1b["nc1_perm"]["subject_mean_auroc"][s],
                                                          "NC2_mean_auroc": n1b["nc2_shift"]["subject_mean_auroc"][s],
                                                          "S-a_held_out": s_a[s], "S-b": s_b[s]},
                  "leakage_checklist": leak_check, "provenance": dict(prov, split_hash=shash, label_vault=vault_logs[s]),
                  "runtime": runtime})
        sub_hashes[s] = write_card(c, os.path.join(cards_dir, "%s_card.json" % s), os.path.join(cards_dir, "%s_card.md" % s))
        if not a.no_figures and not a.rerun:
            figdir = os.path.join(ROOT, "figures") if not synthetic else out
            sc = Scorer(vaults[s], "figure")
            subject_figure(s, metrics[s], primary[s]["p"], primary[s]["hyp"], {f: sc._ref(f) for f in splits[s].test_names},
                           primary[s]["tau"], os.path.join(figdir, "card_%s" % s),
                           "overall N2: %s" % n2_status)

    results = {"n2_verdict": n2_status, "n2_decision_rule_verdict": n2_verdict,
               "per_subject": {s: {k: metrics[s][k] for k in metrics[s] if k != "per_file"} for s in subjects},
               "card_sha256_excl_runtime": {"run": h_run, **sub_hashes}, "S-a": s_a, "S-b": s_b_summary,
               "provenance": dict(prov, split_hash=shash), "runtime": runtime}
    with open(os.path.join(out, "N2_results.json"), "w", newline="\n") as fh:
        fh.write(dumps(results))
    with open(os.path.join(out, "N1_ab.json"), "w", newline="\n") as fh:
        fh.write(dumps({"N1a": n1a_summary, "N1b": n1b_summary, "guard_calls_real_run": guards,
                        "prereg_hash_precedes_first_label_read": runtime["prereg_hash_precedes_first_label_read"],
                        "provenance": dict(prov, split_hash=shash), "runtime": runtime}))
    print(json.dumps({"n2": n2_status, "subjects": {s: (metrics[s]["verdict"], metrics[s]["tp"], metrics[s]["fp"],
                      round(metrics[s]["window_auroc"], 4)) for s in subjects}, "N1a": n1a_summary["verdict"],
                      "N1b": n1b_summary["verdict"], "card_hash": h_run, "wall_s": round(runtime["wall_s"], 1),
                      "peak_mb": runtime["peak_ram_mb"]}))


if __name__ == "__main__":
    main()
