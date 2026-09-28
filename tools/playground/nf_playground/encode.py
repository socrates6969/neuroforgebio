"""Compact, lossless encoding of the playground asset (schema nf-playground/2).

Version 1 stored every integer series as absolute values; version 2 stores the same integers as
first-value-plus-differences, which are much shorter in JSON. Nothing is rounded or dropped:
the web loader (apps/web/src/lib/playground-data.mjs) expands version 2 back to exactly the
version-1 arrays, and apps/web/test/playground.test.mjs pins a digest of the expanded data.

- spikes[u]: sorted spike times (ms) -> deltas.
- noiseSpikes[u]: (ms, level) pairs sorted by time -> {"t": deltas of ms,
  "l": one level digit per spike}.
- truePos and every decoded path: interleaved (x, y) -> deltas per coordinate, still interleaved.

Usage: python -m nf_playground.encode <in.json> <out.json>  (transcode an existing asset)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_V1 = "nf-playground/1"
SCHEMA_V2 = "nf-playground/2"


def delta(values: list[int]) -> list[int]:
    return [v if i == 0 else v - values[i - 1] for i, v in enumerate(values)]


def delta_xy(values: list[int]) -> list[int]:
    """Interleaved (x, y): each coordinate differenced against its own previous value."""
    return [v if i < 2 else v - values[i - 2] for i, v in enumerate(values)]


def undelta(values: list[int]) -> list[int]:
    out: list[int] = []
    for v in values:
        out.append(v if not out else out[-1] + v)
    return out


def undelta_xy(values: list[int]) -> list[int]:
    out: list[int] = []
    for i, v in enumerate(values):
        out.append(v if i < 2 else out[i - 2] + v)
    return out


def encode_noise(pairs: list[int]) -> dict:
    ms, levels = pairs[0::2], pairs[1::2]
    if any(not 1 <= lv <= 9 for lv in levels):
        raise ValueError("noise levels must be single digits")
    return {"t": delta(ms), "l": "".join(str(lv) for lv in levels)}


def decode_noise(enc: dict) -> list[int]:
    ms = undelta(enc["t"])
    levels = [int(c) for c in enc["l"]]
    return [v for pair in zip(ms, levels, strict=True) for v in pair]


def compact(asset: dict) -> dict:
    """Version-1 asset -> version-2 asset (lossless)."""
    if asset.get("schema") != SCHEMA_V1:
        raise ValueError(f"expected {SCHEMA_V1}")
    out = {**asset, "schema": SCHEMA_V2}
    out["trials"] = [
        {
            **t,
            "truePos": delta_xy(t["truePos"]),
            "spikes": [delta(s) for s in t["spikes"]],
            "noiseSpikes": [encode_noise(p) for p in t["noiseSpikes"]],
            "decoded": {
                d: [[delta_xy(path) for path in row] for row in grid]
                for d, grid in t["decoded"].items()
            },
        }
        for t in asset["trials"]
    ]
    return out


def expand(asset: dict) -> dict:
    """Version-2 asset -> version-1 asset (the inverse of compact)."""
    if asset.get("schema") != SCHEMA_V2:
        raise ValueError(f"expected {SCHEMA_V2}")
    out = {**asset, "schema": SCHEMA_V1}
    out["trials"] = [
        {
            **t,
            "truePos": undelta_xy(t["truePos"]),
            "spikes": [undelta(s) for s in t["spikes"]],
            "noiseSpikes": [decode_noise(e) for e in t["noiseSpikes"]],
            "decoded": {
                d: [[undelta_xy(path) for path in row] for row in grid]
                for d, grid in t["decoded"].items()
            },
        }
        for t in asset["trials"]
    ]
    return out


def dumps(asset: dict) -> str:
    return json.dumps(asset, separators=(",", ":")) + "\n"


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    v1 = json.loads(src.read_text(encoding="utf-8"))
    v2 = compact(v1)
    if expand(v2) != v1:
        raise SystemExit("round trip failed: compact() is not lossless for this asset")
    print("round trip: expand(compact(v1)) == v1 (exact)")
    dst.write_text(dumps(v2), encoding="utf-8", newline="\n")
    a, b = src.stat().st_size, dst.stat().st_size
    pct = 100 * (1 - b / a)
    print(f"{src.name}: {a / 1024:.1f} KiB -> {b / 1024:.1f} KiB ({pct:.0f}% smaller)")


if __name__ == "__main__":
    main()
