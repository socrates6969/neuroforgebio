"""Independent reviewer checks for P6 (cycle 4). Does NOT import or modify project code/results.

Usage: python check_p6.py [<rerun_extraction_json>]
  If a re-run extraction JSON (from a scratch copy of notes/published-derived/extract_greenspon2025_pf_segments.py) is given,
  its per-cell labels are compared with the committed extraction JSON and the per-electrode CSV.
Own implementations: territory rules from prereg section 3; P_att by enumeration over the 2^C subsets of surviving
classes (not the DP); exact false-alarm probability of the 3-SE rule for every C3 comparison; 1e6-draw MC (own seed).
"""
import csv, json, math, os, sys
from itertools import product
from collections import Counter
import numpy as np

ROOT = r"C:\Users\mariu\neuro-company\research\somatosensory"
DATA = os.path.join(ROOT, "notes", "published-derived")
RESJ = json.load(open(os.path.join(ROOT, "code", "results", "p6_empirical_channels.json")))
DIG = ["D1", "D2", "D3", "D4", "D5"]


def tmap(surf, tag, ray=False):
    if not tag:
        return None
    if tag[0] == "D" and tag[1] in "12345":
        return "D" + tag[1]
    if surf == "palm":
        if ray and tag[:1] == "P" and tag[1:2] in "2345" and tag.endswith("-mcp"):
            return "D" + tag[1]
        return "PALM"
    return "DORSUM_HAND"  # P-dr (only dorsum non-digit tag present in the CSV)


def terr(palm, dors, rule):
    tp, td = tmap("palm", palm, rule == "ray"), tmap("dors", dors)
    if rule in ("R1", "ray"):
        return tp if tp else td
    if rule == "R3":
        s = {t for t in (tp, td) if t}
        if len(s) == 1 and list(s)[0] in DIG:
            return list(s)[0]
        return "MIXED"


def p_class(n, p, m):
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(m, n + 1))


def p_att(nvec, p, m, L):
    q = [p_class(n, p, m) for n in nvec]
    tot = 0.0
    for s in product((0, 1), repeat=len(q)):
        if sum(s) >= L:
            pr = 1.0
            for si, qi in zip(s, q):
                pr *= qi if si else 1 - qi
            tot += pr
    return tot


rows = list(csv.DictReader(open(os.path.join(DATA, "pf_per_electrode_greenspon2025.csv"))))
pf = [r for r in rows if r["has_PF"] == "1"]
print("== (2) independent recount from CSV ==")
print("wired", Counter(r["participant"] for r in rows), "PF", Counter(r["participant"] for r in pf))
mism = 0
cnts = {}
for q in ("C1", "P2", "P3"):
    E = [r for r in pf if r["participant"] == q]
    for rule in ("R1", "R3", "ray"):
        c = Counter(terr(r["palm_segment"], r["dors_segment"], rule) for r in E)
        cnts[(q, rule)] = c
        kd = {m: sum(c[d] >= m for d in DIG) for m in (1, 2, 3)}
        rep = RESJ["observed"][q][rule]
        same = all(rep["counts"].get(k, 0) == c.get(k, 0) for k in set(c) | set(rep["counts"]) if k not in ("HAND", "MIXED")) \
            and all(rep["K_digit"][str(m)] == kd[m] for m in kd)
        mism += not same
        print(f"{q} {rule}: {dict(sorted(c.items()))}  K_digit m1/2/3={kd[1]}/{kd[2]}/{kd[3]}  matches JSON: {same}")
    c = cnts[(q, "R1")]
    kterr = sum(c[d] >= 2 for d in DIG) + int(c["PALM"] + c["DORSUM_HAND"] >= 2)
    n = np.array(list(c.values()), float)
    ne = n.sum() ** 2 / (n ** 2).sum()
    seg = Counter(("palm:" + r["palm_segment"]) if r["palm_segment"] else ("dors:" + r["dors_segment"]) for r in E)
    ns = np.array(list(seg.values()), float)
    nes = ns.sum() ** 2 / (ns ** 2).sum()
    print(f"   K_terr(m2)={kterr} (JSON {RESJ['observed'][q]['R1']['K_terr']['2']});  N_eff,digit={ne:.4f} "
          f"(JSON {RESJ['observed'][q]['R1']['N_eff_digit']:.4f});  N_eff,seg={nes:.4f} (JSON {RESJ['observed'][q]['R1']['N_eff_seg']:.4f})")
    for a in sorted({r["array"] for r in E}):
        ca = Counter(terr(r["palm_segment"], r["dors_segment"], "R1") for r in E if r["array"] == a)
        print(f"   {a}: {dict(sorted(ca.items()))} K_digit(m2)={sum(ca[d] >= 2 for d in DIG)}")
