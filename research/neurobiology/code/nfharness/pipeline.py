"""The locked N2 pipeline run on one split, plus the N1 control variants.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Flow per split: guards -> training labels (vault, training files only) -> inner CV (train_oof scores) -> tau* ->
final fit -> test scores -> hypothesis masks -> Scorer (the only reader of test labels) -> metrics.
"""
import numpy as np

from . import stats
from .config import LOCKED_CONFIG, guard_hit
from .labels import mask_from_events  # noqa: F401  (re-export for scripts)
from .model import LogRegL2, ZScore, assert_config_locked, assert_search_ids, resample_training
from .postprocess import TaggedScores, hypothesis_mask, select_tau
from .scoring import Scorer, event_score
from .splits import assert_causal, assert_subject_disjoint
from .windows import assert_buffer, buffer_keep, window_labels_from_mask, window_starts

FA_TARGET = LOCKED_CONFIG["tau_rule"]["fa_target_per_24h"]


# ------------------------------------------------------------------ training labels (possibly transformed for NC1/NC2)
class TrainLabels:
    """Training 1-Hz masks + window labels, read from the vault (training files only), optionally transformed:
    mode 'true' | 'nc1_perm' (i.i.d. permutation of all training window labels) | 'nc2_shift' (circular shift of each
    training file's 1-Hz mask by U{600..T-600})."""

    def __init__(self, vault, train_recs, mode="true", rng=None):
        self.mask, self.wl = {}, {}
        for r in train_recs:
            self.mask[r.name] = vault.train_mask(r.name)
        if mode == "true":
            for f, m in self.mask.items():
                self.wl[f] = window_labels_from_mask(m)
        elif mode == "nc2_shift":
            for r in train_recs:
                T = r.duration
                off = int(rng.integers(600, T - 600 + 1))
                self.mask[r.name] = np.roll(self.mask[r.name], off)
                self.wl[r.name] = window_labels_from_mask(self.mask[r.name])
        elif mode == "nc1_perm":
            names = [r.name for r in train_recs]
            wl = [window_labels_from_mask(self.mask[f]) for f in names]
            cat = rng.permutation(np.concatenate(wl))
            o = 0
            for f, w in zip(names, wl):
                self.wl[f] = cat[o:o + w.size].astype(np.int8)
                m = np.zeros(w.size + 1, dtype=np.int8)
                m[:w.size] = self.wl[f]              # second j ictal iff window j labelled 1 (DEVIATIONS D9)
                self.mask[f] = m
                o += w.size
        else:
            raise ValueError(mode)


def _stack(feats, parts):
    """parts: list of (file, index array). Returns X (float32 view-stack) and ids dict."""
    X = np.concatenate([feats[f][i] for f, i in parts], axis=0)
    ids = {}
    for f, i in parts:
        ids[f] = np.concatenate([ids[f], i]) if f in ids else np.asarray(i)
    return X, ids


def fit(feats, labels, parts, allow_leak_norm_parts=None):
    """Fit z-score + L2-LR on the given training window parts. allow_leak_norm_parts = the C2b control only."""
    X, ids = _stack(feats, parts)
    y = np.concatenate([labels(f, i) for f, i in parts])
    norm = ZScore()
    if allow_leak_norm_parts is not None:
        Xn, idn = _stack(feats, allow_leak_norm_parts)
        norm.fit(Xn, idn)
    else:
        norm.fit(X, ids)
    Z = norm.transform_training(X)
    lr = LogRegL2(C=LOCKED_CONFIG["classifier"]["C"]).fit(Z, y)
    return norm, lr


def predict(model, feats, parts, allow_leak=False):
    norm, lr = model
    out = {}
    for f, i in parts:
        Z = norm.transform(feats[f][i], {f: np.asarray(i)}, allow_leak=allow_leak)
        out[f] = lr.predict_proba(Z)
    return out


def _all(rec):
    return np.arange(window_starts(rec.duration).size)


