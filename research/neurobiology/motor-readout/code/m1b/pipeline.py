"""M1b shared pipeline pieces (used by power_m1b.py and run_m1b.py): D1 fitting (ridge, KF-0, KF-L, GRU), D1 PL-1,
D2 session handling with row tags, day fits, NC1 designs, FA-ridge, PL-1 (D2) and PL-2'.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
Blocks adapted from run_m1.py (reviewed; REVIEW_M1 §2-4) cite the source lines. Control logic follows prereg M1b §6.
"""
import numpy as np

from m1lib import data as D
from m1lib import decoders as DEC
from m1lib import metrics as MET
from m1lib.guards import (FeatureWhitelistError, ZScore, assert_bins_disjoint, assert_whitelist, causal_whitelist,
                          feature_names, lag_offsets, lagged)
from nfharness.config import rng as nf_rng

from . import B_BOOT, K_BOOT, K_PLANT
from . import core as CO

J0, W1, H1 = 25, 35, 10          # D1 grid (M1 B.2): window start bin, window bins, history bins
H2 = 6                            # D2 ridge history (M1 d2_fit_day)


# =====================================================================================================================
# D1
# =====================================================================================================================
def d1_zscore(C, ids, itr, j0=J0, W=W1, H=H1):
    """z-score fitted on train rows (history + window) only (run_m1.py l.129-130)."""
    N = C.shape[2]
    zs = ZScore().fit(C[itr][:, j0 - H:j0 + W].reshape(-1, N), np.repeat(ids[itr], H + W), ids[itr])
    return zs, zs.transform(C[:, j0 - H:j0 + W].astype(np.float64))


def _chunks(Z, idx, ks, H, W, chunk=32):
    for a in range(0, len(idx), chunk):
        yield np.vstack([lagged(Z[s], ks)[H:H + W] for s in idx[a:a + chunk]])


def fit_ridge_d1(Z, Vtr, Vva, itr, iva, W=W1, H=H1):
    """Ridge on lagged window rows (run_m1.py l.134-142). Returns (model, info)."""
    N = Z.shape[2]
    ks = lag_offsets(H)
    assert_whitelist(feature_names("u", N, ks), causal_whitelist("u", N, H))
    rs = DEC.RidgeStream(N * H, 2)
    for a, X in zip(range(0, len(itr), 32), _chunks(Z, itr, ks, H, W)):
        rs.add(X, Vtr[a:a + 32].reshape(-1, 2))
    cands = rs.finalize()
    return DEC.select_ridge(cands, lambda: ((X, Vva[a:a + 32].reshape(-1, 2)) for a, X in
                                            zip(range(0, len(iva), 32), _chunks(Z, iva, ks, H, W))))


def predict_ridge_d1(m, Z, idx, W=W1, H=H1):
    return np.vstack([m.predict(X) for X in _chunks(Z, idx, lag_offsets(H), H, W)]).reshape(len(idx), W, 2)


def fit_kf(Z, Vtr, Vva, itr, iva, L=0, B=1, H=H1, W=W1):
    obs = CO.kfl_obs(Z, H, W, L, B)
    kf = DEC.KalmanVel().fit([v for v in Vtr], [obs[s] for s in itr])
    vr = MET.r2_vw(Vva.reshape(-1, 2), np.stack([kf.predict(obs[s]) for s in iva]).reshape(-1, 2))
    return kf, obs, vr


def fit_kfl(Z, Vtr, Vva, itr, iva, H=H1, W=W1):
    """KF-L grid over 23 (L, B) pairs in (B, L) ascending order; first max of validation R^2 (§3)."""
    best, curve = None, []
    for L, B in CO.KFL_GRID:
        kf, obs, vr = fit_kf(Z, Vtr, Vva, itr, iva, L, B, H, W)
        curve.append(dict(L=L, B=B, val_r2=float(vr)))
        if best is None or vr > best[0]:
            best = (vr, kf, obs, L, B)
    vr, kf, obs, L, B = best
    return kf, obs, dict(L=L, B=B, val_r2=float(vr), riccati_iters=kf.riccati_iters, grid=curve)


