"""P1: latency budget for artificial slip feedback in precision grip (prereg\\P1_grip_latency_budget.md).

Simulation only. numpy (+ matplotlib for figures). Seed 20260926.
Usage:  python p1_grip_latency.py test | main | sens | all
Interpretations: code\\DEVIATIONS.md (section P1).
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

BASE = r"C:\Users\mariu\neuro-company\research\somatosensory\code"
RES = os.path.join(BASE, "results")
FIG = os.path.join(BASE, "figures")
SEED = 20260926
DT = 0.002
T_END = 4.0
NSTEP = int(round(T_END / DT))
G_ACC = 9.81
SM_GRID = np.round(np.arange(16) * 0.1, 1)
NS = len(SM_GRID)
KMAX = 30
NDET = 128
DELTAS = [-20, 0, 25, 50, 75, 100, 150, 200, 300]
PS = [0.5, 0.75, 0.95]
TAU_V = [0.150, 0.200, 0.250]

DEFAULT = dict(tau_m=0.040, drop=0.010, amp_lo=0.2, amp_hi=0.6, pois=2.0, c_lo=1.6, c_hi=2.5,
               noise=0.05, nat_tau=0.074, mu_prior=0.75, p_nat=0.95, predictive=False,
               s_vis=0.002, K_zero=False)


# ----------------------------------------------------------------------------------------------
def poisson_ppf(u, lam):
    """Inverse CDF of Poisson(lam) at uniforms u (numpy only)."""
    k = np.zeros(u.shape, dtype=np.int64)
    p = np.exp(-lam)
    cdf = p.copy() if np.ndim(p) else np.full(u.shape, p)
    kk = 0
    while np.any(u > cdf) and kk < 200:
        kk += 1
        p = p * lam / kk
        k += (u > cdf)
        cdf = cdf + p
    return k


def trapezoid(u, rise=0.03, plat=0.2, fall=0.03):
    out = np.zeros_like(u)
    a = (u >= 0) & (u < rise)
    out[a] = u[a] / rise
    b = (u >= rise) & (u < rise + plat)
    out[b] = 1.0
    c = (u >= rise + plat) & (u < rise + plat + fall)
    out[c] = (rise + plat + fall - u[c]) / fall
    return out


def ou_path(z, tau=0.1, dt=DT):
    a = np.exp(-dt / tau)
    b = np.sqrt(1 - a * a)
    xi = np.empty_like(z)
    xi[0] = z[0]
    for n in range(1, z.shape[0]):
        xi[n] = a * xi[n - 1] + b * z[n]
    return xi


def make_trials(N, P, seed=SEED):
    rng = np.random.default_rng(seed)
    m = rng.uniform(0.2, 0.5, N)
    mu = rng.uniform(0.3, 1.2, N)
    cu = rng.uniform(0, 1, N)
    ku = rng.uniform(0, 1, N)
    on = rng.uniform(1.0, 3.5, (N, KMAX))
    au = rng.uniform(0, 1, (N, KMAX))
    z = rng.standard_normal((NSTEP, N))
    udet = rng.uniform(0, 1, (N, NDET))
    ushuf = rng.uniform(0, 1, (N, NDET))
    K = np.zeros(N, dtype=np.int64) if P["K_zero"] else np.minimum(poisson_ppf(ku, P["pois"]), KMAX)
    c = P["c_lo"] + (P["c_hi"] - P["c_lo"]) * cu
    mg = m * G_ACC
    amp = (P["amp_lo"] + (P["amp_hi"] - P["amp_lo"]) * au) * mg[:, None]
    t = np.arange(NSTEP) * DT
    L = (mg[None, :] * np.clip((t[:, None] - 0.5) / 0.3, 0, 1))
    for k in range(KMAX):
        act = K > k
        if not act.any():
            continue
        L[:, act] += amp[act, k][None, :] * trapezoid(t[:, None] - on[act, k][None, :])
    xi = ou_path(z)
    return dict(N=N, m=m, mu=mu, mg=mg, c=c, K=K, Gcrush=c * mg / (2 * mu), L=L.astype(np.float64),
                xi=xi.astype(np.float32), udet=udet, ushuf=ushuf)


# ----------------------------------------------------------------------------------------------
def slip_update(S, L, Geff, mu, m, v, s, dt=DT):
    """Slip physics of the prereg: while S, v += (L-2 mu Geff)/m dt; s += v dt; else v = 0 (s kept)."""
    acc = (L - 2 * mu * Geff) / m
    v_new = np.where(S, v + acc * dt, 0.0)
    s_new = s + np.where(S, v_new * dt, 0.0)
    return v_new, s_new


def cond_list_main():
    c = [dict(name="NAT", kind="FB", tau=None, p=None), dict(name="NOFB", kind="NOFB", tau=0, p=0.0)]
    for tv in TAU_V:
        c.append(dict(name=f"VIS{int(tv*1000)}", kind="VIS", tau=tv, p=1.0))
    c.append(dict(name="VISEV200", kind="VISEV", tau=0.2, p=1.0))
    for p in PS:
        for d in DELTAS:
            c.append(dict(name=f"ART_d{d}_p{p}", kind="FB", tau=0.074 + d / 1000, p=p))
    return c


def resolve(conds, P):
    out = []
    for c in conds:
        c = dict(c)
        if c["name"] == "NAT":
            c["tau"] = P["nat_tau"]
            c["p"] = P["p_nat"]
        out.append(c)
    return out


def simulate(tr, P, conds, record_name=None, preload=None, debug=False):
    """Vectorised simulation over lanes = conditions x trials x SM. Returns fail codes [C,N,S] (0 ok, 1 drop, 2 crush)."""
    N = tr["N"]
    C = len(conds)
    nl = C * N * NS
    lane = np.arange(nl)
    ci = lane // (N * NS)
    ti = (lane // NS) % N
    si = lane % NS
    kind = np.array([c["kind"] for c in conds])
    is_fb = (kind == "FB")[ci]
    is_vis = (kind == "VIS")[ci]
    is_visev = (kind == "VISEV")[ci]
    pl = np.array([c["p"] for c in conds], dtype=float)[ci]
    taul = np.array([int(round(c["tau"] / DT)) for c in conds], dtype=np.int64)[ci]
    rec_c = [i for i, c in enumerate(conds) if c["name"] == record_name]
    rec_c = rec_c[0] if rec_c else -1

    st = dict(idx=lane, ti=ti, sm=SM_GRID[si], m=tr["m"][ti], mu=tr["mu"][ti], mg=tr["mg"][ti], gc=tr["Gcrush"][ti],
              fb=is_fb, vis=is_vis, visev=is_visev, p=pl, tau=taul,
              G=np.zeros(nl), v=np.zeros(nl), s=np.zeros(nl), muh=np.full(nl, P["mu_prior"]), Lfb=np.zeros(nl),
              last=np.full(nl, -10**9, dtype=np.int64), noS=np.full(nl, 10**6, dtype=np.int64),
              evc=np.zeros(nl, dtype=np.int64), crossed=np.zeros(nl, bool), pany=np.zeros(nl, bool),
              pmu=np.full(nl, np.inf), pL=np.zeros(nl), sref=np.zeros(nl))
    if debug:
        st["first_ev"] = np.full(nl, -1, dtype=np.int64)
        st["first_del"] = np.full(nl, -1, dtype=np.int64)
    fail = np.zeros(nl, dtype=np.int8)
    fstep = np.full(nl, -1, dtype=np.int32)
    pos = np.arange(nl)
    sched = defaultdict(list)
    if preload is not None:
        for step, ln, muc, Lc in preload:
            sched[int(step)].append((ln, muc, Lc))
    records = []
    decay = np.exp(-DT / 0.3)
    hold_steps = int(round(0.5 / DT))
    ev_gap = int(round(0.020 / DT))
    L_all, xi_all = tr["L"], tr["xi"]
    first_del_dbg = {}

    def push(step_arr, ln, muc, Lc):
        for sv in np.unique(step_arr):
            if sv >= NSTEP:
                continue
            k = step_arr == sv
            sched[int(sv)].append((ln[k], muc[k], Lc[k]))

    n_alive = nl
    for n in range(NSTEP):
        t = n * DT
        a = st
        # (a) deliveries
        if n in sched:
            for ln, muc, Lc in sched.pop(n):
                p = pos[ln]
                ok = p >= 0
                if not ok.any():
                    continue
                p, muc, Lc = p[ok], muc[ok], Lc[ok]
                np.minimum.at(a["muh"], p, muc)
                np.maximum.at(a["Lfb"], p, Lc)
                a["last"][p] = n
                if debug:
                    fd = a["first_del"]
                    fd[p] = np.where(fd[p] < 0, n, fd[p])
        # (b) reactive hold / decay
        dec = (n - a["last"]) > hold_steps
        a["Lfb"] = np.where(dec, a["Lfb"] * decay, a["Lfb"])
        # (c) grip command and dynamics
        ramp_lead = min(max((t + 0.2 - 0.5) / 0.3, 0.0), 1.0)
        Gcmd = (1 + a["sm"]) * np.maximum(a["mg"] * ramp_lead, a["Lfb"]) / (2 * a["muh"])
        a["G"] = a["G"] + DT * (Gcmd - a["G"]) / P["tau_m"]
        Geff = a["G"] * (1 + P["noise"] * xi_all[n][a["ti"]])
        L = L_all[n][a["ti"]]
        # (d) slip physics
        S = L > 2 * a["mu"] * Geff
        s_prev = a["s"]
        a["v"], a["s"] = slip_update(S, L, Geff, a["mu"], a["m"], a["v"], a["s"])
        # (e) failure
        drop = a["s"] > P["drop"]
        crush = Geff > a["gc"]
        # (f) events and feedback
        event = S & (a["noS"] >= ev_gap)
        a["noS"] = np.where(S, 0, a["noS"] + 1)
        if event.any():
            e = np.nonzero(event)[0]
            evi = np.minimum(a["evc"][e], NDET - 1)
            a["evc"][e] += 1
            if debug:
                fe = a["first_ev"]
                fe[e] = np.where(fe[e] < 0, n, fe[e])
            det = tr["udet"][a["ti"][e], evi] < a["p"][e]
            e, evi = e[det], evi[det]
            if e.size:
                muc = 0.9 * L[e] / (2 * np.maximum(Geff[e], 1e-12))
                if P["predictive"]:
                    fut = np.minimum(n + a["tau"][e], NSTEP - 1)
                    Lc = L_all[fut, a["ti"][e]]
                else:
                    Lc = L[e]
                fbm = a["fb"][e]
                if fbm.any():
                    push(n + a["tau"][e][fbm], a["idx"][e][fbm], muc[fbm], Lc[fbm])
                    if rec_c >= 0:
                        lanes = a["idx"][e][fbm]
                        r = (lanes // (N * NS)) == rec_c
                        if r.any():
                            records.append((lanes[r], evi[fbm][r], muc[fbm][r], Lc[fbm][r]))
                vm = a["vis"][e] | a["visev"][e]
                if vm.any():
                    ev_, muc_, Lc_ = e[vm], muc[vm], Lc[vm]
                    now = a["vis"][ev_] & a["crossed"][ev_]
                    if now.any():
                        push(n + a["tau"][ev_[now]], a["idx"][ev_[now]], muc_[now], Lc_[now])
                    pe, pm, pL_ = ev_[~now], muc_[~now], Lc_[~now]
                    newp = ~a["pany"][pe]
                    a["sref"][pe[newp]] = s_prev[pe[newp]]
                    a["pmu"][pe] = np.minimum(a["pmu"][pe], pm)
                    a["pL"][pe] = np.maximum(a["pL"][pe], pL_)
                    a["pany"][pe] = True
        # vision crossing
        vis_any = a["vis"] | a["visev"]
        if vis_any.any():
            cross_cum = a["vis"] & ~a["crossed"] & (a["s"] > P["s_vis"])
            cross_ev = a["visev"] & a["pany"] & ((a["s"] - a["sref"]) > P["s_vis"])
            a["crossed"] = a["crossed"] | cross_cum
            fire = (cross_cum | cross_ev) & a["pany"]
            if fire.any():
                f = np.nonzero(fire)[0]
                push(n + a["tau"][f], a["idx"][f], a["pmu"][f], a["pL"][f])
                a["pany"][f] = False
                a["pmu"][f] = np.inf
                a["pL"][f] = 0.0
        # record failures and compact
        ft = np.where(drop, 1, np.where(crush, 2, 0)).astype(np.int8)
        done = ft > 0
        if done.any():
            fail[a["idx"][done]] = ft[done]
            fstep[a["idx"][done]] = n
            keep = ~done
            # failed lanes are frozen: removed from the active set (trial ends at first failure)
            pos[a["idx"][done]] = -1
            if debug:
                for k in ("first_ev", "first_del"):
                    first_del_dbg.setdefault(k, {}).update(dict(zip(a["idx"][done].tolist(), a[k][done].tolist())))
            st = {k: vv[keep] for k, vv in a.items()}
            pos[st["idx"]] = np.arange(st["idx"].size)
        if st["idx"].size == 0:
            break
    out = dict(fail=fail.reshape(C, N, NS), fstep=fstep.reshape(C, N, NS), records=records)
    if debug:
        fe = np.full(nl, -1, dtype=np.int64)
        fd = np.full(nl, -1, dtype=np.int64)
        fe[st["idx"]] = st["first_ev"]
        fd[st["idx"]] = st["first_del"]
        for k, arr in (("first_ev", fe), ("first_del", fd)):
            for ln, val in first_del_dbg.get(k, {}).items():
                arr[ln] = val
        out["first_ev"] = fe.reshape(C, N, NS)
        out["first_del"] = fd.reshape(C, N, NS)
    return out


def shuffled_preload(tr, records, n_cond_offset=0):
    """Build delivery list for the SHUF control from ART(0,.95) records (lane ids relative to their condition)."""
    N = tr["N"]
    pre = []
    if not records:
        return pre
    ln = np.concatenate([r[0] for r in records]) % (N * NS)
    evi = np.concatenate([r[1] for r in records])
    muc = np.concatenate([r[2] for r in records])
    Lc = np.concatenate([r[3] for r in records])
    ti = ln // NS
    step = np.minimum((tr["ushuf"][ti, evi] * NSTEP).astype(np.int64), NSTEP - 1)
    ln = ln + n_cond_offset * N * NS
    for sv in np.unique(step):
        k = step == sv
        pre.append((sv, ln[k], muc[k], Lc[k]))
    return pre


def run_conditions(tr, P, conds, batch=8, record_name=None):
    res = {}
    recs = []
    for b in range(0, len(conds), batch):
        cb = conds[b:b + batch]
        o = simulate(tr, P, cb, record_name=record_name)
        for i, c in enumerate(cb):
            res[c["name"]] = o["fail"][i]
        recs += o["records"]
    return res, recs


# ----------------------------------------------------------------------------------------------
def fstar(fail_ns):
    rate = (fail_ns > 0).mean(axis=0)
    j = int(np.argmin(rate))
    return dict(F=float(rate[j]), SM_opt=float(SM_GRID[j]), drop=float((fail_ns[:, j] == 1).mean()),
                crush=float((fail_ns[:, j] == 2).mean()), rate_by_SM=rate.round(5).tolist())


def delta_star(R, deltas=DELTAS):
    R = np.asarray(R, dtype=float)
    if np.any(~np.isfinite(R)):
        return np.nan
    ok = np.nonzero(R >= 0.5)[0]
    if ok.size == 0:
        return -np.inf
    i = ok[-1]
    if i == len(deltas) - 1:
        return np.inf
    r0, r1 = R[i], R[i + 1]
    return deltas[i] + (r0 - 0.5) / (r0 - r1) * (deltas[i + 1] - deltas[i])


def fmt_delta(d):
    if np.isnan(d):
        return "undefined"
    if d == np.inf:
        return "> 300"
    if d == -np.inf:
        return "< -20"
    return round(float(d), 1)


def pct_ci(x, lo=0.025, hi=0.975):
    x = np.sort(np.asarray(x, dtype=float)[~np.isnan(np.asarray(x, dtype=float))])
    if x.size == 0:
        return [None, None]
    a = x[int(np.floor(lo * x.size))]
    b = x[min(int(np.ceil(hi * x.size)) - 1, x.size - 1)]
    return [fmt_delta(a) if np.isinf(a) else float(a), fmt_delta(b) if np.isinf(b) else float(b)]


def boot_weights(N, B, seed):
    rng = np.random.default_rng(seed)
    W = np.empty((B, N), dtype=np.float32)
    for b in range(B):
        W[b] = np.bincount(rng.integers(0, N, N), minlength=N)
    return W


def boot_fstar(W, fail_ns):
    rates = W @ (fail_ns > 0).astype(np.float32) / fail_ns.shape[0]
    return rates.min(axis=1)


def R_of(Fnofb, Fnat, Fart):
    den = Fnofb - Fnat
    return np.where(den > 0, (Fnofb - Fart) / np.where(den > 0, den, 1), np.nan)


def analyse_delta(res, P_names=("NAT", "NOFB"), p=0.95):
    Fn = fstar(res["NOFB"])["F"]
    Fa = fstar(res["NAT"])["F"]
    R = [float(R_of(Fn, Fa, fstar(res[f"ART_d{d}_p{p}"])["F"])) for d in DELTAS]
    return R, delta_star(R), Fn, Fa


# ----------------------------------------------------------------------------------------------
def self_test():
    ok = {}
    # 1. slip physics: free slip with zero grip matches the discrete analytic displacement
    m, mu, L = 0.3, 0.5, 1.0
    v = np.zeros(1); s = np.zeros(1)
    n = 50
    for _ in range(n):
        v, s = slip_update(np.array([True]), np.array([L]), np.array([0.0]), mu, m, v, s)
    a = L / m
    ok["free_slip_analytic"] = bool(abs(s[0] - a * DT**2 * n * (n + 1) / 2) < 1e-12)
    # 2. no slip when friction holds: s and v stay 0
    v = np.zeros(1); s = np.zeros(1)
    for _ in range(50):
        Sx = np.array([L > 2 * mu * 2.0])
        v, s = slip_update(Sx, np.array([L]), np.array([2.0]), mu, m, v, s)
    ok["no_slip_when_held"] = bool(s[0] == 0 and v[0] == 0)
    # 3. OU stationary variance ~1, lag-100ms autocorr ~ e^-1
    z = np.random.default_rng(1).standard_normal((NSTEP, 400))
    xi = ou_path(z)
    var = xi[500:].var()
    ac = np.mean(xi[500:-50] * xi[550:]) / var
    ok["ou_variance"] = bool(abs(var - 1) < 0.05)
    ok["ou_autocorr_100ms"] = bool(abs(ac - np.exp(-1)) < 0.05)
    # 4. trapezoid area = amp*(plateau + rise/2 + fall/2)
    u = np.arange(-0.1, 0.5, 1e-5)
    ok["pulse_area"] = bool(abs(trapezoid(u).sum() * 1e-5 - 0.23) < 1e-4)
    # 5. zero perturbation, high friction, no noise: no slip events, no failure, grip settles at (1+SM) mg/(2 mu_hat)
    P = dict(DEFAULT, K_zero=True, noise=0.0)
    tr = make_trials(20, P, seed=5)
    tr["mu"][:] = 1.0
    tr["Gcrush"] = 10 * tr["mg"] / (2 * tr["mu"])
    o = simulate(tr, P, resolve([dict(name="NAT", kind="FB", tau=None, p=None)], P), debug=True)
    ok["zero_perturbation_no_slip"] = bool((o["fail"] == 0).all() and (o["first_ev"] == -1).all())
    # 6. CRN: ART with p = 0 is identical to NOFB
    P = dict(DEFAULT)
    tr = make_trials(200, P, seed=7)
    o = simulate(tr, P, [dict(name="NOFB", kind="NOFB", tau=0, p=0.0), dict(name="A0", kind="FB", tau=0.1, p=0.0)])
    ok["crn_p0_equals_nofb"] = bool(np.array_equal(o["fail"][0], o["fail"][1]))
    # 7. delivery delay: first delivery exactly tau after first event when p = 1
    o = simulate(tr, P, [dict(name="A", kind="FB", tau=0.074, p=1.0)], debug=True)
    fe, fd = o["first_ev"][0], o["first_del"][0]
    m_ = (fe >= 0) & (fd >= 0)
    ok["delay_exact_tau"] = bool(m_.sum() > 50 and np.all(fd[m_] - fe[m_] == 37))
    # 8. delta* interpolation
    ok["delta_star_interp"] = bool(abs(delta_star([1, 1, .9, .7, .5, .3, .2, .1, 0]) - 75) < 1e-9 and
                                   abs(delta_star([1, 1, .9, .7, .6, .4, .2, .1, 0]) - 87.5) < 1e-9 and
                                   delta_star([1] * 9) == np.inf and delta_star([.4] * 9) == -np.inf)
    ok["poisson_ppf_mean"] = bool(abs(poisson_ppf(np.random.default_rng(3).uniform(size=200000), 2.0).mean() - 2) < 0.02)
    return ok


# ----------------------------------------------------------------------------------------------
def to_json(o):
    if isinstance(o, dict):
        return {str(k): to_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_json(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else str(f)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return to_json(o.tolist())
    return o


def run_main(N=4000):
    t0 = time.time()
    P = dict(DEFAULT)
    out = dict(prereg="P1_grip_latency_budget.md", seed=SEED, N=N)
    tr = make_trials(N, P)
    conds = resolve(cond_list_main(), P)
    res, recs = run_conditions(tr, P, conds, batch=8, record_name="ART_d0_p0.95")
    t_main = time.time() - t0
    # shuffled control
    pre = shuffled_preload(tr, recs)
    o = simulate(tr, P, [dict(name="SHUF", kind="SHUF", tau=0, p=0.0)], preload=pre)
    res["SHUF"] = o["fail"][0]
    # zero-perturbation control
    Pz = dict(P, K_zero=True)
    trz = make_trials(N, Pz)
    rz, _ = run_conditions(trz, Pz, resolve([dict(name="NAT", kind="FB", tau=None, p=None),
                                             dict(name="NOFB", kind="NOFB", tau=0, p=0.0)], Pz))
    out["zero_perturbation"] = {k: fstar(v) for k, v in rz.items()}
    out["zero_perturbation_pass"] = bool(all(v["F"] <= 0.01 for v in out["zero_perturbation"].values()))
    # point estimates
    out["Fstar"] = {k: fstar(v) for k, v in res.items()}
    F = {k: v["F"] for k, v in out["Fstar"].items()}
    Rc = {}
    for p in PS:
        Rc[str(p)] = [float(R_of(F["NOFB"], F["NAT"], F[f"ART_d{d}_p{p}"])) for d in DELTAS]
    out["R_curves"] = dict(deltas=DELTAS, **Rc)
    dstar = delta_star(Rc["0.95"])
    out["delta_star"] = fmt_delta(dstar)
    out["delta_star_p"] = {str(p): fmt_delta(delta_star(Rc[str(p)])) for p in PS}
    G0 = (F["NAT"] <= 0.5 * F["NOFB"]) and (F["NAT"] >= 0.005)
    out["G0"] = dict(holds=bool(G0), F_NAT=F["NAT"], F_NOFB=F["NOFB"], ratio=F["NAT"] / F["NOFB"] if F["NOFB"] > 0 else None)
    out["R_shuffled"] = float(R_of(F["NOFB"], F["NAT"], F["SHUF"]))
    out["shuffled_control_pass"] = bool(out["R_shuffled"] < 0.5)
    out["R_VIS"] = {k: float(R_of(F["NOFB"], F["NAT"], F[k])) for k in ("VIS150", "VIS200", "VIS250", "VISEV200")}
    # bootstrap
    B = 1000
    W = boot_weights(N, B, SEED + 1)
    bF = {k: boot_fstar(W, v) for k, v in res.items()}
    out["Fstar_CI95"] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in bF.items()}
    Rb = np.stack([R_of(bF["NOFB"], bF["NAT"], bF[f"ART_d{d}_p0.95"]) for d in DELTAS], axis=1)  # B x 9
    out["R_CI95_p0.95"] = [[float(np.nanpercentile(Rb[:, j], 2.5)), float(np.nanpercentile(Rb[:, j], 97.5))] for j in range(len(DELTAS))]
    ds = np.array([delta_star(Rb[b]) for b in range(200)])
    out["delta_star_boot"] = dict(n=200, CI95=pct_ci(ds), n_undefined=int(np.isnan(ds).sum()),
                                  n_gt300=int((ds == np.inf).sum()), n_lt_m20=int((ds == -np.inf).sum()),
                                  median=fmt_delta(np.nanmedian(ds)) if np.any(~np.isnan(ds)) else None)
    ratio_b = bF["ART_d100_p0.95"] / np.where(bF["VIS200"] > 0, bF["VIS200"], np.nan)
    ratio = F["ART_d100_p0.95"] / F["VIS200"] if F["VIS200"] > 0 else np.nan
    out["H3b"] = dict(F_ART100=F["ART_d100_p0.95"], F_VIS200=F["VIS200"], ratio=ratio,
                      ratio_CI95=[float(np.nanpercentile(ratio_b, 2.5)), float(np.nanpercentile(ratio_b, 97.5))],
                      verdict="PASS" if ratio <= 0.8 else "FAIL")
    out["H3b"]["CI_straddles_0.8"] = bool(out["H3b"]["ratio_CI95"][0] <= 0.8 <= out["H3b"]["ratio_CI95"][1])
    out["G0_boot_frac_holds"] = float(np.mean((bF["NAT"] <= 0.5 * bF["NOFB"]) & (bF["NAT"] >= 0.005)))
    # verdict H3
    ci = out["delta_star_boot"]["CI95"]
    def num(x):
        return np.inf if x == "> 300" else (-np.inf if x == "< -20" else float(x))
    if not G0:
        v = "G0 FAILED (see redesign)"
    else:
        lo, hi = num(ci[0]), num(ci[1])
        if 50 <= lo and hi <= 150 and np.isfinite(dstar) and 50 <= dstar <= 150:
            v = "PASS"
        elif lo <= 50 <= hi or lo <= 150 <= hi:
            v = "INCONCLUSIVE"
        else:
            v = "FAIL"
    out["H3_verdict"] = v
    # redesign if G0 fails
    if not G0:
        Pr = dict(P, amp_lo=0.4, amp_hi=1.0, c_lo=1.3, c_hi=2.0)
        trr = make_trials(N, Pr)
        rr, _ = run_conditions(trr, Pr, resolve([c for c in cond_list_main() if c["name"] in
                                                 ["NAT", "NOFB", "VIS200"] + [f"ART_d{d}_p0.95" for d in DELTAS]], Pr))
        Fr = {k: fstar(v)["F"] for k, v in rr.items()}
        G0r = (Fr["NAT"] <= 0.5 * Fr["NOFB"]) and (Fr["NAT"] >= 0.005)
        Rr = [float(R_of(Fr["NOFB"], Fr["NAT"], Fr[f"ART_d{d}_p0.95"])) for d in DELTAS]
        out["redesign"] = dict(Fstar={k: fstar(v) for k, v in rr.items()}, G0=bool(G0r), R=Rr, delta_star=fmt_delta(delta_star(Rr)))
        if not G0r:
            out["H3_verdict"] = "ABANDONED: open-loop margin suffices; latency question not addressable with this task"
        else:
            Wr = W
            bFr = {k: boot_fstar(Wr, v) for k, v in rr.items()}
            Rbr = np.stack([R_of(bFr["NOFB"], bFr["NAT"], bFr[f"ART_d{d}_p0.95"]) for d in DELTAS], axis=1)
            dsr = np.array([delta_star(Rbr[b]) for b in range(200)])
            cir = pct_ci(dsr)
            out["redesign"]["delta_star_CI95"] = cir
            dr = delta_star(Rr)
            lo, hi = num(cir[0]), num(cir[1])
            if 50 <= lo and hi <= 150 and 50 <= dr <= 150:
                out["H3_verdict"] = "PASS (redesign)"
            elif lo <= 50 <= hi or lo <= 150 <= hi:
                out["H3_verdict"] = "INCONCLUSIVE (redesign)"
            else:
                out["H3_verdict"] = "FAIL (redesign)"
    out["runtime_s"] = round(time.time() - t0, 1)
    out["runtime_main_conditions_s"] = round(t_main, 1)
    with open(os.path.join(RES, "p1_grip_latency.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    np.savez_compressed(os.path.join(RES, "p1_boot_R.npz"), Rb=Rb, ds=ds)
    return out


SENS = [("tau_m=20ms", dict(tau_m=0.020)), ("tau_m=80ms", dict(tau_m=0.080)),
        ("drop=5mm", dict(drop=0.005)), ("drop=20mm", dict(drop=0.020)),
        ("amp U(0.1,0.4)", dict(amp_lo=0.1, amp_hi=0.4)), ("amp U(0.4,1.0)", dict(amp_lo=0.4, amp_hi=1.0)),
        ("Poisson 1", dict(pois=1.0)), ("Poisson 4", dict(pois=4.0)),
        ("c U(1.3,2.0)", dict(c_lo=1.3, c_hi=2.0)), ("c U(2.0,4.0)", dict(c_lo=2.0, c_hi=4.0)),
        ("noise 0", dict(noise=0.0)), ("noise 0.1", dict(noise=0.1)),
        ("NAT tau 50ms", dict(nat_tau=0.050)), ("NAT tau 100ms", dict(nat_tau=0.100)),
        ("mu_prior 0.4", dict(mu_prior=0.4)), ("mu_prior 1.1", dict(mu_prior=1.1)),
        ("p_det_NAT 0.8", dict(p_nat=0.8)), ("p_det_NAT 1.0", dict(p_nat=1.0)),
        ("predictive (Smith)", dict(predictive=True))]


def run_sens(N=1000):
    t0 = time.time()
    rows = []
    names = ["NAT", "NOFB"] + [f"ART_d{d}_p0.95" for d in DELTAS]
    for label, ch in [("baseline (N=1000)", {})] + SENS:
        P = dict(DEFAULT, **ch)
        tr = make_trials(N, P)
        conds = resolve([c for c in cond_list_main() if c["name"] in names], P)
        res, _ = run_conditions(tr, P, conds, batch=11)
        R, ds, Fn, Fa = analyse_delta(res)
        G0 = (Fa <= 0.5 * Fn) and (Fa >= 0.005)
        rows.append(dict(config=label, F_NOFB=Fn, F_NAT=Fa, G0=bool(G0), R=R, delta_star=fmt_delta(ds),
                         in_50_150=bool(G0 and np.isfinite(ds) and 50 <= ds <= 150),
                         SM_opt_NOFB=fstar(res["NOFB"])["SM_opt"], SM_opt_NAT=fstar(res["NAT"])["SM_opt"]))
        print(label, rows[-1]["delta_star"], "G0", G0, f"{time.time()-t0:.0f}s", flush=True)
    cfg = [r for r in rows if not r["config"].startswith("baseline")]
    frac = float(np.mean([r["in_50_150"] for r in cfg]))
    out = dict(N=N, rows=rows, frac_in_50_150=frac, n_configs=len(cfg), robust=bool(frac >= 0.7),
               runtime_s=round(time.time() - t0, 1))
    with open(os.path.join(RES, "p1_grip_latency_sensitivity.json"), "w") as f:
        json.dump(to_json(out), f, indent=1)
    return out


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with open(os.path.join(RES, "p1_grip_latency.json")) as f:
        o = json.load(f)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    a = ax[0]
    a.axvspan(50, 150, color="#dfe8f5", label="predicted δ* range [50,150] ms")
    a.axhline(0.5, color="k", ls="--", lw=1, label="R = 0.5")
    ci = np.array(o["R_CI95_p0.95"], dtype=float)
    a.fill_between(DELTAS, ci[:, 0], ci[:, 1], color="#1f5fa8", alpha=0.18, label="95% CI (p=0.95)")
    for p, col in zip(PS, ["#bdbdbd", "#6b8fc2", "#1f5fa8"]):
        a.plot(DELTAS, o["R_curves"][str(p)], "o-", color=col, label=f"ART, p_det = {p}")
    a.plot([0], [o["R_shuffled"]], "x", color="#c0392b", ms=10, mew=2, label="shuffled-feedback control")
    for k, mk in (("VIS150", "s"), ("VIS200", "D"), ("VIS250", "^")):
        a.axhline(o["R_VIS"][k], color="#7a7a7a", lw=0.8, ls=":")
        pass
    a.set_xlabel("added latency δ vs natural 74 ms (ms)")
    a.set_ylabel("benefit retained R = (F*NOFB − F*ART)/(F*NOFB − F*NAT)")
    ci_ = [round(float(x), 1) if not isinstance(x, str) else x for x in o['delta_star_boot']['CI95']]
    a.set_title(f"P1: R vs added latency (δ* = {o['delta_star']} ms, 95% CI {ci_})\nG0 validity gate {'holds' if o['G0']['holds'] else 'FAILS'}: F*NAT/F*NOFB = {o['G0']['ratio']:.2f} (needs ≤ 0.5)", fontsize=9)
    a.legend(fontsize=7, loc="lower left")
    b = ax[1]
    keys = ["NOFB", "NAT", "VIS150", "VIS200", "VIS250"] + [f"ART_d{d}_p0.95" for d in DELTAS] + ["SHUF"]
    Fv = [o["Fstar"][k]["F"] for k in keys]
    cl = np.array([o["Fstar_CI95"][k] for k in keys])
    b.bar(range(len(keys)), Fv, color=["#7a7a7a", "#2e7d32"] + ["#b8860b"] * 3 + ["#1f5fa8"] * len(DELTAS) + ["#c0392b"])
    b.errorbar(range(len(keys)), Fv, yerr=[np.array(Fv) - cl[:, 0], cl[:, 1] - np.array(Fv)], fmt="none", ecolor="k", lw=1)
    b.set_xticks(range(len(keys)))
    b.set_xticklabels([k.replace("_p0.95", "").replace("ART_d", "ART δ=") for k in keys], rotation=70, fontsize=7)
    b.set_ylabel("failure rate F* at optimal safety margin")
    b.set_title("F* per condition (95% bootstrap CI)", fontsize=10)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(FIG, f"p1_R_vs_delta.{ext}"), dpi=150)
    plt.close(fig)
    sp = os.path.join(RES, "p1_grip_latency_sensitivity.json")
    if os.path.exists(sp):
        with open(sp) as f:
            s = json.load(f)
        fig, a = plt.subplots(figsize=(8, 6))
        rows = s["rows"]
        vals = []
        for r in rows:
            d = r["delta_star"]
            vals.append(320 if d == "> 300" else (-40 if d == "< -20" else (np.nan if d == "undefined" else float(d))))
        y = np.arange(len(rows))
        a.axvspan(50, 150, color="#dfe8f5")
        cols = ["#1f5fa8" if r["G0"] else "#c0392b" for r in rows]
        a.scatter(vals, y, c=cols, zorder=3)
        a.set_yticks(y)
        a.set_yticklabels([r["config"] for r in rows], fontsize=8)
        a.set_xlabel("δ* (ms); plotted at 320 if > 300, at −40 if < −20")
        a.set_title(f"P1 sensitivity (N=1000): δ* in [50,150] in {s['frac_in_50_150']*100:.0f}% of configs (red = G0 fails)", fontsize=9)
        a.invert_yaxis()
        fig.tight_layout()
        for ext in ("png", "svg"):
            fig.savefig(os.path.join(FIG, f"p1_sensitivity.{ext}"), dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(RES, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    if mode in ("test", "all"):
        r = self_test()
        print("SELF-TEST", r, "ALL PASS" if all(r.values()) else "FAILURES")
        with open(os.path.join(RES, "p1_selftest.json"), "w") as f:
            json.dump(r, f, indent=1)
        if not all(r.values()):
            sys.exit(1)
    if mode in ("main", "all"):
        o = run_main()
        print(json.dumps(to_json({k: o[k] for k in ("G0", "delta_star", "delta_star_boot", "H3_verdict", "H3b",
                                                     "R_shuffled", "zero_perturbation_pass", "runtime_s")}), indent=1))
    if mode in ("sens", "all"):
        s = run_sens()
        print("frac in [50,150]:", s["frac_in_50_150"], "runtime", s["runtime_s"])
    if mode in ("fig", "main", "sens", "all"):
        figures()