def run_split(split, feats, vault, groups, label_mode="true", rng=None, purpose="N2", scorer=None):
    """groups: list of lists of training FileRecords used as inner-CV folds (files, or subjects for S-a)."""
    assert_config_locked(LOCKED_CONFIG)
    if split.kind == "causal":
        assert_causal(split)
    if split.kind == "cross_patient":
        assert_subject_disjoint({r.subject for r in split.train}, {r.subject for r in split.test})
    assert_search_ids(split.train_names, split.test_names)
    TL = TrainLabels(vault, split.train, label_mode, rng)
    lab = lambda f, i: TL.wl[f][i]  # noqa: E731

    keep = {}
    n_drop = 0
    for r in split.train:
        k, d = buffer_keep(r, split.test)
        keep[r.name] = np.flatnonzero(k)
        n_drop += d
    assert_buffer([(r.subject, keep[r.name] + r.t_start, keep[r.name] + r.t_start + 2) for r in split.train], split.test)
    # F5: N2 uses no resampling; the guard is still exercised on the real run with an identity resample (factor 1).
    resample_training({f: v for f, v in keep.items()}, split.train_names, None, factor=1)

    # inner CV -> train_oof
    oof, conv = {}, []
    for g in groups:
        gn = {r.name for r in g}
        tr_parts = [(r.name, keep[r.name]) for r in split.train if r.name not in gn]
        m = fit(feats, lab, tr_parts)
        conv.append(m[1].converged_)
        oof.update(predict(m, feats, [(r.name, _all(r)) for r in g]))
    durs = {r.name: r.duration for r in split.train}
    tagged = TaggedScores("train_oof", oof, durs)

    def fa_of_masks(masks):
        fp = sum(event_score(TL.mask[f], masks[f])["fp"] for f in masks)
        return 24.0 * fp / (sum(durs[f] for f in masks) / 3600.0)
    tau, curve = select_tau(tagged, fa_of_masks, FA_TARGET)

    final = fit(feats, lab, [(r.name, keep[r.name]) for r in split.train])
    conv.append(final[1].converged_)
    p = predict(final, feats, [(r.name, _all(r)) for r in split.test])
    hyp = {r.name: hypothesis_mask(p[r.name], tau, r.duration) for r in split.test}
    sc = scorer or Scorer(vault, purpose)
    per_file = {r.name: sc.score_file(r.name, hyp[r.name]) for r in split.test}
    ylab = {r.name: sc.ref_window_labels(r.name) for r in split.test}
    return {"tau": tau, "tau_curve_len": len(curve), "train_oof_fa_at_tau": curve[-1][1] if curve else None,
            "p": p, "hyp": hyp, "per_file": per_file, "ywin": ylab, "n_buffer_dropped": n_drop,
            "converged_all": bool(all(conv)), "n_fits": len(conv),
            "n_train_windows": int(sum(v.size for v in keep.values())),
            "n_train_pos": int(sum(int(TL.wl[f][keep[f]].sum()) for f in keep)),
            "iters_final": final[1].n_iter_}


