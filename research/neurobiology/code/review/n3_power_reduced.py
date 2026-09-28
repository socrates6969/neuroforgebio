"""Reviewer check of the N3 power analysis (code\\n3_power\\power_sim.py, notes\\n3_power.md). REDUCED independent re-run.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Synthetic data only.
Nothing in code\\n3_power or results\\ is modified; output goes to code\\review\\n3_power_reduced_out.json.

Part 1 (independent of power_sim): a generic exchangeable discrete statistic with a point mass at 0 (like per-replicate
  event F1 with zero-TP fits). Under H0 the observation and its M null draws are i.i.d. Measures the size of
  (a) literal Fisher on p_up = (1 + #{null >= obs})/(M + 1), (b) the pooled sum statistic with index-wise summed nulls.
Part 2 (reuses power_sim.one_fit, the surrogate, read-only): saturated regime, K = 4, 12 subjects x 10 fits,
  honest (+PL-B) / PL-A-hom / PL-A at the published deltas. Power at S = 2 and S = 4 (event pooled F1 and literal Fisher,
  PL-B, window arm), pseudo-null size at S = 3, and the N1b-design validation, each computed TWICE:
    'as_published' = power_sim.combine unchanged (observed F1 float64 vs null F1 stored as float32),
    'tie_fixed'    = observed F1 / T_A rounded to float32 first, so exact ties compare equal.
  The difference quantifies a float32 tie-breaking defect found in review (F1 values such as 1/6 round DOWN in
  float32, so a null equal to the observation is counted as smaller -> p_up too small in the power tables).
"""
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np  # noqa: E402
from scipy.stats import chi2  # noqa: E402

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
sys.path.insert(0, os.path.join(ROOT, "code", "n3_power"))
sys.path.insert(0, os.path.join(ROOT, "code"))
import power_sim as ps  # noqa: E402

OUT = os.path.join(ROOT, "code", "review", "n3_power_reduced_out.json")
SEED = 777001


