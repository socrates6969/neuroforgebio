"""N1b tests (prereg §4, §5.1): planted-leak flag guard, sampler S exact enumeration on a hand fixture, order log,
PhantomVault access rules, observational select_tau hook, exact-null helpers, C3' exact pmf vs brute force.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Synthetic in-memory data only (stream key (99, ...)).
"""
import itertools
import math

import numpy as np
import pytest

from nfharness import stats
from nfharness.config import TAU_GRID
from nfharness.data import FileRecord
from nfharness.errors import TestLabelAccessError as LabelAccessError
from nfharness.labels import _SCORER_KEY, mask_from_events
from nfharness.pipeline import run_split
from nfharness.postprocess import TaggedScores
from nfharness.scoring import event_score, reimpl_event_score
from nfharness.splits import Split

from n1b import rng as nrng
from n1b.c3prime import exact_distribution, file_counts, harness_mc
from n1b.ncp import (EventArm, ScoreSide, f1_of, fisher, n_events, planted_threshold_leak, plant_label_leak, pvals,
                     rate_matched_tau, run_replicate)
from n1b.sampler import place, placement_order, to_annotations, valid_onsets, valid_set
from n1b.segments import allowed_segments, build_pseudo
from n1b.vault import DeferredScorer, OrderLog, PhantomVault, PlantedLeakFlagError, capture_select_tau

T = 3000
SEIZ = {0: [], 1: [(400, 450)], 2: [(2400, 2440)], 3: [(1000, 1060)], 4: [(2000, 2050)]}


@pytest.fixture(scope="module")
def fx():
    """5 files x 3000 s (7-s gaps); train = files 0-3 (3 seizures), test = file 4 (1 seizure). Seizure windows are
    shifted +3 SD in every 6th feature; background is white noise."""
    g = nrng(99, 0)
    recs, ann, feats = [], {}, {}
    t = 0.0
    for i in range(5):
        n = "fx_%02d.edf" % i
        recs.append(FileRecord("fx", n, "<memory>", t, T))
        t += T + 7
        ann[n] = SEIZ[i]
        X = g.standard_normal((T - 1, 132)).astype(np.float32)
        for on, off in SEIZ[i]:
            X[on:off - 1, ::6] += 3.0
        feats[n] = X
    split = Split("causal", recs[:4], recs[4:], label="fx")
    sp, pf = build_pseudo(split, ann, feats, 0)
    allf = dict(feats)
    allf.update(pf)
    return {"sp": sp, "feats": allf, "split": split, "ann": ann}


# ------------------------------------------------------------------------------------------------ segments
def test_allowed_segments_hand():
    assert allowed_segments(3000, []) == [(0, 3000)]
    assert allowed_segments(3000, [(400, 450)]) == [(1350, 3000)]
    assert allowed_segments(3000, [(1000, 1060)]) == [(0, 400), (1960, 3000)]
    assert allowed_segments(3000, [(700, 710), (2000, 2010)]) == [(0, 100), (2910, 3000)]
    assert allowed_segments(3000, [(100, 200), (2800, 2900)]) == [(1100, 2200)]


def test_pseudo_records_and_feature_slices(fx):
    sp = fx["sp"]
    names = [r.name for r in sp.split.train + sp.split.test]
    assert names == ["fx_00.edf[0:3000]", "fx_01.edf[1350:3000]", "fx_02.edf[0:1800]", "fx_03.edf[0:400]",
                     "fx_03.edf[1960:3000]", "fx_04.edf[0:1400]", "fx_04.edf[2950:3000]"]
    assert [len(g) for g in sp.groups] == [1, 1, 1, 2]
    r = sp.split.train[1]
    assert r.t_start == 3007 + 1350 and r.duration == 1650
    assert np.array_equal(fx["feats"][r.name], fx["feats"]["fx_01.edf"][1350:2999])
    assert fx["feats"][r.name].shape[0] == r.duration - 1
    assert [d for d, _, _ in sp.train_seizure_durations] == [50, 40, 60]
    assert placement_order(sp.train_seizure_durations) == [60, 50, 40]


