"""REVIEW N1b: PL-B tie-break ambiguity. §4 says "tau is chosen to maximise the test event F1" without a tie rule; the
code (N1b-10) takes the SMALLEST maximising tau. Here the 30 NC-P fits are reproduced with the unchanged code (sha256(s, h)
compared with the card), and PL-B is re-evaluated with the LARGEST maximising tau (everything else unchanged: same h
construction, same stream-12 null key, M = 999, degenerate exclusion, Fisher). In-memory only; no file is modified.
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Writes n1b_plb_ties_out.json."""
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"
import json  # noqa: E402

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
sys.path.insert(0, os.path.join(ROOT, "code"))
import run_n1b as RN  # noqa: E402
from n1b import K_NULL, ncp, rng  # noqa: E402
from nfharness.config import TAU_GRID  # noqa: E402
from nfharness.postprocess import hypothesis_mask  # noqa: E402
from nfharness.provenance import peak_rss_mb  # noqa: E402

t0 = time.time()
card = json.load(open(os.path.join(ROOT, "results", "N1b_card.json")))
cN = {(r["subject"], r["replicate"]): r for r in card["NC-P"]["replicates"]}
cB = {(r["subject"], r["replicate"]): r for r in card["PL-B"]["replicates"]}
records, ann, splits, shash, feats, fhash, pseudo, table = RN.prepare(os.path.join(ROOT, "data", "raw", "chbmit"), RN.SUBJECTS, True, {})
rows, sha_ok, lit_ok = [], 0, 0
for s in RN.SUBJECTS:
    for rep in range(10):
        pub, priv = ncp.run_replicate(pseudo[s], feats, rep)
        sha_ok += pub["sha256_scores_hyps"] == cN[(s, rep)]["sha256_scores_hyps"]
        ts, pl_te, durs = priv["ts"], priv["pl_te"], priv["durs"]
        f1s = []
        for tau in TAU_GRID:
            h = {f: hypothesis_mask(priv["p"][f], tau, durs[f]) for f in ts.names}
            f1s.append(ncp.EventArm(ts, h).score(pl_te)[0])
        best = max(f1s)
        taus_max = [t for t, f in zip(TAU_GRID, f1s) if f == best]
        lit_ok += taus_max[0] == cB[(s, rep)]["tau_test_optimal"]
        tau = taus_max[-1]
        h = {f: hypothesis_mask(priv["p"][f], tau, durs[f]) for f in ts.names}
        deg = ncp.degeneracy(h, ts.names, priv["te_len"])
        arm = ncp.EventArm(ts, h)
        f1, tp, fp, nr = arm.score(pl_te)
        _, TEn, _ = ncp.null_draws(ts, {"b": arm}, priv["te_len"], priv["te_order"], rng(K_NULL, priv["si"], rep))
        pu, pl = ncp.pvals(f1, TEn["b"])
        rows.append({"s": s, "r": rep, "n_tau_ties": len(taus_max), "tau_small": taus_max[0], "tau_large": tau, "f1": f1,
                     "tp": tp, "fp": fp, "p_up_large": pu, "p_up_small_card": cB[(s, rep)]["p_up"], "degenerate": deg["degenerate"]})
        print(s, rep, len(taus_max), taus_max[0], tau, round(f1, 3), tp, fp, pu, cB[(s, rep)]["p_up"], flush=True)
keep = [r for r in rows if not r["degenerate"]]
fl, n = ncp.fisher([r["p_up_large"] for r in keep])
out = {"ncp_sha_reproduced": sha_ok, "literal_small_tau_reproduced": lit_ok, "n_reps": len(rows),
       "n_reps_with_ties": sum(r["n_tau_ties"] > 1 for r in rows), "fisher_up_largest_tau": fl, "n_retained": n,
       "fisher_up_card_smallest_tau": card["trips"]["PL-B"]["fisher_T_E_up"], "trip_largest_tau": bool(fl < 0.0025),
       "rows": rows, "wall_s": time.time() - t0, "peak_ram_mb": peak_rss_mb()}
json.dump(out, open(os.path.join(ROOT, "code", "review", "n1b_plb_ties_out.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
