"""NC-P phantom-seizure negative control (prereg §2.2-2.4) and the planted leaks PL-A / PL-B (§4).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
One replicate = training phantoms (stream 10) -> nfharness.pipeline.run_split UNCHANGED on the pseudo-records (with a
DeferredScorer, so no test label exists or is read during the fit) -> t_rm from the captured train-OOF scores ->
hypotheses -> SHA-256(s, h) + degeneracy decision logged -> test phantoms (stream 11) sealed into the PhantomVault ->
observed T_A / T_E through nfharness Scorer -> M = 999 fresh placements (stream 12) -> exact p-values.
"""
import math

import numpy as np
from scipy.stats import chi2, rankdata

from nfharness import stats
from nfharness.config import TAU_GRID
from nfharness.data import FileRecord
from nfharness.labels import mask_from_events
from nfharness.pipeline import run_split
from nfharness.postprocess import assert_tau, hypothesis_mask
from nfharness.scoring import Scorer, mask_events, merge_events, reimpl_event_score, split_events
from nfharness.splits import Split
from nfharness.windows import window_labels_from_mask

from . import K_NULL, K_PLA, K_TEST_PH, K_TRAIN_PH, rng
from .sampler import place_with_redraw, placement_order, to_annotations
from .vault import DeferredScorer, OrderLog, PhantomVault, capture_select_tau, require_flag, sha_scores_hyps

M_NULL = 999
RATE_TARGET = 1.323          # scored events per hour of allowed training time (prereg §2.4, literal)
ALWAYS_FRAC = 0.5
SD_MIN = 1e-6
PL_A_FRAC = 0.25
ALPHA_FISHER = 0.0025
MERGE_S, SPLIT_S = 90, 300


def n_events(mask):
    """Hypothesis events after the 90-s merge and 300-s split (label-free)."""
    st, en = split_events(*merge_events(*mask_events(mask), MERGE_S), SPLIT_S)
    return int(st.size)


def rate_matched_tau(oof, target=RATE_TARGET):
    """t_rm = smallest grid tau whose train-OOF hypothesis has <= target events/h of allowed training time.
    Returns (t_rm, flagged_no_tau_qualified, rate_at_t_rm)."""
    files = list(oof.scores)
    H = sum(oof.durations[f] for f in files) / 3600.0
    rate = None
    for tau in TAU_GRID:
        n = sum(n_events(hypothesis_mask(oof.scores[f], tau, oof.durations[f])) for f in files)
        rate = n / H
        if rate <= target:
            assert_tau(tau)
            return tau, False, rate
    return 0.99, True, rate


def degeneracy(h, names, lens):
    cov = sum(int(np.asarray(h[f]).sum()) for f in names) / float(sum(lens))
    nev = sum(n_events(h[f]) for f in names)
    return {"coverage": cov, "n_events": nev, "always_alarm": bool(cov >= ALWAYS_FRAC), "never_alarm": bool(nev == 0),
            "degenerate": bool(cov >= ALWAYS_FRAC or nev == 0)}


def f1_of(tp, fp, nref):
    d = 2 * tp + fp + (nref - tp)
    return 2 * tp / d if d else 0.0


def pvals(obs, null):
    M = null.size
    return (1 + int(np.sum(null >= obs))) / (M + 1), (1 + int(np.sum(null <= obs))) / (M + 1)


def fisher(ps):
    ps = [float(p) for p in ps if p == p]
    n = len(ps)
    if n == 0:
        return float("nan"), 0
    X = -2.0 * sum(math.log(p) for p in ps)
    return float(chi2.sf(X, 2 * n)), n


