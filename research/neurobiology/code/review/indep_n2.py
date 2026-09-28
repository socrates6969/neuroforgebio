"""Reviewer's INDEPENDENT re-implementation of the N2 primary causal pipeline (chb01, chb03, chb10).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Written by the code reviewer from prereg\\N2_baseline_detection.md only; imports NOTHING from nfharness or edf_reader.
Own EDF reader, own features, own z-score, own logistic regression (Newton / IRLS, not L-BFGS), own tau scan,
own k-of-n, own AUROC (Mann-Whitney via scipy.stats.mannwhitneyu), scoring with timescoring 0.0.7 directly AND with
an own any-overlap event scorer. Writes code\\review\\indep_n2_out.json (includes 1-Hz hypothesis event lists).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import datetime as dt
import hashlib
import json
import re
import sys
import time

import numpy as np
from scipy import stats as sst

ROOT = r"C:\Users\mariu\neuro-company\research\neurobiology"
RAW = os.path.join(ROOT, "data", "raw", "chbmit")
OUT = os.path.join(ROOT, "code", "review", "indep_n2_out.json")

SPLIT_TXT = (
    "chb01;train=chb01_01.edf,chb01_02.edf,chb01_03.edf,chb01_04.edf,chb01_05.edf,chb01_06.edf,chb01_15.edf;"
    "test=chb01_16.edf,chb01_18.edf,chb01_21.edf,chb01_26.edf\n"
    "chb03;train=chb03_01.edf,chb03_02.edf,chb03_03.edf;"
    "test=chb03_04.edf,chb03_05.edf,chb03_06.edf,chb03_07.edf,chb03_08.edf,chb03_34.edf,chb03_35.edf,chb03_36.edf\n"
    "chb10;train=chb10_12.edf,chb10_20.edf,chb10_27.edf;test=chb10_30.edf,chb10_31.edf,chb10_38.edf,chb10_89.edf")
assert hashlib.sha256(SPLIT_TXT.encode()).hexdigest() == "433d818f305ba2095ef854b1f7f8b594895ad070f5fc28584a5507bdc7d9f1e2"
SPLIT = {}
for line in SPLIT_TXT.split("\n"):
    s, tr, te = line.split(";")
    SPLIT[s] = (tr[6:].split(","), te[5:].split(","))

TAUS = [round(0.05 + 0.01 * i, 2) for i in range(95)]
BANDS = [(1, 4), (4, 8), (8, 13), (13, 30), (30, 55)]


def edf_read(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    hb = int(raw[184:192]); ns = int(raw[252:256]); nrec = int(raw[236:244]); rdur = float(raw[244:252])
    date, tm = raw[168:176].decode().strip(), raw[176:184].decode().strip()
    d, mo, y = map(int, date.split(".")); hh, mi, ss = map(int, tm.split("."))
    start = dt.datetime(2000 + y if y < 85 else 1900 + y, mo, d, hh, mi, ss)
    off = 256
    def fld(w):
        nonlocal off
        v = [raw[off + i * w: off + (i + 1) * w].decode("latin-1").strip() for i in range(ns)]
        off += ns * w
        return v
    labels = fld(16); fld(80); fld(8)
    pmin = np.array(fld(8), float); pmax = np.array(fld(8), float)
    dmin = np.array(fld(8), float); dmax = np.array(fld(8), float)
    fld(80); spr = np.array(fld(8), int); fld(32)
    assert np.all(spr == 256)
    a = np.frombuffer(raw, dtype="<i2", offset=hb, count=nrec * ns * 256).reshape(nrec, ns, 256)
    return labels, start, int(round(nrec * rdur)), a, pmin, pmax, dmin, dmax


def features(path):
    labels, start, T, a, pmin, pmax, dmin, dmax = edf_read(path)
    assert labels[22] == "T8-P8" and labels[14] == "T8-P8"
    nw = T - 1
    hann = np.hanning(512)
    f = np.fft.rfftfreq(512, 1 / 256)
    F = np.empty((nw, 132), np.float64)
    for c in range(22):
        g = (pmax[c] - pmin[c]) / (dmax[c] - dmin[c])
        x = (a[:, c, :].reshape(-1).astype(np.float64) - dmin[c]) * g + pmin[c]
        idx = np.arange(nw)[:, None] * 256 + np.arange(512)[None, :]
        W = x[idx]
        W = W - W.mean(1, keepdims=True)
        ll = np.mean(np.abs(W[:, 1:] - W[:, :-1]), 1)
        P = np.abs(np.fft.rfft(W * hann, axis=1)) ** 2
        F[:, 6 * c] = np.log10(ll + 1e-3)
        for b, (lo, hi) in enumerate(BANDS):
            F[:, 6 * c + 1 + b] = np.log10(P[:, (f >= lo) & (f < hi)].sum(1) + 1e-3)
        del W, P
    return start, T, F


def parse_summary(path):
    out, cur, st = {}, None, None
    for line in open(path, encoding="latin-1"):
        m = re.match(r"File Name:\s*(\S+)", line.strip())
        if m:
            cur = m.group(1); out[cur] = []; continue
        m = re.search(r"Start Time:\s*(\d+)\s*seconds", line)
        if m: st = int(m.group(1)); continue
        m = re.search(r"End Time:\s*(\d+)\s*seconds", line)
        if m: out[cur].append((st, int(m.group(1))))
    return out


def ref_mask(evs, T):
    m = np.zeros(T, bool)
    for a, b in evs:
        m[a:b] = True
    return m


def win_labels(m):
    return (m[:-1] & m[1:]).astype(int)


def logreg_newton(Z, y, C=1.0, tol=1e-10, maxit=100):
    n, d = Z.shape
    n1 = y.sum(); n0 = n - n1
    w = np.where(y == 1, n / (2.0 * n1), n / (2.0 * n0))
    X = np.hstack([Z, np.ones((n, 1))])
    th = np.zeros(d + 1)
    R = np.eye(d + 1) / C; R[d, d] = 0.0
    for it in range(maxit):
        p = 1 / (1 + np.exp(-(X @ th)))
        g = X.T @ (w * (p - y)) + R @ th
        H = (X * (w * p * (1 - p))[:, None]).T @ X + R
        step = np.linalg.solve(H, g)
        th -= step
        if np.max(np.abs(g)) < 1e-9 or np.max(np.abs(step)) < tol:
            break
    return th, it


def fit_predict(Xtr, ytr, Xte_list):
    mu = Xtr.mean(0); sd = np.maximum(Xtr.std(0), 1e-8)
    th, _ = logreg_newton((Xtr - mu) / sd, ytr)
    return [1 / (1 + np.exp(-(((X - mu) / sd) @ th[:-1] + th[-1]))) for X in Xte_list]


def hyp_mask(p, tau, T):
    b = (p >= tau).astype(int)
    cs = np.concatenate([[0], np.cumsum(b)])
    i = np.arange(b.size)
    cnt = cs[i + 1] - cs[np.maximum(i - 4, 0)]
    d = (cnt >= 4) & (i >= 3)
    m = np.zeros(T, bool)
    m[1:] = d[:T - 1]
    return m


def events(m):
    m = np.asarray(m, bool)
    e = np.diff(np.concatenate([[0], m.astype(int), [0]]))
    return list(zip(np.flatnonzero(e == 1).tolist(), np.flatnonzero(e == -1).tolist()))


def own_score(ref, hyp):
    """Own any-overlap scorer: merge gaps < 90 s, split > 300 s, ref extended [-30, +60)."""
    def prep(m):
        ev = events(m)
        mg = []
        for a, b in ev:
            if mg and a - mg[-1][1] < 90:
                mg[-1] = (mg[-1][0], b)
            else:
                mg.append((a, b))
        out = []
        for a, b in mg:
            while b - a > 300:
                out.append((a, a + 300)); a += 300
            out.append((a, b))
        return out
    R, Hh = prep(ref), prep(hyp)
    ov = lambda r, h: h[0] < r[1] + 60 and h[1] > r[0] - 30
    tp = sum(any(ov(r, h) for h in Hh) for r in R)
    fp = sum(not any(ov(r, h) for r in R) for h in Hh)
    return tp, fp, len(R)


def ts_score(ref, hyp):
    from timescoring import scoring
    from timescoring.annotations import Annotation
    p = scoring.EventScoring.Parameters(toleranceStart=30, toleranceEnd=60, minOverlap=0, maxEventDuration=300,
                                        minDurationBetweenEvents=90)
    s = scoring.EventScoring(Annotation(ref, 1), Annotation(hyp, 1), p)
    return int(s.tp), int(s.fp), int(s.refTrue)


def main():
    t0 = time.time()
    res = {}
    for s in ("chb01", "chb03", "chb10"):
        tr, te = SPLIT[s]
        ann = parse_summary(os.path.join(RAW, s, "%s-summary.txt" % s))
        F, T, ST = {}, {}, {}
        for f in tr + te:
            ST[f], T[f], F[f] = features(os.path.join(RAW, s, f))
        t_first = min(ST.values())
        tabs = {f: (ST[f] - t_first).total_seconds() for f in F}
        # chronology check (F6)
        causal_ok = max(tabs[f] + T[f] for f in tr) <= min(tabs[f] for f in te)
        # buffer: drop training windows whose end lies within 10 s of (or after) the start of any test file
        keep = {}
        for f in tr:
            ends = tabs[f] + np.arange(T[f] - 1) + 2
            k = np.ones(T[f] - 1, bool)
            for g in te:
                k &= ~((ends > tabs[g] - 10) & (tabs[f] + np.arange(T[f] - 1) < tabs[g] + T[g] + 10))
            keep[f] = np.flatnonzero(k)
        ytr = {f: win_labels(ref_mask(ann[f], T[f])) for f in tr}
        # inner LOFO
        oof = {}
        for h in tr:
            others = [f for f in tr if f != h]
            X = np.vstack([F[f][keep[f]] for f in others]); y = np.concatenate([ytr[f][keep[f]] for f in others])
            oof[h] = fit_predict(X, y, [F[h]])[0]
        Htr = sum(T[f] for f in tr) / 3600.0
        tau = 0.99
        for tt in TAUS:
            fp = sum(ts_score(ref_mask(ann[f], T[f]), hyp_mask(oof[f], tt, T[f]))[1] for f in tr)
            if 24.0 * fp / Htr <= 12.0:
                tau = tt
                break
        X = np.vstack([F[f][keep[f]] for f in tr]); y = np.concatenate([ytr[f][keep[f]] for f in tr])
        P = dict(zip(te, fit_predict(X, y, [F[f] for f in te])))
        TP = FP = NR = TPo = FPo = 0
        hyps = {}
        for f in te:
            r = ref_mask(ann[f], T[f]); hm = hyp_mask(P[f], tau, T[f])
            a = ts_score(r, hm); b = own_score(r, hm)
            TP += a[0]; FP += a[1]; NR += a[2]; TPo += b[0]; FPo += b[1]
            hyps[f] = {"T": T[f], "hyp_events": events(hm), "ref_events": ann[f]}
        H = sum(T[f] for f in te) / 3600.0
        yw = np.concatenate([win_labels(ref_mask(ann[f], T[f])) for f in te])
        sc = np.concatenate([P[f] for f in te])
        U = sst.mannwhitneyu(sc[yw == 1], sc[yw == 0]).statistic
        auroc = float(U / ((yw == 1).sum() * (yw == 0).sum()))
        ci_cp = sst.binomtest(TP, NR).proportion_ci(method="exact")
        gl = 0.0 if FP == 0 else sst.gamma.ppf(0.025, FP)          # Garwood via gamma quantiles (independent form)
        gu = sst.gamma.ppf(0.975, FP + 1)
        res[s] = {"causal_chronology_ok": bool(causal_ok), "n_buffer_dropped": int(sum(T[f] - 1 - keep[f].size for f in tr)),
                  "n_train_windows": int(sum(keep[f].size for f in tr)), "n_train_pos": int(sum(ytr[f][keep[f]].sum() for f in tr)),
                  "tau": tau, "tp_timescoring": TP, "fp_timescoring": FP, "n_ref": NR, "tp_own": TPo, "fp_own": FPo,
                  "hours": H, "fa_per_24h": 24.0 * FP / H, "window_auroc": auroc, "n_test_windows": int(yw.size),
                  "n_pos_windows": int(yw.sum()), "cp95": [float(ci_cp.low), float(ci_cp.high)],
                  "garwood95_per_24h": [24 * gl / H, 24 * gu / H], "hyp": hyps,
                  "t_first_test_minus_end_last_train_s": min(tabs[f] for f in te) - max(tabs[f] + T[f] for f in tr)}
        del F
        print(s, {k: v for k, v in res[s].items() if k != "hyp"}, flush=True)
    res["_wall_s"] = time.time() - t0
    with open(OUT, "w") as fh:
        json.dump(res, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
