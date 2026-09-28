"""REVIEW N1b (independent reviewer): hashes/provenance + recompute every gate number from the replicate records.
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Reads results only; modifies nothing. Writes n1b_card_recompute_out.json.
Includes sensitivity analyses (NOT the prereg rule): Fisher with degenerate p=1 included, Lancaster mid-p, Stouffer."""
import glob
import hashlib
import json
import math
import os

import numpy as np
from scipy.stats import chi2, norm

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
CODE = os.path.join(ROOT, "code")
RES = os.path.join(ROOT, "results")
A = 0.0025


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def fisher(ps):
    ps = [p for p in ps if p == p]
    if not ps:
        return float("nan"), 0
    return float(chi2.sf(-2 * sum(math.log(p) for p in ps), 2 * len(ps))), len(ps)


def midp(p_up, p_lo, M=999):
    ge = round(p_up * (M + 1)) - 1          # #null >= obs
    le = round(p_lo * (M + 1)) - 1          # #null <= obs
    gt = M - le
    eq = ge - gt
    return (gt + 0.5 * eq + 0.5) / (M + 1)   # randomised-p centre, (M+1)-denominator convention


def stouffer(ps):
    ps = [min(max(p, 1e-300), 1 - 1e-12) for p in ps]
    z = sum(norm.isf(p) for p in ps) / math.sqrt(len(ps))
    return float(norm.sf(z))


out = {}
card = json.load(open(os.path.join(RES, "N1b_card.json")))
card2 = json.load(open(os.path.join(RES, "rerun", "N1b_card.json")))
n2card = json.load(open(os.path.join(RES, "N2_run_card.json")))
n2res = json.load(open(os.path.join(RES, "N2_results.json")))
verdict = json.load(open(os.path.join(RES, "N1b_verdict.json")))
syn = json.load(open(os.path.join(RES, "N1b_synthetic.json")))

# ---------------- 1. hashes
files = sorted(glob.glob(os.path.join(CODE, "nfharness", "*.py"))) + [os.path.join(CODE, "edf_reader.py"),
                                                                     os.path.join(CODE, "run_n2.py")]
now = {os.path.relpath(f, CODE).replace("\\", "/"): sha(f) for f in files}
ref = n2card["provenance"]["code_sha256"]
out["harness_now_vs_N2_run_card"] = {"n_now": len(now), "n_ref": len(ref),
                                     "mismatch": sorted(k for k in set(now) | set(ref) if now.get(k) != ref.get(k))}
out["harness_card_vs_N2_run_card"] = sorted(k for k in set(ref) | set(card["provenance"]["harness_hash_check"]["sha256"])
                                            if ref.get(k) != card["provenance"]["harness_hash_check"]["sha256"].get(k))
n1bnow = {os.path.relpath(f, CODE).replace("\\", "/"): sha(f)
          for f in sorted(glob.glob(os.path.join(CODE, "n1b", "*.py"))) + [os.path.join(CODE, "run_n1b.py")]
          + sorted(glob.glob(os.path.join(CODE, "tests", "test_n1b*.py")))}
out["n1b_code_now_vs_card"] = sorted(k for k in set(n1bnow) | set(card["provenance"]["n1b_code_sha256"])
                                     if n1bnow.get(k) != card["provenance"]["n1b_code_sha256"].get(k))
out["n1b_code_card_vs_synthetic"] = sorted(k for k in set(n1bnow) if syn["provenance"]["n1b_code_sha256"].get(k) != card["provenance"]["n1b_code_sha256"].get(k))
pre = {n: sha(os.path.join(ROOT, "prereg", n)) for n in ("N1_harness_controls.md", "N2_baseline_detection.md", "N1b_negative_controls_v2.md")}
out["prereg_now"] = pre
out["prereg_now_eq_card"] = pre == card["provenance"]["prereg_sha256"] == syn["provenance"]["prereg_sha256"]
out["deviations_snapshot_sha_eq_card"] = sha(os.path.join(RES, "N1b_DEVIATIONS_snapshot.md")) == card["provenance"]["deviations_snapshot_sha256"]
out["deviations_snapshot_contains_N1b_15"] = "N1b-15" in open(os.path.join(RES, "N1b_DEVIATIONS_snapshot.md"), encoding="utf-8").read()


def canon(o):
    return json.dumps(o, sort_keys=True, indent=1, allow_nan=False)


def chash(c):
    c = {k: v for k, v in c.items() if k not in ("runtime", "card_sha256_excl_runtime")}
    return hashlib.sha256(canon(c).encode()).hexdigest()


out["card_hash"] = {"run1_recomputed": chash(card), "run2_recomputed": chash(card2),
                    "run1_stored": card["card_sha256_excl_runtime"], "run2_stored": card2["card_sha256_excl_runtime"]}
