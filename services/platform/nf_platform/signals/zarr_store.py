"""Canonical recording layout on Zarr v3: writer, window reader, multiscale pyramid.

See `docs/spec/zarr-layout.md` for the normative description. Summary:

    <recording_id>/            group; attrs["nf_signal"] = layout metadata
    <recording_id>/data/0      level 0, shape (time, channel), stored dtype (see DTYPE_POLICY)
    <recording_id>/data/<k>    level k >= 1: block mean over factor**k samples (float32/float64)
    <recording_id>/min/<k>     level k >= 1: block minimum (stored dtype)
    <recording_id>/max/<k>     level k >= 1: block maximum (stored dtype)
    <recording_id>/timestamps  optional float64 (time,), original per-sample timestamps [s]
    <recording_id>/clock_offsets  optional float64 (n, 2): (collection time, offset) pairs

Physical value = stored value * scale[channel] + offset[channel], in units[channel].
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import zarr
from zarr.abc.store import Store

LAYOUT_VERSION = "nf-signal/1"
DEFAULT_CHUNK_S = 4.0
DEFAULT_CHUNK_CHANNELS = 64
PYRAMID_FACTOR = 4
PYRAMID_MIN_SAMPLES = 256
MAX_LEVELS = 12

# stored dtype for each accepted input dtype (lossless in every case)
DTYPE_POLICY: dict[str, str] = {
    "int8": "int16",
    "uint8": "int16",
    "int16": "int16",
    "uint16": "int32",
    "int32": "int32",
    "int64": "int64",
    "float32": "float32",
    "float64": "float64",
}


class SignalError(ValueError):
    """Invalid recording input or window request."""


@dataclass(frozen=True)
class ZarrRef:
    recording_id: str
    shape: tuple[int, int]  # (time, channel)
    dtype: str
    sfreq: float
    chunks: tuple[int, int]
    levels: int  # number of pyramid levels including level 0


@dataclass(frozen=True)
class RecordingInfo:
    recording_id: str
    attrs: dict[str, Any]

    @property
    def signal(self) -> dict[str, Any]:
        return self.attrs["nf_signal"]

    @property
    def sfreq(self) -> float:
        return float(self.signal["sfreq"])

    @property
    def ch_names(self) -> list[str]:
        return list(self.signal["ch_names"])

    @property
    def n_samples(self) -> int:
        return int(self.signal["n_samples"])

    @property
    def scale(self) -> np.ndarray:
        return np.asarray(self.signal["scale"], dtype=np.float64)

    @property
    def offset(self) -> np.ndarray:
        return np.asarray(self.signal["offset"], dtype=np.float64)


def _pyramid_plan(n: int, factor: int, min_samples: int) -> list[int]:
    decims = [1]
    while len(decims) < MAX_LEVELS:
        d = decims[-1] * factor
        if math.ceil(n / d) < min_samples:
            break
        decims.append(d)
    return decims


def _as_list(x: Any, n: int, name: str, default: Any) -> list[Any]:
    if x is None:
        return [default] * n
    if isinstance(x, str | int | float):
        return [x] * n
    lst = list(x)
    if len(lst) != n:
        raise SignalError(f"{name} must have one entry per channel ({n}), got {len(lst)}")
    return lst


def _json_float(v: float) -> float:
    f = float(v)
    if not math.isfinite(f):
        raise SignalError("scale/offset must be finite")
    return f


def write_recording(
    store: Store,
    recording_id: str,
    data: np.ndarray,
    sfreq: float,
    ch_names: Sequence[str],
    units: Sequence[str] | str,
    *,
    chunk_s: float = DEFAULT_CHUNK_S,
    chunk_channels: int = DEFAULT_CHUNK_CHANNELS,
    scale: Sequence[float] | float | None = None,
    offset: Sequence[float] | float | None = None,
    timestamps: np.ndarray | None = None,
    clock_offsets: np.ndarray | None = None,
    start_time: str | None = None,
    channels: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
    pyramid_factor: int = PYRAMID_FACTOR,
    pyramid_min_samples: int = PYRAMID_MIN_SAMPLES,
    compressors: Any = "auto",
) -> ZarrRef:
    """Write `data` (n_channels, n_samples) as a canonical recording under `recording_id`."""
    data = np.asarray(data)
    if data.ndim != 2 or data.shape[0] < 1 or data.shape[1] < 1:
        raise SignalError("data must be a non-empty 2-D array (n_channels, n_samples)")
    src = data.dtype.name
    if src not in DTYPE_POLICY:
        raise SignalError(f"dtype {src} is not accepted (policy: {sorted(DTYPE_POLICY)})")
    stored = np.dtype(DTYPE_POLICY[src])
    if stored.kind == "f" and not np.isfinite(data).all():
        raise SignalError("float data must be finite (NaN/Inf are not stored)")
    n_ch, n = data.shape
    if not (isinstance(sfreq, int | float) and math.isfinite(sfreq) and sfreq > 0):
        raise SignalError("sfreq must be a positive finite number")
    names = [str(c) for c in ch_names]
    if len(names) != n_ch or len(set(names)) != n_ch:
        raise SignalError("ch_names must be unique and match the channel count")
    unit_l = _as_list(units, n_ch, "units", "")
    scale_l = [_json_float(v) for v in _as_list(scale, n_ch, "scale", 1.0)]
    offset_l = [_json_float(v) for v in _as_list(offset, n_ch, "offset", 0.0)]
    if timestamps is not None:
        timestamps = np.asarray(timestamps, dtype=np.float64)
        if timestamps.shape != (n,):
            raise SignalError("timestamps must have one entry per sample")
    if chunk_s <= 0 or chunk_channels < 1 or pyramid_factor < 2:
        raise SignalError("chunk_s, chunk_channels and pyramid_factor must be positive")

    ct = max(1, min(n, round(chunk_s * sfreq)))
    cc = max(1, min(n_ch, chunk_channels))
    decims = _pyramid_plan(n, pyramid_factor, pyramid_min_samples)
    mean_dtype = np.float64 if stored == np.float64 else np.float32

    root = zarr.open_group(store=store, mode="a")
    if recording_id in root:
        del root[recording_id]
    g = root.create_group(recording_id)
    level_info = []
    arrays: dict[tuple[str, int], Any] = {}
    for k, d in enumerate(decims):
        n_k = math.ceil(n / d)
        level_info.append(
            {"level": k, "decimation": d, "n_samples": n_k, "sfreq": float(sfreq) / d}
        )
        common = {
            "chunks": (min(ct, n_k), cc),
            "dimension_names": ("time", "channel"),
            "compressors": compressors,
        }
        if k == 0:
            arrays[("data", 0)] = g.create_array(
                "data/0", shape=(n_k, n_ch), dtype=stored, fill_value=0, **common
            )
            continue
        arrays[("data", k)] = g.create_array(
            f"data/{k}", shape=(n_k, n_ch), dtype=mean_dtype, fill_value=0, **common
        )
        for kind in ("min", "max"):
            arrays[(kind, k)] = g.create_array(
                f"{kind}/{k}", shape=(n_k, n_ch), dtype=stored, fill_value=0, **common
            )

    # Stream over time in slabs aligned to every level's decimation and to the level-0 chunk.
    # A slab must be a multiple of the coarsest decimation (so every block mean is complete);
    # aligning it to the level-0 chunk as well avoids read-modify-write when that stays small.
    row = n_ch * stored.itemsize
    unit = decims[-1]
    if math.lcm(ct, unit) * row <= 32 * 1024 * 1024:
        unit = math.lcm(ct, unit)
    slab = unit * max(1, (8 * 1024 * 1024) // (unit * row))
    for t0 in range(0, n, slab):
        t1 = min(n, t0 + slab)
        x = np.ascontiguousarray(data[:, t0:t1].astype(stored, copy=False).T)  # (time, channel)
        arrays[("data", 0)][t0:t1, :] = x
        for k, d in enumerate(decims[1:], start=1):
            idx = np.arange(0, t1 - t0, d)
            j0 = t0 // d
            sums = np.add.reduceat(x.astype(np.float64), idx, axis=0)
            counts = np.diff(np.append(idx, t1 - t0))[:, None]
            arrays[("data", k)][j0 : j0 + len(idx), :] = (sums / counts).astype(mean_dtype)
            arrays[("min", k)][j0 : j0 + len(idx), :] = np.minimum.reduceat(x, idx, axis=0)
            arrays[("max", k)][j0 : j0 + len(idx), :] = np.maximum.reduceat(x, idx, axis=0)

    if timestamps is not None:
        g.create_array(
            "timestamps", data=timestamps, chunks=(min(n, ct * 16),), dimension_names=("time",)
        )
    if clock_offsets is not None:
        co = np.asarray(clock_offsets, dtype=np.float64).reshape(-1, 2)
        g.create_array("clock_offsets", data=co, dimension_names=("offset", "pair"))

    g.attrs.update(
        {
            "nf_signal": {
                "layout": LAYOUT_VERSION,
                "sfreq": float(sfreq),
                "n_samples": n,
                "n_channels": n_ch,
                "dtype": stored.name,
                "source_dtype": src,
                "dims": ["time", "channel"],
                "ch_names": names,
                "units": unit_l,
                "scale": scale_l,
                "offset": offset_l,
                "physical": "stored * scale + offset",
                "chunks": [ct, cc],
                "start_time": start_time,
                "has_timestamps": timestamps is not None,
                "has_clock_offsets": clock_offsets is not None,
                "pyramid": {
                    "factor": pyramid_factor,
                    "reductions": ["mean", "min", "max"],
                    "levels": level_info,
                },
            },
            "channels": channels or [],
            "meta": meta or {},
        }
    )
    return ZarrRef(recording_id, (n, n_ch), stored.name, float(sfreq), (ct, cc), len(decims))


def open_recording(store: Store, recording_id: str) -> RecordingInfo:
    try:
        g = zarr.open_group(store=store, path=recording_id, mode="r")
    except (FileNotFoundError, KeyError, zarr.errors.GroupNotFoundError) as e:
        raise SignalError(f"recording {recording_id!r} not found") from e
    attrs = g.attrs.asdict()
    sig = attrs.get("nf_signal")
    if not isinstance(sig, dict) or sig.get("layout") != LAYOUT_VERSION:
        raise SignalError(f"{recording_id!r} is not an {LAYOUT_VERSION} recording")
    return RecordingInfo(recording_id, attrs)


def _channel_index(info: RecordingInfo, channels: Sequence[str | int] | None) -> list[int]:
    names = info.ch_names
    if channels is None:
        return list(range(len(names)))
    out = []
    for c in channels:
        if isinstance(c, int | np.integer) and not isinstance(c, bool):
            if not 0 <= int(c) < len(names):
                raise SignalError(f"channel index {c} out of range")
            out.append(int(c))
        elif isinstance(c, str):
            if c not in names:
                raise SignalError(f"unknown channel {c!r}")
            out.append(names.index(c))
        else:
            raise SignalError("channels must be names or indices")
    return out


def read_window(
    store: Store,
    recording_id: str,
    start_s: float,
    end_s: float,
    channels: Sequence[str | int] | None = None,
    level: int = 0,
    *,
    kind: Literal["mean", "min", "max"] = "mean",
    physical: bool = False,
) -> np.ndarray:
    """Return samples with start_s <= t < end_s as (n_channels, n_samples).

    Sample i of level k starts at t = i * decimation_k / sfreq. Level 0 returns the stored dtype
    (exact); `physical=True` applies scale/offset and returns float64.
    """
    info = open_recording(store, recording_id)
    levels = info.signal["pyramid"]["levels"]
    if not isinstance(level, int) or not 0 <= level < len(levels):
        raise SignalError(f"level must be in 0..{len(levels) - 1}")
    if not (math.isfinite(start_s) and math.isfinite(end_s)) or end_s <= start_s or start_s < 0:
        raise SignalError("need 0 <= start_s < end_s")
    lv = levels[level]
    sf_k, n_k = float(lv["sfreq"]), int(lv["n_samples"])
    i0 = min(n_k, max(0, math.ceil(start_s * sf_k - 1e-9)))
    i1 = min(n_k, max(i0, math.ceil(end_s * sf_k - 1e-9)))
    idx = _channel_index(info, channels)
    if level == 0:
        name = "data/0"
    elif kind == "mean":
        name = f"data/{level}"
    elif kind in ("min", "max"):
        name = f"{kind}/{level}"
    else:
        raise SignalError("kind must be mean, min or max")
    arr = zarr.open_array(store=store, path=f"{recording_id}/{name}", mode="r")
    if idx == list(range(idx[0], idx[-1] + 1)):
        block = arr[i0:i1, idx[0] : idx[-1] + 1]
    else:
        block = arr.get_orthogonal_selection((slice(i0, i1), idx))
    out = np.ascontiguousarray(np.asarray(block).T)
    if physical:
        out = out.astype(np.float64) * info.scale[idx, None] + info.offset[idx, None]
    return out


def read_array(store: Store, recording_id: str, name: str) -> np.ndarray:
    """Read a whole auxiliary array (e.g. `timestamps`, `clock_offsets`)."""
    try:
        return np.asarray(
            zarr.open_array(store=store, path=f"{recording_id}/{name}", mode="r")[...]
        )
    except (FileNotFoundError, KeyError, zarr.errors.ArrayNotFoundError) as e:
        raise SignalError(f"{recording_id!r} has no array {name!r}") from e
