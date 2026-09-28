"""Build the Neural Playground web asset from the pinned MC_RTT file (tools/playground/README.md).

Every number shown on /playground comes from here. Decoders are fit on training reaches only;
hyper-parameters are chosen on a validation part of the training reaches; every reported R² and
every displayed trace is from held-out test reaches.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import dataset, encode
from .decoders import Kalman, Ridge, bin_spikes, lagged, r2_score

SCHEMA = "nf-playground/1"  # in memory; written as the compact nf-playground/2 (encode.py)
SEED = 20260927
BIN_S = 0.05
N_LAGS = 10  # 500 ms of causal spike history for the ridge (Wiener) filter
NEURON_COUNTS = [8, 16, 32, 64, 130]
NOISE_HZ = [0.0, 5.0, 10.0, 20.0]
N_SUBSETS = 5  # random unit subsets per neuron count; subset 0 is the one displayed
ALPHAS = [1.0, 10.0, 100.0, 1_000.0, 10_000.0]
KF_LAGS = [0, 1, 2, 3, 4]  # bins by which spikes lead the movement state
REACH_MIN_S, REACH_MAX_S = 0.3, 3.0
BLOCK = 10  # reaches per block; block % 5 == 4 -> test, == 3 -> validation (inside training)
N_SHOW = 12
SHOW_MIN_S, SHOW_MAX_S = 0.8, 2.0
POS_SCALE = 10  # stored positions are integers in 0.1 mm


@dataclass
class Binned:
    edges_s: np.ndarray  # (T, 2) start/stop of each bin
    seg: np.ndarray  # (T,) continuous-segment id
    seg_start: np.ndarray  # (T,) bool, first bin of a segment
    pos: np.ndarray  # (T, 2) mm
    vel: np.ndarray  # (T, 2) mm/s
    reach: np.ndarray  # (T,) reach id or -1
    reaches: list[dict]


def valid_runs(valid: np.ndarray) -> list[tuple[int, int]]:
    """[start, stop) sample index ranges where `valid` is True."""
    d = np.diff(np.concatenate([[0], valid.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0], strict=True))


def segment(sess: dataset.Session) -> Binned:
    rate = sess.rate_hz
    spb = round(BIN_S * rate)
    valid = ~(
        np.isnan(sess.cursor_mm).any(1)
        | np.isnan(sess.finger_vel_mm_s).any(1)
        | np.isnan(sess.target_mm).any(1)
    )
    edges, seg, pos, vel, reach_of_bin = [], [], [], [], []
    reaches: list[dict] = []
    for sid, (a, b) in enumerate(valid_runs(valid)):
        nb = (b - a) // spb
        if nb < N_LAGS + 2:
            continue
        starts = a + spb * np.arange(nb)
        tgt = sess.target_mm[a:b]
        change = a + 1 + np.where(np.any(tgt[1:] != tgt[:-1], axis=1))[0]
        bin_reach = np.full(nb, -1)
        for c0, c1 in zip(change[:-1], change[1:], strict=True):
            dur = (c1 - c0) / rate
            if not REACH_MIN_S <= dur <= REACH_MAX_S:
                continue
            inside = (starts >= c0) & (starts + spb <= c1)
            if inside.sum() < 3:
                continue
            rid = len(reaches)
            bin_reach[inside] = rid
            reaches.append(
                {
                    "id": rid,
                    "startS": c0 / rate,
                    "stopS": c1 / rate,
                    "target": sess.target_mm[c0].tolist(),
                }
            )
        for s in starts:
            edges.append((s / rate, (s + spb) / rate))
            pos.append(sess.cursor_mm[s : s + spb].mean(0))
            vel.append(sess.finger_vel_mm_s[s : s + spb].mean(0))
        seg.extend([sid] * nb)
        reach_of_bin.extend(bin_reach)
    seg_arr = np.array(seg)
    seg_start = np.ones(len(seg_arr), dtype=bool)
    seg_start[1:] = seg_arr[1:] != seg_arr[:-1]
    return Binned(
        edges_s=np.array(edges),
        seg=seg_arr,
        seg_start=seg_start,
        pos=np.array(pos),
        vel=np.array(vel),
        reach=np.array(reach_of_bin),
        reaches=reaches,
    )


def split_reaches(n: int) -> np.ndarray:
    """'train' | 'val' | 'test' per reach, in contiguous blocks of BLOCK reaches (chronological)."""
    block = np.arange(n) // BLOCK
    return np.where(block % 5 == 4, "test", np.where(block % 5 == 3, "val", "train"))


def noise_spikes(n_units: int, t_end: float, rng: np.random.Generator) -> list[np.ndarray]:
    """Spurious spikes at the highest noise rate with a level key; lower levels are nested subsets.

    Returns per unit an array (k, 2): time_s, key in [0, 1). A spike is present at noise level
    rate r when key < r / max(NOISE_HZ).
    """
    out = []
    for _ in range(n_units):
        k = rng.poisson(max(NOISE_HZ) * t_end)
        t = np.sort(rng.uniform(0.0, t_end, k))
        out.append(np.column_stack([t, rng.uniform(0.0, 1.0, k)]))
    return out


def counts_with_noise(
    clean: np.ndarray, noise_counts: list[np.ndarray], level: float
) -> np.ndarray:
    if level == 0:
        return clean
    idx = [i for i, r in enumerate(NOISE_HZ) if r == level][0]
    return clean + noise_counts[idx]


def fit_ridge(x, y, train, val):
    """Pick alpha on the validation reaches, refit on train + val."""
    best = None
    for a in ALPHAS:
        m = Ridge(a).fit(x[train], y[train])
        s = r2_score(y[val], m.predict(x[val]))
        if best is None or s > best[1]:
            best = (a, s)
    return Ridge(best[0]).fit(x[train | val], y[train | val]), best[0]


def shift_obs(counts: np.ndarray, lag: int, seg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Observation for the state at bin t = counts at bin t - lag (same segment)."""
    if lag == 0:
        return counts, np.ones(len(counts), dtype=bool)
    out = np.zeros_like(counts)
    out[lag:] = counts[:-lag]
    ok = np.zeros(len(counts), dtype=bool)
    ok[lag:] = seg[lag:] == seg[:-lag]
    out[~ok] = counts.mean(0)  # at a segment start, use the mean rate (no spikes from before a gap)
    return out, ok


