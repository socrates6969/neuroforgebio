"""P6: empirical (model-free) independent digit channels per 2 x 32 S1 array pair (cycle 4).

Implements prereg\\P6_empirical_channels.md (FIXED) exactly; interpretations are in code\\DEVIATIONS.md, section P6
(items 1-12 plus the cycle-4 addendum). Every estimand is a deterministic function of the digitised PF labels.
Computational analysis only. No stimulation setting is proposed; any clinical claim requires an IRB/FDA-approved study.

Run:  python p6_empirical_channels.py --selftest     (self-tests only)
      python p6_empirical_channels.py                (self-tests, then full analysis, JSON/CSV, figures)
"""
import csv
import json
import math
import os
import sys
import time
from itertools import product

import numpy as np
from scipy.stats import binom

ROOT = r"C:\Users\mariu\neuro-company\research\somatosensory"
DATA = os.path.join(ROOT, "notes", "published-derived")
CODE = os.path.join(ROOT, "code")
RES = os.path.join(CODE, "results")
FIG = os.path.join(CODE, "figures")
SEED = 20260926
PARTS = ["C1", "P2", "P3"]
DIG = ["D1", "D2", "D3", "D4", "D5"]
HANDCLS = ("PALM", "DORSUM_HAND", "HAND")  # HAND = pooled palm/dorsum-of-hand class (R3 variant)
LEVELS = [6, 5, 4, 3, 2]
P0 = 0.62
P_SENS = [0.47, 0.54, 0.62, 0.64, 0.75, 1.0]
P_COND = [0.47, 0.54, 0.62, 0.75, 1.0]
XS = [0.05, 0.10, 0.20]
N_MC, N_REL, N_BOOT, N_NULL, N_SHUF, N_CLUST = 20000, 5000, 10000, 10000, 1000, 2000
THR = 0.80
HUES = ["red", "orange", "yellow", "green"]

SS = np.random.SeedSequence(SEED)
_STREAMS = {name: np.random.default_rng(s) for name, s in
            zip(["mc", "rel", "boot", "nullA", "nullB", "shuf", "clust", "joint", "jhu", "test"], SS.spawn(10))}


def rng(name):
    return _STREAMS[name]


# ------------------------------------------------------------------------------------------------ label rules
def tmap(surface, tag, ray=False):
    """Territory of one segment tag (prereg 3; DEVIATIONS P6 item 1)."""
    if not tag:
        return None
    if tag[0] == "D" and len(tag) > 1 and tag[1] in "12345":
        return "D" + tag[1]
    if tag == "W":
        return "WRIST"
    if surface == "palm":
        if ray and tag[0] == "P" and len(tag) > 1 and tag[1] in "2345" and tag.endswith("-mcp"):
            return "D" + tag[1]
        return "PALM"
    return "DORSUM_HAND"


def territory(palm, dors, rule):
    tp, td = tmap("palm", palm), tmap("dors", dors)
    if rule == "R1":
        return tp if tp is not None else td
    if rule == "ray":
        a = tmap("palm", palm, ray=True)
        return a if a is not None else td
    if rule == "R2":
        for t in (tp, td):
            if t in DIG:
                return t
        return tp if tp is not None else td
    if rule == "R3":
        ts = {t for t in (tp, td) if t is not None}
        if len(ts) == 1 and next(iter(ts)) in DIG:
            return next(iter(ts))
        if ts and ts <= {"PALM", "DORSUM_HAND"}:
            return "HAND"
        return "MIXED"
    raise ValueError(rule)


def dominant_seg(palm, dors):
    return ("palm:" + palm) if palm else ("dors:" + dors)


def counts_of(labels):
    c = {}
    for t in labels:
        c[t] = c.get(t, 0) + 1
    return c


def k_digit(c, m):
    return int(sum(c.get(d, 0) >= m for d in DIG))


def n_hand(c):
    return sum(c.get(h, 0) for h in HANDCLS)


def k_terr(c, m):
    return k_digit(c, m) + int(n_hand(c) >= m)


def neff(c):
    n = np.array([v for v in c.values() if v > 0], float)
    if n.size == 0:
        return float("nan")
    return float(n.sum() ** 2 / np.sum(n ** 2))


def neff_bc(c):
    n = np.array([v for v in c.values() if v > 0], float)
    den = np.sum(n * (n - 1))
    N = n.sum()
    return None if den == 0 else float(N * (N - 1) / den)


def neff_soft(sets):
    """PR of the Jaccard similarity matrix over electrode segment sets (prereg 4b, soft variant)."""
    N = len(sets)
    S = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            u = sets[i] | sets[j]
            S[i, j] = len(sets[i] & sets[j]) / len(u) if u else 0.0
    return float(np.trace(S) ** 2 / np.sum(S ** 2))


# ------------------------------------------------------------------------------------------------ attrition
def class_vector(c, level6):
    v = [c.get(d, 0) for d in DIG]
    if level6:
        v.append(n_hand(c))
    return v


def p_k_ge(nvec, p, m, L):
    """Exact P(#classes keeping >= m survivors >= L): Poisson-binomial DP over disjoint classes."""
    q = [0.0 if n < m else float(1.0 - binom.cdf(m - 1, n, p)) for n in nvec]
    dist = np.zeros(len(q) + 1)
    dist[0] = 1.0
    for qi in q:
        new = dist * (1 - qi)
        new[1:] += dist[:-1] * qi
        dist = new
    return float(dist[L:].sum()) if L <= len(q) else 0.0


def p_k_ge_bruteforce(nvec, p, m, L):
    """Independent check: enumerate all survivor-count vectors (C2)."""
    tot = 0.0
    for s in product(*[range(n + 1) for n in nvec]):
        pr = 1.0
        for si, n in zip(s, nvec):
            pr *= math.comb(n, si) * p ** si * (1 - p) ** (n - si)
        if sum(si >= m for si in s) >= L:
            tot += pr
    return tot


