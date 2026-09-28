"""Reference tables (derived from the digitised Greenspon 2025 data), NOT shipped in the package.

- ``greenspon2025_ed1_segments.json``: the hand-segment table (surface, tag, centroid, area) in the
  research order. Used by Null A (area-proportional) and by the relabelling neighbours.
- ``greenspon2025_pooled_dominant_segments.json``: the R1 dominant segment of every PF electrode of
  the three published participants (C1, P2, P3, in file order). Used by Null B (pooled marginal).

Both are regenerated from the pinned research inputs by ``tests/golden_io.py`` (run as a script),
and a test checks that the files equal the regenerated content.

Licence: the source article is CC BY-NC-ND 4.0 (legal/data-agreements/figure-data-memo.md), so
these files live only in the private source tree for internal tests (see THIRD_PARTY_NOTICE.md
next to them). They are excluded from the wheel and sdist, and a release-guard test fails a build
that contains them. Without them, the estimator still computes counts, diversity and attrition;
the clustering nulls and relabelling report ``skipped``. A user may point
``NF_CHANNELS_REFERENCE_DIR`` (or ``--reference-dir``) at their own copy.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TypedDict

from .labels import tmap

SEGMENTS_FILE = "greenspon2025_ed1_segments.json"
POOLED_FILE = "greenspon2025_pooled_dominant_segments.json"

# Territory classes of the clustering nulls (research TCLS; WRIST only occurs in Null A draws).
NULL_TERRITORY_CLASSES: tuple[str, ...] = (
    "D1",
    "D2",
    "D3",
    "D4",
    "D5",
    "PALM",
    "DORSUM_HAND",
    "WRIST",
)


class SegmentRow(TypedDict):
    """One row of the reference segment table."""

    key: str
    surface: str
    tag: str
    cx: float
    cy: float
    area_mm2: float


@dataclass(frozen=True)
class ReferenceData:
    """Loaded reference tables plus their SHA-256 (over the shipped file bytes, LF line endings)."""

    segments: tuple[SegmentRow, ...]
    pooled_keys: tuple[str, ...]
    segments_sha256: str
    pooled_sha256: str
    source: str

    @property
    def keys(self) -> tuple[str, ...]:
        """Segment keys (``palm:<tag>`` / ``dors:<tag>``) in table order."""
        return tuple(s["key"] for s in self.segments)

    @property
    def key_index(self) -> dict[str, int]:
        """Segment key -> row index."""
        return {k: i for i, k in enumerate(self.keys)}

    @property
    def segment_territory_index(self) -> list[int]:
        """Row index -> index into :data:`NULL_TERRITORY_CLASSES` (R1 territory of the segment)."""
        idx = {t: i for i, t in enumerate(NULL_TERRITORY_CLASSES)}
        out = []
        for s in self.segments:
            t = tmap("palm" if s["surface"] == "palm" else "dors", s["tag"])
            out.append(idx[t])  # type: ignore[index]
        return out


REFERENCE_DIR_ENV = "NF_CHANNELS_REFERENCE_DIR"
REFERENCE_UNAVAILABLE = (
    "reference tables not installed (third-party data, CC BY-NC-ND 4.0, not redistributed; "
    f"set {REFERENCE_DIR_ENV} or --reference-dir to a local copy)"
)


def _candidate_dirs(directory: str | None) -> list[Traversable | Path]:
    if directory is not None:  # an explicit directory is the only place searched
        return [Path(directory)]
    env = os.environ.get(REFERENCE_DIR_ENV)
    dirs: list[Traversable | Path] = [Path(env)] if env else []
    dirs.append(resources.files("nf_channel_estimator.reference_data"))  # source tree only
    return dirs


@cache
def load_reference(directory: str | None = None) -> ReferenceData | None:
    """Load the reference tables (cached), or None when they are not available."""
    for d in _candidate_dirs(directory):
        seg, pool = d.joinpath(SEGMENTS_FILE), d.joinpath(POOLED_FILE)
        if seg.is_file() and pool.is_file():
            return _parse(
                seg.read_bytes().replace(b"\r\n", b"\n"),
                pool.read_bytes().replace(b"\r\n", b"\n"),
            )
    return None


def _parse(seg_bytes: bytes, pool_bytes: bytes) -> ReferenceData:
    seg = json.loads(seg_bytes)
    pool = json.loads(pool_bytes)
    return ReferenceData(
        segments=tuple(seg["segments"]),
        pooled_keys=tuple(pool["keys"]),
        segments_sha256=hashlib.sha256(seg_bytes).hexdigest(),
        pooled_sha256=hashlib.sha256(pool_bytes).hexdigest(),
        source=seg["source"]["citation"],
    )
