"""Canonical JSON and content IDs (docs/spec/hashing.md), computed by nf-core.

The Python server uses the stdlib reference implementation; both must produce identical bytes,
which ``bindings/python/tests/test_canonical.py`` checks on the frozen vectors and on random
values.
"""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np

from . import _native

CanonicalError = _native.CanonicalError

__all__ = [
    "CanonicalError",
    "blob_id",
    "blob_id_file",
    "canonical",
    "chunk_id",
    "format_number",
    "is_valid_id",
    "pipeline_version_id",
    "prov_batch_id",
    "verify_chain",
]


def _text(obj: Any) -> str:
    # json.dumps writes floats with repr() (shortest round-trip), so no precision is lost on the
    # way into nf-core; NaN/Infinity are refused here already.
    return json.dumps(obj, ensure_ascii=False, allow_nan=False)


def canonical(obj: Any) -> bytes:
    """NF-CJSON v1 bytes of a JSON-compatible Python value."""
    try:
        return _native.canonicalize(_text(obj))
    except ValueError as e:
        raise CanonicalError(str(e)) from None


def format_number(x: float) -> str:
    return _native.format_number(float(x))


def blob_id(data: bytes) -> str:
    return _native.blob_id(bytes(data))


def blob_id_file(path: str | os.PathLike[str]) -> tuple[str, int]:
    """(``blob:sha256:...``, size) of a file, streamed (no full read into memory)."""
    return _native.blob_id_file(os.fspath(path))


def pipeline_version_id(spec: dict[str, Any]) -> str:
    return _native.pipeline_version_id(_text(spec))


def chunk_id(array: np.ndarray) -> str:
    """Content ID of an array's decoded samples (C order, little-endian)."""
    a = np.ascontiguousarray(array)
    le = a.astype(a.dtype.newbyteorder("<"), copy=False)
    return _native.chunk_id(a.dtype.name, [int(x) for x in a.shape], le.tobytes())


def prov_batch_id(batch: dict[str, Any]) -> str:
    return _native.prov_batch_id(_text(batch))


def verify_chain(batches: list[dict[str, Any]]) -> list[str]:
    return _native.verify_chain([_text(b) for b in batches])


def is_valid_id(id_: str) -> bool:
    return _native.is_valid_id(id_)