# N2 identity: card recomputed values vs N2_results.json (repr)
idn = {}
for s, v in card["N2_identity"]["per_subject"].items():
    idn[s] = all(repr(v["recomputed"][k]) == repr(n2res["per_subject"][s][k]) for k in v["recomputed"])
out["N2_identity_vs_N2_results_json"] = idn


# ---------------- 2. recompute gate numbers
def agg(reps):
    ev = [r for r in reps if not r["degeneracy_rm"]["degenerate"]]
    wa = [r for r in reps if not r["window_flag_sd"]]
    return {"fA_up": fisher([r["p_A_up"] for r in wa])[0], "fA_lo": fisher([r["p_A_lo"] for r in wa])[0],
            "fE_up": fisher([r["E_rm"]["p_up"] for r in ev])[0], "fE_lo": fisher([r["E_rm"]["p_lo"] for r in ev])[0],
            "n_ev": len(ev), "n_deg": len(reps) - len(ev), "n_wflag": len(reps) - len(wa)}


checks = {}
for blk in ("NC-P", "PL-A"):
    reps = card[blk]["replicates"]
    a = agg(reps)
    f = card[blk]["aggregate"]["fisher"]
    checks[blk] = {"recomputed": a, "card": f,
                   "match": all(abs(a[x] - f[y]) <= 1e-12 * max(1, abs(f[y])) for x, y in
                                (("fA_up", "T_A_up"), ("fA_lo", "T_A_lo"), ("fE_up", "T_E_up"), ("fE_lo", "T_E_lo")))}
    # p-value sanity: grid k/1000, p_up + p_lo >= 1 + 1/1000, degeneracy label-free consistency
    bad = []
    for r in reps:
        for arm in ("E_rm", "E_locked"):
            pu, pl = r[arm]["p_up"], r[arm]["p_lo"]
            if abs(pu * 1000 - round(pu * 1000)) > 1e-9 or pu + pl < 1.001 - 1e-12:
                bad.append((r["subject"], r["replicate"], arm))
            if r[arm]["tp"] == 0 and pu != 1.0:
                bad.append(("zeroTP_p_not_1", r["subject"], r["replicate"], arm))
        d = r["degeneracy_rm"]
        if d["never_alarm"] != (d["n_events"] == 0) or d["always_alarm"] != (d["coverage"] >= 0.5):
            bad.append(("deg", r["subject"], r["replicate"]))
        if d["never_alarm"] and r["E_rm"]["fp"] != 0:
            bad.append(("never_alarm_but_fp", r["subject"], r["replicate"]))
    checks[blk]["sanity_violations"] = bad
    checks[blk]["V1_recomputed"] = all(x >= A for x in (a["fA_up"], a["fA_lo"], a["fE_up"], a["fE_lo"]))
    checks[blk]["V2_recomputed"] = a["n_deg"] <= 10 * len(reps) / 30 and a["n_wflag"] <= 3 * len(reps) / 30
    checks[blk]["t_rm_flag_0.99"] = sum(r["t_rm_flag_no_tau"] for r in reps)
    checks[blk]["zeroTP_nondegenerate"] = sum(1 for r in reps if not r["degeneracy_rm"]["degenerate"] and r["E_rm"]["tp"] == 0)
    checks[blk]["per_rep_E_rm"] = [(r["subject"], r["replicate"], r["t_rm"], r["degeneracy_rm"]["n_events"],
                                    r["E_rm"]["tp"], r["E_rm"]["fp"], r["E_rm"]["p_up"]) for r in reps]
    # order log (NC-P): hash before draw before seal before score
    if blk == "NC-P":
        checks[blk]["order_ok_all"] = all(r["order_ok"] for r in reps)
        seqs = set()
        for r in reps:
            seqs.add(tuple(e.split(" ", 2)[1] for e in r["order_log"]))
        checks[blk]["order_sequences"] = [list(s) for s in seqs]
out["recompute"] = checks

# PL-A paired alignment evidence: n_train_windows / positives differ from the NC-P replicate by exactly the leak
ncp = {(r["subject"], r["replicate"]): r for r in card["NC-P"]["replicates"]}
pla_rows = []
for r in card["PL-A"]["replicates"]:
    b = ncp[(r["subject"], r["replicate"])]
    L = r["leak"]
    pla_rows.append({"s": r["subject"], "r": r["replicate"],
                     "dW_eq_leak": r["n_train_windows"] - b["n_train_windows"] == L["n_leak_windows"],
                     "dPos_eq_leakpos": r["n_train_pos_windows"] - b["n_train_pos_windows"] == L["n_leak_positive"],
                     "leak_eq_floor25": L["n_leak_windows"] == math.floor(0.25 * L["n_test_windows"]),
                     "leak_pos_frac": L["n_leak_positive"] / L["n_test_positive"],
                     "same_test_windows": r["n_test_windows"] == b["n_test_windows"],
                     "same_n_pos_test": r["n_pos_windows"] == b["n_pos_windows"]})
