"""Reviewer checks for N3: lock/timeline, subject selection rule, data provenance, locked-code hashes, rerun identity,
gate recomputation from the card's replicate records, pooled-statistic implementation + exactness, verdict strings.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Read-only on code\\ and results\\; writes code\\review\\n3_provenance_gates_out.json.
"""
import csv
import datetime as dt
import glob
import hashlib
import json
import math
import os
import sys
from fractions import Fraction

import numpy as np
from scipy.stats import chi2

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
CODE = os.path.join(ROOT, "code")
RES = os.path.join(ROOT, "results")
RAW = os.path.join(ROOT, "data", "raw", "chbmit")
OUT = os.path.join(CODE, "review", "n3_provenance_gates_out.json")
out = {}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def utc_mtime(p):
    return dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc)


card = json.load(open(os.path.join(RES, "N3_card.json")))
card2 = json.load(open(os.path.join(RES, "rerun", "N3_card.json")))
lock = json.load(open(os.path.join(RES, "cards", "N3_prereg_lock.json")))
verdict = json.load(open(os.path.join(RES, "N3_verdict.json")))

# ------------------------------------------------------------------ (1) lock and timeline
prereg = os.path.join(ROOT, "prereg", "N3_harness_validation_fresh.md")
lock_t = dt.datetime.fromisoformat(lock["written_utc"])
data_files = sorted(glob.glob(os.path.join(RAW, "chb23", "*")) + glob.glob(os.path.join(RAW, "chb24", "*")))
first_data = min(utc_mtime(p) for p in data_files)
man_rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "data", "manifests", "chbmit_manifest.csv")))
            if r["file"].startswith(("chb23/", "chb24/"))]
first_dl_manifest = min(dt.datetime.fromisoformat(r["download_utc"].replace("Z", "+00:00")) for r in man_rows)
run1_start = dt.datetime.fromisoformat(card["runtime"]["started_utc"])
run2_start = dt.datetime.fromisoformat(card2["runtime"]["started_utc"])
last_data = max(utc_mtime(p) for p in data_files)
out["1_lock_timeline"] = {
    "prereg_sha256_now": sha(prereg), "lock_sha256": lock["prereg_sha256"],
    "prereg_mtime_utc": utc_mtime(prereg).isoformat(), "lock_written_utc": lock["written_utc"],
    "first_chb23_24_file_mtime_utc": first_data.isoformat(), "first_manifest_download_utc": first_dl_manifest.isoformat(),
    "last_data_file_mtime_utc": last_data.isoformat(), "run1_started_utc": run1_start.isoformat(),
    "run2_started_utc": run2_start.isoformat(),
    "prereg_mtime_before_lock": utc_mtime(prereg) < lock_t,
    "lock_before_first_download": lock_t < first_data and lock_t < first_dl_manifest,
    "download_finished_before_run1": last_data < run1_start,
    "lock_hash_eq_prereg_eq_card": sha(prereg) == lock["prereg_sha256"] == card["provenance"]["prereg_sha256"]["N3_harness_validation_fresh.md"],
    "n3_code_mtimes_utc": {os.path.relpath(p, CODE): utc_mtime(p).isoformat() for p in
                           sorted(glob.glob(os.path.join(CODE, "n3", "*.py"))) + [os.path.join(CODE, "run_n3.py")]},
    "dry_run_file_mtime_utc": utc_mtime(os.path.join(RES, "N3_synthetic.json")).isoformat()}

# ------------------------------------------------------------------ (1b) selection rule re-applied (annotations + headers)
inv = list(csv.DictReader(open(os.path.join(ROOT, "notes", "data", "chbmit_inventory.csv"))))
STD = inv[0]["labels"]           # chb01_01 labels (the standard 23)


def tstart(r):
    d, m, y = map(int, r["edf_start_date"].split("."))
    hh, mi, ss = map(int, r["edf_start_time"].split("."))
    return dt.datetime(1900 + y if y > 30 else 2000 + y, m, d, hh, mi, ss)