def onehot_classes(labels, classes):
    """labels -> N x C 0/1 matrix over the given class list (label not in list -> zero row)."""
    M = np.zeros((len(labels), len(classes)))
    idx = {c: i for i, c in enumerate(classes)}
    for i, t in enumerate(labels):
        if t in idx:
            M[i, idx[t]] = 1
    return M


TERR6 = DIG + ["HANDPOOL"]


def terr6_labels(labels):
    return ["HANDPOOL" if t in HANDCLS else t for t in labels]


def mc_attrition(labels, p, m, n_draw, g):
    """MC over independent per-electrode survival; returns arrays K_digit, K_terr (n_draw)."""
    M = onehot_classes(terr6_labels(labels), TERR6)
    surv = (g.random((n_draw, len(labels))) < p).astype(float)
    cnt = surv @ M
    kd = (cnt[:, :5] >= m).sum(1)
    return kd, kd + (cnt[:, 5] >= m)


# ------------------------------------------------------------------------------------------------ data
def load_segments():
    d = json.load(open(os.path.join(DATA, "greenspon2025_ed1_extraction.json")))
    segs = []
    for surf in ("palm", "dors"):
        for s in d["segments"][surf]:
            segs.append({"key": surf + ":" + s["label"], "surf": surf, "tag": s["label"], "cx": s["cx"], "cy": s["cy"],
                         "area": s["area_mm2"]})
    return segs


def load_greenspon():
    rows = list(csv.DictReader(open(os.path.join(DATA, "pf_per_electrode_greenspon2025.csv"))))
    wired, pf = [], []
    for r in rows:
        e = {"part": r["participant"], "array": r["array"], "ch": int(r["electrode_channel"]),
             "x": float(r["x_mm"]), "y": float(r["y_mm"]), "palm": r["palm_segment"], "dors": r["dors_segment"],
             "has_pf": r["has_PF"] == "1",
             "pcx": r["palm_centroid_x_mm"], "pcy": r["palm_centroid_y_mm"],
             "dcx": r["dors_centroid_x_mm"], "dcy": r["dors_centroid_y_mm"]}
        wired.append(e)
        if e["has_pf"]:
            pf.append(e)
    return wired, pf


def load_fifer():
    rows = list(csv.DictReader(open(os.path.join(DATA, "pf_per_electrode_fifer2022.csv"))))
    out = []
    for r in rows:
        if r["status"] != "PF":
            continue
        hs = [h for h in r["hue_classes"].split("|") if h]
        out.append({"array": r["array"], "hues": hs, "x": float(r["x_mm"]), "y": float(r["y_mm"])})
    return out


def build_seg_tables(segs, pf):
    """Global segment list, 3-nearest same-surface neighbours, segment -> R1 territory."""
    keys = [s["key"] for s in segs]
    # CSV-centroid fallback for any tag missing from the table (DEVIATIONS P6 item 4)
    for e in pf:
        for surf, tag, cx, cy in (("palm", e["palm"], e["pcx"], e["pcy"]), ("dors", e["dors"], e["dcx"], e["dcy"])):
            if tag and surf + ":" + tag not in keys:
                segs.append({"key": surf + ":" + tag, "surf": surf, "tag": tag, "cx": float(cx) * 5, "cy": float(cy) * 5,
                             "area": 0.0, "fallback": True})
                keys.append(surf + ":" + tag)
    kidx = {k: i for i, k in enumerate(keys)}
    nbr = np.zeros((len(segs), 3), int)
    for i, s in enumerate(segs):
        cand = [(math.hypot(s["cx"] - t["cx"], s["cy"] - t["cy"]), j) for j, t in enumerate(segs)
                if j != i and t["surf"] == s["surf"]]
        cand.sort()
        nbr[i] = [j for _, j in cand[:3]]
    seg_terr = [tmap(s["surf"], s["tag"]) for s in segs]
    return segs, keys, kidx, nbr, seg_terr


# ------------------------------------------------------------------------------------------------ analysis blocks
def participant_block(els, rule="R1"):
    labs = [territory(e["palm"], e["dors"], rule) for e in els]
    return labs, counts_of(labs)


def mean_same_terr_dist(els, labs):
    ds = []
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            if els[i]["array"] == els[j]["array"] and labs[i] == labs[j]:
                ds.append(math.hypot(els[i]["x"] - els[j]["x"], els[i]["y"] - els[j]["y"]))
    return float(np.mean(ds)) if ds else float("nan")


def dp_levels(c, p, m):
    return {L: p_k_ge(class_vector(c, L == 6), p, m, L if L < 6 else 6) for L in LEVELS}


def k_star_simple(obs_by_part, patt_by_part):
    """Criteria 1-2 only (conditions table, DEVIATIONS item 9)."""
    for L in LEVELS:
        if all(obs_by_part[q][L] for q in obs_by_part) and min(patt_by_part[q][L] for q in patt_by_part) >= THR:
            return L
    return None


def counts_from_idx(cls_idx, C):
    B = cls_idx.shape[0]
    out = np.zeros((B, C))
    np.add.at(out, (np.repeat(np.arange(B), cls_idx.shape[1]), cls_idx.ravel()), 1)
    return out


def neff_rows(cnt):
    N = cnt.sum(1)
    return N ** 2 / np.sum(cnt ** 2, 1)


