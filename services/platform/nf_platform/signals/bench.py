"""Chunk-size benchmark for the canonical layout (BUILD-GUIDE 2.4). Records MEASUREMENTS only:
no target is claimed. Synthetic data only.

    python -m nf_platform.signals.bench --channels 64 --sfreq 1000 --duration 60 --out bench.json

Writes to a temporary LocalObjectStore through the EncryptedZarrStore (so encryption cost is
included, as in production) unless --plain is given.
"""

from __future__ import annotations

import argparse
import json
import platform
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from nf_platform.signals.encrypted_store import EncryptedZarrStore
from nf_platform.signals.zarr_store import read_window, write_recording
from nf_platform.storage.keyring import InMemoryKeyStore, Keyring
from nf_platform.storage.kms import LocalKms
from nf_platform.storage.objects import LocalObjectStore


def _dir_bytes(root: Path) -> tuple[int, int]:
    files = [p for p in root.rglob("*") if p.is_file()]
    return sum(p.stat().st_size for p in files), len(files)


def run(
    n_channels: int,
    sfreq: int,
    duration_s: int,
    chunk_s_list: list[float],
    *,
    chunk_channels: int = 64,
    dtype: str = "int16",
    encrypted: bool = True,
    window_s: float = 1.0,
    n_windows: int = 20,
    seed: int = 0,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    n = int(sfreq * duration_s)
    # Band-limited-ish synthetic signal (random walk) so compression is not trivially perfect.
    data = np.cumsum(rng.integers(-40, 41, size=(n_channels, n), dtype=np.int32), axis=1)
    data = np.clip(data, -32768, 32767).astype(dtype)
    raw_bytes = data.nbytes
    results = []
    for chunk_s in chunk_s_list:
        with tempfile.TemporaryDirectory() as td:
            objects = LocalObjectStore(td)
            if encrypted:
                store: Any = EncryptedZarrStore(
                    objects, Keyring(LocalKms(), InMemoryKeyStore()), "bench", "subj", "bench"
                )
            else:
                from zarr.storage import LocalStore

                store = LocalStore(Path(td) / "plain")
            t = time.perf_counter()
            write_recording(
                store,
                "rec",
                data,
                float(sfreq),
                [f"ch{i}" for i in range(n_channels)],
                "uV",
                chunk_s=chunk_s,
                chunk_channels=chunk_channels,
            )
            write_s = time.perf_counter() - t
            size, n_obj = _dir_bytes(Path(td))
            starts = rng.uniform(0, max(0.0, duration_s - window_s), size=n_windows)
            t = time.perf_counter()
            for s in starts:
                read_window(store, "rec", float(s), float(s) + window_s)
            win_ms = (time.perf_counter() - t) / n_windows * 1000
            t = time.perf_counter()
            read_window(store, "rec", 0.0, float(duration_s), channels=[0])
            one_ch_ms = (time.perf_counter() - t) * 1000
            t = time.perf_counter()
            read_window(store, "rec", 0.0, float(duration_s), level=1)
            overview_ms = (time.perf_counter() - t) * 1000
        results.append(
            {
                "chunk_s": chunk_s,
                "chunk_channels": min(chunk_channels, n_channels),
                "write_s": round(write_s, 3),
                "write_MB_per_s": round(raw_bytes / 1e6 / write_s, 1),
                "stored_MB_incl_pyramid": round(size / 1e6, 2),
                "objects": n_obj,
                f"read_{window_s:g}s_window_all_ch_ms": round(win_ms, 2),
                "read_full_duration_1ch_ms": round(one_ch_ms, 1),
                "read_level1_full_ms": round(overview_ms, 1),
            }
        )
    return {
        "kind": "MEASUREMENT (no target claimed)",
        "data": f"synthetic random walk, {n_channels} ch x {sfreq} Hz x {duration_s} s, {dtype}",
        "raw_MB": round(raw_bytes / 1e6, 2),
        "encrypted": encrypted,
        "machine": f"{platform.system()} {platform.machine()} py{platform.python_version()}",
        "results": results,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--channels", type=int, default=64)
    ap.add_argument("--sfreq", type=int, default=1000)
    ap.add_argument("--duration", type=int, default=60)
    ap.add_argument("--chunks", default="1,2,4,10")
    ap.add_argument("--chunk-channels", type=int, default=64)
    ap.add_argument("--plain", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    res = run(
        a.channels,
        a.sfreq,
        a.duration,
        [float(x) for x in a.chunks.split(",")],
        chunk_channels=a.chunk_channels,
        encrypted=not a.plain,
    )
    text = json.dumps(res, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