class ScoreSide:
    """Concatenated test scores over the test pseudo-records (allowed windows only) with precomputed ranks."""

    def __init__(self, recs, p):
        self.names = [r.name for r in recs]
        self.lens = [int(r.duration) for r in recs]
        nw = np.array([L - 1 for L in self.lens], dtype=np.int64)
        self.off = np.concatenate([[0], np.cumsum(nw)])[:-1]
        self.s = np.concatenate([np.asarray(p[f], dtype=np.float64) for f in self.names])
        self.ranks = rankdata(self.s)
        self.N = self.s.size

    def pos_index(self, placement):
        idx = np.concatenate([self.off[j] + np.arange(o, o + d - 1) for j, o, d in placement])
        idx.sort()
        return idx

    def auroc(self, placement):
        """Mann-Whitney AUROC (average ranks), identical formula and summation order to nfharness.stats.auroc."""
        idx = self.pos_index(placement)
        n1 = idx.size
        n0 = self.N - n1
        return float((self.ranks[idx].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


class EventArm:
    """Event F1 of a FIXED hypothesis against phantom references, via the validated re-implementation scorer."""

    def __init__(self, ts, hyp):
        self.ts = ts
        self.h = [np.asarray(hyp[f], dtype=np.int8) for f in ts.names]
        self.fp0 = [reimpl_event_score(np.zeros(L, np.int8), h)["fp"] for L, h in zip(ts.lens, self.h)]

    def score(self, placement):
        by = {}
        for j, o, d in placement:
            by.setdefault(j, []).append((o, o + d))
        TP = FP = NR = 0
        for j in range(len(self.h)):
            if j in by:
                e = reimpl_event_score(mask_from_events(by[j], self.ts.lens[j]), self.h[j])
                TP, FP, NR = TP + e["tp"], FP + e["fp"], NR + e["n_ref"]
            else:
                FP += self.fp0[j]
        return f1_of(TP, FP, NR), TP, FP, NR


def null_draws(ts, arms, seg_lengths, dur_order, g, M=M_NULL):
    TA = np.empty(M)
    TE = {a: np.empty(M) for a in arms}
    redraws = 0
    for m in range(M):
        pl, n = place_with_redraw(seg_lengths, dur_order, g)
        redraws += n
        TA[m] = ts.auroc(pl)
        for a, arm in arms.items():
            TE[a][m] = arm.score(pl)[0]
    return TA, TE, redraws


# ------------------------------------------------------------------------------------------------- PL-A (planted)
def plant_label_leak(sp, feats, test_ann, g13, allow_planted_leak=False):
    """PL-A: floor(25%) of the subject's allowed test windows (uniform without replacement, stream 13) become 1-window
    TRAINING pseudo-records carrying their PHANTOM test labels (DEVIATIONS N1b-5). They enter the training set, the
    inner-CV training folds and the normaliser fit; the test pseudo-records are unchanged and still scored."""
    require_flag(allow_planted_leak, "PL-A plant_label_leak")
    te = sp.split.test
    nw = np.array([r.duration - 1 for r in te], dtype=np.int64)
    off = np.concatenate([[0], np.cumsum(nw)])
    N = int(off[-1])
    k = int(math.floor(PL_A_FRAC * N))
    sel = np.sort(g13.choice(N, size=k, replace=False))
    wl = {r.name: window_labels_from_mask(mask_from_events(test_ann[r.name], r.duration)) for r in te}
    recs, fx, ann = [], {}, {}
    npos = 0
    for n, gi in enumerate(sel.tolist()):
        j = int(np.searchsorted(off, gi, side="right") - 1)
        i = gi - int(off[j])
        r = te[j]
        name = "PLA|%s|w%d" % (r.name, i)
        recs.append(FileRecord(r.subject, name, "<planted PL-A>", -1.0e7 + 10.0 * n, 2))
        fx[name] = feats[r.name][i:i + 1]
        lab = int(wl[r.name][i])
        npos += lab
        ann[name] = [(0, 2)] if lab else []
    return recs, fx, ann, {"n_test_windows": N, "n_leak_windows": k, "n_leak_positive": npos,
                           "n_test_positive": int(sum(int(v.sum()) for v in wl.values()))}


def draw_train_phantoms(sp, tr_len, g, max_redraws=10000):
    """Sampler S for the TRAINING phantoms, redrawn (same generator, counted) until the phantoms lie in >= 2 different
    original training files, so that every inner-LOFO training fold contains a positive (DEVIATIONS N1b-15). This
    conditions only the training phantoms; the test phantoms and the null draws are unaffected (exactness holds)."""
    group_of = {r.name: gi for gi, grp in enumerate(sp.groups) for r in grp}
    names = [r.name for r in sp.split.train]
    order = placement_order(sp.train_seizure_durations)
    rd_total, n_lofo = 0, 0
    for _ in range(max_redraws):
        pl, rd = place_with_redraw(tr_len, order, g)
        rd_total += rd
        if len(sp.groups) < 2 or len({group_of[names[j]] for j, _, _ in pl}) >= 2:
            return pl, rd_total, n_lofo
        n_lofo += 1
    raise RuntimeError("no LOFO-feasible training phantom placement")


# ------------------------------------------------------------------------------------------------- one replicate
def run_replicate(sp, feats, rep, key_prefix=(), plant=None, allow_planted_leak=False, M=M_NULL):
    """Returns (public result dict for the card, private objects for PL-B)."""
    si = sp.subject_index
    log = OrderLog()
    split = sp.split
    tr, te = list(split.train), list(split.test)
    tr_names, te_names = [r.name for r in tr], [r.name for r in te]
    tr_len, te_len = [r.duration for r in tr], [r.duration for r in te]
    durs = {r.name: r.duration for r in tr + te}
    te_order = placement_order(sp.test_seizure_durations)
    tag = "%s-%s-r%d" % (plant or "NC-P", sp.subject, rep)

    g10 = rng(*key_prefix, K_TRAIN_PH, si, rep)
    pl_tr, rd_tr, rd_lofo = draw_train_phantoms(sp, tr_len, g10)
    train_ann = to_annotations(pl_tr, tr_names)
    log.add("draw_train_phantoms", "stream=%d redraws=%d lofo_redraws=%d" % (K_TRAIN_PH, rd_tr, rd_lofo))
    g11 = rng(*key_prefix, K_TEST_PH, si, rep)

    feats_run, leak_recs, leak_info, pl_te, rd_te = feats, [], None, None, None
    if plant is not None:
        if plant != "PL-A":
            raise ValueError(plant)
        require_flag(allow_planted_leak, "PL-A")
        pl_te, rd_te = place_with_redraw(te_len, te_order, g11)
        test_ann = to_annotations(pl_te, te_names)
        log.add("PLANTED_draw_test_phantoms_before_fit", "stream=%d redraws=%d" % (K_TEST_PH, rd_te))
        g13 = rng(*key_prefix, K_PLA, si, rep)
        leak_recs, lfx, lann, leak_info = plant_label_leak(sp, feats, test_ann, g13, allow_planted_leak=True)
        log.add("PLANTED_PL-A_leak_records", "n=%d stream=%d" % (len(leak_recs), K_PLA))
        feats_run = dict(feats)
        feats_run.update(lfx)
        train_ann = dict(train_ann)
        train_ann.update(lann)
        durs.update({r.name: r.duration for r in leak_recs})
    vault = PhantomVault(train_ann, durs, te_names, "N1b-" + tag, log)
    if plant is not None:
        vault.seal_test_phantoms(test_ann, "PL-A: sealed BEFORE the fit (planted leak)")

    run_sp = Split("causal", tr + leak_recs, te, label="N1b-" + tag)
    with capture_select_tau() as box:
        res = run_split(run_sp, feats_run, vault, sp.groups, purpose="N1b " + tag, scorer=DeferredScorer())
    if len(box) != 1:
        raise RuntimeError("expected exactly one select_tau call, got %d" % len(box))
    oof, (tau_locked, curve) = box[0]
    if tau_locked != res["tau"]:
        raise RuntimeError("captured tau differs from run_split tau")
    log.add("fit_run_split", "tau_locked=%r" % res["tau"])
    t_rm, rm_flag, rm_rate = rate_matched_tau(oof)
    p = res["p"]
    h_rm = {f: hypothesis_mask(p[f], t_rm, durs[f]) for f in te_names}
    h_lk = res["hyp"]
    deg_rm = degeneracy(h_rm, te_names, te_len)
    deg_lk = degeneracy(h_lk, te_names, te_len)
    sd = float(np.std(np.concatenate([p[f] for f in te_names])))
    win_flag = bool(sd < SD_MIN)
    sha = sha_scores_hyps(te_names, p, [h_rm, h_lk])
    log.add("hash_scores_hyps", sha)
    log.add("degeneracy_decided", "rm=%s locked=%s window_flag=%s" % (deg_rm["degenerate"], deg_lk["degenerate"], win_flag))

    if plant is None:
        pl_te, rd_te = place_with_redraw(te_len, te_order, g11)
        test_ann = to_annotations(pl_te, te_names)
        log.add("draw_test_phantoms", "stream=%d redraws=%d" % (K_TEST_PH, rd_te))
        vault.seal_test_phantoms(test_ann)

    # ---- observed statistics (harness Scorer = the only reader of test phantoms)
    sc = Scorer(vault, "N1b " + tag)
    y = np.concatenate([sc.ref_window_labels(f) for f in te_names])
    ts = ScoreSide(te, p)
    TA = ts.auroc(pl_te)
    TA_stats = stats.auroc(y, ts.s)
    if not (abs(TA - TA_stats) <= 1e-12 or (TA != TA and TA_stats != TA_stats)):
        raise RuntimeError("rank AUROC %r != nfharness.stats.auroc %r" % (TA, TA_stats))
    arms = {"rm": EventArm(ts, h_rm), "locked": EventArm(ts, h_lk)}
    obs = {}
    for a, h in (("rm", h_rm), ("locked", h_lk)):
        e = [sc.score_file(f, h[f]) for f in te_names]
        tp, fp, nr = sum(x["tp"] for x in e), sum(x["fp"] for x in e), sum(x["n_ref"] for x in e)
        f1r, tpr, fpr, nrr = arms[a].score(pl_te)
        if (tp, fp, nr) != (tpr, fpr, nrr):
            raise RuntimeError("timescoring (%d,%d,%d) != re-implementation (%d,%d,%d)" % (tp, fp, nr, tpr, fpr, nrr))
        obs[a] = {"T_E": f1_of(tp, fp, nr), "tp": tp, "fp": fp, "n_ref": nr}
    log.add("score_observed", "scorer_reads=%d" % vault.summary()["test"]["scorer_reads"])

    g12 = rng(*key_prefix, K_NULL, si, rep)
    TAn, TEn, rd_null = null_draws(ts, arms, te_len, te_order, g12, M)
    log.add("null_draws", "stream=%d M=%d redraws=%d" % (K_NULL, M, rd_null))
    pa_up, pa_lo = pvals(TA, TAn)
    out = {"subject": sp.subject, "replicate": rep, "plant": plant,
           "redraws": {"train": rd_tr, "train_lofo": rd_lofo, "test": rd_te, "null": rd_null},
           "tau_locked": res["tau"], "locked_curve_len": len(curve), "t_rm": t_rm, "t_rm_flag_no_tau": rm_flag,
           "t_rm_train_oof_rate_per_h": rm_rate, "sd_scores": sd, "window_flag_sd": win_flag,
           "degeneracy_rm": deg_rm, "degeneracy_locked": deg_lk, "sha256_scores_hyps": sha,
           "T_A": TA, "T_A_null_mean": float(TAn.mean()), "T_A_null_sd": float(TAn.std()),
           "p_A_up": pa_up, "p_A_lo": pa_lo, "n_pos_windows": int(y.sum()), "n_test_windows": int(y.size),
           "converged_all": res["converged_all"], "n_fits": res["n_fits"], "n_train_windows": res["n_train_windows"],
           "n_train_pos_windows": res["n_train_pos"], "n_buffer_dropped": res["n_buffer_dropped"],
           "leak": leak_info, "order_log": log.events, "vault": vault.summary()}
    for a in arms:
        pu, pl = pvals(obs[a]["T_E"], TEn[a])
        out["E_" + a] = dict(obs[a], T_E_null_mean=float(TEn[a].mean()), p_up=pu, p_lo=pl)
    if plant is None:
        out["order_ok"] = bool(log.index("hash_scores_hyps") < log.index("draw_test_phantoms")
                               < log.index("seal_test_phantoms") < log.index("score_observed"))
    else:
        out["order_ok"] = None     # planted leak: test phantoms exist before the fit by design
    priv = {"p": p, "ts": ts, "pl_te": pl_te, "te_len": te_len, "te_order": te_order, "durs": durs, "TAn": TAn,
            "si": si, "rep": rep, "key_prefix": key_prefix, "sp": sp}
    return out, priv


# ------------------------------------------------------------------------------------------------- PL-B (planted)
def planted_threshold_leak(priv, pub, allow_planted_leak=False, M=M_NULL):
    """PL-B on one NC-P fit: tau = argmax over the locked grid of the subject's event F1 against the TEST phantoms
    (ties -> smallest tau); the F3 train_oof-only rule is bypassed on purpose (select_tau is not used). No refit.
    The control then judges this h exactly as in NC-P (same stream-12 key, so T_A is unchanged)."""
    require_flag(allow_planted_leak, "PL-B planted_threshold_leak")
    ts, pl_te, durs = priv["ts"], priv["pl_te"], priv["durs"]
    best_tau, best = None, -1.0
    for tau in TAU_GRID:
        h = {f: hypothesis_mask(priv["p"][f], tau, durs[f]) for f in ts.names}
        f1 = EventArm(ts, h).score(pl_te)[0]
        if f1 > best:
            best_tau, best = tau, f1
    assert_tau(best_tau)
    h = {f: hypothesis_mask(priv["p"][f], best_tau, durs[f]) for f in ts.names}
    deg = degeneracy(h, ts.names, priv["te_len"])
    arm = EventArm(ts, h)
    f1, tp, fp, nr = arm.score(pl_te)
    g12 = rng(*priv["key_prefix"], K_NULL, priv["si"], priv["rep"])
    TAn, TEn, _ = null_draws(ts, {"plb": arm}, priv["te_len"], priv["te_order"], g12, M)
    TA = ts.auroc(pl_te)
    pa_up, pa_lo = pvals(TA, TAn)
    pu, pl = pvals(f1, TEn["plb"])
    return {"subject": pub["subject"], "replicate": pub["replicate"], "tau_test_optimal": best_tau, "T_E": f1, "tp": tp,
            "fp": fp, "n_ref": nr, "T_E_null_mean": float(TEn["plb"].mean()), "p_up": pu, "p_lo": pl,
            "degeneracy": deg, "p_A_up": pa_up, "p_A_lo": pa_lo,
            "T_A_pvalues_identical_to_NCP": bool(pa_up == pub["p_A_up"] and pa_lo == pub["p_A_lo"]
                                                 and np.array_equal(TAn, priv["TAn"]))}


# ------------------------------------------------------------------------------------------------- aggregation
def aggregate(reps):
    """Fisher combinations and V1/V2 over NC-P (or PL-A) replicates (t_rm arm is the gate arm)."""
    ev = [r for r in reps if not r["degeneracy_rm"]["degenerate"]]
    wa = [r for r in reps if not r["window_flag_sd"]]
    fA_up, nA = fisher([r["p_A_up"] for r in wa])
    fA_lo, _ = fisher([r["p_A_lo"] for r in wa])
    fE_up, nE = fisher([r["E_rm"]["p_up"] for r in ev])
    fE_lo, _ = fisher([r["E_rm"]["p_lo"] for r in ev])
    lk = [r for r in reps if not r["degeneracy_locked"]["degenerate"]]
    fL_up, nL = fisher([r["E_locked"]["p_up"] for r in lk])
    fL_lo, _ = fisher([r["E_locked"]["p_lo"] for r in lk])
    n_deg = len(reps) - len(ev)
    n_wflag = len(reps) - len(wa)
    tpE = sum(r["E_rm"]["tp"] for r in reps)
    fpE = sum(r["E_rm"]["fp"] for r in reps)
    nrE = sum(r["E_rm"]["n_ref"] for r in reps)
    out = {"n_replicates": len(reps),
           "fisher": {"T_A_up": fA_up, "T_A_lo": fA_lo, "T_E_up": fE_up, "T_E_lo": fE_lo},
           "fisher_n": {"T_A": nA, "T_E": nE},
           "n_degenerate_event_arm": n_deg, "n_always_alarm": sum(r["degeneracy_rm"]["always_alarm"] for r in reps),
           "n_never_alarm": sum(r["degeneracy_rm"]["never_alarm"] for r in reps), "n_window_flagged": n_wflag,
           "n_t_rm_flag_0.99": sum(bool(r["t_rm_flag_no_tau"]) for r in reps),
           "T_A_mean": float(np.mean([r["T_A"] for r in reps])), "T_A_sd": float(np.std([r["T_A"] for r in reps], ddof=1)) if len(reps) > 1 else float("nan"),
           "T_A_subject_means": {s: float(np.mean([r["T_A"] for r in reps if r["subject"] == s]))
                                 for s in sorted({r["subject"] for r in reps})},
           "T_A_null_mean_mean": float(np.mean([r["T_A_null_mean"] for r in reps])),
           "T_E_rm_mean": float(np.mean([r["E_rm"]["T_E"] for r in reps])),
           "T_E_rm_pooled_f1": f1_of(tpE, fpE, nrE), "T_E_rm_pooled_tp_fp_nref": [tpE, fpE, nrE],
           "T_E_rm_null_mean_mean": float(np.mean([r["E_rm"]["T_E_null_mean"] for r in reps])),
           "t_rm_values": [r["t_rm"] for r in reps],
           "locked_arm_descriptive": {"fisher_up": fL_up, "fisher_lo": fL_lo, "n_retained": nL,
                                      "n_degenerate": len(reps) - len(lk),
                                      "n_never_alarm": sum(r["degeneracy_locked"]["never_alarm"] for r in reps),
                                      "n_always_alarm": sum(r["degeneracy_locked"]["always_alarm"] for r in reps),
                                      "tau_locked_values": [r["tau_locked"] for r in reps],
                                      "T_E_mean": float(np.mean([r["E_locked"]["T_E"] for r in reps]))},
           "all_order_ok": all(r["order_ok"] is not False for r in reps),
           "all_converged": all(r["converged_all"] for r in reps),
           "total_redraws": {k: sum(r["redraws"][k] or 0 for r in reps) for k in ("train", "train_lofo", "test", "null")}}
    fs = [fA_up, fA_lo, fE_up, fE_lo]
    out["V1"] = bool(all(f == f and f >= ALPHA_FISHER for f in fs))
    out["V2"] = bool(n_deg <= 10 * len(reps) / 30.0 and n_wflag <= 3 * len(reps) / 30.0)
    return out
