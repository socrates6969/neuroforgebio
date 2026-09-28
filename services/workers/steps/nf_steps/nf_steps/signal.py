"""The value passed between steps, and its deterministic on-disk form.

A :class:`Signal` is one of three kinds:

- ``raw``: continuous data, ``data.shape == (n_channels, n_samples)``;
- ``epochs``: ``(n_epochs, n_channels, n_times)``, ``meta["tmin"]`` and ``meta["event_codes"]``;
- ``features``: ``(n_epochs, n_channels, n_features)``, ``meta["feature_names"]``.

On disk (step inputs/outputs, run artifacts) a signal is two files in one directory:
``signal.npy`` (float64, C order, little-endian, NumPy format 1.0 header) and ``signal.json``
(canonical JSON: sorted keys, no whitespace, UTF-8). Both are byte-deterministic for equal
content, which the reproducibility harness (3.5) relies on.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np

Kind = Literal["raw", "epochs", "features"]
DATA_FILE = "signal.npy"
META_FILE = "signal.json"
FILES = (DATA_FILE, META_FILE)
FORMAT = "nf.signal/v1"
_NDIM = {"raw": 2, "epochs": 3, "features": 3}


class SignalError(ValueError):
    """The signal does not have the shape or metadata a step needs."""


@dataclass
class Signal:
    kind: Kind
    data: np.ndarray
    sfreq: float
    ch_names: list[str]
    ch_types: list[str]
    bads: list[str] = field(default_factory=list)
    # Raw only: [[sample, code], ...] (sample index into this signal's time axis).
    events: list[list[int]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.data = np.ascontiguousarray(np.asarray(self.data, dtype="<f8"))
        if self.kind not in _NDIM:
            raise SignalError(f"unknown signal kind {self.kind!r}")
        if self.data.ndim != _NDIM[self.kind]:
            raise SignalError(f"{self.kind} data must have {_NDIM[self.kind]} dimensions")
        n_ch = self.data.shape[0] if self.kind == "raw" else self.data.shape[1]
        if len(self.ch_names) != n_ch or len(self.ch_types) != n_ch:
            raise SignalError("ch_names/ch_types do not match the channel axis")
        if len(set(self.ch_names)) != len(self.ch_names):
            raise SignalError("duplicate channel names")
        if not (math.isfinite(self.sfreq) and self.sfreq > 0):
            raise SignalError("sfreq must be a positive finite number")
        unknown = set(self.bads) - set(self.ch_names)
        if unknown:
            raise SignalError(f"bad channels not in the signal: {sorted(unknown)}")
        self.bads = sorted(self.bads, key=self.ch_names.index)
        self.events = [[int(s), int(c)] for s, c in self.events]

    def metadata(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "kind": self.kind,
            "shape": list(self.data.shape),
            "sfreq": float(self.sfreq),
            "ch_names": list(self.ch_names),
            "ch_types": list(self.ch_types),
            "bads": list(self.bads),
            "events": self.events,
            "meta": self.meta,
        }


def canonical_json(obj: Any) -> bytes:
    """Sorted keys, no whitespace, UTF-8, no NaN/Infinity (they are not JSON)."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def npy_bytes(data: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.lib.format.write_array(
        buf, np.ascontiguousarray(data, dtype="<f8"), version=(1, 0), allow_pickle=False
    )
    return buf.getvalue()


def to_files(sig: Signal) -> dict[str, bytes]:
    """The two files of a signal, as bytes (deterministic)."""
    return {DATA_FILE: npy_bytes(sig.data), META_FILE: canonical_json(sig.metadata())}


def write(sig: Signal, directory: str | Path) -> dict[str, str]:
    """Write ``sig`` into ``directory``; returns {file name: sha256 hex}."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, blob in to_files(sig).items():
        (d / name).write_bytes(blob)
        out[name] = hashlib.sha256(blob).hexdigest()
    return out


def from_files(files: dict[str, bytes]) -> Signal:
    meta = json.loads(files[META_FILE].decode("utf-8"))
    if meta.get("format") != FORMAT:
        raise SignalError(f"not an {FORMAT} signal")
    data = np.lib.format.read_array(io.BytesIO(files[DATA_FILE]), allow_pickle=False)
    if list(data.shape) != meta["shape"]:
        raise SignalError("data shape does not match signal.json")
    return Signal(
        kind=meta["kind"],
        data=data,
        sfreq=meta["sfreq"],
        ch_names=meta["ch_names"],
        ch_types=meta["ch_types"],
        bads=meta.get("bads", []),
        events=meta.get("events", []),
        meta=meta.get("meta", {}),
    )


def read(directory: str | Path) -> Signal:
    d = Path(directory)
    return from_files({n: (d / n).read_bytes() for n in (DATA_FILE, META_FILE)})