print("count/K mismatches vs JSON:", mism)

print("\n== (2) P_att(L; p) by 2^5 subset enumeration (not the DP) vs JSON exact ==")
worst = 0.0
for q in ("C1", "P2", "P3"):
    c = cnts[(q, "R1")]
    nv = [c[d] for d in DIG]
    for p in (0.47, 0.54, 0.62, 0.64, 0.75, 1.0):
        v = {L: p_att(nv, p, 2, L) for L in (2, 3, 4, 5)}
        v[6] = p_att(nv + [c["PALM"] + c["DORSUM_HAND"]], p, 2, 6)
        for L in v:
            worst = max(worst, abs(v[L] - RESJ["attrition"][q][str(p)]["exact"][str(L)]))
        if p == 0.62:
            print(f"{q} n={nv} p=0.62: " + " ".join(f"L{L}={v[L]:.6f}" for L in (2, 3, 4, 5, 6)))
print(f"max |enum - JSON exact| over 3 x 6 p x 5 L: {worst:.2e}")
print(f"P2 L2 closed form: q_D1*q_D2 + ... ; q_D2 = 0.62^2 = {0.62**2:.4f}; q_D1 = {p_class(9, .62, 2):.6f}")

# JHU strict counts
fif = [r for r in csv.DictReader(open(os.path.join(DATA, "pf_per_electrode_fifer2022.csv"))) if r["status"] == "PF"]
left = [r for r in fif if r["array"] in ("left_array_A", "left_array_B")]
hs = Counter((r["hue_classes"] if "|" not in r["hue_classes"] else "MIXED") for r in left)
print("\nJHU left strict counts:", dict(hs), " JSON:", RESJ["JHU"]["left_pair"]["strict_counts"])
jn = [hs.get(h, 0) for h in ("red", "orange", "yellow", "green")]
jh = {p: {L: p_att(jn, p, 2, L) for L in (2, 3, 4)} for p in (0.47, 0.54, 0.62, 0.64, 0.75, 1.0)}
print("JHU P_att(p=0.62) L2/3/4:", [round(jh[0.62][L], 6) for L in (2, 3, 4)])

print("\n== (3) C3: exact probability that the 3-SE rule (SE at exact P, N=20000) flags a CORRECT implementation ==")
from scipy.stats import binom
N = 20000
fa = []
for q in ("C1", "P2", "P3"):
    c = cnts[(q, "R1")]
    nv = [c[d] for d in DIG]
    for p in (0.47, 0.54, 0.62, 0.64, 0.75, 1.0):
        for L in (2, 3, 4, 5, 6):
            e = p_att(nv + ([c["PALM"] + c["DORSUM_HAND"]] if L == 6 else []), p, 2, L)
            fa.append((q, p, L, e))
for p in jh:
    for L in (2, 3, 4):
        fa.append(("JHU", p, L, jh[p][L]))
exp_fa, probs = 0.0, []
for q, p, L, e in fa:
    if e < 1e-15 or e > 1 - 1e-15:
        pf_ = 0.0
    else:
        se = math.sqrt(e * (1 - e) / N)
        lo, hi = math.ceil(N * (e - 3 * se) - 1e-9), math.floor(N * (e + 3 * se) + 1e-9)
        pf_ = 1 - (binom.cdf(hi, N, e) - binom.cdf(lo - 1, N, e))
    probs.append(pf_)
    exp_fa += pf_
