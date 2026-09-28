"""M1b new primitives (prereg §9 "New code"): condition readers, condition-constrained derangement (+ DV-b1 fallback),
NL-1, DC-free frequency mask, I_coh (no DC) and the sign/gain-sensitive I_mse with derangement nulls, start-aligned B0,
KF-L observations, the PL-1 analytic expectation E, and row-tag session-order checks.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import hashlib

import h5py
import numpy as np

from m1lib import metrics as MET
from m1lib.guards import assert_session_order


# ---------------------------------------------------------------- trial-table readers (no behaviour)
def d1_trial_table(path):
    """Timing + condition metadata of an MC_Maze train file. Condition = (trial_type, trial_version) (C16)."""
    with h5py.File(path, "r") as f:
        t = f["intervals/trials"]
        keys = set(t.keys())
        has_vel = "processing" in f and "behavior" in f["processing"] and "hand_vel" in f["processing/behavior"]
        out = dict(id=t["id"][:].astype(int), start=t["start_time"][:], stop=t["stop_time"][:],
                   onset=t["move_onset_time"][:] if "move_onset_time" in keys else None,
                   n_units=int(f["units/id"].shape[0]), has_hand_vel=bool(has_vel),
                   has_onset="move_onset_time" in keys)
        tt = t["trial_type"][:]
        tv = t["trial_version"][:]
    out["cond"] = [(int(a), int(b)) for a, b in zip(tt, tv)]
    return out


def d2_trial_conditions(path):
    """LINK condition = (index_target_position, mrs_target_position) rounded to 4 d.p. (review definition)."""
    with h5py.File(path, "r") as f:
        t = f["intervals/trials"]
        a = t["index_target_position"][:]
        b = t["mrs_target_position"][:]
        ids = t["id"][:].astype(int)
    return {int(i): (round(float(x), 4), round(float(y), 4)) for i, x, y in zip(ids, a, b)}


def d2_timing(path):
    """A6 timing facts from the SBP timestamps (no data values)."""
    with h5py.File(path, "r") as f:
        ts = f["analysis/SpikingBandPower/timestamps"][:]
    d = np.diff(ts)
    return dict(dt_median_s=float(np.median(d)), dt_min_s=float(d.min()), dt_max_s=float(d.max()), n20=int(len(ts)))


# ---------------------------------------------------------------- constrained derangement (§6.1; DV-b1)
def _cond_codes(cond):
    u = {}
    return np.array([u.setdefault(c, len(u)) for c in cond], dtype=np.int64)


def _valid(p, cc):
    return not np.any(cc[p] == cc)


def constrained_derangement(cond, rng, max_draws=100000, mcmc_factor=200):
    """Uniform random permutation p with cond[p[i]] != cond[i] for all i (hence no fixed point).
    Returns (p, info). info['method'] in {'rejection', 'mcmc', 'unconstrained (>50%)'}.
    - rejection: literal prereg sampler (uniform permutations until valid, at most max_draws).
    - mcmc (DV-b1): only if the cap is hit; symmetric random-transposition chain on valid permutations.
    - if one condition holds > 50 % of the trials no valid p exists: unconstrained derangement, flagged."""
    cc = _cond_codes(cond)
    n = len(cc)
    counts = np.bincount(cc)
    if counts.max() * 2 > n:
        for d in range(1, max_draws + 1):
            p = rng.permutation(n)
            if not np.any(p == np.arange(n)):
                return p, dict(method="unconstrained (>50%)", draws=d, flag=True, max_class_frac=float(counts.max() / n))
        raise RuntimeError("no derangement found")
    for d in range(1, max_draws + 1):
        p = rng.permutation(n)
        if _valid(p, cc):
            return p, dict(method="rejection", draws=d, flag=False, max_class_frac=float(counts.max() / n))
    # DV-b1 fallback: start = cyclic shift by the largest class size of the condition-sorted order
    order = sorted(range(n), key=lambda i: (-counts[cc[i]], cc[i], i))
    m = int(counts.max())
    p = np.empty(n, dtype=np.int64)
    for pos in range(n):
        p[order[pos]] = order[(pos + m) % n]
    assert _valid(p, cc)
    steps = mcmc_factor * n
    ij = rng.integers(0, n, size=(steps, 2))
    pl = p.tolist()
    cl = cc.tolist()
    acc = 0
    for i, j in ij.tolist():
        if i == j:
            continue
        a, b = pl[i], pl[j]
        if cl[b] != cl[i] and cl[a] != cl[j]:
            pl[i], pl[j] = b, a
            acc += 1
    p = np.array(pl, dtype=np.int64)
    assert _valid(p, cc)
    return p, dict(method="mcmc", draws=max_draws, flag=False, mcmc_steps=int(steps), mcmc_accepted=int(acc),
                   max_class_frac=float(counts.max() / n))


def nl1_permutation(cond, rng_keep, rng_perm, frac=0.25):
    """NL-1 planted NC1 leak: exactly round(frac*n) trials keep their true partner (stream 8 picks them); the rest are
    re-paired among themselves by constrained_derangement."""
    n = len(cond)
    k = int(round(frac * n))
    keep = np.sort(rng_keep.choice(n, size=k, replace=False))
    rest = np.setdiff1d(np.arange(n), keep)
    q, info = constrained_derangement([cond[i] for i in rest], rng_perm)
    p = np.arange(n)
    p[rest] = rest[q]
    info = dict(info, kept=int(k), n=int(n))
    return p, keep, info


def perm_hash(p):
    return hashlib.sha256(np.asarray(p, dtype=np.int64).tobytes()).hexdigest()


# ---------------------------------------------------------------- bits (§4.2)
def freq_mask_nodc(n, bin_ms, fmax_hz=10):
    """0 < f_j <= fmax (exact integer test). Returns (mask, df_hz)."""
    j = np.arange(n // 2 + 1)
    return (j >= 1) & (j * 1000 <= fmax_hz * n * bin_ms), 1000.0 / (n * bin_ms)


def mse_bits_from_spectra(X, Y, mask, df, pair=None):
    """I_mse = df * sum_d sum_j log2( sum_k |X_k|^2 / sum_k |X_pi(k) - Y_k|^2 ). X = true, Y = issued output (rfft of
    Hann-tapered segments, [K, d, F]). pair = derangement of the true segments (null). No clipping."""
    Syy = (np.abs(X) ** 2).sum(0)
    Xp = X if pair is None else X[pair]
    See = (np.abs(Xp - Y) ** 2).sum(0)
    with np.errstate(divide="ignore"):
        v = np.log2(Syy[:, mask]) - np.log2(See[:, mask])
    return float(v.sum() * df)


def bits_all(y_segs, yh_segs, bin_ms, perms):
    """I_coh (DC excluded; primary), I_coh with DC (M1 report), I_mse (DC excluded), each with the same derangement
    null (list of permutations). Returns dict."""
    X, Y = MET.seg_spectra(y_segs, yh_segs)
    n = np.asarray(y_segs).shape[1]
    m0, df = freq_mask_nodc(n, bin_ms)
    mdc, _ = MET.freq_mask(n, bin_ms)
    coh = MET.bits_from_spectra(X, Y, m0, df)
    cohdc = MET.bits_from_spectra(X, Y, mdc, df)
    mse = mse_bits_from_spectra(X, Y, m0, df)
    ncoh = np.array([MET.bits_from_spectra(X, Y, m0, df, pair=p) for p in perms])
    ncohdc = np.array([MET.bits_from_spectra(X, Y, mdc, df, pair=p) for p in perms])
    nmse = np.array([mse_bits_from_spectra(X, Y, m0, df, pair=p) for p in perms])
    med = lambda a: float(np.median(a))  # noqa: E731
    return dict(I_coh=coh, I_coh_null_median=med(ncoh), I_coh_net=coh - med(ncoh),
                I_coh_dc=cohdc, I_coh_dc_net=cohdc - med(ncohdc),
                I_mse=mse, I_mse_null_median=med(nmse), I_mse_net=mse - med(nmse),
                n_segments=int(X.shape[0]), df_hz=df, n_freqs=int(m0.sum()), n_freqs_dc=int(mdc.sum()))


# ---------------------------------------------------------------- B0 (§6.1)
def start_aligned_profile(trial_behaviours):
    """Mean over trials of behaviour at trial-relative bin i (trials with length > i). [Lmax, d]."""
    L = max(len(b) for b in trial_behaviours)
    d = trial_behaviours[0].shape[1]
    s = np.zeros((L, d))
    c = np.zeros(L)
    for b in trial_behaviours:
        s[:len(b)] += b
        c[:len(b)] += 1
    return s / c[:, None]


def start_aligned_predict(profile, lengths):
    """Concatenated B0 prediction for trials of the given lengths (longer trials repeat the last profile value)."""
    out = []
    for n in lengths:
        if n <= len(profile):
            out.append(profile[:n])
        else:
            out.append(np.vstack([profile, np.repeat(profile[-1:], n - len(profile), axis=0)]))
    return np.vstack(out)


# ---------------------------------------------------------------- KF-L (§3)
KFL_GRID = [(L, B) for B in (1, 2, 5, 10) for L in range(8) if L + B <= 10]    # (B, L) ascending order; 23 pairs


def kfl_obs(Z, H, W, L, B):
    """Z [S, H+W, N] z-scored counts (history rows 0..H-1, window rows H..H+W-1). o_t = mean of z over rows
    t-L-B+1 .. t-L, for window rows t. Returns [S, W, N]. (L, B) = (0, 1) returns Z[:, H:H+W] exactly."""
    if L + B - 1 > H:
        raise ValueError("KF-L needs L+B-1 <= H history rows")
    acc = Z[:, H - L:H - L + W].copy()
    for b in range(1, B):
        acc += Z[:, H - L - b:H - L - b + W]
    return acc / B if B > 1 else acc


# ---------------------------------------------------------------- PL-1 analytic expectation (§6.2)
def pl1_expected(y_val, yh_val, sigma2):
    """E = sum_d w_d r_d^2 / (r_d + sigma2); r_d = SSE_d/SST_d, w_d = SST_d / sum SST (validation)."""
    y = np.asarray(y_val, float)
    yh = np.asarray(yh_val, float)
    sst = ((y - y.mean(0)) ** 2).sum(0)
    sse = ((y - yh) ** 2).sum(0)
    r = sse / sst
    w = sst / sst.sum()
    return float((w * r * r / (r + sigma2)).sum()), r.tolist(), w.tolist()


def pl1_sigma2_and_E(y_val, yh_val):
    E, r, w = pl1_expected(y_val, yh_val, 0.1)
    s2 = 0.1
    if E < 0.10:
        s2 = 0.02
        E, r, w = pl1_expected(y_val, yh_val, s2)
    return s2, E, r, w


# ---------------------------------------------------------------- row tags (§2 additions; review C1)
def check_rows(declared_day, tags, allow_future=False):
    """tags: iterable of (day, block) for every row passed to a fit (training + selection rows)."""
    u = sorted(set((int(d), str(b)) for d, b in tags))
    return assert_session_order(declared_day, [d for d, _ in u], [b for _, b in u], allow_future=allow_future)


def row_tags(day, blocks):
    """Row tags for rows of one session: blocks = array of block labels of the rows."""
    return [(day, b) for b in np.unique(np.asarray(blocks)).tolist()]