sel = {}
for s in sorted({r["subject"] for r in inv}):
    rows = [r for r in inv if r["subject"] == s and r["n_seizures"] not in ("", "0")]
    rows.sort(key=tstart)
    seiz = []
    for r in rows:
        ev = [tuple(map(int, x.split("-"))) for x in r["seizures_start_end_s"].split(";") if x]
        seiz.append((r, ev))
    cum, train, test, nref = 0, [], [], 0
    reason = []
    if s in ("chb01", "chb03", "chb10", "chb21"):
        reason.append("E0")
    i = 0
    while i < len(seiz) and cum < 3:
        cum += len(seiz[i][1]); train.append(seiz[i][0]); i += 1
    while i < len(seiz) and nref < 4:
        ev = seiz[i][1]
        # merge seizures < 90 s apart into one reference
        n = 0
        last_end = None
        for a, b in ev:
            if last_end is None or a - last_end >= 90:
                n += 1
            last_end = b
        nref += n; test.append(seiz[i][0]); i += 1
    if cum < 3 or nref < 4:
        reason.append("E2*")
    if len(train) < 2:
        reason.append("E5")
    r2 = train + test
    if any(r["labels"] != STD or r["n_signals"] != "23" for r in r2):
        reason.append("E1")
    if any(r["in_summary"] != "1" for r in r2):
        reason.append("E3*")
    sel[s] = {"eligible": not reason, "fail": reason, "train": [r["file"] for r in train], "test": [r["file"] for r in test],
              "n_ref": nref, "r2_bytes": sum(int(r["size_bytes"]) for r in r2),
              "test_hours": round(sum(int(r["duration_s"]) for r in test) / 3600, 3)}
elig = sorted([s for s in sel if sel[s]["eligible"]], key=lambda s: sel[s]["r2_bytes"])
split_txt = "\n".join("%s;train=%s;test=%s" % (s, ",".join(sel[s]["train"]), ",".join(sel[s]["test"])) for s in sorted(elig[:2]))
out["1b_selection"] = {"eligible": elig, "chosen_two_smallest": sorted(elig[:2]), "per_subject": sel,
                       "split_string": split_txt, "split_hash": hashlib.sha256(split_txt.encode()).hexdigest(),
                       "split_hash_eq_prereg": hashlib.sha256(split_txt.encode()).hexdigest()
                       == "9320fa73c5e52ce449f7257f47dda5fce87a25b53d812f51dbf6b21bc0397a19",
                       "chb24_header_order": [(r["file"], r["edf_start_date"], r["edf_start_time"])
                                              for r in sorted([r for r in inv if r["subject"] == "chb24"
                                                               and r["n_seizures"] not in ("", "0")], key=tstart)][:5]}

# ------------------------------------------------------------------ (5) data provenance
sums = {}
for line in open(os.path.join(RAW, "_meta", "SHA256SUMS.txt")):
    p = line.split()
    if len(p) == 2:
        sums[p[1]] = p[0]
prov = {}
for p in data_files:
    rel = os.path.relpath(p, RAW).replace("\\", "/")
    h = sha(p)
    prov[rel] = {"sha256": h, "eq_physionet": sums.get(rel) == h, "eq_card": card["provenance"]["input_sha256"].get(rel) == h,
                 "eq_manifest": any(r["file"] == rel and r["sha256"] == h and r["verified"] == "yes" for r in man_rows)}
out["5_data_provenance"] = {"n_files": len(prov), "all_eq_physionet": all(v["eq_physionet"] for v in prov.values()),
                            "all_eq_card": all(v["eq_card"] for v in prov.values()),
                            "all_eq_manifest": all(v["eq_manifest"] for v in prov.values()),
                            "card_n_inputs": card["provenance"]["n_inputs_verified"], "files": prov}

# ------------------------------------------------------------------ (2h) locked code hashes, n3 code = code that ran
ref = json.load(open(os.path.join(RES, "N2_run_card.json")))["provenance"]["code_sha256"]
refb = json.load(open(os.path.join(RES, "N1b_card.json")))["provenance"]["n1b_code_sha256"]
now = {k: sha(os.path.join(CODE, *k.split("/"))) for k in ref}
nowb = {k: sha(os.path.join(CODE, *k.split("/"))) for k in refb}
now3 = {k: sha(os.path.join(CODE, *k.split("/"))) for k in card["provenance"]["n3_code_sha256"]}
extra_nf = sorted(os.path.relpath(p, CODE).replace("\\", "/") for p in glob.glob(os.path.join(CODE, "nfharness", "*.py")))
out["2h_code_hashes"] = {"nfharness_17_eq_N2_run_card": now == ref, "n_nfharness_files": len(ref),
                         "nfharness_py_on_disk_all_in_ref": all(k in ref for k in extra_nf),
                         "n1b_eq_N1b_card": nowb == refb, "n3_code_eq_card": now3 == card["provenance"]["n3_code_sha256"],
                         "n3_code_eq_rerun_card": now3 == card2["provenance"]["n3_code_sha256"],
                         "card_locked_nfharness_eq_ref": card["provenance"]["locked_code"]["nfharness"]["sha256"] == ref,
                         "N2_run_card_sha_now": sha(os.path.join(RES, "N2_run_card.json")),
                         "deviations_snapshot_sha_eq_card": sha(os.path.join(RES, "N3_DEVIATIONS_snapshot.md"))
                         == card["provenance"]["deviations_snapshot_sha256"],
                         "snapshot_is_prefix_of_current_DEVIATIONS": open(os.path.join(CODE, "DEVIATIONS.md"), "rb").read().startswith(
                             open(os.path.join(RES, "N3_DEVIATIONS_snapshot.md"), "rb").read())}