def fit_gru_d1(Z, Vtr, Vva, itr, iva, seeds, H=H1, W=W1):
    """run_m1.py l.148-159."""
    Xs = Z[itr].astype(np.float32)
    Ys = np.concatenate([np.zeros((len(itr), H, 2)), Vtr], axis=1)
    mask = np.zeros((len(itr), H + W))
    mask[:, H:] = 1
    Xva = Z[iva].astype(np.float32)

    def vf(e):
        return MET.r2_vw(Vva.reshape(-1, 2), e.predict_seqs(Xva)[:, H:].reshape(-1, 2))
    ens, ginf = DEC.train_gru(Xs, Ys, mask, vf, seeds=seeds)
    return ens, dict(seeds=ginf, val_r2=float(vf(ens)))


def fit_d1(Z, Vtr, Vva, itr, iva, ite, which, gru_seeds, H=H1, W=W1):
    """Fits the requested decoders on (possibly re-paired) train/val targets; returns test predictions [n_te, W, 2],
    model hashes and info. which subset of ('ridge', 'kf0', 'kfl', 'gru')."""
    preds, hashes, info = {}, {}, {}
    if "ridge" in which:
        m, inf = fit_ridge_d1(Z, Vtr, Vva, itr, iva, W, H)
        preds["ridge"] = predict_ridge_d1(m, Z, ite, W, H)
        hashes["ridge"], info["ridge"] = m.hash(), inf
        info["_ridge_model"] = m
    if "kf0" in which:
        kf, obs, vr = fit_kf(Z, Vtr, Vva, itr, iva, 0, 1, H, W)
        preds["kf0"] = np.stack([kf.predict(obs[s]) for s in ite])
        hashes["kf0"], info["kf0"] = kf.hash(), dict(val_r2=float(vr), riccati_iters=kf.riccati_iters)
    if "kfl" in which:
        kf, obs, inf = fit_kfl(Z, Vtr, Vva, itr, iva, H, W)
        preds["kfl"] = np.stack([kf.predict(obs[s]) for s in ite])
        hashes["kfl"], info["kfl"] = kf.hash(), inf
    if "gru" in which:
        ens, inf = fit_gru_d1(Z, Vtr, Vva, itr, iva, gru_seeds, H, W)
        preds["gru"] = ens.predict_seqs(Z[ite].astype(np.float32))[:, H:]
        hashes["gru"], info["gru"] = ens.hash(), inf
    return preds, hashes, info


def repair_targets(V, idx, perm):
    """Trial idx[i]'s neural data paired with trial idx[perm[i]]'s behaviour."""
    return V[idx[perm]]


# ---------------------------------------------------------------- D1 PL-1 (§6.2)
def pl1_design_d1(Z, idx, v, mu, sd, sigma2, g, H=H1, W=W1):
    ks = lag_offsets(H)
    X = np.vstack([lagged(Z[s], ks)[H:H + W] for s in idx])
    vv = v.reshape(-1, 2)
    P = (vv - mu) / sd + np.sqrt(sigma2) * g.standard_normal(vv.shape)
    return np.column_stack([X, P])


def pl1_whitelist(N, H, prefix="u"):
    """Undeclared call must raise FeatureWhitelistError; returns the exception name (or None)."""
    ks = lag_offsets(H)
    cols = feature_names(prefix, N, ks) + ["planted_v1", "planted_v2"]
    try:
        assert_whitelist(cols, causal_whitelist(prefix, N, H))
        raised = None
    except FeatureWhitelistError as e:
        raised = type(e).__name__
    assert_whitelist(cols, causal_whitelist(prefix, N, H), declared_extra=["planted_v1", "planted_v2"])
    return raised


