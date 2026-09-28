"""Append-only writer of a live stream into the canonical ``nf-signal/1`` layout (2.4 + 2.7).

While a stream is open its group holds level 0 only (``data/0`` + ``timestamps``), grown in
~60 s steps; ``nf_signal.n_samples`` (and pyramid level 0) are published whenever a ~1 s time
chunk is completed, so the data endpoint can read a live stream up to ~1 s behind the last
committed chunk (the authoritative count is ``ingest_stream.n_samples`` in Postgres). Samples are
written at the committed offset kept in Postgres, never "at the end of the array", so a retried
chunk overwrites identical bytes instead of appending twice. ``finish`` rebuilds the group with
``write_recording`` (pyramid, clock offsets) and adds the local-clock series; the level-0 bytes
and the original timestamps are carried over unchanged (SEC-094).

Limit (M2): ``finish`` holds one stream's level 0 in memory (10 min of 64 ch x 1 kHz float32 is
~150 MB). Incremental pyramids are future work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import zarr
from zarr.abc.store import Store

from nf_platform.signals.zarr_store import (
    DEFAULT_CHUNK_CHANNELS,
    LAYOUT_VERSION,
    PYRAMID_FACTOR,
    write_recording,
)

GROUP = "signal"
GROW_S = 60.0
LIVE_CHUNK_S = 1.0


@dataclass
class LiveArrays:
    data: Any
    timestamps: Any
    group: Any


def _signal_attrs(
    *,
    sfreq: float,
    n: int,
    dtype: str,
    ch_names: list[str],
    units: list[str],
    scale: list[float],
    offset: list[float],
    chunks: list[int],
) -> dict[str, Any]:
    return {
        "layout": LAYOUT_VERSION,
        "sfreq": float(sfreq),
        "n_samples": int(n),
        "n_channels": len(ch_names),
        "dtype": dtype,
        "source_dtype": dtype,
        "dims": ["time", "channel"],
        "ch_names": ch_names,
        "units": units,
        "scale": scale,
        "offset": offset,
        "physical": "stored * scale + offset",
        "chunks": chunks,
        "start_time": None,
        "has_timestamps": True,
        "has_clock_offsets": False,
        "live": True,
        "pyramid": {
            "factor": PYRAMID_FACTOR,
            "reductions": ["mean", "min", "max"],
            "levels": [{"level": 0, "decimation": 1, "n_samples": int(n), "sfreq": float(sfreq)}],
        },
    }


def open_live(
    store: Store,
    *,
    sfreq: float,
    dtype: str,
    ch_names: list[str],
    units: list[str],
    scale: list[float],
    offset: list[float],
    channels: list[dict[str, Any]],
    meta: dict[str, Any],
) -> LiveArrays:
    """Open the live group, creating it (level 0 + timestamps, capacity ~60 s) on first use."""
    root = zarr.open_group(store=store, mode="a")
    if GROUP in root:
        g = root[GROUP]
        return LiveArrays(g["data/0"], g["timestamps"], g)
    n_ch = len(ch_names)
    ct = max(1, round(LIVE_CHUNK_S * sfreq))
    cap = math.ceil(GROW_S * sfreq / ct) * ct
    g = root.create_group(GROUP)
    data = g.create_array(
        "data/0",
        shape=(cap, n_ch),
        dtype=dtype,
        chunks=(ct, min(n_ch, DEFAULT_CHUNK_CHANNELS)),
        fill_value=0,
        dimension_names=("time", "channel"),
    )
    ts = g.create_array(
        "timestamps",
        shape=(cap,),
        dtype="float64",
        chunks=(ct * 4,),
        fill_value=0.0,
        dimension_names=("time",),
    )
    g.attrs.update(
        {
            "nf_signal": _signal_attrs(
                sfreq=sfreq,
                n=0,
                dtype=dtype,
                ch_names=ch_names,
                units=units,
                scale=scale,
                offset=offset,
                chunks=[ct, min(n_ch, DEFAULT_CHUNK_CHANNELS)],
            ),
            "channels": channels,
            "meta": meta,
        }
    )
    return LiveArrays(data, ts, g)


def write_at(live: LiveArrays, start: int, samples: np.ndarray, timestamps: np.ndarray) -> int:
    """Write (n, n_ch) samples + n timestamps at ``start``; grow capacity if needed. Returns the
    new capacity."""
    n = samples.shape[0]
    cap = live.data.shape[0]
    if start + n > cap:
        ct = live.data.chunks[0]
        sfreq = float(live.group.attrs["nf_signal"]["sfreq"])
        grow = max(start + n - cap, math.ceil(GROW_S * sfreq / ct) * ct)
        cap = cap + math.ceil(grow / ct) * ct
        live.data.resize((cap, live.data.shape[1]))
        live.timestamps.resize((cap,))
    live.data[start : start + n, :] = samples
    live.timestamps[start : start + n] = timestamps
    ct = live.data.chunks[0]
    if (start + n) // ct == start // ct:
        # Publishing n_samples costs one more sealed object write; do it once per completed
        # time chunk (~1 s). Postgres (ingest_stream.n_samples) stays the authoritative count.
        return cap
    sig = dict(live.group.attrs["nf_signal"])
    sig["n_samples"] = int(start + n)
    sig["pyramid"] = dict(sig["pyramid"])
    sig["pyramid"]["levels"] = [
        {"level": 0, "decimation": 1, "n_samples": int(start + n), "sfreq": sig["sfreq"]}
    ]
    live.group.attrs["nf_signal"] = sig
    return cap


def finish(
    store: Store,
    n_samples: int,
    clock_offsets: np.ndarray,
    local_clock: np.ndarray,
    extra_meta: dict[str, Any],
) -> None:
    """Rebuild the group as a finished canonical recording (pyramid + timing series)."""
    g = zarr.open_group(store=store, path=GROUP, mode="r")
    attrs = g.attrs.asdict()
    sig = attrs["nf_signal"]
    data = np.asarray(g["data/0"][:n_samples, :])
    ts = np.asarray(g["timestamps"][:n_samples])
    write_recording(
        store,
        GROUP,
        np.ascontiguousarray(data.T),
        float(sig["sfreq"]),
        sig["ch_names"],
        sig["units"],
        scale=sig["scale"],
        offset=sig["offset"],
        timestamps=ts,
        clock_offsets=clock_offsets if len(clock_offsets) else None,
        channels=attrs.get("channels") or [],
        meta={**(attrs.get("meta") or {}), **extra_meta},
    )
    g2 = zarr.open_group(store=store, path=GROUP, mode="a")
    if len(local_clock):
        g2.create_array(
            "local_clock",
            data=np.asarray(local_clock, dtype=np.float64).reshape(-1, 2),
            dimension_names=("sample", "pair"),
        )