# ------------------------------------------------------------------ (5b) rerun identity (own comparison, not card_hash)
c1 = {k: v for k, v in card.items() if k not in ("runtime", "card_sha256_excl_runtime")}
c2 = {k: v for k, v in card2.items() if k not in ("runtime", "card_sha256_excl_runtime")}
own = lambda c: hashlib.sha256(json.dumps(c, sort_keys=True, separators=(",", ":")).encode()).hexdigest()  # noqa: E731
sys.path.insert(0, CODE)
from nfharness.provenance import card_hash  # noqa: E402
out["5b_rerun"] = {"dict_equal_excl_runtime": c1 == c2, "own_hash_run1": own(c1), "own_hash_run2": own(c2),
                   "harness_card_hash_run1": card_hash({k: v for k, v in card.items() if k != "card_sha256_excl_runtime"}),
                   "stored_run1": card["card_sha256_excl_runtime"], "stored_run2": card2["card_sha256_excl_runtime"],
                   "run2_fresh_process_distinct_start": card["runtime"]["started_utc"] != card2["runtime"]["started_utc"]}
out["5b_rerun"]["harness_hash_eq_stored"] = out["5b_rerun"]["harness_card_hash_run1"] == card["card_sha256_excl_runtime"] == card2["card_sha256_excl_runtime"]


# ------------------------------------------------------------------ (2) gates recomputed from replicate records
def fisher(ps):
    ps = [p for p in ps]
    return float(chi2.sf(-2 * sum(math.log(p) for p in ps), 2 * len(ps))), len(ps)


ct = card["controls"]
ncp = ct["NC-P"]["replicates"]
wf = [r for r in ncp if not r["window_flag_sd"]]
fu, n = fisher([r["p_A_up"] for r in wf]); fl, _ = fisher([r["p_A_lo"] for r in wf])
ret = [r for r in ncp if not r["degeneracy_rm"]["degenerate"]]
T = sum((Fraction(2 * r["E_rm"]["tp"], r["E_rm"]["tp"] + r["E_rm"]["fp"] + r["E_rm"]["n_ref"])
         if (r["E_rm"]["tp"] + r["E_rm"]["fp"] + r["E_rm"]["n_ref"]) else Fraction(0) for r in ret), Fraction(0))
pla = ct["PL-A"]["replicates"]
pla_f, pla_n = fisher([r["p_A_up"] for r in pla if not r["window_flag_sd"]])
pla10 = ct["PL-A10_descriptive"]["replicates"]
pla10_f, _ = fisher([r["p_A_up"] for r in pla10 if not r["window_flag_sd"]])
plb = ct["PL-B_descriptive"]["replicates"]
spec = sum(1 for a, b in zip(ncp, plb) if (a["p_A_up"], a["p_A_lo"], a["subject"], a["replicate"]) ==
           (b.get("p_A_up", a["p_A_up"]), b.get("p_A_lo", a["p_A_lo"]), b.get("subject", a["subject"]), b.get("replicate", a["replicate"])))
c3 = card["C3prime"]
ex, mc = c3["exact"], c3["mc"]
b_i = 3 * ex["sigma_star"] / math.sqrt(mc["M"])
b_ii = ex["a_star"] + 3 * math.sqrt(ex["a_star"] * (1 - ex["a_star"]) / mc["M"])
pool = ct["NC-P"]["event_arm"]["pooled_SigmaF1"]
out["2_gates"] = {
    "V1-A": {"fisher_up": fu, "fisher_lo": fl, "n": n, "eq_card": (abs(fu - ct["NC-P"]["T_A_fisher_up"]) < 1e-12,
                                                                  abs(fl - ct["NC-P"]["T_A_fisher_lo"]) < 1e-12),
             "met": fu >= 0.0025 and fl >= 0.0025},
    "V2-A": {"n_window_flagged": sum(r["window_flag_sd"] for r in ncp), "n": len(ncp),
             "met": sum(r["window_flag_sd"] for r in ncp) <= 1},
    "V1-E": {"n_retained": len(ret), "T_recomputed": str(T), "T_eq_card": str(T) == pool["T_exact"], "p_up": pool["p_up"],
             "p_lo": pool["p_lo"], "p_up_plus_p_lo_ge_1": pool["p_up"] + pool["p_lo"] >= 1.0,
             "met": pool["p_up"] >= 0.0025 and pool["p_lo"] >= 0.0025,
             "degenerate_ids": [(r["subject"], r["replicate"]) for r in ncp if r["degeneracy_rm"]["degenerate"]]},
    "PL-A": {"fisher_T_A_up": pla_f, "n": pla_n, "eq_card": abs(pla_f - ct["PL-A"]["fisher_T_A_up"]) < 1e-20 or
             abs(pla_f / ct["PL-A"]["fisher_T_A_up"] - 1) < 1e-9, "trips": pla_f < 0.0025,
             "plant_labels": sorted({str(r.get("plant")) for r in pla}),
             "leak_fracs": sorted({json.dumps(r.get("leak"), sort_keys=True)[:200] for r in pla})[:2]},
    "PL-A10": {"fisher_T_A_up": pla10_f, "eq_card": abs(pla10_f / ct["PL-A10_descriptive"]["fisher_T_A_up"] - 1) < 1e-9},
    "PL-B_specificity_pairs_equal": spec, "PL-B_n": len(plb),
    "C3prime": {"bound_i": b_i, "bound_ii": b_ii, "abs_diff": abs(mc["mean_mc"] - ex["mu_star"]),
                "crit_i": abs(mc["mean_mc"] - ex["mu_star"]) <= b_i, "crit_ii": mc["frac_above_q95"] <= b_ii,
                "pmf_mass": float(sum(Fraction(v) if isinstance(v, str) else Fraction(v) for v in
                                      (c3["exact_pmf"].values() if isinstance(c3["exact_pmf"], dict) else [])) or 0)},
    "PL-C": {"frac_above_q95": c3["PL-C"]["frac_above_q95"], "bound_ii": b_ii, "trips": c3["PL-C"]["frac_above_q95"] > b_ii},
    "PL-B-code_inprocess": card["PL-B-code_inprocess"]["all_raised"],
}