probs = np.array(probs)
# P(>=1) and P(>=2) treating the comparisons as independent (they share draws within (q,p); rough)
pk = np.zeros(len(probs) + 1); pk[0] = 1
for x in probs:
    pk[1:] = pk[1:] * (1 - x) + pk[:-1] * x; pk[0] *= 1 - x
print(f"n comparisons = {len(fa)}; expected false alarms = {exp_fa:.3f}; P(>=1) = {1-pk[0]:.3f}; P(>=2) = {1-pk[0]-pk[1]:.3f}")
top = sorted(zip(probs, fa), reverse=True)[:5]
for pr, (q, p, L, e) in top:
    print(f"   highest per-test false-alarm prob: {q} p={p} L={L} exact={e:.7f} P(flag)={pr:.4f}")
for q, p, L, e, mcv in RESJ["controls"]["C3_failures"]:
    se_e = math.sqrt(e * (1 - e) / N); se_m = math.sqrt(mcv * (1 - mcv) / N)
    print(f"   reported failure {q} p={p} L={L}: exact {e:.7f} MC {mcv:.5f} |d|/SE(exact P)={abs(mcv-e)/se_e:.3f} "
          f"|d|/SE(MC P)={abs(mcv-e)/se_m:.3f}  two-sided binomial tail P(|d| >= obs) = "
          f"{binom.sf(round(mcv*N)-1, N, e) if mcv > e else binom.cdf(round(mcv*N), N, e):.4f} (one side)")

# own 1e6 MC for the two flagged cases
g = np.random.default_rng(777)
lab = {q: [terr(r["palm_segment"], r["dors_segment"], "R1") for r in pf if r["participant"] == q] for q in ("P3",)}
nvP3 = [cnts[("P3", "R1")][d] for d in DIG]
hits, tot = 0, 0
for _ in range(20):
    s = g.binomial(np.array(nvP3)[None, :], 0.62, (50000, 5))
    hits += int(((s >= 2).sum(1) >= 2).sum()); tot += 50000
print(f"own MC 1e6: P3 L2 p0.62 = {hits/tot:.6f} (enum {p_att(nvP3, .62, 2, 2):.7f})")
hits, tot = 0, 0
for _ in range(20):
    s = g.binomial(np.array(jn)[None, :], 0.64, (50000, 4))
    hits += int(((s >= 2).sum(1) >= 4).sum()); tot += 50000
print(f"own MC 1e6: JHU L4 p0.64 = {hits/tot:.5f} +/- {math.sqrt(jh[0.64][4]*(1-jh[0.64][4])/tot):.5f} (enum {jh[0.64][4]:.5f})")

print("\n== (4) P2 labels ==")
E = [r for r in pf if r["participant"] == "P2"]
palmtags = Counter(r["palm_segment"] for r in E if tmap("palm", r["palm_segment"]) == "PALM")
print("P2 PALM-by-R1 palm tags:", dict(palmtags))
pd = Counter(tmap("dors", r["dors_segment"]) for r in E if tmap("palm", r["palm_segment"]) == "PALM")
print("  their dorsum territory:", dict(pd))
print("  P2 electrodes with EMPTY palm segment:", sum(1 for r in E if not r["palm_segment"]))
for r in E[:24]:
    print(f"   {r['array']:15s} ch{int(r['electrode_channel']):2d} r{r['grid_row']}c{r['grid_col']} palm={r['palm_segment'] or '-':16s} "
          f"dors={r['dors_segment'] or '-':10s} dist p/d={r['palm_colour_dist']}/{r['dors_colour_dist']} R1={terr(r['palm_segment'], r['dors_segment'], 'R1')}")

