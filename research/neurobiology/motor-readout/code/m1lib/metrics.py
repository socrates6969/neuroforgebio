"""M1 metrics (prereg §4): M-R2, rho^2, M-BITS (Gaussian coherence bound + permutation null), M-MI (Miller-Madow),
Wolpaw ITR, drift ratios, paired bootstraps, sign-flip permutation test.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
"""
import numpy as np
from scipy.stats import spearmanr


# ---------------------------------------------------------------- accuracy
def r2_vw(y, yh):
    """sklearn r2_score(multioutput='variance_weighted') = 1 - sum_d SSE_d / sum_d SST_d (re-implemented; sklearn is
    not installed, see DEVIATIONS)."""
    y = np.asarray(y, float).reshape(len(y), -1)
    yh = np.asarray(yh, float).reshape(len(yh), -1)
    sse = ((y - yh) ** 2).sum(axis=0)
    sst = ((y - y.mean(axis=0)) ** 2).sum(axis=0)
    return float(1.0 - sse.sum() / sst.sum())


def rho2(y, yh):
    """Mean over output dimensions of the squared Pearson correlation."""
    y = np.asarray(y, float).reshape(len(y), -1)
    yh = np.asarray(yh, float).reshape(len(yh), -1)
    out = []
    for d in range(y.shape[1]):
        a, b = y[:, d] - y[:, d].mean(), yh[:, d] - yh[:, d].mean()
        den = np.sqrt((a * a).sum() * (b * b).sum())
        out.append(0.0 if den == 0 else float((a * b).sum() / den) ** 2)
    return float(np.mean(out))


def unit_stats(y_units, yh_units):
    """Per resampling unit (trial / segment): sufficient statistics for the pooled variance-weighted R^2."""
    sse = np.array([((np.asarray(y) - np.asarray(h)) ** 2).sum(axis=0) for y, h in zip(y_units, yh_units)])
    sy = np.array([np.asarray(y).sum(axis=0) for y in y_units])
    syy = np.array([(np.asarray(y) ** 2).sum(axis=0) for y in y_units])
    n = np.array([len(y) for y in y_units], float)
    return dict(sse=sse, sy=sy, syy=syy, n=n)


def r2_from_stats(W, st):
    """W [B, U] multiplicities -> pooled variance-weighted R^2 per replicate [B]."""
    N = W @ st["n"]
    SSE = W @ st["sse"]
    Sy = W @ st["sy"]
    Syy = W @ st["syy"]
    SST = Syy - Sy ** 2 / N[:, None]
    return 1.0 - SSE.sum(axis=1) / SST.sum(axis=1)


