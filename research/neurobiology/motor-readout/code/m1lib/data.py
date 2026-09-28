"""NWB (h5py, only the needed arrays) and EDF+ loaders for M1.

RESEARCH USE ONLY. NOT A MEDICAL DEVICE.
D1: MC_Maze(_Large/_Small) train NWB -> per-trial onset-aligned grids of spike counts and mean hand velocity.
D2: LINK NWB -> SBP (96 ch) and index/MRS velocity, re-binned 20 ms -> 32 ms (area-preserving), per-bin trial owner.
D3: EEGMMIDB EDF+ -> 64-ch EEG + TAL annotations.
"""
import os

import h5py
import numpy as np

from . import NB_CODE  # noqa: F401
from edf_reader import read_edf, read_header  # noqa: E402  (pure-numpy reader, research/neurobiology/code)

GRID_PRE_MS = 750     # grid starts 750 ms before movement onset (window -250 ms, history 200 ms, NC2b tau -500 ms)
GRID_POST_MS = 950    # grid ends 950 ms after onset (window +450 ms, NC2b tau +500 ms)


def _s(x):
    return x.decode() if isinstance(x, bytes) else str(x)


# ---------------------------------------------------------------- D1
def d1_trials(path):
    """Trial table only (timing + condition metadata; no behaviour)."""
    with h5py.File(path, "r") as f:
        t = f["intervals/trials"]
        return dict(id=t["id"][:].astype(int), start=t["start_time"][:], stop=t["stop_time"][:],
                    onset=t["move_onset_time"][:], maze_id=t["maze_id"][:].astype(int), n_units=int(f["units/id"].shape[0]))


class D1Source:
    """Loads spike times (per unit) and the 1 kHz hand velocity once; grids are cut on demand.
    Grid: bins [onset + (rel0 + bin*j)/1000, +bin) s, j = 0..nb-1."""

    def __init__(self, path):
        with h5py.File(path, "r") as f:
            st = f["units/spike_times"][:]
            idx = f["units/spike_times_index"][:].astype(np.int64)
            self.vts = f["processing/behavior/hand_vel/timestamps"][:]
            conv = float(f["processing/behavior/hand_vel/data"].attrs.get("conversion", 1.0))
            vel = f["processing/behavior/hand_vel/data"][:] * conv
        lo, self.spikes = 0, []
        for u in range(idx.size):
            self.spikes.append(np.sort(st[lo:idx[u]]))
            lo = idx[u]
        self.n_units = idx.size
        self.n_spikes = int(st.size)
        self.vcs = np.vstack([np.zeros((1, 2)), np.cumsum(vel, axis=0)])
        self.vel_nan = int(np.isnan(vel).sum())

    @staticmethod
    def edges(onset, bin_ms, rel0_ms, nb):
        return onset[:, None] + ((rel0_ms + bin_ms * np.arange(nb + 1)) / 1000.0)[None, :]

    def counts(self, onset, bin_ms, rel0_ms=-GRID_PRE_MS, nb=None):
        nb = (GRID_PRE_MS + GRID_POST_MS) // bin_ms if nb is None else nb
        e = self.edges(onset, bin_ms, rel0_ms, nb)
        flat = e.ravel()
        out = np.empty((len(onset), nb, self.n_units), dtype=np.float32)
        for u, s in enumerate(self.spikes):
            out[:, :, u] = np.diff(np.searchsorted(s, flat, side="left").reshape(e.shape), axis=1)
        return out

    def velocity(self, onset, bin_ms, rel0_ms=-GRID_PRE_MS, nb=None):
        nb = (GRID_PRE_MS + GRID_POST_MS) // bin_ms if nb is None else nb
        e = self.edges(onset, bin_ms, rel0_ms, nb)
        ci = np.searchsorted(self.vts, e.ravel(), side="left").reshape(e.shape)
        n = np.diff(ci, axis=1).astype(float)
        if np.any(n == 0):
            raise ValueError("velocity grid has %d empty bins" % int((n == 0).sum()))
        v = (self.vcs[ci[:, 1:]] - self.vcs[ci[:, :-1]]) / n[..., None]
        if not np.all(np.isfinite(v)):
            raise ValueError("non-finite velocity in grid")
        return v