# ------------------------------------------------------------------ (2e) pooled_test implementation vs own, and exactness
from n3.pooled import pooled_test  # noqa: E402

g = np.random.default_rng(20260926)


def own_pooled(obs, nulls):
    # exact integer arithmetic: common denominator of all F1 fractions
    fr = lambda tp, fp, nr: Fraction(2 * int(tp), int(tp + fp + nr)) if (tp + fp + nr) else Fraction(0)  # noqa: E731
    T = sum(fr(*o) for o in obs)
    M = nulls[0].shape[0]
    Tn = [sum(fr(*a[b]) for a in nulls) for b in range(M)]
    return (1 + sum(x >= T for x in Tn)) / (M + 1), (1 + sum(x <= T for x in Tn)) / (M + 1)


def draw(n, q, nev, K=4):
    tp = g.binomial(K, q, size=n)
    tp = np.minimum(tp, nev)
    return np.stack([tp, nev - tp, np.full(n, K)], axis=1)


agree, ps_up = 0, []
n_exp, R, M = 400, 18, 199
for e in range(n_exp):
    qs = g.beta(0.6, 3.0, size=R); nevs = 1 + g.poisson(5.0, size=R)
    reps = [draw(M + 1, qs[r], nevs[r]) for r in range(R)]
    obs = [tuple(int(x) for x in a[0]) for a in reps]
    nulls = [a[1:] for a in reps]
    pt = pooled_test(obs, nulls, "F1")
    if e < 60:
        agree += (pt["p_up"], pt["p_lo"]) == own_pooled(obs, nulls)
    ps_up.append(pt["p_up"])
ps_up = np.asarray(ps_up)
out["2e_pooled_impl"] = {"n_compared_with_own_exact": 60, "n_agree": agree, "size_check_n_exp": n_exp, "M": M, "R": R,
                         "frac_p_up_lt_0.05": float(np.mean(ps_up < 0.05)), "frac_p_up_lt_0.1": float(np.mean(ps_up < 0.1)),
                         "frac_p_up_le_0.01": float(np.mean(ps_up <= 0.01))}

# ------------------------------------------------------------------ (4) verdict strings
pers = card["N2_model"]["per_subject"]
out["4_verdicts"] = {"harness": verdict["N3_harness_verdict"], "failed_items": verdict["failed_items"], "flags": verdict["flags"],
                     "all_13_items_true": all(verdict["gate_items"].values()) and len(verdict["gate_items"]) == 13,
                     "chb23": pers["chb23"]["verdict"], "chb24": pers["chb24"]["verdict"],
                     "overall": verdict["N2_model_test"]["status"], "label": verdict["N2_model_test"]["label"],
                     "pytest": verdict["tests"]["summary"], "dry_run_PASS": verdict["synthetic_dry_run"]["PASS"],
                     "dry_run_event_arm_n_retained": verdict["synthetic_dry_run"]["a_pooled_SigmaF1_up_per_replicate"]["n"],
                     "verdict_code_hashes_eq_now": verdict["provenance"]["n3_code_sha256"] == now3}

with open(OUT, "w") as fh:
    json.dump(out, fh, indent=1, default=str)
for k, v in out.items():
    s = json.dumps(v, default=str)
    print(k, s[:1500])
