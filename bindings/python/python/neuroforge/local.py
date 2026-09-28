"""Offline tools that need no server: the local provenance recorder, the Zarr v3 signal store
and the content-addressed chunk cache (all in nf-core)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from . import _native

__all__ = ["ChunkCache", "ProvRecorder", "read_signal", "write_signal"]


class ProvRecorder:
    """A local provenance hash chain (hashing spec §5.3) that works offline.

    >>> rec = ProvRecorder("~/.neuroforge/prov", chain="local:lab-pc-1")
    >>> seq, batch_id = rec.record([
    ...     {"type": "entity", "id": "e1", "label": "raw", "content": "blob:sha256:..."},
    ...     {"type": "activity", "id": "a1", "label": "acquire"},
    ...     {"type": "edge", "rel": "wasGeneratedBy", "from": "e1", "to": "a1"},
    ... ])

    The chain is re-verified every time it is opened; an edited file raises. ``sync(upload)``
    sends pending batches in order and marks each one only after ``upload`` returns.
    """

    def __init__(self, directory: str | os.PathLike[str], chain: str) -> None:
        self._r = _native.ProvRecorder(os.path.expanduser(os.fspath(directory)), chain)
        self.chain = chain

    def record(self, records: list[dict[str, Any]]) -> tuple[int, str]:
        return self._r.record(json.dumps(records, allow_nan=False))

    def pending(self) -> list[tuple[int, str, bytes]]:
        return self._r.pending()

    def head(self) -> tuple[int, str] | None:
        return self._r.head()

    def batch_ids(self) -> list[str]:
        return self._r.batch_ids()

    def sync(self, upload: Callable[[bytes, str], None]) -> int:
        n = 0
        for seq, bid, payload in self._r.pending():
            upload(payload, bid)
            self._r.mark_synced(seq)
            n += 1
        return n

    def __len__(self) -> int:
        return len(self._r)


STORED = {  # zarr-layout.md §4
    "int8": "int16",
    "uint8": "int16",
    "int16": "int16",
    "uint16": "int32",
    "int32": "int32",
    "uint32": "int64",
    "int64": "int64",
    "float32": "float32",
    "float64": "float64",
}


def write_signal(
    root: str | os.PathLike[str],
    recording_id: str,
    data: np.ndarray,
    sfreq: float,
    ch_names: list[str],
    units: list[str] | str = "uV",
    *,
    chunk_s: float = 4.0,
    chunk_channels: int = 64,
    timestamps: np.ndarray | None = None,
) -> None:
    """Write ``data`` (samples x channels) as level 0 of an ``nf-signal/1`` Zarr v3 group."""
    a = np.asarray(data)
    if a.ndim != 2 or a.shape[1] != len(ch_names):
        raise ValueError("data must be (n_samples, n_channels) matching ch_names")
    stored = STORED.get(a.dtype.name)
    if stored is None:
        raise ValueError(f"dtype {a.dtype} is not accepted (zarr-layout.md §4)")
    if a.dtype.kind == "f" and not np.isfinite(a).all():
        raise ValueError("float data must be finite")
    le = np.ascontiguousarray(a, dtype=np.dtype(stored).newbyteorder("<"))
    u = [units] * len(ch_names) if isinstance(units, str) else list(units)
    ts = (
        None if timestamps is None else [float(x) for x in np.asarray(timestamps, dtype=np.float64)]
    )
    _native.write_signal(
        os.fspath(root),
        recording_id,
        le.tobytes(),
        stored,
        a.shape[0],
        float(sfreq),
        list(ch_names),
        u,
        chunk_s,
        chunk_channels,
        ts,
    )


def read_signal(
    root: str | os.PathLike[str], recording_id: str, start: int = 0, stop: int | None = None
) -> np.ndarray:
    """Samples ``[start, stop)`` x all channels of level 0, in the stored dtype."""
    dtype, shape, raw = _native.read_signal(
        os.fspath(root), recording_id, start, stop if stop is not None else 2**63 - 1
    )
    return np.frombuffer(raw, dtype=np.dtype(dtype).newbyteorder("<")).reshape(shape).astype(dtype)


class ChunkCache:
    """Content-addressed chunk cache (entries verified against their ID on every read)."""

    def __init__(self, root: str | os.PathLike[str], max_bytes: int = 2 * 1024**3) -> None:
        Path(root).mkdir(parents=True, exist_ok=True)
        self._c = _native.ChunkCache(os.fspath(root), max_bytes)

    def put(self, array: np.ndarray) -> str:
        a = np.ascontiguousarray(array)
        le = a.astype(a.dtype.newbyteorder("<"), copy=False)
        return self._c.put(a.dtype.name, [int(x) for x in a.shape], le.tobytes())

    def get(self, chunk_id: str) -> np.ndarray | None:
        got = self._c.get(chunk_id)
        if got is None:
            return None
        dtype, shape, raw = got
        return (
            np.frombuffer(raw, dtype=np.dtype(dtype).newbyteorder("<")).reshape(shape).astype(dtype)
        )

    def size(self) -> int:
        return self._c.size()