# ------------------------------------------------------------------ part 1: independent generic size check
def part1(n_exp=4000, R=30, M=999, K=4, chunk=50):
    g = np.random.default_rng(SEED)
    fis, pool = [], []
    for c in range(n_exp // chunk):
        # per replicate: hit prob q ~ Beta(0.6, 3), n hypothesis events ~ 1 + Poisson(6); F1 = 2TP/(TP+FP+K)
        q = g.beta(0.6, 3.0, size=(chunk, R, 1))
        nev = 1 + g.poisson(6.0, size=(chunk, R, 1))
        tp = g.binomial(K, np.broadcast_to(q, (chunk, R, M + 1)))
        tp = np.minimum(tp, nev)
        fp = nev - tp
        f1 = 2 * tp / (tp + fp + K)          # exact rationals as float64 (same value -> same float)
        obs, nul = f1[..., 0], f1[..., 1:]
        pup = (1 + (nul >= obs[..., None]).sum(-1)) / (M + 1)
        fis.append(chi2.sf(-2 * np.log(pup).sum(-1), 2 * R))
        T, Tn = obs.sum(-1), nul.sum(1)
        pool.append((1 + (Tn >= T[:, None] - 1e-9).sum(-1)) / (M + 1))
    fis, pool = np.concatenate(fis), np.concatenate(pool)
    return {"n_exp": int(fis.size), "R": R, "M": M,
            "literal_fisher_size": {str(a): float(np.mean(fis < a)) for a in (0.0025, 0.0125, 0.05)},
            "pooled_sum_size": {str(a): float(np.mean(pool < a)) for a in (0.0025, 0.0125, 0.05)}}


# ------------------------------------------------------------------ part 2: surrogate, reduced
def fixed(fits):
    out = []
    for f in fits:
        f = dict(f)
        f["F1_obs"] = float(np.float32(f["F1_obs"]))
        f["TA_obs"] = float(np.float32(f["TA_obs"]))
        if "B_F1_obs" in f:
            f["B_F1_obs"] = float(np.float32(f["B_F1_obs"]))
        out.append(f)
    return out


def power(pool, S, R, arm, n_exp, seed, fix):
    g = np.random.default_rng(seed)
    subs = sorted(pool)
    res = {"pooled_F1": [], "fisher": []}
    for _ in range(n_exp):
        chosen = g.choice(subs, size=S, replace=False)
        fits = []
        for s in chosen:
            fl = pool[s]
            idx = g.choice(len(fl), size=R, replace=False) if R < len(fl) else np.arange(len(fl))
            fits += [fl[i] for i in idx]
        if fix:
            fits = fixed(fits)
        r = ps.combine(fits, arm, g)
        for k in res:
            if k in r:
                res[k].append(r[k])
    return {k: {"0.0025": float(np.mean(np.asarray(v) < 0.0025)), "median": float(np.median(v))} for k, v in res.items() if v}


def n1b_like(pool, R, arm, n_exp, seed, fix):
    g = np.random.default_rng(seed)
    subs = sorted(pool)
    out = []
    for _ in range(n_exp):
        chosen = g.choice(subs, size=3, replace=False)
        fits = sum([[pool[s][i] for i in g.choice(len(pool[s]), size=R, replace=False)] for s in chosen], [])
        if fix:
            fits = fixed(fits)
        out.append(ps.combine(fits, arm, g)["fisher"])
    out = np.asarray(out)
    return {"median": float(np.median(out)), "P(p<0.0025)": float(np.mean(out < 0.0025))}


def main():
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    res = {"part1_independent_generic": part1()}
    print("part1", res["part1_independent_generic"], round(time.time() - t0, 1), flush=True)
    pub = json.load(open(os.path.join(ROOT, "results", "n3_power", "power_sim.json")))
    d = pub["deltas"]["saturated"]
    sat = ps.REGIMES["saturated"]
    hom = dict(sat, leak_gamma_shape=20.0)
    n_subj, K = 12, 4
    with ProcessPoolExecutor(4) as ex:
        honest = ps.by_subject(list(ex.map(ps.one_fit, [("honest", K, s, r, 0.0, True, ps.M, "saturated")
                                                        for s in range(n_subj) for r in range(10)], chunksize=4)))
        pla_hom = ps.by_subject(list(ex.map(ps.one_fit, [("pla", K, s, r, d["PL-A-hom"], False, ps.M, hom)
                                                         for s in range(n_subj) for r in range(10)], chunksize=4)))
        pla = ps.by_subject(list(ex.map(ps.one_fit, [("pla", K, s, r, d["PL-A"], False, ps.M, "saturated")
                                                     for s in range(n_subj) for r in range(10)], chunksize=4)))
    print("fits done", round(time.time() - t0, 1), flush=True)
    allh = sum(honest.values(), [])
    # how often an observed F1 is float32-rounded down AND tied with >= 1 null draw
    n_down = sum(1 for f in allh if float(np.float32(f["F1_obs"])) < f["F1_obs"])
    n_down_tied = sum(1 for f in allh if float(np.float32(f["F1_obs"])) < f["F1_obs"]
                      and np.any(f["F1_null"] == np.float32(f["F1_obs"])))
    n_down_B = sum(1 for f in allh if float(np.float32(f["B_F1_obs"])) < f["B_F1_obs"]
                   and np.any(f["B_F1_null"] == np.float32(f["B_F1_obs"])))
    res["tie_defect_incidence_honest_fits"] = {"n": len(allh), "E_obs_rounded_down": n_down,
                                               "E_obs_rounded_down_and_tied": n_down_tied,
                                               "B_obs_rounded_down_and_tied": n_down_B}
    res["diag"] = {"honest": ps.honest_diag(allh), "PL-A-hom": ps.summarise(sum(pla_hom.values(), [])),
                   "PL-A": ps.summarise(sum(pla.values(), []))}
    tabs = {}
    for fix in (False, True):
        tag = "tie_fixed" if fix else "as_published"
        t = {}
        for S in (2, 4):
            t["S%d" % S] = {"PL-A-hom_event_R10": power(pla_hom, S, 10, "E", 300, 11 + S, fix),
                            "PL-A_event_R10": power(pla, S, 10, "E", 300, 21 + S, fix),
                            "PL-B_event_R10": power(honest, S, 10, "B", 300, 31 + S, fix),
                            "PL-A-hom_window_R5": power(pla_hom, S, 5, "A", 300, 41 + S, fix),
                            "PL-A_window_R5": power(pla, S, 5, "A", 300, 51 + S, fix)}
        t["n1b_validation"] = {"PL-B_R10_literal": n1b_like(honest, 10, "B", 300, 61, fix),
                               "PL-A-hom_E_R5_literal": n1b_like(pla_hom, 5, "E", 300, 62, fix)}
        tabs[tag] = t
        print(tag, json.dumps(t), round(time.time() - t0, 1), flush=True)
    res["power"] = tabs
    gs = np.random.default_rng(99)
    res["size_pseudo_null_K4_S3_R10"] = {"E": ps.size_table({4: honest}, [4], [3], 10, "E", 2000, gs)[4][3],
                                         "B": ps.size_table({4: honest}, [4], [3], 10, "B", 2000, gs)[4][3]}
    res["published_reference"] = {"PL-A-hom_S2": 0.587, "PL-A-hom_S4": 0.823, "PL-B_S2": 0.307, "PL-B_S4": 0.653,
                                  "window_hom_S2": 0.957, "window_PLA_S2": 1.0, "n1b_PLB_median": 0.375,
                                  "n1b_PLAhom_median": 0.152}
    res["wall_s"] = round(time.time() - t0, 1)
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    print("wrote", OUT, res["wall_s"])


if __name__ == "__main__":
    main()