def pl1_fit_d1(Z, Vtr, Vva, itr, iva, honest_val_pred, sigma2, plant_key, boot_key, H=H1, W=W1):
    """Planted ridge (2 columns) on train, lambda on val. Returns dict with model, E/s on validation and a closure that
    builds the test design from the (declared) test velocities."""
    mu = Vtr.reshape(-1, 2).mean(0)
    sd = Vtr.reshape(-1, 2).std(0)
    g = nf_rng(K_PLANT, *plant_key)
    Xtr = pl1_design_d1(Z, itr, Vtr, mu, sd, sigma2, g, H, W)
    Xva = pl1_design_d1(Z, iva, Vva, mu, sd, sigma2, g, H, W)
    yva = Vva.reshape(-1, 2)
    m, inf = DEC.fit_ridge_select(Xtr, Vtr.reshape(-1, 2), lambda mm: (yva, mm.predict(Xva)))
    pv = m.predict(Xva)
    E, r, w = CO.pl1_expected(yva, honest_val_pred.reshape(-1, 2), sigma2)
    units = [(k * W, (k + 1) * W) for k in range(len(iva))]
    s = rise_sd(yva, honest_val_pred.reshape(-1, 2), pv, units, boot_key)
    return dict(model=m, lambda_=inf["lambda_"], E=E, r=r, w=w, s=s, sigma2=sigma2,
                val_rise=MET.r2_vw(yva, pv) - MET.r2_vw(yva, honest_val_pred.reshape(-1, 2)),
                design_test=lambda vte, idx: pl1_design_d1(Z, idx, vte, mu, sd, sigma2, g, H, W))


def rise_sd(y, yh_honest, yh_planted, units, boot_key, B=B_BOOT):
    """Bootstrap SD (validation units) of R2_planted - R2_honest (§6.2)."""
    Wb = MET.boot_weights(len(units), B, nf_rng(K_BOOT, *boot_key))
    sh = MET.unit_stats([y[a:b] for a, b in units], [yh_honest[a:b] for a, b in units])
    sp = MET.unit_stats([y[a:b] for a, b in units], [yh_planted[a:b] for a, b in units])
    return float(np.std(MET.r2_from_stats(Wb, sp) - MET.r2_from_stats(Wb, sh)))


# =====================================================================================================================
# D2
# =====================================================================================================================
class RealD2:
    trials = staticmethod(D.d2_trials)
    neural = staticmethod(D.d2_neural)
    behaviour = staticmethod(D.d2_behaviour)
    conditions = staticmethod(CO.d2_trial_conditions)


def d2_session(loader, path, date, lag, pp, vault=None):
    """Adapted from run_m1.py l.433-459. pp = chrono_split parts. Test behaviour goes to the vault (if given; else kept
    in S['beh_test'] for the power check on OLD data) and is NaN-ed in S['beh']."""
    t = loader.trials(path)
    sbp, info = loader.neural(path)
    own = D.d2_owner(t, len(sbp))
    part = np.full(len(sbp), "none", dtype="<U5")
    for k, lab in (("train", "calib"), ("val", "val"), ("test", "test"), ("gap", "gap")):
        part[np.isin(own, pp[k])] = lab
    assert_bins_disjoint({lab: own[part == lab] for lab in ("calib", "val", "test", "gap")})
    beh = loader.behaviour(path)
    if len(beh) != len(sbp):
        raise RuntimeError("SBP / velocity length mismatch")
    rng_ = {}
    for lab in ("calib", "val", "test"):
        w = np.flatnonzero(part == lab)
        rng_[lab] = (int(w[0]), int(w[-1]) + 1, int((part[w[0]:w[-1] + 1] != lab).sum()))
    te = part == "test"
    S = dict(date=date, lag=lag, sbp=sbp, own=own, part=part, ranges=rng_, bin_info=info, n_bins=int(len(sbp)),
             style=sorted(set(t["style"].tolist())), test_pos=np.flatnonzero(te))
    if vault is not None:
        vault.deposit(("D2", date), beh[te])
        S["beh_test"] = None
    else:
        S["beh_test"] = beh[te].copy()
    beh[te] = np.nan
    S["beh"] = beh
    cond = loader.conditions(path)
    for k, lab in (("train", "calib"), ("val", "val"), ("test", "test")):
        rows = []
        for i in pp[k]:
            r = np.flatnonzero((own == i) & (part == lab))
            rows.append(r)
        S["trows_" + lab] = rows
        S["tids_" + lab] = [int(i) for i in pp[k]]
        S["cond_" + lab] = [cond[int(i)] for i in pp[k]]
    own_te = own[te]
    S["test_trial_rows"] = [(int(np.flatnonzero(own_te == i)[0]), int(np.flatnonzero(own_te == i)[-1]) + 1)
                            for i in pp["test"]]
    S["calib_trials"] = S["tids_calib"]
    return S


def tags_of(S, rows):
    return [(S["lag"], b) for b in np.unique(S["part"][rows]).tolist()]


