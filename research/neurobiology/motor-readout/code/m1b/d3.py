"""M1b D3 (EEGMMIDB imagined left/right fist): honest LDA / Riemannian TS, NC1-D3 label permutations, and the new PL-4
planted channel (§6.2). Blocks copied from run_m1.py (reviewed) cite the source lines; the D3 spec is unchanged from M1.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt

from m1lib import decoders as DEC
from m1lib.guards import FeatureWhitelistError, assert_whitelist

EEG_WL = ["eeg%02d" % i for i in range(64)]
PL4_COL = "planted_ch65"


def bandpass(x, fs):
    sos = butter(4, [8, 30], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, x, axis=1)


def task_events(ann):
    return [(on, dur, txt) for on, dur, txt in ann if txt in ("T1", "T2")]


def epochs(xf, fs, ev):
    """run_m1.py l.640-653 (after filtering): epoch [onset+0.5, onset+2.5) s."""
    ep, lab, ons = [], [], []
    n = int(round(2.0 * fs))
    for on, dur, txt in ev:
        a = int(round((on + 0.5) * fs))
        if a + n > xf.shape[1]:
            continue
        ep.append(xf[:, a:a + n])
        lab.append(0 if txt == "T1" else 1)
        ons.append(on)
    return np.array(ep), np.array(lab), np.array(ons)


def a6_check(ann, dur_s):
    """run_m1.py l.656-663."""
    labels = sorted(set(t for _, _, t in ann))
    bad = [t for t in labels if t not in ("T0", "T1", "T2")]
    task = [d for _, d, t in ann if t in ("T1", "T2")]
    ok = (not bad) and ("T1" in labels) and ("T2" in labels) and all(d is not None and 3.5 <= d <= 5.0 for d in task) \
        and 110 <= dur_s <= 130
    return ok, dict(labels=labels, task_dur_min=min(task) if task else None, task_dur_max=max(task) if task else None,
                    file_s=dur_s)


def lda_select(Xr, yr):
    """run_m1.py l.666-676."""
    gammas = [0, 0.1, 0.3, 0.5, 0.9]
    acc = []
    for g in gammas:
        s = []
        for tr, te in (("R04", "R08"), ("R08", "R04")):
            m = DEC.ShrinkLDA().fit(Xr[tr], yr[tr], g)
            s.append(float((m.predict(Xr[te]) == yr[te]).mean()))
        acc.append(np.mean(s))
    return gammas[int(np.argmax(acc))], acc


def ts_select(Cr, yr):
    """run_m1.py l.679-693."""
    Cs = [float(c) for c in np.logspace(-3, 2, 11)]
    acc = []
    feats = {}
    for tr, te in (("R04", "R08"), ("R08", "R04")):
        M = DEC.riemann_mean(Cr[tr])
        feats[(tr, te)] = (DEC.tangent(Cr[tr], M), DEC.tangent(Cr[te], M))
    for c in Cs:
        s = []
        for tr, te in (("R04", "R08"), ("R08", "R04")):
            Ftr, Fte = feats[(tr, te)]
            m = DEC.LogRegL2().fit(Ftr, yr[tr], c)
            s.append(float((m.predict(Fte) == yr[te]).mean()))
        acc.append(np.mean(s))
    return Cs[int(np.argmax(acc))], acc


def lda_fit_predict(Xr, yr, X12):
    g, gacc = lda_select(Xr, yr)
    Xtr = np.vstack([Xr["R04"], Xr["R08"]])
    ytr = np.concatenate([yr["R04"], yr["R08"]])
    lda = DEC.ShrinkLDA().fit(Xtr, ytr, g)
    return lda.predict(X12), dict(gamma=g, gamma_inner_acc=gacc), DEC.arr_hash(lda.w, [lda.b])


def fit_subject(Xr, Cr, yr, X12, C12, with_ts=True):
    """run_m1.py l.696-707."""
    pl, sl, hl = lda_fit_predict(Xr, yr, X12)
    preds, sel, hs = dict(LDA=pl), dict(sl), dict(LDA=hl)
    if with_ts:
        c, cacc = ts_select(Cr, yr)
        Ctr = np.concatenate([Cr["R04"], Cr["R08"]])
        ytr = np.concatenate([yr["R04"], yr["R08"]])
        M = DEC.riemann_mean(Ctr)
        lr = DEC.LogRegL2().fit(DEC.tangent(Ctr, M), ytr, c)
        preds["TS"] = lr.predict(DEC.tangent(C12, M))
        sel.update(C=c, C_inner_acc=cacc)
        hs["TS"] = DEC.arr_hash(lr.w, [lr.b], M)
    return preds, sel, hs


def pl4_whitelist():
    cols = EEG_WL + [PL4_COL]
    try:
        assert_whitelist(cols, EEG_WL)
        raised = None
    except FeatureWhitelistError as e:
        raised = type(e).__name__
    assert_whitelist(cols, EEG_WL, declared_extra=[PL4_COL])
    return raised


def pl4_channel(n_samples, fs, t2_intervals, g):
    """White N(0,1) with SD x 2 inside T2 intervals [onset, onset+dur)."""
    z = g.standard_normal(n_samples)
    for on, dur in t2_intervals:
        a, b = int(round(on * fs)), int(round((on + dur) * fs))
        z[a:b] *= 2.0
    return z


def pl4_features(ch, fs, ev):
    """log-variance of the band-passed planted channel over the task epochs ev (label-free timing)."""
    xf = bandpass(ch[None, :], fs)
    ep, _, _ = epochs(xf, fs, ev)
    return np.log(ep.var(axis=2))