# ------------------------------------------------------------------------------------------------ sampler S
def test_sampler_enumerates_valid_set_exactly():
    """Hand fixture: segments of 200, 500 and 100 s."""
    S, O = valid_set([200, 500, 100], 50, {})
    assert list(zip(S.tolist(), O.tolist())) == [(0, o) for o in range(30, 91)] + [(1, o) for o in range(30, 391)]
    # after a 50-s phantom at onset 30 in segment 1, a 40-s phantom needs onset >= 380 there (gap 300) and <= 400
    S, O = valid_set([200, 500, 100], 40, {1: [(30, 50)]})
    assert list(zip(S.tolist(), O.tolist())) == [(0, o) for o in range(30, 101)] + [(1, o) for o in range(380, 401)]
    # a phantom placed at 250 (d 50) in a 1000-s segment forbids onsets (250-40-300, 250+50+300) = (-90, 600)
    assert valid_onsets(1000, 40, [(250, 50)]).tolist() == list(range(600, 901))
    assert valid_onsets(100, 50).size == 0


class _Pick:
    """Stub generator: integers(0, n) returns a fixed index (to check the enumeration -> placement mapping)."""

    def __init__(self, idx):
        self.idx = list(idx)

    def integers(self, lo, hi):
        i = self.idx.pop(0)
        assert lo == 0 and 0 <= i < hi
        return i


def test_sampler_mapping_and_empty():
    pl = place([200, 500, 100], [50, 40], _Pick([61, 0]))
    assert pl == [(1, 30, 50), (0, 30, 40)]
    assert place([100, 120], [50], _Pick([0])) is None
    ann = to_annotations(pl, ["a", "b", "c"])
    assert ann == {"a": [(30, 70)], "b": [(30, 80)], "c": []}


def test_train_phantoms_span_two_lofo_groups(fx):
    from n1b.ncp import draw_train_phantoms
    sp = fx["sp"]
    group_of = {r.name: gi for gi, grp in enumerate(sp.groups) for r in grp}
    names = [r.name for r in sp.split.train]
    g = nrng(99, 6)
    n_lofo = 0
    for _ in range(30):
        pl, _, k = draw_train_phantoms(sp, [r.duration for r in sp.split.train], g)
        n_lofo += k
        assert len({group_of[names[j]] for j, _, _ in pl}) >= 2


def test_sampler_uniform_over_valid_set():
    g = nrng(99, 1)
    cnt = np.zeros(61 + 361, dtype=int)
    for _ in range(20000):
        (j, o, d), = place([200, 500, 100], [50], g)
        cnt[(o - 30) if j == 0 else 61 + (o - 30)] += 1
    chi = ((cnt - cnt.mean()) ** 2 / cnt.mean()).sum()
    assert chi < 421 + 5 * math.sqrt(2 * 421)


# ------------------------------------------------------------------------------------------------ flag guard (S5 style)
def test_planted_leaks_refuse_without_flag(fx):
    sp, feats = fx["sp"], fx["feats"]
    with pytest.raises(PlantedLeakFlagError):
        run_replicate(sp, feats, 0, key_prefix=(99,), plant="PL-A", M=9)
    with pytest.raises(PlantedLeakFlagError):
        plant_label_leak(sp, feats, {r.name: [] for r in sp.split.test}, nrng(99, 2))
    pub, priv = run_replicate(sp, feats, 0, key_prefix=(99,), M=9)
    with pytest.raises(PlantedLeakFlagError):
        planted_threshold_leak(priv, pub)
    with pytest.raises(PlantedLeakFlagError):
        harness_mc([], {}, nrng(99, 3), 1, plant="PL-C")
    v = PhantomVault({}, {"a": 100, "b": 100}, ["b"], "t", OrderLog())
    v.seal_test_phantoms({"b": [(10, 20)]})
    with pytest.raises(PlantedLeakFlagError):
        v.release_test_labels()
    assert v.release_test_labels(allow_planted_leak=True)["b"].sum() == 10