# ------------------------------------------------------------------------------------------------ self-tests
def selftests():
    res = {}

    def ok(name, cond, info=""):
        res[name] = {"pass": bool(cond), "info": str(info)}

    ok("tmap_digit", tmap("palm", "D3m-u+D3m-r") == "D3" and tmap("dors", "D5p") == "D5")
    ok("tmap_palm_dorsum_wrist", tmap("palm", "P2-mcp") == "PALM" and tmap("dors", "P-dr") == "DORSUM_HAND"
       and tmap("palm", "W") == "WRIST" and tmap("palm", "") is None)
    ok("tmap_ray", tmap("palm", "P5-mcp", ray=True) == "D5" and tmap("palm", "P0-d", ray=True) == "PALM")
    ok("R1_palm_first", territory("P3-mcp", "D2m", "R1") == "PALM" and territory("", "D2m", "R1") == "D2")
    ok("R2_first_digit", territory("P3-mcp", "D2m", "R2") == "D2" and territory("D1p-u+D1p-r", "D2m", "R2") == "D1")
    ok("R3_strict", territory("D2m-u+D2m-r", "D2m", "R3") == "D2" and territory("D2m-u+D2m-r", "D3m", "R3") == "MIXED"
       and territory("P3-mcp", "P-dr", "R3") == "HAND" and territory("P3-mcp", "D2m", "R3") == "MIXED")
    # C2 planted truth
    c = {"D1": 6, "D2": 4, "D3": 1, "D4": 2, "PALM": 3}
    ok("C2_K_digit", k_digit(c, 2) == 3, k_digit(c, 2))
    ok("C2_K_terr", k_terr(c, 2) == 4, k_terr(c, 2))
    ok("C2_neff", abs(neff(c) - 256 / 66) < 1e-12, neff(c))
    ex = p_k_ge([6, 4, 1, 2, 0], 0.62, 2, 3)
    bf = p_k_ge_bruteforce([6, 4, 1, 2, 0], 0.62, 2, 3)
    ok("C2_exact_vs_bruteforce", abs(ex - bf) < 1e-12, (ex, bf))
    g = rng("test")
    worst = 0.0
    for _ in range(40):
        nv = list(g.integers(0, 5, 5))
        for m in (1, 2, 3):
            for L in range(1, 6):
                worst = max(worst, abs(p_k_ge(nv, 0.55, m, L) - p_k_ge_bruteforce(nv, 0.55, m, L)))
    ok("DP_random_vs_bruteforce", worst < 1e-12, worst)
    labs = ["D1"] * 6 + ["D2"] * 4 + ["D3"] + ["D4"] * 2 + ["PALM"] * 3
    kd, kt = mc_attrition(labs, 0.62, 2, N_MC, g)
    pm = float(np.mean(kd >= 3))
    se = math.sqrt(ex * (1 - ex) / N_MC)
    ok("MC_vs_exact_planted", abs(pm - ex) <= 3 * se, (pm, ex, se))
    # level 6 on planted: HAND=3 -> K_terr; exact equals MC
    ex6 = p_k_ge([6, 4, 1, 2, 0, 3], 0.62, 2, 4)
    pm6 = float(np.mean(kt >= 4))
    ok("MC_vs_exact_planted_terr", abs(pm6 - ex6) <= 3 * math.sqrt(ex6 * (1 - ex6) / N_MC), (pm6, ex6))
    ok("p1_limit", p_k_ge([2, 2, 1, 0, 5], 1.0, 2, 3) == 1.0 and p_k_ge([2, 2, 1, 0, 5], 1.0, 2, 4) == 0.0)
    # bootstrap distinct rule: one electrode drawn many times must not create an m=2 channel
    idx = np.array([[0, 0, 0, 1]])
    drawn = np.zeros((1, 4), bool)
    drawn[np.arange(1)[:, None], idx] = True
    M = onehot_classes(["D1", "D2", "D2", "D3"], DIG)
    ok("boot_distinct_rule", int(((drawn.astype(float) @ M) >= 2).sum()) == 0)
    # soft N_eff equals hard N_eff when each electrode has a single segment
    sets = [{"a"}, {"a"}, {"b"}, {"c"}, {"c"}, {"c"}]
    ok("soft_equals_hard_single", abs(neff_soft(sets) - neff(counts_of(["a", "a", "b", "c", "c", "c"]))) < 1e-12)
    ok("neff_bc", abs(neff_bc({"a": 2, "b": 2}) - 12 / 4) < 1e-12 and neff_bc({"a": 1, "b": 1}) is None)
    # counts_from_idx equals bincount
    ci = g.integers(0, 7, (50, 20))
    cf = counts_from_idx(ci, 7)
    ok("counts_from_idx", all(np.array_equal(cf[b], np.bincount(ci[b], minlength=7)) for b in range(50)))
    return res