def fit_kalman(b: Binned, counts, lag, fit_mask):
    y, ok = shift_obs(counts, lag, b.seg)
    z = np.hstack([b.pos, b.vel])
    m = fit_mask & ok
    contiguous = np.zeros(len(z), dtype=bool)
    contiguous[1:] = (b.seg[1:] == b.seg[:-1]) & m[1:] & m[:-1]
    kf = Kalman().fit(z[m], y[m], contiguous[m])
    return kf, y


def run(nwb: Path, out: Path, verify: bool = True) -> dict:
    sess = dataset.load(nwb, verify=verify)
    b = segment(sess)
    n_units = len(sess.spike_times)
    split = split_reaches(len(b.reaches))
    rsplit = np.where(b.reach >= 0, split[np.maximum(b.reach, 0)], "none")
    train, val, test = rsplit == "train", rsplit == "val", rsplit == "test"

    rng = np.random.default_rng(SEED)
    t_end = float(b.edges_s[-1, 1]) + 1.0
    noise = noise_spikes(n_units, t_end, rng)
    perms = [rng.permutation(n_units) for _ in range(N_SUBSETS)]

    # Bin clean spikes and nested noise levels on the same (possibly gapped) bin grid.
    def binned(times: list[np.ndarray]) -> np.ndarray:
        out = np.zeros((len(b.edges_s), len(times)))
        for sid in np.unique(b.seg):
            rows = np.where(b.seg == sid)[0]
            e = np.concatenate([b.edges_s[rows, 0], [b.edges_s[rows[-1], 1]]])
            out[rows] = bin_spikes(times, e)
        return out

    clean = binned(sess.spike_times)
    noise_counts = [
        binned([u[u[:, 1] < r / max(NOISE_HZ), 0] for u in noise]) if r > 0 else None
        for r in NOISE_HZ
    ]
    z_true = np.hstack([b.pos, b.vel])

    # Kalman lag chosen once, on the validation reaches, with all units and no added noise.
    kf_lag_scores = {}
    for lag in KF_LAGS:
        kf, y = fit_kalman(b, clean, lag, train)
        est = kf.filter(y, b.seg_start)
        kf_lag_scores[lag] = r2_score(z_true[val, :2], est[val, :2])
    kf_lag = max(kf_lag_scores, key=kf_lag_scores.get)

    # Display trials: evenly spaced test reaches of a watchable length (chosen before decoding).
    test_ids = [r["id"] for r in b.reaches if split[r["id"]] == "test"]
    eligible = [
        i
        for i in test_ids
        if SHOW_MIN_S <= b.reaches[i]["stopS"] - b.reaches[i]["startS"] <= SHOW_MAX_S
    ]
    show = [eligible[int(round(k))] for k in np.linspace(0, len(eligible) - 1, N_SHOW)]
    show_rows = {i: np.where(b.reach == i)[0] for i in show}

    results: dict[str, list[list[dict]]] = {"ridge": [], "kalman": []}
    decoded: dict[int, dict[str, list[list[list[int]]]]] = {
        i: {"ridge": [], "kalman": []} for i in show
    }
    alphas_used = {}
    for ci, nc in enumerate(NEURON_COUNTS):
        for name in results:
            results[name].append([])
            for i in show:
                decoded[i][name].append([])
        for lvl in NOISE_HZ:
            counts_all = counts_with_noise(clean, noise_counts, lvl)
            per = {"ridge": [], "kalman": []}
            for p, perm in enumerate(perms):
                if nc == n_units and p > 0:
                    break  # every subset of all units is the same set
                cols = np.sort(perm[:nc])
                c = counts_all[:, cols]
                x = lagged(c, N_LAGS, b.seg)
                ridge, alpha = fit_ridge(x, z_true, train, val)
                est_r = ridge.predict(x)
                kf, y = fit_kalman(b, c, kf_lag, train | val)
                est_k = kf.filter(y, b.seg_start)
                for name, est in (("ridge", est_r), ("kalman", est_k)):
                    per[name].append(
                        {
                            "pos": r2_score(z_true[test, :2], est[test, :2]),
                            "vel": r2_score(z_true[test, 2:], est[test, 2:]),
                        }
                    )
                    if p == 0:
                        for i in show:
                            rows = show_rows[i]
                            decoded[i][name][ci].append(
                                np.round(est[rows, :2] * POS_SCALE).astype(int).ravel().tolist()
                            )
                if p == 0:
                    alphas_used[f"{nc}/{lvl:g}"] = alpha
            for name in results:
                pos = [s["pos"] for s in per[name]]
                results[name][ci].append(
                    {
                        "posR2": round(per[name][0]["pos"], 4),
                        "velR2": round(per[name][0]["vel"], 4),
                        "posR2Mean": round(float(np.mean(pos)), 4),
                        "posR2Min": round(float(np.min(pos)), 4),
                        "posR2Max": round(float(np.max(pos)), 4),
                        "subsets": len(pos),
                    }
                )
            rr, kk = results["ridge"][ci][-1], results["kalman"][ci][-1]
            print(
                f"units={nc:3d} noise={lvl:4.1f}Hz"
                f"  ridge pos {rr['posR2']:.3f} vel {rr['velR2']:.3f}"
                f" | kalman pos {kk['posR2']:.3f} vel {kk['velR2']:.3f}",
                flush=True,
            )

    # Negative control: labels circularly shifted by half the session -> R² should be <= ~0.
    x_full = lagged(clean, N_LAGS, b.seg)
    shifted = np.roll(z_true, len(z_true) // 2, axis=0)
    ctrl, _ = fit_ridge(x_full, shifted, train, val)
    control_r2 = r2_score(shifted[test, :2], ctrl.predict(x_full)[test, :2])

    trials = []
    for i in show:
        rows = show_rows[i]
        t0 = float(b.edges_s[rows[0], 0])
        t1 = float(b.edges_s[rows[-1], 1])
        spikes = []
        extra = []
        for u in range(n_units):
            st = sess.spike_times[u]
            spikes.append(np.round((st[(st >= t0) & (st < t1)] - t0) * 1000).astype(int).tolist())
            nz = noise[u]
            nz = nz[(nz[:, 0] >= t0) & (nz[:, 0] < t1)]
            # level index = first NOISE_HZ index at which this spurious spike is present
            lv = [
                next(k for k, r in enumerate(NOISE_HZ) if r > 0 and key < r / max(NOISE_HZ))
                for key in nz[:, 1]
            ]
            ms = np.round((nz[:, 0] - t0) * 1000).astype(int).tolist()
            extra.append([v for pair in zip(ms, lv, strict=True) for v in pair])
        r = b.reaches[i]
        trials.append(
            {
                "reach": i,
                "t0Ms": round(t0 * 1000),
                "durationMs": round((t1 - t0) * 1000),
                "bins": len(rows),
                "target": [round(v * POS_SCALE) for v in r["target"]],
                "truePos": np.round(b.pos[rows] * POS_SCALE).astype(int).ravel().tolist(),
                "spikes": spikes,
                "noiseSpikes": extra,
                "decoded": decoded[i],
            }
        )

    all_pos = b.pos[b.reach >= 0]
    asset = {
        "schema": SCHEMA,
        "dataset": {
            "shortName": "MC_RTT",
            "name": "MC_RTT (Neural Latents Benchmark), monkey Indy, random-target reaching",
            "dandiset": dataset.DANDISET,
            "version": dataset.VERSION,
            "asset": dataset.ASSET_PATH,
            "sha256": dataset.SHA256,
            "doi": dataset.DOI,
            "licence": dataset.LICENCE,
            "citation": dataset.CITATION,
            "units": n_units,
            "meanRateHz": round(
                sum(len(st) for st in sess.spike_times)
                / n_units
                / (len(sess.cursor_mm) / sess.rate_hz),
                2,
            ),
            "area": "primary motor cortex (M1), 96-channel Utah array",
        },
        "method": {
            "binMs": round(BIN_S * 1000),
            "ridgeLags": N_LAGS,
            "kalmanLagBins": kf_lag,
            "kalmanLagValR2": {str(k): round(v, 4) for k, v in kf_lag_scores.items()},
            "ridgeAlpha": alphas_used,
            "split": (
                f"reaches in chronological blocks of {BLOCK}; every 5th block is test, the block "
                "before it is validation (hyper-parameters), the rest is training"
            ),
            "reaches": {s: int((split == s).sum()) for s in ("train", "val", "test")},
            "testBins": int(test.sum()),
            "seed": SEED,
            "noise": "random extra spikes (Poisson) added to every unit, training and test alike",
            "shownTrials": (
                f"{N_SHOW} test reaches lasting {SHOW_MIN_S}-{SHOW_MAX_S} s, evenly spaced in "
                "time; chosen before decoding"
            ),
            "controlShuffledPosR2": round(control_r2, 4),
        },
        "neuronCounts": NEURON_COUNTS,
        "noiseHz": NOISE_HZ,
        "decoders": ["ridge", "kalman"],
        "unitOrder": perms[0].tolist(),
        # Electrode id per unit. The file has no array map: any drawn grid layout is illustrative.
        "unitElectrode": sess.unit_electrode.astype(int).tolist(),
        "electrodes": 96,
        "bounds": {
            "min": np.floor(all_pos.min(0) * POS_SCALE).astype(int).tolist(),
            "max": np.ceil(all_pos.max(0) * POS_SCALE).astype(int).tolist(),
        },
        "posScale": POS_SCALE,
        "results": results,
        "trials": trials,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    text = encode.dumps(encode.compact(asset))  # lossless nf-playground/2 (encode.py)
    out.write_text(text, encoding="utf-8", newline="\n")  # LF on Windows too
    print(f"wrote {out} ({out.stat().st_size / 1024:.1f} KiB); kalman lag {kf_lag} bins;")
    print(f"control (shifted labels) ridge pos R2 {control_r2:.3f}")
    print(f"reaches {asset['method']['reaches']}")
    return asset


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--nwb",
        type=Path,
        default=Path(os.environ.get("NF_PLAYGROUND_DATA", Path.home() / "playground-data"))
        / dataset.FILE_NAME,
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[3]
        / "apps/web/src/assets/playground/mc-rtt-playground.json",
    )
    ap.add_argument("--no-verify", action="store_true", help="skip the sha256 check")
    a = ap.parse_args()
    run(a.nwb, a.out, verify=not a.no_verify)


if __name__ == "__main__":
    main()