out["PL-A_pairing"] = {"all_ok": all(x["dW_eq_leak"] and x["dPos_eq_leakpos"] and x["leak_eq_floor25"] and x["same_test_windows"]
                                     and x["same_n_pos_test"] for x in pla_rows),
                       "leak_pos_frac_mean": float(np.mean([x["leak_pos_frac"] for x in pla_rows])), "rows": pla_rows}

# PL-B recompute
plb = card["PL-B"]["replicates"]
keep = [r for r in plb if not r["degeneracy"]["degenerate"]]
out["PL-B"] = {"fisher_up_recomputed": fisher([r["p_up"] for r in keep])[0], "card": card["trips"]["PL-B"]["fisher_T_E_up"],
               "n_keep": len(keep), "spec_all": all(r["T_A_pvalues_identical_to_NCP"] for r in plb),
               "tp_hist": np.bincount([r["tp"] for r in plb], minlength=5).tolist(),
               "p_up_sorted": sorted(r["p_up"] for r in plb)}

# ---------------- 3. sensitivity (NOT the prereg rule)
sens = {}
for blk, reps in (("NC-P", card["NC-P"]["replicates"]), ("PL-A", card["PL-A"]["replicates"]),
                  ("SYN-PL-A", syn["PL-A"]["replicates"]), ("SYN-NC-P", syn["NC-P"]["replicates"])):
    ev = [r for r in reps if not r["degeneracy_rm"]["degenerate"]]
    sens[blk] = {"literal_fisher_up_T_E": fisher([r["E_rm"]["p_up"] for r in ev])[0],
                 "incl_degenerate_as_p1": fisher([r["E_rm"]["p_up"] for r in reps])[0],
                 "midp_fisher_up": fisher([midp(r["E_rm"]["p_up"], r["E_rm"]["p_lo"]) for r in ev])[0],
                 "midp_fisher_lo": fisher([midp(r["E_rm"]["p_lo"], r["E_rm"]["p_up"]) for r in ev])[0],
                 "stouffer_up": stouffer([r["E_rm"]["p_up"] for r in ev]),
                 "drop_zeroTP_INVALID_label_dependent": fisher([r["E_rm"]["p_up"] for r in ev if r["E_rm"]["tp"] > 0])[0],
                 "locked_arm_fisher_up": fisher([r["E_locked"]["p_up"] for r in reps if not r["degeneracy_locked"]["degenerate"]])[0],
                 "n_ev": len(ev), "n_zeroTP_ev": sum(r["E_rm"]["tp"] == 0 for r in ev)}
sens["PL-B_midp"] = fisher([midp(r["p_up"], r["p_lo"]) for r in keep])[0]
out["sensitivity_not_prereg"] = sens
out["verdict_json"] = {"N1b": verdict["N1b_verdict"], "N1prime": verdict["N1prime_verdict"], "steps": verdict["steps"],
                       "N2": verdict["N2"]["status"], "run_criteria": verdict["run_criteria"]}
json.dump(out, open(os.path.join(CODE, "review", "n1b_card_recompute_out.json"), "w"), indent=1, default=str)
print(json.dumps({k: out[k] for k in ("harness_now_vs_N2_run_card", "harness_card_vs_N2_run_card", "n1b_code_now_vs_card",
                                      "n1b_code_card_vs_synthetic", "prereg_now_eq_card", "deviations_snapshot_sha_eq_card",
                                      "card_hash", "N2_identity_vs_N2_results_json", "verdict_json")}, indent=1, default=str))
for b in ("NC-P", "PL-A"):
    c = checks[b]
    print(b, c["match"], c["recomputed"], "V1", c["V1_recomputed"], "V2", c["V2_recomputed"], "viol", c["sanity_violations"][:5],
          "zeroTP_ev", c["zeroTP_nondegenerate"], "flag99", c["t_rm_flag_0.99"])
print("order", checks["NC-P"].get("order_ok_all"), checks["NC-P"].get("order_sequences"))
print("PL-A pairing", out["PL-A_pairing"]["all_ok"], out["PL-A_pairing"]["leak_pos_frac_mean"])
print("PL-B", {k: v for k, v in out["PL-B"].items()})
print(json.dumps(sens, indent=1))
print("PL-A per rep", checks["PL-A"]["per_rep_E_rm"])