# ------------------------------------------------------------------------------------------------ main analysis
def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, float) and math.isnan(o):
        return None
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def main():
    t0 = time.time()
    os.makedirs(RES, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    st = selftests()
    n_pass = sum(v["pass"] for v in st.values())
    print(f"self-tests {n_pass}/{len(st)}")
    for k, v in st.items():
        if not v["pass"]:
            print("  FAIL", k, v["info"])
    if "--selftest" in sys.argv:
        return

    segs, pf_wired_all = None, None
    wired, pf = load_greenspon()
    segs = load_segments()
    segs, keys, kidx, nbr, seg_terr = build_seg_tables(segs, pf)
    TCLS = DIG + ["PALM", "DORSUM_HAND", "WRIST"]
    tcls_idx = {t: i for i, t in enumerate(TCLS)}
    seg_tc = np.array([tcls_idx[t] for t in seg_terr])  # segment -> territory class index
    out = {"prereg": "prereg/P6_empirical_channels.md", "seed": SEED, "selftests": st,
           "selftests_pass": f"{n_pass}/{len(st)}", "participants": {}}

    by = {q: [e for e in pf if e["part"] == q] for q in PARTS}
    wired_by = {q: [e for e in wired if e["part"] == q] for q in PARTS}
    arrays = {q: sorted({e["array"] for e in by[q]}) for q in PARTS}

    # ---------------- observed estimands
    obs = {}
    for q in PARTS:
        els = by[q]
        d = {"N_PF": len(els), "N_wired": len(wired_by[q])}
        d["per_array_denominators"] = {a: {"wired": sum(e["array"] == a for e in wired_by[q]),
                                           "PF": sum(e["array"] == a for e in els)} for a in arrays[q]}
        for rule in ("R1", "R2", "R3", "ray"):
            labs, c = participant_block(els, rule)
            d[rule] = {"counts": c, "K_digit": {m: k_digit(c, m) for m in (1, 2, 3)},
                       "K_terr": {m: k_terr(c, m) for m in (1, 2, 3)}}
        labs1, c1 = participant_block(els, "R1")
        segc = counts_of([dominant_seg(e["palm"], e["dors"]) for e in els])
        d["R1"]["N_eff_digit"] = neff(c1)
        d["R1"]["N_eff_digit_bc"] = neff_bc(c1)
        d["R1"]["N_eff_seg"] = neff(segc)
        d["R1"]["N_eff_seg_bc"] = neff_bc(segc)
        d["R1"]["n_seg_classes"] = len(segc)
        d["R1"]["N_eff_soft"] = neff_soft([{s for s in ("palm:" + e["palm"] if e["palm"] else "",
                                                          "dors:" + e["dors"] if e["dors"] else "") if s} for e in els])
        # per array
        pa = {}
        for a in arrays[q]:
            ea = [e for e in els if e["array"] == a]
            la, ca = participant_block(ea, "R1")
            sa = counts_of([dominant_seg(e["palm"], e["dors"]) for e in ea])
            pa[a] = {"counts": ca, "K_digit": {m: k_digit(ca, m) for m in (1, 2, 3)},
                     "K_terr_m2": k_terr(ca, 2), "N_eff_digit": neff(ca), "N_eff_seg": neff(sa)}
        d["per_array"] = pa
        d["G_second_array_gain_m2"] = d["R1"]["K_digit"][2] - max(pa[a]["K_digit"][2] for a in arrays[q])
        obs[q] = d

    # ---------------- attrition exact + MC (C3)
    c3_fail = []
    att = {}
    for q in PARTS:
        c = obs[q]["R1"]["counts"]
        labs, _ = participant_block(by[q], "R1")
        att[q] = {}
        for p in P_SENS:
            ex = dp_levels(c, p, 2)
            kd, kt = mc_attrition(labs, p, 2, N_MC, rng("mc"))
            mc = {L: float(np.mean((kt if L == 6 else kd) >= L)) for L in LEVELS}
            for L in LEVELS:
                e = ex[L]
                if e in (0.0, 1.0):
                    good = abs(mc[L] - e) < 1e-15
                else:
                    good = abs(mc[L] - e) <= 3 * math.sqrt(e * (1 - e) / N_MC)
                if not good:
                    c3_fail.append((q, p, L, e, mc[L]))
            att[q][p] = {"exact": ex, "mc": mc}
    # fine grid for figure 2
    pgrid = np.round(np.linspace(0.30, 1.0, 71), 4)
    att_curve = {q: {L: [p_k_ge(class_vector(obs[q]["R1"]["counts"], L == 6), float(p), 2, L) for p in pgrid]
                     for L in LEVELS} for q in PARTS}

    # ---------------- relabelling
    def dom_idx(els):
        return np.array([kidx[dominant_seg(e["palm"], e["dors"])] for e in els])

    rel = {}
    rel_draws = {}
    for q in PARTS:
        base = dom_idx(by[q])
        N = len(base)
        rel[q] = {}
        rel_draws[q] = {}
        for x in XS:
            k = int(round(x * N))
            g = rng("rel")
            KD = np.zeros(N_REL, int)
            KT = np.zeros(N_REL, int)
            for b in range(N_REL):
                dom = base.copy()
                if k:
                    idx = g.choice(N, k, replace=False)
                    dom[idx] = nbr[dom[idx], g.integers(0, 3, k)]
                cnt = np.bincount(seg_tc[dom], minlength=len(TCLS))
                kd = int((cnt[:5] >= 2).sum())
                KD[b] = kd
                KT[b] = kd + int(cnt[5] + cnt[6] >= 2)
            obsK = obs[q]["R1"]["K_digit"][2]
            rel[q][x] = {"k_relabelled": k,
                         "P_rel": {L: float(np.mean((KT if L == 6 else KD) >= L)) for L in LEVELS},
                         "P_change_le1": float(np.mean(np.abs(KD - obsK) <= 1)),
                         "K_digit_dist": {int(v): int(np.sum(KD == v)) for v in np.unique(KD)}}
            rel_draws[q][x] = KD
    # joint attrition p=0.62 + relabelling x=0.10 (descriptive)
    joint = {}
    for q in PARTS:
        base = dom_idx(by[q])
        N = len(base)
        k = int(round(0.10 * N))
        g = rng("joint")
        KD = np.zeros(N_REL, int)
        KT = np.zeros(N_REL, int)
        for b in range(N_REL):
            dom = base.copy()
            idx = g.choice(N, k, replace=False)
            dom[idx] = nbr[dom[idx], g.integers(0, 3, k)]
            surv = g.random(N) < P0
            cnt = np.bincount(seg_tc[dom[surv]], minlength=len(TCLS))
            KD[b] = int((cnt[:5] >= 2).sum())
            KT[b] = KD[b] + int(cnt[5] + cnt[6] >= 2)
        joint[q] = {L: float(np.mean((KT if L == 6 else KD) >= L)) for L in LEVELS}

    # ---------------- bootstrap
    boot = {}
    for q in PARTS:
        els = by[q]
        N = len(els)
        labs, _ = participant_block(els, "R1")
        g = rng("boot")
        idx = g.integers(0, N, (N_BOOT, N))
        drawn = np.zeros((N_BOOT, N), bool)
        drawn[np.arange(N_BOOT)[:, None], idx] = True
        M = onehot_classes(terr6_labels(labs), TERR6)
        cd = drawn.astype(float) @ M
        KD = (cd[:, :5] >= 2).sum(1)
        KT = KD + (cd[:, 5] >= 2)
        terr_i = np.array([tcls_idx[t] for t in labs])
        ne_d = neff_rows(counts_from_idx(terr_i[idx], len(TCLS)))
        segi = dom_idx(els)
        ne_s = neff_rows(counts_from_idx(segi[idx], len(keys)))

        def ci(v):
            return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
        boot[q] = {"K_digit_m2_CI": ci(KD), "K_terr_m2_CI": ci(KT), "N_eff_digit_CI": ci(ne_d), "N_eff_seg_CI": ci(ne_s),
                   "P_K_digit_ge": {L: float(np.mean(KD >= L)) for L in (2, 3, 4, 5)}}

    # ---------------- C1 label shuffle within array
    c1 = {}
    c1_pass = True
    for q in PARTS:
        els = by[q]
        labs, c = participant_block(els, "R1")
        segl = [dominant_seg(e["palm"], e["dors"]) for e in els]
        obs_d = mean_same_terr_dist(els, labs)
        base = (k_digit(c, 2), k_terr(c, 2), neff(c), neff(counts_of(segl)))
        g = rng("shuf")
        max_diff, n_change = 0.0, 0
        arr_idx = {a: [i for i, e in enumerate(els) if e["array"] == a] for a in arrays[q]}
        for _ in range(N_SHUF):
            perm = list(range(len(els)))
            for a, ii in arr_idx.items():
                pi = g.permutation(ii)
                for src, dst in zip(ii, pi):
                    perm[src] = dst
            L2 = [labs[perm[i]] for i in range(len(els))]
            S2 = [segl[perm[i]] for i in range(len(els))]
            c2 = counts_of(L2)
            val = (k_digit(c2, 2), k_terr(c2, 2), neff(c2), neff(counts_of(S2)))
            max_diff = max(max_diff, max(abs(a - b) for a, b in zip(val, base)))
            dsh = mean_same_terr_dist(els, L2)
            if not (math.isnan(dsh) and math.isnan(obs_d)) and not abs(dsh - obs_d) <= 1e-12:
                n_change += 1
        frac = n_change / N_SHUF
        good = max_diff < 1e-12 and frac >= 0.95
        c1_pass &= good
        c1[q] = {"max_abs_diff_invariants": max_diff, "frac_same_terr_dist_changed": frac,
                 "obs_mean_same_terr_dist_mm": obs_d, "pass": good}

    # ---------------- C2 (planted) is in selftests; C3 summary
    c2_pass = all(st[k]["pass"] for k in ("C2_K_digit", "C2_K_terr", "C2_neff", "C2_exact_vs_bruteforce"))
    c3_pass = len(c3_fail) == 0
    controls_pass = bool(c1_pass and c2_pass and c3_pass and n_pass == len(st))

    # ---------------- C4 nulls
    areas = np.array([s["area"] for s in segs], float)
    wA = areas / areas.sum()
    pooled = np.concatenate([dom_idx(by[q]) for q in PARTS])
    c4 = {}
    for q in PARTS:
        N = obs[q]["N_PF"]
        o_seg, o_dig = obs[q]["R1"]["N_eff_seg"], obs[q]["R1"]["N_eff_digit"]
        o_K = obs[q]["R1"]["K_digit"][2]
        c4[q] = {}
        for nm, draw in (("nullA_area", lambda g: g.choice(len(segs), (N_NULL, N), p=wA)),
                         ("nullB_pooled", lambda g: pooled[g.integers(0, len(pooled), (N_NULL, N))])):
            si = draw(rng("nullA" if nm.startswith("nullA") else "nullB"))
            ns = neff_rows(counts_from_idx(si, len(keys)))
            cd = counts_from_idx(seg_tc[si], len(TCLS))
            nd = neff_rows(cd)
            kd = (cd[:, :5] >= 2).sum(1)
            c4[q][nm] = {"seg": {"obs": o_seg, "null_median": float(np.median(ns)), "p": float(np.mean(ns <= o_seg)),
                                 "ratio": o_seg / float(np.median(ns))},
                         "digit": {"obs": o_dig, "null_median": float(np.median(nd)), "p": float(np.mean(nd <= o_dig)),
                                   "ratio": o_dig / float(np.median(nd))},
                         "K_digit_m2": {"obs": o_K, "null_median": float(np.median(kd)), "p": float(np.mean(kd <= o_K))}}
        # Null A without wrist (descriptive, DEVIATIONS item 1)
        wnw = np.array([0.0 if s["tag"] == "W" else s["area"] for s in segs])
        si = rng("nullA").choice(len(segs), (N_NULL, N), p=wnw / wnw.sum())
        ns = neff_rows(counts_from_idx(si, len(keys)))
        c4[q]["nullA_noWrist_seg"] = {"null_median": float(np.median(ns)), "p": float(np.mean(ns <= o_seg))}
        c4[q]["expected_pattern_met_seg_nullB"] = bool(c4[q]["nullB_pooled"]["seg"]["p"] < 0.05)
        c4[q]["fails_seg_nullB"] = bool(o_seg >= c4[q]["nullB_pooled"]["seg"]["null_median"])

    # ---------------- clustered loss (descriptive)
    clust = {}
    for q in PARTS:
        els = by[q]
        labs, _ = participant_block(els, "R1")
        g = rng("clust")
        KD = np.zeros(N_CLUST, int)
        for b in range(N_CLUST):
            keep = np.ones(len(els), bool)
            for a in arrays[q]:
                ii = [i for i, e in enumerate(els) if e["array"] == a]
                ws = [e for e in wired_by[q] if e["array"] == a]
                s = ws[g.integers(len(ws))]
                dist = np.array([math.hypot(els[i]["x"] - s["x"], els[i]["y"] - s["y"]) for i in ii])
                order = np.lexsort((g.random(len(ii)), dist))
                nrem = math.ceil(0.38 * len(ii))
                for o in order[:nrem]:
                    keep[ii[o]] = False
            KD[b] = k_digit(counts_of([labs[i] for i in range(len(els)) if keep[i]]), 2)
        clust[q] = {L: float(np.mean(KD >= L)) for L in (2, 3, 4, 5)}

    # ---------------- JHU secondary
    fif = load_fifer()
    left = [e for e in fif if e["array"] in ("left_array_A", "left_array_B")]
    right = [e for e in fif if e["array"] == "right_array"]

    def strict(e):
        return e["hues"][0] if len(e["hues"]) == 1 else "MIXED"

    def jhu_block(els):
        cs = counts_of([strict(e) for e in els])
        cl = counts_of([e["hues"][0] for e in els])
        return {"N_PF": len(els), "strict_counts": cs, "liberal_counts": cl,
                "K_finger_strict": {m: int(sum(cs.get(h, 0) >= m for h in HUES)) for m in (1, 2, 3)},
                "K_finger_liberal": {m: int(sum(cl.get(h, 0) >= m for h in HUES)) for m in (1, 2, 3)},
                "N_eff_strict_incl_mixed": neff(cs)}
    jl = jhu_block(left)
    jr = jhu_block(right)
    jl["per_array"] = {a: jhu_block([e for e in left if e["array"] == a]) for a in ("left_array_A", "left_array_B")}
    cs = jl["strict_counts"]
    nvec = [cs.get(h, 0) for h in HUES]
    jl_att = {p: {L: p_k_ge(nvec, p, 2, L) for L in (2, 3, 4)} for p in P_SENS}
    # MC check for JHU
    lab_j = [strict(e) for e in left]
    Mj = onehot_classes(lab_j, HUES)
    for p in P_SENS:
        surv = (rng("jhu").random((N_MC, len(left))) < p).astype(float)
        kk = ((surv @ Mj) >= 2).sum(1)
        for L in (2, 3, 4):
            e = jl_att[p][L]
            mcv = float(np.mean(kk >= L))
            good = abs(mcv - e) < 1e-15 if e in (0.0, 1.0) else abs(mcv - e) <= 3 * math.sqrt(e * (1 - e) / N_MC)
            if not good:
                c3_fail.append(("JHU", p, L, e, mcv))
    # relabelling (hue adjacency; DEVIATIONS item 10)
    hi = {h: i for i, h in enumerate(HUES)}
    base = np.array([hi[t] if t in hi else -1 for t in lab_j])
    Nj = len(base)
    kj = int(round(0.10 * Nj))
    KJ = np.zeros(N_REL, int)
    g = rng("jhu")
    for b in range(N_REL):
        lab = base.copy()
        idx = g.choice(Nj, kj, replace=False)
        for i in idx:
            if lab[i] >= 0:
                nb = [j for j in (lab[i] - 1, lab[i] + 1) if 0 <= j < 4]
                lab[i] = nb[g.integers(len(nb))]
        cnt = np.bincount(lab[lab >= 0], minlength=4)
        KJ[b] = int((cnt >= 2).sum())
    jl_rel = {L: float(np.mean(KJ >= L)) for L in (2, 3, 4)}
    jhu_ladder = {}
    for L in (4, 3, 2):
        cr = {"1_observed": jl["K_finger_strict"][2] >= L, "2_attrition": jl_att[P0][L] >= THR,
              "3_relabel": jl_rel[L] >= THR, "4_strict": jl["K_finger_strict"][2] >= L}
        jhu_ladder[L] = {"criteria": cr, "pass": all(cr.values()), "P_att": jl_att[P0][L], "P_rel": jl_rel[L]}
    c3_pass = len(c3_fail) == 0
    controls_pass = bool(c1_pass and c2_pass and c3_pass and n_pass == len(st))

    # ---------------- ladder verdict
    ladder = {}
    for L in LEVELS:
        key = "K_terr" if L == 6 else "K_digit"
        k_obs = {q: obs[q]["R1"][key][2] for q in PARTS}
        k_r3 = {q: obs[q]["R3"][key][2] for q in PARTS}
        n_ok = sum(k_obs[q] >= L for q in PARTS)
        pa = {q: att[q][P0]["exact"][L] for q in PARTS}
        pr = {q: rel[q][0.10]["P_rel"][L] for q in PARTS}
        cr = {"1_observed_3of3": n_ok == 3, "2_attrition_min_ge_0.8": min(pa.values()) >= THR,
              "3_relabel_min_ge_0.8": min(pr.values()) >= THR,
              "4_R3_2of3": sum(k_r3[q] >= L for q in PARTS) >= 2, "5_controls": controls_pass}
        ladder[L] = {"K_obs": k_obs, "n_participants_ge_L": n_ok, "P_att_0.62": pa, "P_rel_0.10": pr, "K_R3": k_r3,
                     "criteria": cr, "VERIFIED": all(cr.values()),
                     "label": "VERIFIED" if all(cr.values()) else ("MAJORITY (not verified)" if n_ok == 2 else "not verified")}
    verified = [L for L in LEVELS if ladder[L]["VERIFIED"]]
    kstar = max(verified) if verified else None
    if not controls_pass:
        claim = "not verifiable: code"
    elif kstar is None:
        claim = "not verifiable from open data"
    elif kstar >= 5:
        claim = f"K >= 5 VERIFIED (K* = {kstar})"
    else:
        claim = f"K >= 5 NOT supported; verified conservative K = {kstar}"
    nonmonotone = any(ladder[L]["VERIFIED"] and not ladder[L2]["VERIFIED"] for L in LEVELS for L2 in LEVELS if L2 < L)

    # ---------------- conditions table (criteria 1-2 only; DEVIATIONS item 9)
    cond = {}
    for rule in ("R1", "R2", "ray"):
        for m in (1, 2, 3):
            for p in P_COND:
                o = {q: {L: obs[q][rule]["K_terr" if L == 6 else "K_digit"][m] >= L for L in LEVELS} for q in PARTS}
                pa = {q: dp_levels(obs[q][rule]["counts"], p, m) for q in PARTS}
                cond[f"{rule}|m={m}|p={p}"] = k_star_simple(o, pa)

    jhu_top = max([L for L in (4, 3, 2) if jhu_ladder[L]["pass"]], default=None)
    jhu_note = ("replicated in an independent lab" if (kstar is not None and kstar <= 4 and jhu_top is not None
                                                        and jhu_top >= kstar) else
                "caveat: JHU pair does not reach K*" if kstar is not None else "n/a (no K*)")

    runtime = time.time() - t0
    out.update({"observed": obs, "attrition": att, "relabelling": rel, "joint_attrition_relabel": joint,
                "bootstrap": boot, "controls": {"C1": c1, "C1_pass": c1_pass, "C2_pass": c2_pass, "C3_pass": c3_pass,
                                                "C3_failures": c3_fail, "all_code_controls_pass": controls_pass},
                "C4_nulls": c4, "clustered_loss": clust, "ladder": ladder, "K_star": kstar, "claim": claim,
                "nonmonotone_ladder": nonmonotone, "conditions_table": cond,
                "JHU": {"left_pair": jl, "right_array": jr, "attrition_exact": jl_att, "relabel_0.10": jl_rel,
                        "ladder": jhu_ladder, "highest_passing_level": jhu_top, "corroboration": jhu_note},
                "attrition_curve": {"p": pgrid.tolist(), "P": att_curve}, "runtime_s": runtime})
    json.dump(jsonable(out), open(os.path.join(RES, "p6_empirical_channels.json"), "w"), indent=1)

    # CSV per participant
    with open(os.path.join(RES, "p6_per_participant.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["participant", "N_wired", "N_PF"] + [f"n_{t}" for t in DIG + ["PALM", "DORSUM_HAND"]] +
                   ["K_digit_m1", "K_digit_m2", "K_digit_m3", "K_terr_m2", "K_digit_m2_R2", "K_digit_m2_R3",
                    "K_digit_m2_ray", "N_eff_digit", "N_eff_seg", "N_eff_soft", "G_gain"] +
                   [f"Patt_L{L}_p0.62" for L in LEVELS] + [f"Prel_L{L}_x0.10" for L in LEVELS])
        for q in PARTS:
            o = obs[q]
            c = o["R1"]["counts"]
            w.writerow([q, o["N_wired"], o["N_PF"]] + [c.get(t, 0) for t in DIG + ["PALM", "DORSUM_HAND"]] +
                       [o["R1"]["K_digit"][1], o["R1"]["K_digit"][2], o["R1"]["K_digit"][3], o["R1"]["K_terr"][2],
                        o["R2"]["K_digit"][2], o["R3"]["K_digit"][2], o["ray"]["K_digit"][2],
                        round(o["R1"]["N_eff_digit"], 4), round(o["R1"]["N_eff_seg"], 4), round(o["R1"]["N_eff_soft"], 4),
                        o["G_second_array_gain_m2"]] +
                       [round(att[q][P0]["exact"][L], 6) for L in LEVELS] +
                       [round(rel[q][0.10]["P_rel"][L], 6) for L in LEVELS])

    figures(obs, att_curve, pgrid, ladder, kstar, jl, rel, att, arrays, by)
    print(json.dumps(jsonable({"K_star": kstar, "claim": claim, "controls": controls_pass, "runtime_s": runtime})))


# ------------------------------------------------------------------------------------------------ figures
C_SURF, C_TXT, C_TXT2, C_GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#d9d8d3"
SER = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def _style(ax):
    ax.set_facecolor(C_SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(C_TXT2)
    ax.tick_params(colors=C_TXT2, labelsize=9)
    ax.yaxis.grid(True, color=C_GRID, lw=0.6)
    ax.set_axisbelow(True)


def _save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"), dpi=180, facecolor=C_SURF, bbox_inches="tight")


def figures(obs, att_curve, pgrid, ladder, kstar, jl, rel, att, arrays, by):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "text.color": C_TXT, "axes.labelcolor": C_TXT2, "svg.fonttype": "none"})

    # (1) counts per territory, stacked by array, with m = 2 line
    terrs = DIG + ["PALM", "DORSUM_HAND"]
    fig, axs = plt.subplots(1, 4, figsize=(15, 3.8), sharey=True, gridspec_kw={"width_ratios": [7, 7, 7, 4]})
    fig.patch.set_facecolor(C_SURF)
    for ax, q in zip(axs, PARTS):
        _style(ax)
        bottom = np.zeros(len(terrs))
        for ai, a in enumerate(arrays[q]):
            ea = [e for e in by[q] if e["array"] == a]
            ca = counts_of([territory(e["palm"], e["dors"], "R1") for e in ea])
            v = np.array([ca.get(t, 0) for t in terrs], float)
            ax.bar(range(len(terrs)), v, bottom=bottom, color=SER[ai], width=0.7, edgecolor=C_SURF, linewidth=1.5,
                   label=a.replace("Sensory", " array"))
            bottom += v
        for i, v in enumerate(bottom):
            ax.text(i, v + 0.3, str(int(v)), ha="center", va="bottom", fontsize=8, color=C_TXT2)
        ax.axhline(2, color=C_TXT, lw=1.2, ls="--")
        ax.set_xticks(range(len(terrs)))
        ax.set_xticklabels(["D1", "D2", "D3", "D4", "D5", "palm", "dorsum\nhand"], fontsize=8)
        kd = obs[q]["R1"]["K_digit"][2]
        ax.set_title(f"{q}: K_digit(m=2) = {kd}  (N_PF = {obs[q]['N_PF']})", fontsize=10, loc="left", color=C_TXT)
    axs[0].set_ylabel("PF electrodes (R1 dominant territory)")
    axs[0].legend(frameon=False, fontsize=8, loc="upper right")
    axs[0].text(5.0, 2.6, "m = 2", fontsize=8, color=C_TXT, ha="right", va="bottom")
    ax = axs[3]
    _style(ax)
    cs = jl["strict_counts"]
    v = [cs.get(h, 0) for h in HUES] + [cs.get("MIXED", 0)]
    ax.bar(range(5), v, color=SER[0], width=0.7)
    for i, vv in enumerate(v):
        ax.text(i, vv + 0.3, str(vv), ha="center", va="bottom", fontsize=8, color=C_TXT2)
    ax.axhline(2, color=C_TXT, lw=1.2, ls="--")
    ax.set_xticks(range(5))
    ax.set_xticklabels(["hue1\n(red)", "hue2\n(orange)", "hue3\n(yellow)", "hue4\n(green)", "mixed"], fontsize=7)
    ax.set_title(f"JHU-1 left pair (secondary): K_finger = {jl['K_finger_strict'][2]}", fontsize=10, loc="left")
    fig.suptitle("P6: PF electrodes per territory, both arrays pooled (Greenspon 2025 ED Fig 1; Fifer 2022 Fig 1C, digitised)",
                 fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    _save(fig, "p6_counts_per_territory")
    plt.close(fig)

    # (2) attrition curves
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.9), sharey=True)
    fig.patch.set_facecolor(C_SURF)
    lv = [2, 3, 4, 5]
    for ax, q in zip(axs, PARTS):
        _style(ax)
        for i, L in enumerate(lv):
            y = att_curve[q][L]
            ax.plot(pgrid, y, color=SER[i], lw=2, label=f"K >= {L}")
        ax.axvline(0.62, color=C_TXT2, lw=1, ls=":")
        ax.axhline(0.8, color=C_TXT, lw=1, ls="--")
        ax.set_xlim(0.3, 1.0)
        ax.set_ylim(-0.02, 1.02)
        ax.set_xlabel("functional fraction p (independent survival)")
        ax.set_title(q, loc="left", fontsize=10)
        ax.text(0.625, 0.03, "p = 0.62", fontsize=8, color=C_TXT2)
        ax.text(0.305, 0.815, "0.8 threshold", fontsize=8, color=C_TXT)
    axs[0].set_ylabel("P(K_digit(m=2) >= L)  (exact)")
    axs[-1].legend(frameon=False, fontsize=8, loc="center right")
    fig.suptitle("P6 attrition: probability that >= L digit channels (each >= 2 electrodes) survive", fontsize=11,
                 x=0.01, ha="left")
    fig.tight_layout()
    _save(fig, "p6_attrition")
    plt.close(fig)

    # (3) web figure
    fig, ax = plt.subplots(figsize=(8, 4.6))
    fig.patch.set_facecolor(C_SURF)
    _style(ax)
    cats = PARTS
    series = [("observed (R1)", lambda q: obs[q]["R1"]["K_digit"][2], "o"),
              ("strict label (R3)", lambda q: obs[q]["R3"]["K_digit"][2], "s"),
              ("survives 62% function (P>=0.8)",
               lambda q: max([L for L in (2, 3, 4, 5) if att[q][P0]["exact"][L] >= THR], default=0), "^"),
              ("survives 10% relabelling (P>=0.8)",
               lambda q: max([L for L in (2, 3, 4, 5) if rel[q][0.10]["P_rel"][L] >= THR], default=0), "D")]
    for si, (nm, fn, mk) in enumerate(series):
        xs = [i + (si - 1.5) * 0.14 for i in range(len(cats))]
        ys = [fn(q) for q in cats]
        ax.scatter(xs, ys, s=70, color=SER[si], marker=mk, label=nm, zorder=3, edgecolors=C_SURF, linewidths=1.5)
    if kstar is not None:
        ax.axhline(kstar, color=C_TXT, lw=2)
        ax.text(len(cats) - 0.45, kstar + 0.08, f"verified K* = {kstar}", fontsize=10, color=C_TXT, ha="right",
                va="bottom", fontweight="bold")
    ax.axhline(5, color=C_TXT2, lw=1, ls="--")
    ax.text(-0.45, 5.08, "design target K_min = 5 (one per digit)", fontsize=8, color=C_TXT2, va="bottom")
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([f"participant {q}" for q in cats])
    ax.set_ylim(-0.3, 6)
    ax.set_xlim(-0.5, len(cats) - 0.5)
    ax.set_ylabel("digit channels (>= 2 electrodes each)")
    ttl = (f"One 2 x 32 S1 array pair: >= {kstar} verified digit channels" if kstar is not None
           else "One 2 x 32 S1 array pair: no digit-channel level verified (2 of 3 implants reach 4; P2 fails)")
    fig.text(0.01, 0.98, ttl, fontsize=13, fontweight="bold", color=C_TXT, ha="left", va="top")
    fig.text(0.01, 0.915, "computed from digitised published PF maps; analysis, not stimulation settings", fontsize=9,
             color=C_TXT2, ha="left", va="top")
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    _save(fig, "p6_channels_web")
    plt.close(fig)


if __name__ == "__main__":
    main()