def summarize(res, test_recs, rng_boot=None, B=10000):
    """Per-subject metrics summed over test files (N2 §3)."""
    pf = res["per_file"]
    tp = sum(v["tp"] for v in pf.values())
    fp = sum(v["fp"] for v in pf.values())
    nref = sum(v["n_ref"] for v in pf.values())
    H = sum(v["dur_s"] for v in pf.values()) / 3600.0
    lat = [x for v in pf.values() for x in v["latencies"]]
    ind = [x for v in pf.values() for x in v["tp_indicators"]]
    stp = sum(v["s_tp"] for v in pf.values())
    sfp = sum(v["s_fp"] for v in pf.values())
    snr = sum(v["s_nref"] for v in pf.values())
    names = [r.name for r in test_recs]
    y = np.concatenate([res["ywin"][f] for f in names])
    s = np.concatenate([res["p"][f] for f in names])
    out = {
        "tp": tp, "fp": fp, "n_ref": nref, "hours": H, "tau": res["tau"],
        "sensitivity": tp / nref if nref else float("nan"),
        "fa_per_24h": 24.0 * fp / H,
        "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
        "f1": 2 * tp / (2 * tp + fp + (nref - tp)) if (2 * tp + fp + nref - tp) else float("nan"),
        "latency_s": lat,
        "latency_median": float(np.median(lat)) if lat else float("nan"),
        "latency_iqr": [float(np.percentile(lat, 25)), float(np.percentile(lat, 75))] if lat else [float("nan")] * 2,
        "latency_frac_le_10s": float(np.mean(np.asarray(lat) <= 10)) if lat else float("nan"),
        "sample_sensitivity": stp / snr if snr else float("nan"),
        "sample_precision": stp / (stp + sfp) if (stp + sfp) else float("nan"),
        "sample_f1": 2 * stp / (2 * stp + sfp + (snr - stp)) if snr + sfp else float("nan"),
        "window_auroc": stats.auroc(y, s), "window_auprc": stats.auprc(y, s),
        "prevalence": float(y.mean()), "n_test_windows": int(y.size), "n_pos_windows": int(y.sum()),
        "scores_complete": bool(all(res["p"][f].size == r.duration - 1 for f, r in zip(names, test_recs))),
        "per_file": {f: {k: v for k, v in pf[f].items()} for f in names},
    }
    out["sens_ci_clopper_pearson"] = list(stats.clopper_pearson(tp, nref))
    g = stats.garwood(fp)
    out["fa_ci_garwood_per_24h"] = [24.0 * g[0] / H, 24.0 * g[1] / H]
    if rng_boot is not None:
        out["sens_ci_bootstrap_by_event"] = list(stats.bootstrap_indicators(ind, rng_boot, B))
        ci, nnan = stats.block_bootstrap_auroc([res["ywin"][f] for f in names], [res["p"][f] for f in names], rng_boot, B)
        out["auroc_ci_block_bootstrap_files"] = list(ci)
        out["auroc_bootstrap_nan_draws"] = nnan
    return out


# ------------------------------------------------------------------ N1 (a) leaky arms
def leak_random_split(recs, feats, annotations, p_train, rng):
    """C2a: window-level random split over all files of one subject (allow_random_split=True)."""
    from .labels import LabelVault
    from .splits import random_window_split
    nwin = {r.name: window_starts(r.duration).size for r in recs}
    is_tr = random_window_split(nwin, p_train, rng, allow_random_split=True)
    vault = LabelVault(annotations, {r.name: r.duration for r in recs},
                       protected_windows={f: ~m for f, m in is_tr.items()}, name="C2a")
    tr_parts = [(f, np.flatnonzero(m)) for f, m in is_tr.items()]
    te_parts = [(f, np.flatnonzero(~m)) for f, m in is_tr.items()]
    lab = lambda f, i: vault.train_window_labels(f, i)  # noqa: E731
    model = fit(feats, lab, tr_parts)
    p = predict(model, feats, te_parts)
    sc = Scorer(vault, "N1a-C2a")
    y = np.concatenate([sc.ref_window_labels(f)[i] for f, i in te_parts])
    s = np.concatenate([p[f] for f, _ in te_parts])
    return {"auroc": stats.auroc(y, s), "n_train": int(sum(i.size for _, i in tr_parts)),
            "n_test": int(y.size), "converged": model[1].converged_, "vault": vault.summary()}


def leak_normaliser(split, feats, vault):
    """C2b: honest split, z-score fitted on train + test windows (descriptive)."""
    TL = TrainLabels(vault, split.train, "true")
    lab = lambda f, i: TL.wl[f][i]  # noqa: E731
    keep = {r.name: np.flatnonzero(buffer_keep(r, split.test)[0]) for r in split.train}
    tr_parts = [(r.name, keep[r.name]) for r in split.train]
    te_parts = [(r.name, _all(r)) for r in split.test]
    model = fit(feats, lab, tr_parts, allow_leak_norm_parts=tr_parts + te_parts)
    p = predict(model, feats, te_parts, allow_leak=True)
    sc = Scorer(vault, "N1a-C2b")
    y = np.concatenate([sc.ref_window_labels(f) for f, _ in te_parts])
    s = np.concatenate([p[f] for f, _ in te_parts])
    return {"auroc": stats.auroc(y, s)}


def pooled_f1(tp, fp, nref):
    d = 2 * tp + fp + (nref - tp)
    return 2 * tp / d if d else float("nan")


__all__ = ["run_split", "summarize", "leak_random_split", "leak_normaliser", "TrainLabels", "pooled_f1", "guard_hit"]