def test_planted_leaks_run_with_flag(fx):
    pub, priv = run_replicate(fx["sp"], fx["feats"], 0, key_prefix=(99,), plant="PL-A", allow_planted_leak=True, M=9)
    assert pub["order_ok"] is None
    assert any("PLANTED_draw_test_phantoms_before_fit" in e for e in pub["order_log"])
    assert pub["leak"]["n_leak_windows"] == math.floor(0.25 * (1399 + 49))
    npub, npriv = run_replicate(fx["sp"], fx["feats"], 0, key_prefix=(99,), M=9)
    b = planted_threshold_leak(npriv, npub, allow_planted_leak=True, M=9)
    assert b["T_A_pvalues_identical_to_NCP"] and b["tau_test_optimal"] in TAU_GRID


# ------------------------------------------------------------------------------------------------ order log + vault
def test_order_log_and_vault_rules(fx):
    pub, _ = run_replicate(fx["sp"], fx["feats"], 1, key_prefix=(99,), M=19)
    ev = [e.split(" ", 2)[1] for e in pub["order_log"]]
    assert ev.index("hash_scores_hyps") < ev.index("draw_test_phantoms") < ev.index("seal_test_phantoms") < ev.index("score_observed")
    assert pub["order_ok"] is True
    assert pub["E_rm"]["n_ref"] == 1 and pub["n_pos_windows"] == 49
    v = PhantomVault({"a": [(5, 9)]}, {"a": 100, "b": 100}, ["b"], "t", OrderLog())
    with pytest.raises(LabelAccessError):
        v.scorer_mask("b", _SCORER_KEY, "early")           # test phantoms not drawn yet
    with pytest.raises(LabelAccessError):
        v.train_mask("b")                                   # test record protected from training code
    assert v.train_mask("a").sum() == 4
    v.seal_test_phantoms({"b": [(1, 3)]})
    with pytest.raises(LabelAccessError):
        v.scorer_mask("b", object(), "wrong key")
    assert v.scorer_mask("b", _SCORER_KEY, "ok").sum() == 2
    with pytest.raises(RuntimeError):
        v.seal_test_phantoms({"b": []})


def test_capture_hook_is_observational(fx):
    sp, feats = fx["sp"], fx["feats"]
    ann = {r.name: [] for r in sp.split.train + sp.split.test}
    ann[sp.split.train[0].name] = [(100, 150)]
    ann[sp.split.train[2].name] = [(200, 260)]
    durs = {r.name: r.duration for r in sp.split.train + sp.split.test}
    te = [r.name for r in sp.split.test]
    a = run_split(sp.split, feats, PhantomVault(ann, durs, te, "x", OrderLog()), sp.groups, scorer=DeferredScorer())
    with capture_select_tau() as box:
        b = run_split(sp.split, feats, PhantomVault(ann, durs, te, "y", OrderLog()), sp.groups, scorer=DeferredScorer())
    import nfharness.pipeline as P
    from nfharness.postprocess import select_tau
    assert P.select_tau is select_tau
    assert len(box) == 1 and box[0][0].tag == "train_oof" and box[0][1][0] == a["tau"] == b["tau"]
    assert all(np.array_equal(a["p"][f], b["p"][f]) for f in te)
    assert set(box[0][0].scores) == {r.name for r in sp.split.train}


# ------------------------------------------------------------------------------------------------ statistics helpers
def test_rank_auroc_equals_stats_auroc():
    g = nrng(99, 4)
    recs = [FileRecord("x", "r%d" % i, "", 0, L) for i, L in enumerate([400, 700, 300])]
    p = {r.name: np.round(g.random(r.duration - 1), 2) for r in recs}      # ties on purpose
    ts = ScoreSide(recs, p)
    for _ in range(20):
        pl = place([400, 700, 300], [60, 45], g)
        ann = to_annotations(pl, [r.name for r in recs])
        y = np.concatenate([(lambda m: (m[:-1] & m[1:]))(mask_from_events(ann[r.name], r.duration).astype(bool))
                            for r in recs])
        assert abs(ts.auroc(pl) - stats.auroc(y, ts.s)) <= 1e-12