def d2_fit_day(S, which=("ridge",), gru_seeds=(20261001,), train=None, val=None, models=None, name=""):
    """Fit on session S (declared day = S['lag']). train = (rows, Y, kf_segs, gru_block) override (NC1 re-pairing);
    val = (rows, Y) override. Row-tag session-order check on the rows actually passed (review C1).
    Adapted from run_m1.py l.462-512."""
    N = S["sbp"].shape[1]
    part = S["part"]
    cal = np.flatnonzero(part == "calib")
    vrows = np.flatnonzero(part == "val")
    yval = S["beh"][vrows]
    if val is not None:
        vrows, yval = val
    trows = cal if train is None else train[0]
    CO.check_rows(S["lag"], tags_of(S, trows) + tags_of(S, vrows))
    zs = ZScore().fit(S["sbp"][cal], S["own"][cal], S["calib_trials"])
    Z = zs.transform(S["sbp"])
    ks = lag_offsets(H2)
    assert_whitelist(feature_names("sbp", N, ks), causal_whitelist("sbp", N, H2))
    Lg = lagged(Z, ks)
    out = dict(zs=zs, info={}, lam=None)
    Xr, Yr = (Lg[cal], S["beh"][cal]) if train is None else (Lg[train[0]], train[1])
    if "ridge" in which:
        m, inf = DEC.fit_ridge_select(Xr, Yr, lambda mm: (yval, mm.predict(Lg[vrows])))
        out["ridge"], out["info"]["ridge"], out["lam"] = m, inf, m.lam
        out["ridge_val_pred"] = m.predict(Lg[vrows])
        if models is not None:
            models["%s/ridge" % name] = m.hash()
    ca, cb, _ = S["ranges"]["calib"]
    va, vb, _ = S["ranges"]["val"]
    if "kf" in which:
        segs = [(Z[ca:cb], S["beh"][ca:cb])] if train is None else train[2]
        kf = DEC.KalmanVel().fit([s[1] for s in segs], [s[0] for s in segs])
        vr = MET.r2_vw(yval, kf.predict(Z[va:vb])[vrows - va])
        out["kf"], out["info"]["kf"] = kf, dict(val_r2=float(vr), riccati_iters=kf.riccati_iters)
        if models is not None:
            models["%s/kf" % name] = kf.hash()
    if "gru" in which:
        if train is None:
            Xc, Yc, Mc = Z[ca:cb], S["beh"][ca:cb], (part[ca:cb] == "calib").astype(float)
        else:
            Xc, Yc, Mc = train[3]
        nch = len(Xc) // 64
        Xs = Xc[:nch * 64].reshape(nch, 64, N).astype(np.float32)
        Ys = np.nan_to_num(Yc[:nch * 64].reshape(nch, 64, 2))
        Ms = Mc[:nch * 64].reshape(nch, 64).copy()
        Ms[:, :10] = 0
        Xv = Z[va - 10:vb][None].astype(np.float32)

        def vf(e):
            return MET.r2_vw(yval, e.predict_seqs(Xv)[0, 10:][vrows - va])
        ens, ginf = DEC.train_gru(Xs, Ys, Ms, vf, seeds=gru_seeds)
        out["gru"], out["info"]["gru"] = ens, dict(seeds=ginf, val_r2=float(vf(ens)), n_chunks=nch)
        if models is not None:
            models["%s/gru" % name] = ens.hash()
    return out


def d2_apply(M, dec, Sk, zs=None):
    """run_m1.py l.515-527."""
    zs = M["zs"] if zs is None else zs
    Z = zs.transform(Sk["sbp"])
    ta, tb, _ = Sk["ranges"]["test"]
    tm = Sk["part"][ta:tb] == "test"
    if dec == "ridge":
        return M["ridge"].predict(lagged(Z, lag_offsets(H2))[Sk["test_pos"]])
    if dec == "kf":
        return M["kf"].predict(Z[ta:tb])[tm]
    if dec == "gru":
        return M["gru"].predict_seqs(Z[ta - 10:tb][None].astype(np.float32))[0, 10:][tm]
    raise KeyError(dec)