# ---------------------------------------------------------------- bits/s (TD §1.1, §2.1)
def freq_mask(n, bin_ms, fmax_hz=10):
    """f_j = j*1000/(n*bin_ms) Hz; keep f_j <= fmax (exact integer comparison, DC included). Returns (mask, df_hz)."""
    j = np.arange(n // 2 + 1)
    return (j * 1000 <= fmax_hz * n * bin_ms), 1000.0 / (n * bin_ms)


def seg_spectra(y_segs, yh_segs):
    """y_segs, yh_segs [K, n, d] -> (X, Y) rfft of Hann-tapered segments, shape [K, d, F]."""
    y_segs = np.asarray(y_segs, float)
    yh_segs = np.asarray(yh_segs, float)
    w = np.hanning(y_segs.shape[1])[None, :, None]
    X = np.fft.rfft(y_segs * w, axis=1).transpose(0, 2, 1)
    Y = np.fft.rfft(yh_segs * w, axis=1).transpose(0, 2, 1)
    return X, Y


def _coh(num, den):
    """|Sxy|^2 / (Sxx Syy); defined as 0 where a spectrum is identically zero (e.g. a constant prediction)."""
    out = np.zeros_like(num)
    np.divide(num, den, out=out, where=den > 0)
    return out


def bits_from_spectra(X, Y, mask, df, W=None, pair=None):
    """Coherence-bound information rate summed over dims. W [B, K] weights (bootstrap) or None; pair = permutation of
    true segments (null). Returns bits/s (scalar or [B])."""
    Xp = X if pair is None else X[pair]
    Sxy = Xp * np.conj(Y)
    Sxx = np.abs(Xp) ** 2
    Syy = np.abs(Y) ** 2
    if W is None:
        g = _coh(np.abs(Sxy.sum(0)) ** 2, Sxx.sum(0) * Syy.sum(0))
        g = np.clip(g[:, mask], 0, 1 - 1e-12)
        return float((-np.log2(1 - g)).sum() * df)
    K = X.shape[0]
    a = (W @ Sxy.reshape(K, -1)).reshape(W.shape[0], *Sxy.shape[1:])
    b = (W @ Sxx.reshape(K, -1)).reshape(W.shape[0], *Sxx.shape[1:])
    c = (W @ Syy.reshape(K, -1)).reshape(W.shape[0], *Syy.shape[1:])
    g = np.clip(_coh(np.abs(a) ** 2, b * c)[:, :, mask], 0, 1 - 1e-12)
    return (-np.log2(1 - g)).sum(axis=(1, 2)) * df


def derangements(K, n_perm, rng):
    out = []
    while len(out) < n_perm:
        p = rng.permutation(K)
        if not np.any(p == np.arange(K)):
            out.append(p)
    return out


def bits_with_null(y_segs, yh_segs, bin_ms, rng, n_perm=200, fmax_hz=10):
    X, Y = seg_spectra(y_segs, yh_segs)
    mask, df = freq_mask(np.asarray(y_segs).shape[1], bin_ms, fmax_hz)
    raw = bits_from_spectra(X, Y, mask, df)
    null = np.array([bits_from_spectra(X, Y, mask, df, pair=p) for p in derangements(X.shape[0], n_perm, rng)])
    return dict(I_raw=raw, I_null_median=float(np.median(null)), I_net=raw - float(np.median(null)),
                n_segments=int(X.shape[0]), df_hz=df, n_freqs=int(mask.sum()))


# ---------------------------------------------------------------- bootstrap
def boot_weights(U, B, rng):
    idx = rng.integers(0, U, size=(B, U))
    W = np.zeros((B, U))
    for b in range(B):
        W[b] = np.bincount(idx[b], minlength=U)
    return W


def pct_ci(v, level):
    a = (100 - level) / 2.0
    lo, hi = np.percentile(np.asarray(v, float), [a, 100 - a])
    return [float(lo), float(hi)]


# ---------------------------------------------------------------- discrete (D3)
def mi_miller_madow(conf):
    """Plug-in MI (bits) of a confusion matrix minus the Miller-Madow bias (Bx-1)(By-1)/(2 n ln 2), with B = number of
    non-empty marginal bins."""
    c = np.asarray(conf, float)
    n = c.sum()
    p = c / n
    px, py = p.sum(1), p.sum(0)
    nz = p > 0
    mi = float((p[nz] * np.log2(p[nz] / (px[:, None] * py[None, :])[nz])).sum())
    bx, by = int((px > 0).sum()), int((py > 0).sum())
    return mi - (bx - 1) * (by - 1) / (2 * n * np.log(2)), mi


def wolpaw_bits(N, P):
    if P >= 1:
        return float(np.log2(N))
    if P <= 0:
        return float(np.log2(N) + np.log2(1.0 / (N - 1)))
    return float(np.log2(N) + P * np.log2(P) + (1 - P) * np.log2((1 - P) / (N - 1)))


def signflip_p(d, n_flip, rng):
    """One-sided paired sign-flip permutation p for mean(d) > 0: (1 + #{mean* >= obs}) / (1 + n_flip)."""
    d = np.asarray(d, float)
    obs = d.mean()
    s = rng.choice([-1.0, 1.0], size=(n_flip, d.size))
    m = (s * d[None, :]).mean(axis=1)
    return float((1 + np.sum(m >= obs - 1e-15)) / (1 + n_flip))


def spearman(a, b):
    r = spearmanr(a, b)
    return float(r.statistic if hasattr(r, "statistic") else r[0])