def test_eventarm_equals_timescoring():
    g = nrng(99, 5)
    recs = [FileRecord("x", "r%d" % i, "", 0, L) for i, L in enumerate([1800, 2400])]
    for _ in range(15):
        hyp = {}
        for r in recs:
            m = np.zeros(r.duration, np.int8)
            for _k in range(int(g.integers(0, 6))):
                a = int(g.integers(0, r.duration - 50))
                m[a:a + int(g.integers(1, 50))] = 1
            hyp[r.name] = m
        ts = ScoreSide(recs, {r.name: np.zeros(r.duration - 1) for r in recs})
        pl = place([1800, 2400], [90, 50, 40], g)
        ann = to_annotations(pl, [r.name for r in recs])
        tp = fp = nr = 0
        for r in recs:
            e = event_score(mask_from_events(ann[r.name], r.duration), hyp[r.name])
            tp, fp, nr = tp + e["tp"], fp + e["fp"], nr + e["n_ref"]
        assert EventArm(ts, hyp).score(pl) == (f1_of(tp, fp, nr), tp, fp, nr)


def test_pvals_fisher_rate_tau():
    null = np.array([0.1, 0.2, 0.2, 0.3])
    assert pvals(0.2, null) == (4 / 5, 4 / 5)
    assert pvals(0.35, null) == (1 / 5, 1.0)
    assert abs(fisher([0.01])[0] - 0.01) < 1e-12 and fisher([1.0, 1.0])[0] == 1.0 and fisher([])[1] == 0
    # train-OOF: one 3600-s record; scores 0.9 in 3 bursts of 20 s -> 3 events/h at tau <= 0.9, 0 events above
    s = np.full(3599, 0.1)
    for a in (100, 1000, 2000):
        s[a:a + 20] = 0.9
    oof = TaggedScores("train_oof", {"f": s}, {"f": 3600})
    assert n_events(np.r_[0, (s >= 0.5).astype(np.int8)]) == 3
    t, flag, rate = rate_matched_tau(oof)
    assert (t, flag, rate) == (0.91, False, 0.0)
    t, flag, rate = rate_matched_tau(oof, target=3.0)
    assert (t, flag, rate) == (0.11, False, 3.0)


# ------------------------------------------------------------------------------------------------ C3' exact vs brute force
def test_c3_exact_equals_bruteforce():
    ref1 = mask_from_events([(60, 80)], 200)
    hyp1 = mask_from_events([(10, 15), (150, 170)], 200)
    ref2 = mask_from_events([], 150)
    hyp2 = mask_from_events([(40, 44)], 150)
    c = [file_counts(ref1, hyp1), file_counts(ref2, hyp2)]
    ex, pmf = exact_distribution(c, 1)
    f1s = []
    for o1, o2 in itertools.product(range(200), range(150)):
        e1 = reimpl_event_score(ref1, np.roll(hyp1, o1))
        e2 = reimpl_event_score(ref2, np.roll(hyp2, o2))
        tp, fp = e1["tp"] + e2["tp"], e1["fp"] + e2["fp"]
        f1s.append(f1_of(tp, fp, 1))
    f1s = np.array(f1s)
    assert abs(ex["mu_star"] - f1s.mean()) < 1e-12
    assert abs(ex["sigma_star"] - f1s.std()) < 1e-12
    srt = np.sort(f1s)
    q95 = srt[int(math.ceil(0.95 * f1s.size)) - 1]
    assert ex["q95"] == q95 and abs(ex["a_star"] - np.mean(f1s > q95)) < 1e-12
    assert abs(sum(m for _, m in pmf) - 1) < 1e-12