# ---------------------------------------------------------------- D2
def rebin(x, old_ms=20, new_ms=32):
    """Area-preserving re-binning on the uniform index grid: new bin m = mean over [m*new, (m+1)*new) ms of the
    piecewise-constant old signal (old bin i covers [i*old, (i+1)*old))."""
    T = x.shape[0]
    n_new = (T * old_ms) // new_ms
    C = np.vstack([np.zeros((1,) + x.shape[1:]), np.cumsum(x * old_ms, axis=0)])
    t = np.arange(n_new + 1) * new_ms
    i = np.minimum(t // old_ms, T - 1)
    frac = (t - i * old_ms)[:, None]
    Ct = C[i] + frac * x[i]
    return np.diff(Ct, axis=0) / new_ms


def d2_trials(path):
    with h5py.File(path, "r") as f:
        t = f["intervals/trials"]
        ts0 = float(f["analysis/SpikingBandPower/timestamps"][0])
        T = int(f["analysis/SpikingBandPower/timestamps"].shape[0])
        return dict(id=t["id"][:].astype(int), start=t["start_time"][:], stop=t["stop_time"][:],
                    style=np.array([_s(s) for s in t["target_style"][:]]), ts0=ts0, T20=T)


def d2_owner(tr, n32, bin_ms=32, old_ms=20):
    """Trial owner per 32-ms bin by bin centre; trial k spans [start_k, stop_k + 20 ms) (stop = last 20-ms stamp)."""
    centre = tr["ts0"] + (np.arange(n32) + 0.5) * bin_ms / 1000.0
    own = np.full(n32, -1, dtype=int)
    for i, a, b in zip(tr["id"], tr["start"], tr["stop"]):
        own[(centre >= a) & (centre < b + old_ms / 1000.0)] = i
    return own


def d2_neural(path):
    with h5py.File(path, "r") as f:
        x = f["analysis/SpikingBandPower/data"][:]
        ts = f["analysis/SpikingBandPower/timestamps"][:]
    d = np.diff(ts)
    return rebin(x), dict(dt_median_s=float(np.median(d)), dt_min_s=float(d.min()), dt_max_s=float(d.max()), n20=int(len(ts)))


def d2_behaviour(path):
    with h5py.File(path, "r") as f:
        v = np.column_stack([f["analysis/index_velocity/data"][:, 0], f["analysis/mrs_velocity/data"][:, 0]])
    return rebin(v)


# ---------------------------------------------------------------- D3 (EDF+)
def edf_annotations(path):
    h = read_header(path)
    ai = h["labels"].index("EDF Annotations")
    spr = h["samples_per_record"]
    rec = int(spr.sum()) * 2
    off = int(spr[:ai].sum()) * 2
    out = []
    with open(path, "rb") as fh:
        fh.seek(h["header_bytes"])
        raw = fh.read(rec * h["n_records"])
    for r in range(h["n_records"]):
        blk = raw[r * rec + off: r * rec + off + int(spr[ai]) * 2].decode("latin-1")
        for tal in blk.split("\x00"):
            if not tal:
                continue
            parts = tal.split("\x14")
            head = parts[0].split("\x15")
            onset = float(head[0])
            dur = float(head[1]) if len(head) > 1 and head[1] else None
            for txt in parts[1:]:
                if txt:
                    out.append((onset, dur, txt))
    return out, h


def d3_run(path, n_eeg=64):
    x, fs, lab = read_edf(path, channels=list(range(n_eeg)))
    ann, h = edf_annotations(path)
    return x.astype(np.float64), float(fs), lab, ann, h["n_records"] * h["record_duration"]


def file_paths():
    from . import RAW
    d1 = os.path.join(RAW, "000138", "sub-Jenkins_ses-large_desc-train_behavior+ecephys.nwb")
    dry = os.path.join(RAW, "000140", "sub-Jenkins_ses-small_desc-train_behavior+ecephys.nwb")
    return d1, dry