def d2_b0(S, trial_rows_key="trows_calib"):
    prof = CO.start_aligned_profile([S["beh"][r] for r in S[trial_rows_key]])
    return prof, CO.start_aligned_predict(prof, [b - a for a, b in S["test_trial_rows"]])


# ---------------------------------------------------------------- FA-ridge (R-b; run_m1.py l.540-571)
def fa_anchor(S0, models=None, name=""):
    cal0 = S0["part"] == "calib"
    sd0 = np.maximum(S0["sbp"][cal0].std(0), 1e-12)
    fa0 = DEC.FA().fit(S0["sbp"][cal0] / sd0, k=10, iters=200)
    lat0 = lagged(fa0.posterior_mean(S0["sbp"] / sd0), lag_offsets(H2))
    if models is not None:
        models["%s/FA" % name] = DEC.arr_hash(fa0.L, fa0.psi, fa0.mu)
    return dict(sd0=sd0, fa0=fa0, lat0=lat0)


def fa_ridge_fit(S0, FA0, train=None, val=None, models=None, name=""):
    part = S0["part"]
    cal = np.flatnonzero(part == "calib")
    vrows = np.flatnonzero(part == "val")
    yval = S0["beh"][vrows]
    if val is not None:
        vrows, yval = val
    trows, Y = (cal, S0["beh"][cal]) if train is None else (train[0], train[1])
    CO.check_rows(S0["lag"], tags_of(S0, trows) + tags_of(S0, vrows))
    lat0 = FA0["lat0"]
    fr, inf = DEC.fit_ridge_select(lat0[trows], Y, lambda mm: (yval, mm.predict(lat0[vrows])))
    if models is not None:
        models["%s/FAridge" % name] = fr.hash()
    return fr, inf


def fa_ridge_apply(fr, FA0, Sk, is_anchor):
    calk = Sk["part"] == "calib"
    fak = FA0["fa0"] if is_anchor else DEC.FA().fit(Sk["sbp"][calk] / FA0["sd0"], k=10, iters=200)
    O = DEC.procrustes(fak.L, FA0["fa0"].L)
    latk = lagged(fak.posterior_mean(Sk["sbp"] / FA0["sd0"]) @ O, lag_offsets(H2))
    return fr.predict(latk[Sk["test_pos"]]), DEC.arr_hash(fak.L, fak.psi, O)


# ---------------------------------------------------------------- D2 NC1 designs (M1 DV-7; run_m1.py l.575-601)
def d2_nc1_design(S0, Z0, perm_cal, perm_val):
    """Calib trial i's rows (first m) paired with trial perm[i]'s behaviour (first m); same for val."""
    rows_i, tgt, segs = [], [], []
    cr = S0["trows_calib"]
    for i, j in enumerate(perm_cal):
        m = min(len(cr[i]), len(cr[j]))
        rows_i.append(cr[i][:m])
        tgt.append(S0["beh"][cr[j][:m]])
        segs.append((Z0[cr[i][:m]], S0["beh"][cr[j][:m]]))
    rows = np.concatenate(rows_i)
    Y = np.vstack(tgt)
    vr = S0["trows_val"]
    vrows, vtgt = [], []
    for i, j in enumerate(perm_val):
        m = min(len(vr[i]), len(vr[j]))
        vrows.append(vr[i][:m])
        vtgt.append(S0["beh"][vr[j][:m]])
    return (rows, Y, segs, (Z0[rows], Y, np.ones(len(rows)))), (np.concatenate(vrows), np.vstack(vtgt))


# ---------------------------------------------------------------- D2 PL-1 (§6.2)
def pl1_d2_fit(S0, M0, sigma2, plant_key, boot_key):
    """Planted columns appended to the anchor's lagged SBP ridge design; lambda on val. Test design built later from the
    declared vault read."""
    Z = M0["zs"].transform(S0["sbp"])
    Lg = lagged(Z, lag_offsets(H2))
    cal = np.flatnonzero(S0["part"] == "calib")
    val = np.flatnonzero(S0["part"] == "val")
    ycal, yval = S0["beh"][cal], S0["beh"][val]
    mu, sd = ycal.mean(0), ycal.std(0)
    g = nf_rng(K_PLANT, *plant_key)

    def des(rows, y):
        return np.column_stack([Lg[rows], (y - mu) / sd + np.sqrt(sigma2) * g.standard_normal(y.shape)])
    Xtr = des(cal, ycal)
    Xva = des(val, yval)
    m, inf = DEC.fit_ridge_select(Xtr, ycal, lambda mm: (yval, mm.predict(Xva)))
    pv = m.predict(Xva)
    hv = M0["ridge_val_pred"]
    E, r, w = CO.pl1_expected(yval, hv, sigma2)
    units = [(a, min(a + 64, len(val))) for a in range(0, len(val), 64)]
    s = rise_sd(yval, hv, pv, units, boot_key)
    return dict(model=m, lambda_=inf["lambda_"], E=E, r=r, w=w, s=s, sigma2=sigma2,
                val_rise=MET.r2_vw(yval, pv) - MET.r2_vw(yval, hv),
                design_test=lambda yte: des(S0["test_pos"], yte))


