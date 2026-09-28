"""REVIEW N1b: independent re-implementation of the §2.1 exclusion and sampler S from notes\\data\\chbmit_selection.csv
(no nfharness, no n1b import for the reference), brute-force per-onset validity, then comparison with n1b.sampler on the
same SeedSequence streams (k=10 train with the N1b-15 condition, k=11 test, first 50 of the k=12 null draws), all 30
real replicates. Also checks every drawn phantom (+tolerance) against the real-seizure exclusion in absolute file time.
RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Writes n1b_sampler_indep_out.json."""
import csv
import json
import os
import sys

import numpy as np

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
SEED = 20261001
SUBJ = ["chb01", "chb03", "chb10"]


def g(*key):
    return np.random.default_rng(np.random.SeedSequence(SEED, spawn_key=tuple(key)))


rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "notes", "data", "chbmit_selection.csv"))) if r["subject"] in SUBJ]


def seizures(r):
    s = r["seizures_start_end_s"].strip()
    if not s:
        return []
    return [tuple(int(x) for x in p.split("-")) for p in s.split(";")]


def build(subj):
    fs = sorted([r for r in rows if r["subject"] == subj], key=lambda r: float(r["t_start_h_from_subject_first_file"]))
    cum, cut = 0, None
    for i, r in enumerate(fs):
        cum += len(seizures(r))
        if cum >= 3:
            cut = i
            break
    tr, te = fs[:cut + 1], fs[cut + 1:]

    def segs(files):
        out = []
        for fo, r in enumerate(files):
            T = int(r["duration_s"])
            ok = [True] * T
            for on, off in seizures(r):
                for t in range(max(0, on - 600), min(T, off + 900)):
                    ok[t] = False
            a = None
            for t in range(T + 1):
                inside = t < T and ok[t]
                if inside and a is None:
                    a = t
                if not inside and a is not None:
                    if t - a >= 2:
                        out.append((r["file"], fo, a, t))
                    a = None
        return out

    def durs(files):
        return [(off - on, fo, k) for fo, r in enumerate(files) for k, (on, off) in enumerate(seizures(r))]
    return tr, te, segs(tr), segs(te), durs(tr), durs(te)


def valid_bruteforce(Ls, d, placed):
    V = []
    for j, L in enumerate(Ls):
        for o in range(0, L):
            if not (o - 30 >= 0 and o + d + 60 <= L):
                continue
            if all(o + d + 300 <= o2 or o >= o2 + d2 + 300 for o2, d2 in placed.get(j, [])):
                V.append((j, o))
    return V


def place(Ls, order, rng):
    placed, out = {}, []
    for d in order:
        V = valid_bruteforce(Ls, d, placed)
        if not V:
            return None
        j, o = V[int(rng.integers(0, len(V)))]
        placed.setdefault(j, []).append((o, d))
        out.append((j, o, d))
    return out


def place_redraw(Ls, order, rng):
    n = 0
    while True:
        p = place(Ls, order, rng)
        if p is not None:
            return p, n
        n += 1


sys.path.insert(0, os.path.join(ROOT, "code"))
from n1b import sampler as S  # noqa: E402  (implementation under review, compared only)

res = {"table": {}, "mismatch": [], "exclusion_violations": [], "valid_set_size_first_test_phantom": {}}
for si, s in enumerate(SUBJ):
    tr, te, str_, ste, dtr, dte = build(s)
    res["table"][s] = [round(sum(b - a for _, _, a, b in str_) / 3600, 2), len(str_), round(sum(b - a for _, _, a, b in ste) / 3600, 2), len(ste),
                       [d for d, _, _ in dtr], [d for d, _, _ in dte]]
    Ltr = [b - a for _, _, a, b in str_]
    Lte = [b - a for _, _, a, b in ste]
    otr = [d for d, _, _ in sorted(dtr, key=lambda x: (-x[0], x[1], x[2]))]
    ote = [d for d, _, _ in sorted(dte, key=lambda x: (-x[0], x[1], x[2]))]
    res["valid_set_size_first_test_phantom"][s] = len(valid_bruteforce(Lte, ote[0], {}))
    ann = {r["file"]: seizures(r) for r in tr + te}
    for rep in range(10):
        # training phantoms with the N1b-15 condition (>= 2 original training files)
        ga, gb = g(10, si, rep), g(10, si, rep)
        while True:
            mine, _ = place_redraw(Ltr, otr, ga)
            if len({str_[j][1] for j, _, _ in mine}) >= 2:
                break
        # implementation
        while True:
            theirs, _ = S.place_with_redraw(Ltr, S.placement_order(dtr), gb)
            if len({str_[j][1] for j, _, _ in theirs}) >= 2:
                break
        if mine != theirs:
            res["mismatch"].append((s, rep, "train"))
        mt, _ = place_redraw(Lte, ote, g(11, si, rep))
        tt, _ = S.place_with_redraw(Lte, S.placement_order(dte), g(11, si, rep))
        if mt != tt:
            res["mismatch"].append((s, rep, "test"))
        gn1, gn2 = g(12, si, rep), g(12, si, rep)
        for m in range(50):
            if place_redraw(Lte, ote, gn1)[0] != S.place_with_redraw(Lte, S.placement_order(dte), gn2)[0]:
                res["mismatch"].append((s, rep, "null", m))
                break
        for segs, pl in ((str_, mine), (ste, mt)):
            for j, o, d in pl:
                f, _, a, b = segs[j]
                lo, hi = a + o - 30, a + o + d + 60
                if lo < a or hi > b:
                    res["exclusion_violations"].append((s, rep, f, "outside segment"))
                for on, off in ann[f]:
                    if lo < off + 900 and hi > on - 600:
                        res["exclusion_violations"].append((s, rep, f, "touches excluded time"))
res["ok"] = not res["mismatch"] and not res["exclusion_violations"]
json.dump(res, open(os.path.join(ROOT, "code", "review", "n1b_sampler_indep_out.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
