r"""M1 runner: offline motor-decoder comparison, exactly per prereg\M1_decoder_comparison.md (LOCKED, SHA 9eada9d7...).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Computational decoding of recorded activity only.

Usage (venv python):
  run_m1.py --dry            dry run on MC_Maze_Small (DANDI 000140; D1 pipeline only; not part of any verdict)
  run_m1.py --tag run1       real run  -> results\M1_card_run1.json (+ split lock, frozen models, log)
  run_m1.py --tag rerun      fresh-process rerun -> results\M1_card_rerun.json (card hash must be identical)
Deviations: code\DEVIATIONS.md.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"          # BLAS threads = 1 (owner rule; nfharness pin_blas_threads concept) BEFORE numpy

import argparse  # noqa: E402
import csv  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from importlib.metadata import PackageNotFoundError, version  # noqa: E402

import numpy as np  # noqa: E402
from scipy.signal import butter, sosfiltfilt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from m1lib import NB_CODE, RAW, ROOT, SEED  # noqa: E402
from m1lib import data as D  # noqa: E402
from m1lib import decoders as DEC  # noqa: E402
from m1lib import metrics as MET  # noqa: E402
from m1lib.guards import (GUARD_CALLS, CausalFeatureError, FeatureWhitelistError, LabelVault,  # noqa: E402
                          RandomSplitForbiddenError, SessionOrderError, ZScore, assert_bins_disjoint,
                          assert_causal_blocks, assert_file_hash, assert_input_lock, assert_session_order,
                          assert_trial_disjoint, assert_whitelist, causal_whitelist, chrono_split, feature_names,
                          lag_offsets, lagged, random_bin_split, sha256_file)
from nfharness.config import rng as nf_rng  # noqa: E402  (SeedSequence(20261001, spawn_key=(k, ...)))
from nfharness.provenance import card_hash, dumps, peak_rss_mb  # noqa: E402

PREREG = os.path.join(ROOT, "prereg", "M1_decoder_comparison.md")
PREREG_SHA = "9eada9d79c849b2c5572dd4eb629ef29d0dc9b294e8933a05de674a8bd4bd06f"
INPUT_LOCK = ("000138|0.220113.0407|e67b57b2-e9ad-4d95-b9e3-1262997360dc\n"
              "001201|0.251023.2336|c002a9a1-664d-4a69-af02-ba810046c4fb,9d1820f1-7583-4faf-bbd0-7e9fb7001ca4,"
              "ea07a2e3-d5f4-4036-9b62-93d1f89cba64,9c0ac931-d97e-464b-a134-c366b7c84727,b424f116-7827-4ab0-80ed-1e8951eea67a,"
              "88039197-6170-4d06-ba3e-f58b68c6eb7f,b9868d49-f641-4b95-a8e3-6295111b958b,9db3b62a-6fea-493b-98bf-2f6ded6eefec,"
              "1a7aadf8-eb08-427b-93e3-8df11d71ae9e\n"
              "eegmmidb|1.0.0|S001-S020|R04,R08,R12")
INPUT_LOCK_SHA = "aa0f8e1b4e86c93b8bb14c108046dcab1d2ae798806cd21d74e5065388e65d7a"
MANIFEST = os.path.join(ROOT, "data", "manifests", "motor_manifest.csv")
RES = os.path.join(ROOT, "results")
RUO = ("RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or "
       "treatment decisions may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical "
       "use requires regulatory clearance and clinical validation (IRB/ethics approval).")
SESSIONS = [("20200127", 0), ("20200130", 3), ("20200204", 8), ("20200211", 15), ("20200228", 32), ("20200626", 151),
            ("20200924", 241), ("20210223", 393), ("20220126", 730)]
B_BOOT = 2000
N_NULL = 200
GRU_SEEDS = (20261001, 20261002, 20261003)
CFG = dict(gru_seeds=GRU_SEEDS, d3=True, cuts=[])
TAUS_MS = (-500, -250, -100, 0, 100, 250, 500)
BINS_MS = (10, 20, 50, 100)
PKGS = ["numpy", "scipy", "h5py", "torch", "matplotlib", "pytest", "httpx"]
# RNG streams (prereg §8 "seed 20261001 with streams k = 1..6"; assignment logged in DEVIATIONS)
K_BOOT, K_SHUF, K_NULL, K_SIGNFLIP, K_D3PERM, K_PLANT = 1, 2, 3, 4, 5, 6


class Ctx:
    def __init__(self, tag, dry):
        self.tag, self.dry = tag, dry
        self.t0 = time.time()
        self.vault = LabelVault("M1-dry" if dry else "M1")
        self.models = {}          # name -> hash
        self.card = {}
        self.logf = open(os.path.join(RES, "M1_run_log_%s.txt" % tag), "w", encoding="utf-8")

    def log(self, msg):
        line = "%s +%7.1fs %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), time.time() - self.t0, msg)
        print(line, flush=True)
        self.logf.write(line + "\n")
        self.logf.flush()


def rng(k, *sub):
    return nf_rng(k, *sub)


def pkg_versions():
    out = {}
    for p in PKGS:
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def manifest():
    with open(MANIFEST, newline="") as f:
        return {r["path"]: r for r in csv.DictReader(f)}


def check_inputs(ctx, rels):
    man = manifest()
    out = {}
    for rel in rels:
        r = man[rel]
        if r["check"] != "MATCH":
            raise RuntimeError("manifest row not MATCH: %s" % rel)
        out[rel] = assert_file_hash(os.path.join(RAW, rel.replace("/", os.sep)), r["expected_sha256"])
    ctx.log("input hashes verified against DANDI/PhysioNet digests: %d files" % len(out))
    return out


# =====================================================================================================================
# D1 helpers
# =====================================================================================================================
def d1_design_chunks(Z, idx, ks, H, W, chunk=32):
    """Yields lagged designs for window rows of trials idx; Z [S, H+W(+pad), N] z-scored, window starts at row H."""
    for a in range(0, len(idx), chunk):
        yield np.vstack([lagged(Z[s], ks)[H:H + W] for s in idx[a:a + chunk]])


def fit_d1(C, ids, Vtr, Vva, itr, iva, ite, j0, W, H, which):
    """C raw counts [S, nb, N]; V* window targets [n, W, 2]; returns (preds{dec: [n_te, W, 2]}, hashes, info)."""
    N = C.shape[2]
    zs = ZScore().fit(C[itr][:, j0 - H:j0 + W].reshape(-1, N), np.repeat(ids[itr], H + W), ids[itr])
    Z = zs.transform(C[:, j0 - H:j0 + W].astype(np.float64))
    ks = lag_offsets(H)
    assert_whitelist(feature_names("u", N, ks), causal_whitelist("u", N, H))
    preds, hashes, info = {}, {}, {}
    if "ridge" in which:
        rs = DEC.RidgeStream(N * H, 2)
        for a, X in zip(range(0, len(itr), 32), d1_design_chunks(Z, itr, ks, H, W)):
            rs.add(X, Vtr[a:a + 32].reshape(-1, 2))
        cands = rs.finalize()
        m, inf = DEC.select_ridge(cands, lambda: ((X, Vva[a:a + 32].reshape(-1, 2)) for a, X in
                                                 zip(range(0, len(iva), 32), d1_design_chunks(Z, iva, ks, H, W))))
        preds["ridge"] = np.vstack([m.predict(X) for X in d1_design_chunks(Z, ite, ks, H, W)]).reshape(len(ite), W, 2)
        hashes["ridge"], info["ridge"] = m.hash(), inf
    if "kf" in which:
        kf = DEC.KalmanVel().fit([v for v in Vtr], [Z[s, H:] for s in itr])
        preds["kf"] = np.stack([kf.predict(Z[s, H:]) for s in ite])
        vr2 = MET.r2_vw(Vva.reshape(-1, 2), np.stack([kf.predict(Z[s, H:]) for s in iva]).reshape(-1, 2))
        hashes["kf"], info["kf"] = kf.hash(), dict(val_r2=vr2, riccati_iters=kf.riccati_iters)
    if "gru" in which:
        Xs = Z[itr].astype(np.float32)
        Ys = np.concatenate([np.zeros((len(itr), H, 2)), Vtr], axis=1)
        mask = np.zeros((len(itr), H + W))
        mask[:, H:] = 1
        Xva = Z[iva].astype(np.float32)

        def vf(e):
            return MET.r2_vw(Vva.reshape(-1, 2), e.predict_seqs(Xva)[:, H:].reshape(-1, 2))
        ens, ginf = DEC.train_gru(Xs, Ys, mask, vf, seeds=CFG["gru_seeds"])
        preds["gru"] = ens.predict_seqs(Z[ite].astype(np.float32))[:, H:]
        hashes["gru"], info["gru"] = ens.hash(), dict(seeds=ginf, val_r2=float(vf(ens)))
    return preds, hashes, info


def cont_score(y, yh, units, bin_ms, seg_len, rng_null):
    """Pooled M-R2 / rho2 over rows; units = list of (a, b) row ranges (bootstrap units); bits over units of
    length seg_len. Returns (public dict, private dict for bootstraps)."""
    r2 = MET.r2_vw(y, yh)
    st = MET.unit_stats([y[a:b] for a, b in units], [yh[a:b] for a, b in units])
    full = [i for i, (a, b) in enumerate(units) if b - a == seg_len]
    ys = np.stack([y[units[i][0]:units[i][1]] for i in full])
    yhs = np.stack([yh[units[i][0]:units[i][1]] for i in full])
    bits = MET.bits_with_null(ys, yhs, bin_ms, rng_null, n_perm=N_NULL)
    X, Y = MET.seg_spectra(ys, yhs)
    return (dict(r2=r2, rho2=MET.rho2(y, yh), bits=bits, n_rows=int(len(y)), n_units=len(units)),
            dict(st=st, X=X, Y=Y, full=full, null_med=bits["I_null_median"], bin_ms=bin_ms, seg_len=seg_len))


def boot_block(priv, W):
    """Bootstrap replicates of R2 and I_net for one decoder, given shared weights W [B, U]."""
    r2 = MET.r2_from_stats(W, priv["st"])
    mask, df = MET.freq_mask(priv["seg_len"], priv["bin_ms"])
    bits = MET.bits_from_spectra(priv["X"], priv["Y"], mask, df, W=W[:, priv["full"]]) - priv["null_med"]
    return r2, bits


# =====================================================================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--tag", default="run1")
    ap.add_argument("--skip-pytest", action="store_true")
    ap.add_argument("--synthetic", action="store_true", help="D1 = MC_Maze_Small; D2/D3 = synthetic loaders (code-path check)")
    ap.add_argument("--cut", action="append", default=[], choices=["D3", "GRU_SEEDS_1"],
                    help="A4 cuts, in prereg order (logged in DEVIATIONS)")
    a = ap.parse_args()
    tag = "dry" if a.dry else ("synthetic" if a.synthetic else a.tag)
    if a.synthetic:
        from m1lib import synthetic
        synthetic.patch(D)
    if "D3" in a.cut:
        CFG["d3"] = False
        CFG["cuts"].append("A4 cut (1): D3 NOT TESTED")
    if "GRU_SEEDS_1" in a.cut:
        if "D3" not in a.cut:
            raise SystemExit("A4 order: cut D3 before GRU seeds")
        CFG["gru_seeds"] = GRU_SEEDS[:1]
        CFG["cuts"].append("A4 cut (2): GRU seeds 3 -> 1 (20261001)")
    os.makedirs(RES, exist_ok=True)
    ctx = Ctx(tag, a.dry)
    import torch  # noqa: F401  (import cost counted in RSS)
    DEC.torch_setup()
    ctx.log("M1 start tag=%s dry=%s python=%s torch=%s" % (tag, a.dry, sys.version.split()[0], version("torch")))

    # ---------------- 1. prereg + input lock + input hashes
    ph = sha256_file(PREREG)
    if ph != PREREG_SHA:
        raise RuntimeError("prereg SHA mismatch %s" % ph)
    lock = assert_input_lock(INPUT_LOCK, INPUT_LOCK_SHA)
    man = manifest()
    if a.dry or a.synthetic:
        rels = [r for r in man if man[r]["arm"] == "DRY"]
    else:
        rels = [r for r in man if man[r]["arm"] in (("D1", "D2", "D3") if CFG["d3"] else ("D1", "D2"))]
    in_hashes = check_inputs(ctx, sorted(rels))
    card = ctx.card
    card.update(run_id="M1" + ("-dryrun" if a.dry else ("-synthetic" if a.synthetic else "")), ruo=RUO, prereg_sha256=ph, input_lock_sha256=lock,
                inputs=in_hashes, seed=SEED, rng_streams=dict(bootstrap=K_BOOT, nc1_shuffle=K_SHUF, bits_null=K_NULL,
                                                             h6_signflip=K_SIGNFLIP, d3_label_perm=K_D3PERM,
                                                             planted=K_PLANT, gru_seeds=list(CFG["gru_seeds"])))
    card["A4_cuts"] = list(CFG["cuts"])
    code_files = sorted(glob.glob(os.path.join(HERE, "m1lib", "*.py"))) + [os.path.abspath(__file__)] + \
        sorted(glob.glob(os.path.join(HERE, "tests", "*.py")))
    card["code_sha256"] = {os.path.relpath(f, HERE).replace("\\", "/"): sha256_file(f) for f in code_files}
    card["nfharness_sha256_readonly"] = {os.path.basename(f): sha256_file(f) for f in
                                         sorted(glob.glob(os.path.join(NB_CODE, "nfharness", "*.py")))}
    card["nfharness_sha256_readonly"]["edf_reader.py"] = sha256_file(os.path.join(NB_CODE, "edf_reader.py"))
    card["packages"] = pkg_versions()
    card["python"] = sys.version.split()[0]
    card["threads"] = dict(blas_env={v: os.environ.get(v) for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                                     "MKL_NUM_THREADS")},
                           torch_threads=__import__("torch").get_num_threads(),
                           torch_deterministic=__import__("torch").are_deterministic_algorithms_enabled())

    # ---------------- 2. guard suite (pytest)
    if not a.skip_pytest:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", os.path.join(HERE, "tests")],
                           capture_output=True, text=True)
        tail = [l for l in r.stdout.strip().splitlines() if " passed" in l or " failed" in l or " error" in l]
        summ = tail[-1] if tail else r.stdout[-300:]
        import re
        counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|error|errors|skipped)", summ)}
        card["guard_suite"] = dict(returncode=r.returncode, counts=counts, pass_=(r.returncode == 0))
        ctx.log("pytest: %s" % summ.split(" in ")[0])
    else:
        card["guard_suite"] = dict(returncode=None, counts={}, pass_=None, note="skipped (--skip-pytest)")

    # ---------------- 3. trial tables -> splits -> split lock (BEFORE any fit)
    d1path = D.file_paths()[1 if (a.dry or a.synthetic) else 0]
    t1 = D.d1_trials(d1path)
    ids1 = t1["id"]
    p1 = chrono_split(list(ids1.tolist()), t1["start"], t1["stop"])
    lock_parts = {"D1": "train=%s;val=%s;test=%s;gap=%s" % tuple(",".join(map(str, p1[k])) for k in
                                                                  ("train", "val", "test", "gap"))}
    d2tr = {}
    if not a.dry:
        for date, lag in SESSIONS:
            p = os.path.join(RAW, "001201", "sub-Monkey-N_ses-%s_ecephys.nwb" % date)
            t = D.d2_trials(p)
            pp = chrono_split(list(t["id"].tolist()), t["start"], t["stop"])
            d2tr[date] = (p, t, pp)
            lock_parts["D2_%s" % date] = "calib=%s;val=%s;test=%s;gap=%s" % tuple(
                ",".join(map(str, pp[k])) for k in ("train", "val", "test", "gap"))
        for s in (range(1, 21) if CFG["d3"] else []):
            lock_parts["D3_S%03d" % s] = "train=R04,R08;test=R12;inner=R04|R08"
    mazes = sorted(set(t1["maze_id"].tolist()))
    fold_of = {m: i % 5 for i, m in enumerate(mazes)}
    lock_parts["D1_condition_folds"] = ";".join("%d:%d" % (m, fold_of[m]) for m in mazes)
    split_lock = dict(partitions={k: dict(string=v, sha256=hashlib.sha256(v.encode()).hexdigest())
                                  for k, v in lock_parts.items()},
                      grids=dict(ridge_lambda=[float(x) for x in DEC.LAMBDAS], lda_gamma=[0, 0.1, 0.3, 0.5, 0.9],
                                 logreg_C=[float(x) for x in np.logspace(-3, 2, 11)], gru=dict(
                                     h=64, dropout=0.2, lr=1e-3, wd=1e-4, batch=32, max_epochs=50, patience=5,
                                     warmup=10, seeds=list(CFG["gru_seeds"]), threads=4)),
                      code_sha256=card["code_sha256"])
    split_lock["sha256_all"] = hashlib.sha256(dumps(split_lock["partitions"]).encode()).hexdigest()
    lock_path = os.path.join(RES, "M1_split_lock.json" if tag == "run1" else "M1_split_lock_%s.json" % tag)
    with open(lock_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(split_lock))
    card["split_lock_sha256"] = split_lock["sha256_all"]
    card["split_sizes"] = {"D1": {k: len(v) for k, v in p1.items()},
                           **{"D2_" + d: {k: len(v) for k, v in pp.items()} for d, (_, _, pp) in d2tr.items()}}
    ctx.log("split lock written: %s (sha %s)" % (os.path.basename(lock_path), split_lock["sha256_all"][:12]))

    # ================================================================================================= D1 load
    ctx.log("FIRST DATA READ (D1 behaviour + spikes)")
    src = D.D1Source(d1path)
    idx = {int(i): k for k, i in enumerate(ids1)}
    iTR = np.array([idx[i] for i in p1["train"]])
    iVA = np.array([idx[i] for i in p1["val"]])
    iTE = np.array([idx[i] for i in p1["test"]])
    onset = t1["onset"]
    card["D1_facts"] = dict(n_trials=int(len(ids1)), n_units=int(src.n_units), n_spikes=src.n_spikes,
                            vel_nan_samples=src.vel_nan, n_mazes=len(mazes), grid_ms=[-750, 950])
    grids = {}
    for b in (BINS_MS if True else (20,)):
        Cb = src.counts(onset, b)
        Vb = src.velocity(onset, b)
        ctx.vault.deposit(("D1", b), Vb[iTE])
        Vb[iTE] = np.nan
        grids[b] = (Cb, Vb)
    Vtau = {}
    for tau in TAUS_MS:
        if tau == 0:
            continue
        v = src.velocity(onset + tau / 1000.0, 20, rel0_ms=-250, nb=35)
        ctx.vault.deposit(("D1tau", tau), v[iTE])
        v[iTE] = np.nan
        Vtau[tau] = v
    del src
    C20, V20 = grids[20]
    j0, W, H = 25, 35, 10
    Vtr, Vva = V20[iTR][:, j0:j0 + W], V20[iVA][:, j0:j0 + W]
    assert_bins_disjoint({"train": np.repeat(ids1[iTR], W), "val": np.repeat(ids1[iVA], W),
                          "test": np.repeat(ids1[iTE], W)})
    ctx.log("FIRST MODEL FIT (D1 honest)")
    P = {}          # (arm, what) -> predictions
    INFO = {}
    pr, hs, inf = fit_d1(C20, ids1, Vtr, Vva, iTR, iVA, iTE, j0, W, H, ("ridge", "kf", "gru"))
    for k in pr:
        P[("D1", k)] = pr[k]
        ctx.models["D1/" + k] = hs[k]
    INFO["D1"] = inf
    P[("D1", "B0")] = np.repeat(Vtr.mean(0)[None], len(iTE), axis=0)
    ctx.log("D1 honest fitted: val R2 ridge %.3f kf %.3f gru %.3f" % (inf["ridge"]["val_r2"], inf["kf"]["val_r2"],
                                                                      inf["gru"]["val_r2"]))
    a3 = {"D1_ridge_val_r2": inf["ridge"]["val_r2"]}

    # D1 NC1 shuffled alignment (stream 2)
    pi = rng(K_SHUF, 1).permutation(len(iTR))
    piv = rng(K_SHUF, 3).permutation(len(iVA))          # validation pairs shuffled too (no true pair seen)
    pr, hs, inf = fit_d1(C20, ids1, Vtr[pi], Vva[piv], iTR, iVA, iTE, j0, W, H, ("ridge", "kf", "gru"))
    for k in pr:
        P[("D1_NC1", k)] = pr[k]
        ctx.models["D1_NC1/" + k] = hs[k]
    INFO["D1_NC1"] = inf
    ctx.log("D1 NC1 fitted")

    # D1 condition-held-out (descriptive)
    maze = t1["maze_id"]
    cond_pred = {k: np.full((len(iTE), W, 2), np.nan) for k in ("ridge", "kf", "gru")}
    for f in range(5):
        infold = np.array([fold_of[m] == f for m in maze])
        itr_f, iva_f = iTR[~infold[iTR]], iVA[~infold[iVA]]
        te_sel = infold[iTE]
        if te_sel.sum() == 0:
            continue
        pr, hs, _ = fit_d1(C20, ids1, V20[itr_f][:, j0:j0 + W], V20[iva_f][:, j0:j0 + W], itr_f, iva_f, iTE[te_sel],
                           j0, W, H, ("ridge", "kf", "gru"))
        for k in pr:
            cond_pred[k][te_sel] = pr[k]
            ctx.models["D1_cond_f%d/%s" % (f, k)] = hs[k]
    for k in cond_pred:
        P[("D1_cond", k)] = cond_pred[k]
    ctx.log("D1 condition-held-out fitted")

    # D1 bin sweep (ridge, KF; history 200 ms)
    for b in BINS_MS:
        if b == 20:
            continue
        Cb, Vb = grids[b]
        jb, Wb, Hb = 500 // b, 700 // b, 200 // b
        pr, hs, inf = fit_d1(Cb, ids1, Vb[iTR][:, jb:jb + Wb], Vb[iVA][:, jb:jb + Wb], iTR, iVA, iTE, jb, Wb, Hb,
                             ("ridge", "kf"))
        for k in pr:
            P[("D1bin%d" % b, k)] = pr[k]
            ctx.models["D1bin%d/%s" % (b, k)] = hs[k]
        INFO["D1bin%d" % b] = inf
        ctx.log("D1 bin %d ms fitted" % b)
    grids = {20: grids[20]}

    # D1 NC2b lag sweep (ridge, GRU)
    for tau, v in Vtau.items():
        pr, hs, inf = fit_d1(C20, ids1, v[iTR], v[iVA], iTR, iVA, iTE, j0, W, H, ("ridge", "gru"))
        for k in pr:
            P[("D1tau%d" % tau, k)] = pr[k]
            ctx.models["D1tau%d/%s" % (tau, k)] = hs[k]
        INFO["D1tau%d" % tau] = inf
    ctx.log("D1 NC2b lag sweep fitted")

    # ================================================================================================= D2
    D2 = {}
    if not a.dry:
        D2 = run_d2_fit(ctx, d2tr, P, INFO, a3)
    # ================================================================================================= D3
    D3 = dict(tested=False, reason="A4 cut (1)")
    if not a.dry and CFG["d3"]:
        D3 = run_d3_fit(ctx, P, INFO)

    # ---------------- A3 sanity gate (before the vault is opened)
    card["A3"] = dict(values=a3, threshold=0.20, pass_=all(v >= 0.20 for v in a3.values()))
    if not card["A3"]["pass_"]:
        ctx.log("A3 STOP: honest ridge validation R2 < 0.20 %s" % a3)
        return finish(ctx, stopped="A3")

    # ---------------- freeze
    fm = dict(sorted(ctx.models.items()))
    fm_sha = hashlib.sha256(dumps(fm).encode()).hexdigest()
    fpath = os.path.join(RES, "M1_frozen_models_%s.json" % tag)
    with open(fpath, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(dict(models=fm, sha256=fm_sha)))
    ctx.vault.freeze(fm_sha)
    card["frozen_models_sha256"] = fm_sha
    card["n_frozen_models"] = len(fm)
    ctx.log("models frozen: %d hashes -> %s (sha %s)" % (len(fm), os.path.basename(fpath), fm_sha[:12]))

    # ---------------- planted-leak controls (declared vault access, logged)
    PL = {}
    PL["PL1"] = pl1(ctx, C20, ids1, V20, iTR, iVA, iTE, j0, W, H)
    PL["PL3"] = pl3(ctx, C20, ids1, V20, iTR, iVA, iTE, j0, W, H, t1)
    if not a.dry:
        PL["PL2"] = pl2(ctx, D2)
    ctx.log("planted-leak fits done")

    # ================================================================================================= scoring
    ctx.log("VAULT OPEN (final scores)")
    S = score_all(ctx, P, INFO, D2, D3, PL, iTE, j0, W, a.dry)
    card.update(S)
    return finish(ctx)


# =====================================================================================================================
# D2
# =====================================================================================================================
def d2_session(ctx, date, path, t, pp):
    sbp, info = D.d2_neural(path)
    own = D.d2_owner(t, len(sbp))
    part = np.full(len(sbp), "none", dtype="<U5")
    for k, lab in (("train", "calib"), ("val", "val"), ("test", "test"), ("gap", "gap")):
        part[np.isin(own, pp[k])] = lab
    assert_bins_disjoint({lab: own[part == lab] for lab in ("calib", "val", "test", "gap")})
    beh = D.d2_behaviour(path)
    if len(beh) != len(sbp):
        raise RuntimeError("SBP / velocity length mismatch")
    rng_ = {}
    for lab in ("calib", "val", "test"):
        w = np.flatnonzero(part == lab)
        rng_[lab] = (int(w[0]), int(w[-1]) + 1, int((part[w[0]:w[-1] + 1] != lab).sum()))
    te = part == "test"
    ctx.vault.deposit(("D2", date), beh[te])
    beh[te] = np.nan
    test_trials = [int(i) for i in pp["test"]]
    tt_rows = []
    pos = np.flatnonzero(te)
    own_te = own[te]
    for i in test_trials:
        r = np.flatnonzero(own_te == i)
        tt_rows.append((int(r[0]), int(r[-1]) + 1))
    style = sorted(set(t["style"].tolist()))
    return dict(date=date, sbp=sbp, beh=beh, own=own, part=part, ranges=rng_, test_pos=pos, test_trial_rows=tt_rows,
                calib_trials=[int(i) for i in pp["train"]], style=style, bin_info=info, n_bins=int(len(sbp)))


def d2_fit_day(ctx, S, name, which=("ridge", "kf", "gru"), beh_override=None, rows_override=None, val_override=None):
    """Fit decoders on session S calib (selection on val). Returns dict with zs and models."""
    N, H = 96, 6
    part = S["part"]
    cal = np.flatnonzero(part == "calib")
    val = np.flatnonzero(part == "val")
    yval = S["beh"][val]
    if val_override is not None:
        val, yval = val_override
    assert_session_order(0, [0], ["calib", "val"])
    zs = ZScore().fit(S["sbp"][cal], S["own"][cal], S["calib_trials"])
    Z = zs.transform(S["sbp"])
    ks = lag_offsets(H)
    assert_whitelist(feature_names("sbp", N, ks), causal_whitelist("sbp", N, H))
    L = lagged(Z, ks)
    beh = S["beh"] if beh_override is None else beh_override
    out = dict(zs=zs, info={})
    X_rows, Y_rows = (L[cal], S["beh"][cal]) if rows_override is None else (L[rows_override[0]], rows_override[1])
    if "ridge" in which:
        m, inf = DEC.fit_ridge_select(X_rows, Y_rows, lambda mm: (yval, mm.predict(L[val])))
        out["ridge"], out["info"]["ridge"] = m, inf
        ctx.models["%s/ridge" % name] = m.hash()
    ca, cb, _ = S["ranges"]["calib"]
    va, vb, _ = S["ranges"]["val"]
    if "kf" in which:
        if rows_override is None:
            segs = [(Z[ca:cb], beh[ca:cb])]
        else:
            segs = rows_override[2]
        kf = DEC.KalmanVel().fit([s[1] for s in segs], [s[0] for s in segs])
        vr = MET.r2_vw(yval, kf.predict(Z[va:vb])[val - va])
        out["kf"], out["info"]["kf"] = kf, dict(val_r2=vr, riccati_iters=kf.riccati_iters)
        ctx.models["%s/kf" % name] = kf.hash()
    if "gru" in which:
        if rows_override is None:
            Xc, Yc, Mc = Z[ca:cb], beh[ca:cb], (part[ca:cb] == "calib").astype(float)
        else:
            Xc, Yc, Mc = rows_override[3]
        nch = len(Xc) // 64
        Xs = Xc[:nch * 64].reshape(nch, 64, N).astype(np.float32)
        Ys = np.nan_to_num(Yc[:nch * 64].reshape(nch, 64, 2))
        Ms = Mc[:nch * 64].reshape(nch, 64).copy()
        Ms[:, :10] = 0
        Xv = Z[va - 10:vb][None].astype(np.float32)

        def vf(e):
            return MET.r2_vw(yval, e.predict_seqs(Xv)[0, 10:][val - va])
        ens, ginf = DEC.train_gru(Xs, Ys, Ms, vf, seeds=CFG["gru_seeds"])
        out["gru"], out["info"]["gru"] = ens, dict(seeds=ginf, val_r2=float(vf(ens)), n_chunks=nch)
        ctx.models["%s/gru" % name] = ens.hash()
    return out


def d2_apply(M, dec, Sk, zs=None):
    """Predict session Sk's test rows with decoder dec of fitted day-model M (z-scorer zs; default M's)."""
    zs = M["zs"] if zs is None else zs
    Z = zs.transform(Sk["sbp"])
    ta, tb, _ = Sk["ranges"]["test"]
    tm = Sk["part"][ta:tb] == "test"
    if dec == "ridge":
        return M["ridge"].predict(lagged(Z, lag_offsets(6))[Sk["test_pos"]])
    if dec == "kf":
        return M["kf"].predict(Z[ta:tb])[tm]
    if dec == "gru":
        return M["gru"].predict_seqs(Z[ta - 10:tb][None].astype(np.float32))[0, 10:][tm]
    raise KeyError(dec)


def run_d2_fit(ctx, d2tr, P, INFO, a3):
    SS = {}
    for date, lag in SESSIONS:
        p, t, pp = d2tr[date]
        SS[date] = d2_session(ctx, date, p, t, pp)
    ctx.log("D2 sessions loaded (re-binned 20 -> 32 ms)")
    d0 = SESSIONS[0][0]
    M0 = d2_fit_day(ctx, SS[d0], "D2_%s" % d0)
    a3["D2_day0_ridge_val_r2"] = M0["info"]["ridge"]["val_r2"]
    INFO["D2_day0"] = M0["info"]
    # FA-Procrustes day-0 latent ridge (R-b); scaling x / sd0 (day-0 calib SD) for every day
    S0 = SS[d0]
    cal0 = S0["part"] == "calib"
    sd0 = np.maximum(S0["sbp"][cal0].std(0), 1e-12)
    fa0 = DEC.FA().fit(S0["sbp"][cal0] / sd0, k=10, iters=200)
    ctx.models["D2_%s/FA" % d0] = DEC.arr_hash(fa0.L, fa0.psi, fa0.mu)
    lat0 = lagged(fa0.posterior_mean(S0["sbp"] / sd0), lag_offsets(6))
    val0 = S0["part"] == "val"
    fr, finf = DEC.fit_ridge_select(lat0[cal0], S0["beh"][cal0], lambda mm: (S0["beh"][val0], mm.predict(lat0[val0])))
    ctx.models["D2_%s/FAridge" % d0] = fr.hash()
    INFO["D2_FAridge"] = finf
    WITHIN = {}
    for date, lag in SESSIONS:
        Sk = SS[date]
        for dec in ("ridge", "kf", "gru"):
            P[("D2fixed", dec, date)] = d2_apply(M0, dec, Sk)
        if date == d0:
            Mk = M0
        else:
            Mk = d2_fit_day(ctx, Sk, "D2_%s" % date)
        WITHIN[date] = Mk["info"]
        for dec in ("ridge", "kf", "gru"):
            P[("D2within", dec, date)] = d2_apply(Mk, dec, Sk)
        # R-a: day-0 ridge on day-k features re-z-scored with day-k calib stats
        P[("D2Ra", "ridge", date)] = d2_apply(M0, "ridge", Sk, zs=Mk["zs"])
        # R-b: FA on day-k calib, Procrustes to day-0 loadings, day-0 latent ridge
        calk = Sk["part"] == "calib"
        fak = fa0 if date == d0 else DEC.FA().fit(Sk["sbp"][calk] / sd0, k=10, iters=200)
        O = DEC.procrustes(fak.L, fa0.L)
        latk = lagged(fak.posterior_mean(Sk["sbp"] / sd0) @ O, lag_offsets(6))
        P[("D2Rb", "ridge", date)] = fr.predict(latk[Sk["test_pos"]])
        ctx.models["D2_%s/FA_O" % date] = DEC.arr_hash(fak.L, fak.psi, O)
        P[("D2", "B0", date)] = np.repeat(np.nanmean(Sk["beh"][calk], axis=0)[None], len(Sk["test_pos"]), axis=0)
        ctx.log("D2 %s (lag %d) fitted" % (date, lag))
    INFO["D2_within"] = WITHIN
    # NC1 on day 0: calib trial i neural paired with trial pi(i) behaviour (truncated to the shorter trial)
    own, part = S0["own"], S0["part"]
    ct = S0["calib_trials"]
    pi = rng(K_SHUF, 2).permutation(len(ct))
    rows_i, tgt, segs, Xcat, Ycat = [], [], [], [], []
    zs0 = M0["zs"]
    Z0 = zs0.transform(S0["sbp"])
    for i, j in zip(range(len(ct)), pi):
        ri = np.flatnonzero((own == ct[i]) & (part == "calib"))
        rj = np.flatnonzero((own == ct[j]) & (part == "calib"))
        m = min(len(ri), len(rj))
        rows_i.append(ri[:m])
        tgt.append(S0["beh"][rj[:m]])
        segs.append((Z0[ri[:m]], S0["beh"][rj[:m]]))
    rows = np.concatenate(rows_i)
    Y = np.vstack(tgt)
    vt = sorted(set(own[part == "val"].tolist()) - {-1})
    piv = rng(K_SHUF, 4).permutation(len(vt))
    vrows, vtgt = [], []
    for i, j in zip(range(len(vt)), piv):
        ri = np.flatnonzero((own == vt[i]) & (part == "val"))
        rj = np.flatnonzero((own == vt[j]) & (part == "val"))
        m = min(len(ri), len(rj))
        vrows.append(ri[:m])
        vtgt.append(S0["beh"][rj[:m]])
    Mn = d2_fit_day(ctx, S0, "D2_NC1", rows_override=(rows, Y, segs, (Z0[rows], Y, np.ones(len(rows)))),
                    val_override=(np.concatenate(vrows), np.vstack(vtgt)))
    for dec in ("ridge", "kf", "gru"):
        P[("D2_NC1", dec, d0)] = d2_apply(Mn, dec, S0)
    INFO["D2_NC1"] = Mn["info"]
    ctx.log("D2 NC1 fitted")
    return dict(SS=SS, M0=M0, d0=d0, zs0=zs0)


def pl2(ctx, D2d):
    """PL-2: 'day-0' ridge trained on day-0 calib + the day-32 TEST block; undeclared version must raise."""
    SS, M0, d0 = D2d["SS"], D2d["M0"], D2d["d0"]
    dk = "20200228"
    Sk = SS[dk]
    out = {}
    try:
        assert_session_order(0, [0, 32], ["calib", "test"])
        out["undeclared_raised"] = None
    except SessionOrderError as e:
        out["undeclared_raised"] = type(e).__name__
    assert_session_order(0, [0, 32], ["calib", "test"], allow_future=True)
    yk = ctx.vault.planted_access(("D2", dk), "PL-2 day-32 test block into day-0 training", declared=True)
    zs0 = M0["zs"]
    L0 = lagged(zs0.transform(SS[d0]["sbp"]), lag_offsets(6))
    Lk = lagged(zs0.transform(Sk["sbp"]), lag_offsets(6))
    cal0 = SS[d0]["part"] == "calib"
    X = np.vstack([L0[cal0], Lk[Sk["test_pos"]]])
    Y = np.vstack([SS[d0]["beh"][cal0], yk])
    lam = M0["ridge"].lam
    path = DEC.RidgePath(X, Y)
    Wt, b = path.coef(lam)
    m = DEC.Ridge(Wt, b, lam)
    out["pred"] = m.predict(Lk[Sk["test_pos"]])
    out["lambda"] = lam
    return out


# =====================================================================================================================
# D3
# =====================================================================================================================
def d3_epochs(x, fs, ann):
    ev = [(on, dur, txt) for on, dur, txt in ann if txt in ("T1", "T2")]
    sos = butter(4, [8, 30], btype="bandpass", fs=fs, output="sos")
    xf = sosfiltfilt(sos, x, axis=1)
    ep, lab, ons = [], [], []
    n = int(round(2.0 * fs))
    for on, dur, txt in ev:
        a = int(round((on + 0.5) * fs))
        if a + n > xf.shape[1]:
            continue
        ep.append(xf[:, a:a + n])
        lab.append(0 if txt == "T1" else 1)
        ons.append(on)
    return np.array(ep), np.array(lab), np.array(ons), len(ev)


def a6_check(ann, dur_s):
    labels = sorted(set(t for _, _, t in ann))
    bad = [t for t in labels if t not in ("T0", "T1", "T2")]
    task = [d for _, d, t in ann if t in ("T1", "T2")]
    ok = (not bad) and ("T1" in labels) and ("T2" in labels) and all(d is not None and 3.5 <= d <= 5.0 for d in task) \
        and 110 <= dur_s <= 130
    return ok, dict(labels=labels, task_dur_min=min(task) if task else None, task_dur_max=max(task) if task else None,
                    file_s=dur_s)


def lda_select(Xr, yr):
    """Inner 2-fold by run (R04 vs R08). Xr, yr: dict run -> arrays."""
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


def d3_fit_subject(Xr, Cr, yr, X12, C12):
    g, gacc = lda_select(Xr, yr)
    Xtr = np.vstack([Xr["R04"], Xr["R08"]])
    ytr = np.concatenate([yr["R04"], yr["R08"]])
    lda = DEC.ShrinkLDA().fit(Xtr, ytr, g)
    c, cacc = ts_select(Cr, yr)
    Ctr = np.concatenate([Cr["R04"], Cr["R08"]])
    M = DEC.riemann_mean(Ctr)
    lr = DEC.LogRegL2().fit(DEC.tangent(Ctr, M), ytr, c)
    return (dict(LDA=lda.predict(X12), TS=lr.predict(DEC.tangent(C12, M))),
            dict(gamma=g, gamma_inner_acc=gacc, C=c, C_inner_acc=cacc),
            dict(LDA=DEC.arr_hash(lda.w, [lda.b]), TS=DEC.arr_hash(lr.w, [lr.b], M)))


def run_d3_fit(ctx, P, INFO):
    base = os.path.join(RAW, "eegmmidb")
    a6 = {}
    runs = {}
    for s in range(1, 21):
        for r in ("R04", "R08", "R12"):
            p = os.path.join(base, "S%03d" % s, "S%03d%s.edf" % (s, r))
            ann, h = D.edf_annotations(p)
            ok, det = a6_check(ann, h["n_records"] * h["record_duration"])
            a6["S%03d%s" % (s, r)] = dict(ok=ok, **det)
    a6_ok = all(v["ok"] for v in a6.values())
    INFO["D3_A6"] = dict(pass_=a6_ok, files=a6)
    if not a6_ok:
        ctx.log("A6: D3 NOT TESTED (run map not confirmed)")
        return dict(tested=False, reason="A6")
    ctx.log("A6 confirmed (only T0/T1/T2; task durations in [3.5, 5] s)")
    subj = {}
    cue_iv = []
    for s in range(1, 21):
        Xr, Cr, yr = {}, {}, {}
        for r in ("R04", "R08", "R12"):
            p = os.path.join(base, "S%03d" % s, "S%03d%s.edf" % (s, r))
            x, fs, lab, ann, dur = D.d3_run(p)
            if fs != 160.0:
                raise RuntimeError("fs %s" % fs)
            ep, y, ons, n_ev = d3_epochs(x, fs, ann)
            del x
            Xr[r] = np.log(ep.var(axis=2))
            Cr[r] = np.array([DEC.reg_cov(e) for e in ep])
            if r == "R12":
                ctx.vault.deposit(("D3", s), y)
                cue_iv.extend(np.diff(ons).tolist())
                yr[r] = None
            else:
                yr[r] = y
        preds, sel, hs = d3_fit_subject(Xr, Cr, yr, Xr["R12"], Cr["R12"])
        for k in preds:
            P[("D3", k, s)] = preds[k]
            ctx.models["D3_S%03d/%s" % (s, k)] = hs[k]
        # NC1: 5 label permutations of the pooled training labels (stream 5)
        nperm = {"LDA": [], "TS": []}
        ytr = np.concatenate([yr["R04"], yr["R08"]])
        n4 = len(yr["R04"])
        for pix in range(5):
            yp = rng(K_D3PERM, s, pix).permutation(ytr)
            pp, _, _ = d3_fit_subject(Xr, Cr, {"R04": yp[:n4], "R08": yp[n4:]}, Xr["R12"], Cr["R12"])
            for k in pp:
                nperm[k].append(pp[k])
        for k in nperm:
            P[("D3_NC1", k, s)] = np.array(nperm[k])
        subj[s] = dict(sel=sel, n_train=int(len(ytr)), n_test=int(len(Xr["R12"])))
    INFO["D3_subjects"] = subj
    ctx.log("D3 fitted (20 subjects, LDA + TS + NC1 perms)")
    return dict(tested=True, cue_interval_mean_s=float(np.mean(cue_iv)), n_cue_intervals=len(cue_iv))


# =====================================================================================================================
# planted leaks PL-1 / PL-3 (D1)
# =====================================================================================================================
def pl1(ctx, C20, ids1, V20, iTR, iVA, iTE, j0, W, H):
    out = {}
    N = C20.shape[2]
    ks = lag_offsets(H)
    cols = feature_names("u", N, ks) + ["planted_v1"]
    try:
        assert_whitelist(cols, causal_whitelist("u", N, H))
        out["undeclared_raised"] = None
    except FeatureWhitelistError as e:
        out["undeclared_raised"] = type(e).__name__
    assert_whitelist(cols, causal_whitelist("u", N, H), declared_extra=["planted_v1"])
    vte = ctx.vault.planted_access(("D1", 20), "PL-1 true v1 as a feature", declared=True)[:, j0:j0 + W]
    zs = ZScore().fit(C20[iTR][:, j0 - H:j0 + W].reshape(-1, N), np.repeat(ids1[iTR], H + W), ids1[iTR])
    Z = zs.transform(C20[:, j0 - H:j0 + W].astype(np.float64))
    v1tr = V20[iTR][:, j0:j0 + W, 0]
    mu, sd = v1tr.mean(), v1tr.std()
    g = rng(K_PLANT, 1)

    def des(idx, v1):
        X = np.vstack([lagged(Z[s], ks)[H:] for s in idx])
        pc = (v1.reshape(-1) - mu) / sd + g.standard_normal(X.shape[0])
        return np.column_stack([X, pc])
    Xtr = des(iTR, v1tr)
    Xva = des(iVA, V20[iVA][:, j0:j0 + W, 0])
    Xte = des(iTE, vte[:, :, 0])
    m, inf = DEC.fit_ridge_select(Xtr, V20[iTR][:, j0:j0 + W].reshape(-1, 2),
                                  lambda mm: (V20[iVA][:, j0:j0 + W].reshape(-1, 2), mm.predict(Xva)))
    out["pred"] = m.predict(Xte).reshape(len(iTE), W, 2)
    out["lambda"] = inf["lambda_"]
    return out


def pl3(ctx, C20, ids1, V20, iTR, iVA, iTE, j0, W, H, t1):
    """PL-3: bin-level random 60/20/20 split + centred +/-5-bin feature window (GRU required, ridge descriptive)."""
    out = {}
    nT = C20.shape[0]
    N = C20.shape[2]
    try:
        random_bin_split(nT * W, rng(K_PLANT, 3))
        out["undeclared_split_raised"] = None
    except RandomSplitForbiddenError as e:
        out["undeclared_split_raised"] = type(e).__name__
    try:
        lag_offsets(0, centred=5)
        out["undeclared_features_raised"] = None
    except CausalFeatureError as e:
        out["undeclared_features_raised"] = type(e).__name__
    lab = random_bin_split(nT * W, rng(K_PLANT, 3), allow_random_split=True).reshape(nT, W)
    ks = lag_offsets(0, centred=5, allow_noncausal=True)
    Vall = V20[:, j0:j0 + W].copy()
    Vall[iTE] = ctx.vault.planted_access(("D1", 20), "PL-3 random-bin split over all trials", declared=True)[:, j0:j0 + W]
    zs = ZScore().fit(C20[iTR][:, j0 - H:j0 + W].reshape(-1, N), np.repeat(ids1[iTR], H + W), ids1[iTR])
    Z = zs.transform(C20[:, j0 - H - 5:j0 + W + 5].astype(np.float64))     # rows: 5 pad, H hist, W window, 5 pad
    rs = DEC.RidgeStream(N * len(ks), 2)
    Xw = np.empty((nT, W, N * len(ks)), dtype=np.float32)
    for s in range(nT):
        Xw[s] = lagged(Z[s], ks, allow_noncausal=True)[5 + H:5 + H + W]
    trm, vam, tem = lab == "train", lab == "val", lab == "test"
    for a in range(0, nT, 50):
        X = Xw[a:a + 50].reshape(-1, Xw.shape[2]).astype(np.float64)
        msk = trm[a:a + 50].reshape(-1)
        rs.add(X[msk], Vall[a:a + 50].reshape(-1, 2)[msk])
    cands = rs.finalize()

    def vch():
        for a in range(0, nT, 50):
            X = Xw[a:a + 50].reshape(-1, Xw.shape[2]).astype(np.float64)
            msk = vam[a:a + 50].reshape(-1)
            yield X[msk], Vall[a:a + 50].reshape(-1, 2)[msk]
    m, inf = DEC.select_ridge(cands, vch)
    pr = np.vstack([m.predict(Xw[a:a + 50].reshape(-1, Xw.shape[2]).astype(np.float64))
                    for a in range(0, nT, 50)]).reshape(nT, W, 2)
    out["ridge_r2"] = MET.r2_vw(Vall[tem], pr[tem])
    del Xw
    # GRU: sequences = history + window rows with centred features; loss on train bins only
    Xs = np.stack([lagged(Z[s], ks, allow_noncausal=True)[5:5 + H + W] for s in range(nT)]).astype(np.float32)
    Ys = np.concatenate([np.zeros((nT, H, 2)), np.nan_to_num(Vall)], axis=1)
    mask = np.concatenate([np.zeros((nT, H)), trm.astype(float)], axis=1)

    def vf(e):
        p = e.predict_seqs(Xs)[:, H:]
        return MET.r2_vw(Vall[vam], p[vam])
    ens, ginf = DEC.train_gru(Xs, Ys, mask, vf, seeds=CFG["gru_seeds"])
    pg = ens.predict_seqs(Xs)[:, H:]
    out["gru_r2"] = MET.r2_vw(Vall[tem], pg[tem])
    out["n_bins"] = dict(train=int(trm.sum()), val=int(vam.sum()), test=int(tem.sum()))
    out["gru_epochs"] = [g["epochs"] for g in ginf]
    del Xs
    return out


# =====================================================================================================================
# scoring (the only place test labels are read: vault.final_score)
# =====================================================================================================================
def score_all(ctx, P, INFO, D2d, D3d, PL, iTE, j0, W, dry):
    V = ctx.vault
    out = {}
    nte = len(iTE)
    units = [(k * W, (k + 1) * W) for k in range(nte)]
    Wb = MET.boot_weights(nte, B_BOOT, rng(K_BOOT, 1))
    # ---------------- D1 primary
    d1, priv = {}, {}
    for di, dec in enumerate(("ridge", "kf", "gru", "B0")):
        yh = P[("D1", dec)].reshape(-1, 2)

        def fn(y, yh=yh, di=di):
            return cont_score(y[:, j0:j0 + W].reshape(-1, 2), yh, units, 20, W, rng(K_NULL, 1, di))
        d1[dec], priv[dec] = V.final_score(("D1", 20), dec, fn)
    boots = {dec: boot_block(priv[dec], Wb) for dec in ("ridge", "kf", "gru")}
    for dec in ("ridge", "kf", "gru"):
        d1[dec]["r2_ci99"] = MET.pct_ci(boots[dec][0], 99)
        d1[dec]["I_net_ci99"] = MET.pct_ci(boots[dec][1], 99)
    dGR = boots["gru"][0] - boots["ridge"][0]
    dKR = boots["kf"][0] - boots["ridge"][0]
    dIb = boots["gru"][1] - boots["ridge"][1]
    d1["diff"] = dict(
        gru_minus_ridge_r2=d1["gru"]["r2"] - d1["ridge"]["r2"], gru_minus_ridge_r2_ci99=MET.pct_ci(dGR, 99),
        kf_minus_ridge_r2=d1["kf"]["r2"] - d1["ridge"]["r2"], kf_minus_ridge_r2_ci98=MET.pct_ci(dKR, 98),
        kf_minus_ridge_r2_ci99=MET.pct_ci(dKR, 99),
        gru_minus_ridge_Inet=d1["gru"]["bits"]["I_net"] - d1["ridge"]["bits"]["I_net"],
        gru_minus_ridge_Inet_ci99=MET.pct_ci(dIb, 99))
    d1["fit_info"] = INFO["D1"]
    # NC2a (honest decoders, trial shift s = 1..5 within the test block)
    nc2a = {}
    for dec in ("ridge", "kf", "gru"):
        yh = P[("D1", dec)]

        def fn(y, yh=yh):
            yw = y[:, j0:j0 + W]
            return {s: MET.r2_vw(np.roll(yw, -s, axis=0).reshape(-1, 2), yh.reshape(-1, 2)) for s in range(1, 6)}
        nc2a[dec] = V.final_score(("D1", 20), "NC2a|" + dec, fn)
    # NC1
    nc1 = {}
    for di, dec in enumerate(("ridge", "kf", "gru")):
        yh = P[("D1_NC1", dec)].reshape(-1, 2)

        def fn(y, yh=yh, di=di):
            return cont_score(y[:, j0:j0 + W].reshape(-1, 2), yh, units, 20, W, rng(K_NULL, 2, di))[0]
        r = V.final_score(("D1", 20), "NC1|" + dec, fn)
        nc1[dec] = dict(r2=r["r2"], I_net=r["bits"]["I_net"], rho2=r["rho2"])
    # condition-held-out
    cond = {}
    for dec in ("ridge", "kf", "gru"):
        yh = P[("D1_cond", dec)].reshape(-1, 2)
        cond[dec] = V.final_score(("D1", 20), "cond|" + dec,
                                  lambda y, yh=yh: MET.r2_vw(y[:, j0:j0 + W].reshape(-1, 2), yh))
    # bin sweep
    sweep = {20: {k: d1[k]["r2"] for k in ("ridge", "kf")}}
    for b in BINS_MS:
        if b == 20:
            continue
        jb, Wb_ = 500 // b, 700 // b
        sweep[b] = {}
        for dec in ("ridge", "kf"):
            yh = P[("D1bin%d" % b, dec)].reshape(-1, 2)
            sweep[b][dec] = V.final_score(("D1", b), dec,
                                          lambda y, yh=yh, jb=jb, Wb_=Wb_: MET.r2_vw(y[:, jb:jb + Wb_].reshape(-1, 2), yh))
    # NC2b lag sweep
    lagsw = {0: {k: d1[k]["r2"] for k in ("ridge", "gru")}}
    for tau in TAUS_MS:
        if tau == 0:
            continue
        lagsw[tau] = {}
        for dec in ("ridge", "gru"):
            yh = P[("D1tau%d" % tau, dec)].reshape(-1, 2)
            lagsw[tau][dec] = V.final_score(("D1tau", tau), dec, lambda y, yh=yh: MET.r2_vw(y.reshape(-1, 2), yh))
    # PL-1 score
    yh = PL["PL1"]["pred"].reshape(-1, 2)
    pl1_r2 = V.final_score(("D1", 20), "PL1|ridge", lambda y: MET.r2_vw(y[:, j0:j0 + W].reshape(-1, 2), yh))
    yhr = P[("D1", "ridge")].reshape(-1, 2)

    def pl1_expect(y):
        """Non-gating diagnostic (DEVIATIONS D.1): expected rise w1 * r^2 / (1 + r), r = honest v1 residual fraction."""
        yw = y[:, j0:j0 + W].reshape(-1, 2)
        sst = ((yw - yw.mean(0)) ** 2).sum(0)
        sse = ((yw - yhr) ** 2).sum(0)
        r = sse[0] / sst[0]
        w1 = sst[0] / sst.sum()
        return dict(r_v1=float(r), w1=float(w1), expected_rise=float(w1 * r * r / (1 + r)),
                    honest_r2_per_dim=[float(1 - sse[0] / sst[0]), float(1 - sse[1] / sst[1])])
    pl1_exp = V.final_score(("D1", 20), "PL1_expected|ridge", pl1_expect)
    b0 = d1["B0"]["r2"]
    thr = max(0.05, b0 + 0.02)
    out["D1"] = d1
    out["D1_descriptive"] = dict(condition_held_out_r2=cond, bin_sweep_r2={str(k): v for k, v in sweep.items()},
                                 NC2b_lag_sweep_r2={str(k): v for k, v in lagsw.items()},
                                 NC2b_argmax_ms={dec: int(max(lagsw, key=lambda t: lagsw[t][dec])) for dec in ("ridge", "gru")},
                                 NC2b_prediction="argmax in [0, +300] ms",
                                 fit_info={k: v for k, v in INFO.items() if k.startswith("D1bin") or k.startswith("D1tau")})
    ctrl = dict(NC1={"D1": dict(r2=nc1, B0_r2=b0, threshold_r2=thr, threshold_Inet=0.15,
                                pass_=all(v["r2"] <= thr and v["I_net"] <= 0.15 for v in nc1.values()))},
                NC2a={"D1": dict(r2=nc2a, threshold_r2=thr, pass_=all(r <= thr for v in nc2a.values() for r in v.values()))},
                PL1=dict(honest_ridge_r2=d1["ridge"]["r2"], planted_ridge_r2=pl1_r2, rise=pl1_r2 - d1["ridge"]["r2"],
                         power_diagnostic_non_gating=pl1_exp,
                         undeclared_raised=PL["PL1"]["undeclared_raised"],
                         pass_=(pl1_r2 - d1["ridge"]["r2"] >= 0.10) and PL["PL1"]["undeclared_raised"] == "FeatureWhitelistError"),
                PL3=dict(honest_gru_r2=d1["gru"]["r2"], planted_gru_r2=PL["PL3"]["gru_r2"],
                         gru_inflation=PL["PL3"]["gru_r2"] - d1["gru"]["r2"], honest_ridge_r2=d1["ridge"]["r2"],
                         planted_ridge_r2_descriptive=PL["PL3"]["ridge_r2"], n_bins=PL["PL3"]["n_bins"],
                         undeclared_split_raised=PL["PL3"]["undeclared_split_raised"],
                         undeclared_features_raised=PL["PL3"]["undeclared_features_raised"],
                         pass_=(PL["PL3"]["gru_r2"] - d1["gru"]["r2"] >= 0.01)
                         and PL["PL3"]["undeclared_split_raised"] == "RandomSplitForbiddenError"
                         and PL["PL3"]["undeclared_features_raised"] == "CausalFeatureError"))
    # ---------------- D2
    if not dry:
        d2, ctrl2 = score_d2(ctx, P, INFO, D2d, PL)
        out["D2"] = d2
        ctrl["NC1"]["D2_day0"] = ctrl2["NC1"]
        ctrl["NC2a"]["D2_day0"] = ctrl2["NC2a"]
        ctrl["PL2"] = ctrl2["PL2"]
    # ---------------- D3
    if not dry:
        d3, c3 = score_d3(ctx, P, INFO, D3d)
        out["D3"] = d3
        if c3 is not None:
            ctrl["NC1"]["D3"] = c3
    for k in ("NC1", "NC2a"):
        ctrl[k]["pass_"] = all(v["pass_"] for kk, v in ctrl[k].items() if kk != "pass_")
    out["controls"] = ctrl
    out["guard_calls"] = dict(sorted(GUARD_CALLS.items()))
    out["vault"] = ctx.vault.summary()
    out["vault_log"] = list(ctx.vault.log)
    out["hypotheses_pre_harness"] = verdicts(out, dry)
    return out


def d2_units(n):
    return [(a, min(a + 64, n)) for a in range(0, n, 64)]


def score_d2(ctx, P, INFO, D2d, PL):
    V = ctx.vault
    SS = D2d["SS"]
    d0 = D2d["d0"]
    ses = {}
    for si, (date, lag) in enumerate(SESSIONS):
        Sk = SS[date]
        n = len(Sk["test_pos"])
        units = d2_units(n)
        Wb = MET.boot_weights(len(units), B_BOOT, rng(K_BOOT, 2, si))
        res, priv = {}, {}
        keys = [("D2fixed", d) for d in ("ridge", "kf", "gru")] + [("D2within", d) for d in ("ridge", "kf", "gru")] + \
            [("D2Ra", "ridge"), ("D2Rb", "ridge"), ("D2", "B0")]
        for ki, (arm, dec) in enumerate(keys):
            yh = P[(arm, dec, date)]

            def fn(y, yh=yh, si=si, ki=ki):
                return cont_score(y, yh, units, 32, 64, rng(K_NULL, 3, si, ki))
            res[arm + "/" + dec], priv[arm + "/" + dec] = V.final_score(("D2", date), arm + "|" + dec, fn)
        bt = {k: MET.r2_from_stats(Wb, priv[k]["st"]) for k in priv}
        e = dict(lag_days=lag, style=Sk["style"], flagged_random_targets=(Sk["style"] != ["CO"]),
                 n_test_bins=n, n_units=len(units), ranges=Sk["ranges"], bin_info=Sk["bin_info"],
                 scores={k: dict(r2=v["r2"], rho2=v["rho2"], I_net=v["bits"]["I_net"], I_raw=v["bits"]["I_raw"],
                                 r2_ci99=MET.pct_ci(bt[k], 99)) for k, v in res.items()})
        for dec in ("ridge", "kf", "gru"):
            fx, wi = res["D2fixed/" + dec]["r2"], res["D2within/" + dec]["r2"]
            usable = wi >= 0.10
            rb = bt["D2fixed/" + dec] / bt["D2within/" + dec]
            e["rho_" + dec] = dict(value=fx / wi if usable else None, usable=bool(usable), ci99=MET.pct_ci(rb, 99))
        fx, wi = res["D2fixed/ridge"]["r2"], res["D2within/ridge"]["r2"]
        for arm in ("D2Ra", "D2Rb"):
            ar = res[arm + "/ridge"]["r2"]
            den = wi - fx
            e["phi_" + arm] = dict(value=(ar - fx) / den if lag > 0 and den != 0 else None,
                                   ci99=MET.pct_ci((bt[arm + "/ridge"] - bt["D2fixed/ridge"]) /
                                                   (bt["D2within/ridge"] - bt["D2fixed/ridge"]), 99) if lag > 0 else None)
        e["_boot"] = {k: bt[k] for k in ("D2fixed/ridge", "D2within/ridge", "D2Rb/ridge", "D2Ra/ridge")}
        ses[date] = e
    # aggregates
    late = [d for d, l in SESSIONS if l >= 30]
    later8 = [d for d, l in SESSIONS if l > 0]
    usable = [d for d in late if ses[d]["rho_ridge"]["usable"]]
    rhos = [ses[d]["rho_ridge"]["value"] for d in usable]
    phib = [ses[d]["phi_D2Rb"]["value"] for d in usable]
    phia = [ses[d]["phi_D2Ra"]["value"] for d in usable]
    sp = MET.spearman([ses[d]["lag_days"] for d in later8], [ses[d]["scores"]["D2fixed/ridge"]["r2"] for d in later8])
    # bootstrap CI of the median rho / phi over usable late sessions (sessions resampled independently within)
    if usable:
        R = np.array([ses[d]["_boot"]["D2fixed/ridge"] / ses[d]["_boot"]["D2within/ridge"] for d in usable])
        Fb = np.array([(ses[d]["_boot"]["D2Rb/ridge"] - ses[d]["_boot"]["D2fixed/ridge"]) /
                       (ses[d]["_boot"]["D2within/ridge"] - ses[d]["_boot"]["D2fixed/ridge"]) for d in usable])
        med_rho_ci = MET.pct_ci(np.median(R, axis=0), 99)
        med_phi_ci = MET.pct_ci(np.median(Fb, axis=0), 99)
    else:
        med_rho_ci = med_phi_ci = None
    for d in ses:
        ses[d].pop("_boot")
    agg = dict(late_sessions=late, usable_late=usable, median_rho_ridge=float(np.median(rhos)) if rhos else None,
               median_rho_ridge_ci99=med_rho_ci, spearman_lag_vs_r2fixed_ridge_8later=sp,
               median_phi_Rb=float(np.median(phib)) if phib else None, median_phi_Rb_ci99=med_phi_ci,
               median_phi_Ra=float(np.median(phia)) if phia else None,
               drift_curves={dec: {d: dict(lag=ses[d]["lag_days"], r2_fixed=ses[d]["scores"]["D2fixed/" + dec]["r2"],
                                          r2_within=ses[d]["scores"]["D2within/" + dec]["r2"],
                                          rho=ses[d]["rho_" + dec]["value"]) for d in ses} for dec in ("ridge", "kf", "gru")})
    # controls on day 0
    S0 = SS[d0]
    b0 = ses[d0]["scores"]["D2/B0"]["r2"]
    thr = max(0.05, b0 + 0.02)
    units0 = d2_units(len(S0["test_pos"]))
    nc1 = {}
    for di, dec in enumerate(("ridge", "kf", "gru")):
        yh = P[("D2_NC1", dec, d0)]

        def fn(y, yh=yh, di=di):
            return cont_score(y, yh, units0, 32, 64, rng(K_NULL, 4, di))[0]
        r = V.final_score(("D2", d0), "NC1|" + dec, fn)
        nc1[dec] = dict(r2=r["r2"], I_net=r["bits"]["I_net"])
    nc2a = {}
    tt = S0["test_trial_rows"]
    for dec in ("ridge", "kf", "gru"):
        yh = P[("D2within", dec, d0)]

        def fn(y, yh=yh):
            r = {}
            for s in range(1, 6):
                ys, ps = [], []
                for i in range(len(tt)):
                    a1, b1 = tt[i]
                    a2, b2 = tt[(i + s) % len(tt)]
                    m = min(b1 - a1, b2 - a2)
                    ps.append(yh[a1:a1 + m])
                    ys.append(y[a2:a2 + m])
                r[s] = MET.r2_vw(np.vstack(ys), np.vstack(ps))
            return r
        nc2a[dec] = V.final_score(("D2", d0), "NC2a|" + dec, fn)
    dk = "20200228"
    pl2r2 = V.final_score(("D2", dk), "PL2|ridge", lambda y: MET.r2_vw(y, PL["PL2"]["pred"]))
    wi = ses[dk]["scores"]["D2within/ridge"]["r2"]
    ctrl = dict(NC1=dict(r2=nc1, B0_r2=b0, threshold_r2=thr, threshold_Inet=0.15,
                         pass_=all(v["r2"] <= thr and v["I_net"] <= 0.15 for v in nc1.values())),
                NC2a=dict(r2=nc2a, threshold_r2=thr, pass_=all(r <= thr for v in nc2a.values() for r in v.values())),
                PL2=dict(session=dk, planted_r2=pl2r2, within_r2=wi, rho=pl2r2 / wi if wi else None,
                         honest_rho=ses[dk]["rho_ridge"]["value"], undeclared_raised=PL["PL2"]["undeclared_raised"],
                         pass_=(wi > 0 and pl2r2 / wi >= 0.9) and PL["PL2"]["undeclared_raised"] == "SessionOrderError"))
    d2 = dict(sessions=ses, aggregate=agg, day0_fit_info=INFO["D2_day0"], FAridge_info=INFO["D2_FAridge"],
              within_fit_info=INFO["D2_within"], NC1_fit_info=INFO["D2_NC1"])
    return d2, ctrl


def score_d3(ctx, P, INFO, D3d):
    if not D3d.get("tested"):
        return dict(tested=False, reason=D3d.get("reason"), A6=INFO.get("D3_A6")), None
    V = ctx.vault
    acc = {"LDA": {}, "TS": {}}
    conf = {"LDA": np.zeros((2, 2)), "TS": np.zeros((2, 2))}
    nc1 = {"LDA": {}, "TS": {}}
    for s in range(1, 21):
        for k in ("LDA", "TS"):
            yh = P[("D3", k, s)]

            def fn(y, yh=yh):
                c = np.zeros((2, 2))
                np.add.at(c, (y, yh), 1)
                return float((y == yh).mean()), c
            a_, c_ = V.final_score(("D3", s), k, fn)
            acc[k][s] = a_
            conf[k] += c_
            yp = P[("D3_NC1", k, s)]
            nc1[k][s] = V.final_score(("D3", s), "NC1|" + k, lambda y, yp=yp: [float((y == p).mean()) for p in yp])
    c = D3d["cue_interval_mean_s"]
    res = {}
    for k in ("LDA", "TS"):
        mi_mm, mi = MET.mi_miller_madow(conf[k])
        n = conf[k].sum()
        frac = conf[k].sum(1) / n
        P_ = np.trace(conf[k]) / n
        bal = bool(np.all((frac >= 0.45) & (frac <= 0.55)))
        res[k] = dict(mean_acc=float(np.mean(list(acc[k].values()))), acc_by_subject={str(s): v for s, v in acc[k].items()},
                      pooled_confusion=conf[k].tolist(), MI_bits_per_trial_MM=mi_mm, MI_plugin=mi,
                      bits_per_s=mi_mm / c, bits_per_min=60 * mi_mm / c, class_fracs=frac.tolist(), balanced=bal,
                      wolpaw_bits_per_min=(60 * MET.wolpaw_bits(2, P_) / c) if bal else "ITR not applicable",
                      pooled_acc=float(P_))
    d = np.array([acc["TS"][s] - acc["LDA"][s] for s in range(1, 21)])
    res["H6_diff_mean"] = float(d.mean())
    res["H6_signflip_p"] = MET.signflip_p(d, 10000, rng(K_SIGNFLIP, 1))
    res["cue_interval_mean_s"] = c
    res["n_cue_intervals"] = D3d["n_cue_intervals"]
    res["selection"] = {str(s): v for s, v in INFO["D3_subjects"].items()}
    res["A6"] = dict(pass_=INFO["D3_A6"]["pass_"])
    m = {k: float(np.mean([np.mean(v) for v in nc1[k].values()])) for k in nc1}
    c3 = dict(mean_acc_perm=m, range=[0.40, 0.60], pass_=all(0.40 <= v <= 0.60 for v in m.values()))
    res["tested"] = True
    return res, c3


# =====================================================================================================================
def verdicts(o, dry):
    V = {}
    d1 = o["D1"]
    df = d1["diff"]
    lo, hi = df["gru_minus_ridge_r2_ci99"]
    dv = df["gru_minus_ridge_r2"]
    V["H1"] = dict(delta=dv, ci99=[lo, hi], prediction="ridge 0.65, KF 0.62, GRU 0.72",
                   verdict="PASS" if (dv >= 0.02 and lo > 0) else ("FAIL" if hi < 0.02 else "INCONCLUSIVE"))
    lo, hi = df["kf_minus_ridge_r2_ci98"]
    V["H2"] = dict(delta=df["kf_minus_ridge_r2"], ci98=[lo, hi], prediction="delta -0.03",
                   verdict="PASS" if (lo >= -0.05 and hi <= 0.05) else ("FAIL" if (hi < -0.05 or lo > 0.05) else "INCONCLUSIVE"))
    r2 = {k: d1[k]["r2"] for k in ("ridge", "kf", "gru")}
    ib = {k: d1[k]["bits"]["I_net"] for k in ("ridge", "kf", "gru")}
    same_order = sorted(r2, key=r2.get) == sorted(ib, key=ib.get)
    lo, hi = df["gru_minus_ridge_Inet_ci99"]
    V["H3"] = dict(order_r2=sorted(r2, key=r2.get, reverse=True), order_Inet=sorted(ib, key=ib.get, reverse=True),
                   same_order=same_order, gru_minus_ridge_Inet=df["gru_minus_ridge_Inet"], ci99=[lo, hi],
                   I_net=ib, prediction="ridge ~5, GRU ~7 bits/s (factor-3 uncertain); ordering is the real prediction",
                   verdict="PASS" if (same_order and df["gru_minus_ridge_Inet"] > 0 and lo > 0)
                   else ("FAIL" if (df["gru_minus_ridge_Inet"] < 0 and hi < 0) else "INCONCLUSIVE"))
    if dry:
        return V
    a = o["D2"]["aggregate"]
    if len(a["usable_late"]) < 3:
        V["H4"] = dict(verdict="INCONCLUSIVE (underpowered)", **{k: a[k] for k in ("usable_late",)})
        V["H5"] = dict(verdict="INCONCLUSIVE (underpowered)")
    else:
        mr, sp = a["median_rho_ridge"], a["spearman_lag_vs_r2fixed_ridge_8later"]
        V["H4"] = dict(median_rho=mr, median_rho_ci99=a["median_rho_ridge_ci99"], spearman=sp,
                       usable_late=a["usable_late"], prediction="rho +3 d 0.85, +32 d 0.5, >=151 d <= 0.2",
                       verdict="PASS" if (mr <= 0.5 and sp <= -0.5) else ("FAIL" if mr >= 0.8 else "INCONCLUSIVE"))
        mp = a["median_phi_Rb"]
        V["H5"] = dict(median_phi_Rb=mp, median_phi_Rb_ci99=a["median_phi_Rb_ci99"], median_phi_Ra=a["median_phi_Ra"],
                       prediction="phi median 0.4; R-a 0.3",
                       verdict="PASS" if mp >= 0.5 else ("FAIL" if mp <= 0.1 else "INCONCLUSIVE"))
    d3 = o["D3"]
    if d3.get("tested"):
        dm, p = d3["H6_diff_mean"], d3["H6_signflip_p"]
        V["H6"] = dict(diff_mean=dm, p_signflip=p, lda=d3["LDA"]["mean_acc"], ts=d3["TS"]["mean_acc"],
                       prediction="LDA 0.60, TS 0.64",
                       verdict="PASS" if (dm >= 0.03 and p < 0.05) else ("FAIL" if dm <= 0 else "INCONCLUSIVE"))
    else:
        V["H6"] = dict(verdict="NOT TESTED (%s)" % d3.get("reason"))
    return V


def finish(ctx, stopped=None):
    card = ctx.card
    if stopped:
        card["stopped"] = stopped
    card["runtime"] = dict(wall_s=time.time() - ctx.t0, peak_rss_mb=peak_rss_mb(), finished=time.strftime("%Y-%m-%dT%H:%M:%S"),
                           vault_first_open=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ctx.vault.first_open_time))
                           if ctx.vault.first_open_time else None)
    card["runtime"]["A4_budget"] = dict(wall_limit_s=1200, rss_limit_mb=1536,
                                        pass_=card["runtime"]["wall_s"] < 1200 and (card["runtime"]["peak_rss_mb"] or 0) < 1536)
    h = card_hash(card)
    card["card_sha256_excl_runtime"] = h
    path = os.path.join(RES, "M1_card_%s.json" % ctx.tag)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(card))
    ctx.log("card written %s sha %s wall %.0fs peak RSS %.0f MB" % (os.path.basename(path), h, card["runtime"]["wall_s"],
                                                                   card["runtime"]["peak_rss_mb"] or -1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