# ---------------------------------------------------------------- PL-2' (§6.2)
def pl2_fit(S0, M0, Sk):
    """'Day-0' ridge on anchor calib + session-k calib (true labels), anchor z-scorer, lambda = honest anchor lambda.
    Undeclared row-tag check must raise SessionOrderError. Returns (test prediction, undeclared exception name)."""
    from m1lib.guards import SessionOrderError
    cal0 = np.flatnonzero(S0["part"] == "calib")
    calk = np.flatnonzero(Sk["part"] == "calib")
    tags = tags_of(S0, cal0) + tags_of(Sk, calk)
    try:
        CO.check_rows(S0["lag"], tags)
        raised = None
    except SessionOrderError as e:
        raised = type(e).__name__
    CO.check_rows(S0["lag"], tags, allow_future=True)
    zs0 = M0["zs"]
    L0 = lagged(zs0.transform(S0["sbp"]), lag_offsets(H2))
    Lk = lagged(zs0.transform(Sk["sbp"]), lag_offsets(H2))
    X = np.vstack([L0[cal0], Lk[calk]])
    Y = np.vstack([S0["beh"][cal0], Sk["beh"][calk]])
    lam = M0["ridge"].lam
    Wt, b = DEC.RidgePath(X, Y).coef(lam)
    m = DEC.Ridge(Wt, b, lam)
    return m.predict(Lk[Sk["test_pos"]]), raised, m.hash()


def d2_units(n):
    return [(a, min(a + 64, n)) for a in range(0, n, 64)]


# ---------------------------------------------------------------- scoring helper (run_m1.py l.163-174, extended)
def cont_score(y, yh, units, bin_ms, seg_len, null_key):
    """Pooled M-R2 / rho2 over rows; bits (I_coh no DC, I_coh DC, I_mse) over full-length units, null = 200
    derangements of the true segments (stream 3, null_key). Returns (public, private-for-bootstrap)."""
    from . import K_NULL, N_NULL
    y = np.asarray(y, float)
    yh = np.asarray(yh, float)
    st = MET.unit_stats([y[a:b] for a, b in units], [yh[a:b] for a, b in units])
    full = [i for i, (a, b) in enumerate(units) if b - a == seg_len]
    ys = np.stack([y[units[i][0]:units[i][1]] for i in full])
    yhs = np.stack([yh[units[i][0]:units[i][1]] for i in full])
    perms = MET.derangements(len(full), N_NULL, nf_rng(K_NULL, *null_key))
    bits = CO.bits_all(ys, yhs, bin_ms, perms)
    X, Y = MET.seg_spectra(ys, yhs)
    return (dict(r2=MET.r2_vw(y, yh), rho2=MET.rho2(y, yh), bits=bits, n_rows=int(len(y)), n_units=len(units)),
            dict(st=st, X=X, Y=Y, full=full, coh_null_med=bits["I_coh_null_median"], bin_ms=bin_ms, seg_len=seg_len))


def boot_r2_coh(priv, Wb):
    """Bootstrap replicates of R2 and I_coh,net (DC excluded; fixed null median; M1 B.10)."""
    r2 = MET.r2_from_stats(Wb, priv["st"])
    mask, df = CO.freq_mask_nodc(priv["seg_len"], priv["bin_ms"])
    bits = MET.bits_from_spectra(priv["X"], priv["Y"], mask, df, W=Wb[:, priv["full"]]) - priv["coh_null_med"]
    return r2, bits