print("\n== (4) digitisation: committed extraction JSON vs CSV vs re-run ==")
com = json.load(open(os.path.join(DATA, "greenspon2025_ed1_extraction.json")))
def key(r): return (r["participant"], r["array"], r["surface"], r["grid_row"], r["grid_col"])
cm = {key(r): r for r in com["records"]}
bad = 0
for r in rows:
    for surf, col in (("palm", "palm_segment"), ("dors", "dors_segment")):
        s = cm[(r["participant"], r["array"], surf, int(r["grid_row"]), int(r["grid_col"]))]["seg"]
        bad += (("" if s == "NONE" else s) != r[col])
print(f"CSV vs committed JSON label mismatches over {2*len(rows)} surface-cells: {bad}")
marg = [r["margin"] for r in com["records"] if r["participant"] == "P2"]
print(f"P2 colour margin (nearest vs 2nd) min/median: {min(marg)}/{np.median(marg)}; max dist {max(r['dist'] for r in com['records'])}")
if len(sys.argv) > 1:
    new = json.load(open(sys.argv[1]))
    nm = {key(r): r for r in new["records"]}
    diff = [k for k in cm if cm[k]["seg"] != nm[k]["seg"]]
    print(f"re-run vs committed: {len(nm)} cells, label differences: {len(diff)}", diff[:5])
    segdiff = sum(1 for a, b in zip(com["segments"]["palm"] + com["segments"]["dors"], new["segments"]["palm"] + new["segments"]["dors"])
                  if a["label"] != b["label"] or abs(a["cx"] - b["cx"]) > 1e-6)
    print("segment-table differences:", segdiff)

print("\n== (5) verdict logic recomputed ==")
kobs = {q: sum(cnts[(q, 'R1')][d] >= 2 for d in DIG) for q in ("C1", "P2", "P3")}
for L in (5, 4, 3, 2):
    c1 = all(kobs[q] >= L for q in kobs)
    pa = min(p_att([cnts[(q, 'R1')][d] for d in DIG], .62, 2, L) for q in kobs)
    r3 = sum(sum(cnts[(q, 'R3')][d] >= 2 for d in DIG) >= L for q in kobs)
    print(f"L{L}: crit1 {c1} ({kobs}); min P_att {pa:.4f} -> crit2 {pa >= .8}; R3 >=L in {r3}/3 -> crit4 {r3 >= 2}; "
          f"verified ignoring crit3/5: {c1 and pa >= .8 and r3 >= 2}")

print("\n== (1) relabelling x=0.10, independent re-implementation (3 nearest same-surface segment centroids) ==")
segs = [(surf, s["label"], s["cx"], s["cy"]) for surf in ("palm", "dors") for s in com["segments"][surf]]
sid = {(a, b): i for i, (a, b, _, _) in enumerate(segs)}
nb = []
for i, (sf, t, x, y) in enumerate(segs):
    d = sorted((math.hypot(x - x2, y - y2), j) for j, (sf2, t2, x2, y2) in enumerate(segs) if j != i and sf2 == sf)
    nb.append([j for _, j in d[:3]])
def seg_terr(i):
    sf, t = segs[i][0], segs[i][1]
    return "WRIST" if t == "W" else tmap(sf, t)
g2 = np.random.default_rng(4242)
for q in ("C1", "P2", "P3"):
    E = [r for r in pf if r["participant"] == q]
    base = [sid[("palm", r["palm_segment"])] if r["palm_segment"] else sid[("dors", r["dors_segment"])] for r in E]
    k = round(0.10 * len(E)); K = []
    for _ in range(5000):
        dom = list(base)
        for i in g2.choice(len(E), k, replace=False):
            dom[i] = nb[dom[i]][g2.integers(3)]
        c = Counter(seg_terr(i) for i in dom)
        K.append(sum(c[d] >= 2 for d in DIG))
    K = np.array(K)
    rep = RESJ["relabelling"][q]["0.1"]["P_rel"]
    print(f"{q}: P_rel L2/3/4 = {np.mean(K>=2):.3f}/{np.mean(K>=3):.3f}/{np.mean(K>=4):.3f}  JSON {rep['2']:.3f}/{rep['3']:.3f}/{rep['4']:.3f}")
