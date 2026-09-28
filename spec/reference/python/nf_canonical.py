"""Reference implementation of docs/spec/hashing.md (NF canonical JSON v1 + content IDs).

Standard library only. This is the executable form of the spec: the server (M2/M3) and nf-core (M4)
must reproduce spec/test-vectors/*.json, which this module generates and checks.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import unicodedata
from decimal import Decimal
from typing import Any

MAX_SAFE_INT = 2**53 - 1

# Domain-separation tags for structured IDs (docs/spec/hashing.md §5).
TAG_PIPELINE_VERSION = "nf.pipeline-version.v1"
TAG_CHUNK = "nf.chunk.v1"
TAG_PROV_BATCH = "nf.prov-batch.v1"

KIND_BLOB = "blob"
KIND_PIPELINE_VERSION = "pv"
KIND_CHUNK = "chunk"
KIND_PROV_BATCH = "provb"

DTYPES = {  # name -> (struct format char, itemsize); always little-endian
    "int8": ("b", 1),
    "uint8": ("B", 1),
    "int16": ("h", 2),
    "uint16": ("H", 2),
    "int32": ("i", 4),
    "uint32": ("I", 4),
    "int64": ("q", 8),
    "float32": ("f", 4),
    "float64": ("d", 8),
}

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
ID_RE = re.compile(r"^(blob|pv|chunk|provb):sha256:[0-9a-f]{64}$")


class CanonicalError(ValueError):
    """Input cannot be canonicalised (NaN, big integer, lone surrogate, duplicate key...)."""


# ---------------------------------------------------------------- numbers (RFC 8785 §3.2.2.3)
def format_number(x: int | float) -> str:
    """ECMAScript Number.prototype.toString for a finite double; integers must be safe."""
    if isinstance(x, bool):
        raise CanonicalError("bool is not a number")
    if isinstance(x, int):
        if abs(x) > MAX_SAFE_INT:
            raise CanonicalError(f"integer {x} exceeds 2^53-1; encode it as a string")
        return str(x)
    if not math.isfinite(x):
        raise CanonicalError("NaN and Infinity are not allowed")
    if x == 0:
        return "0"  # also -0
    sign = "-" if x < 0 else ""
    # repr() gives the shortest round-trip digits (Python >= 3.1).
    t = Decimal(repr(abs(x))).normalize().as_tuple()
    digits = "".join(map(str, t.digits))
    k = len(digits)
    n = t.exponent + k  # value = 0.d1d2..dk * 10^n
    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        es = ("+" if e >= 0 else "-") + str(abs(e))
        s = digits + "e" + es if k == 1 else digits[0] + "." + digits[1:] + "e" + es
    return sign + s


# ---------------------------------------------------------------- strings
_ESC = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def nfc(s: str) -> str:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError as e:
        raise CanonicalError("lone surrogate in string") from e
    return unicodedata.normalize("NFC", s)


def format_string(s: str) -> str:
    out = ['"']
    for ch in nfc(s):
        if ch in _ESC:
            out.append(_ESC[ch])
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _utf16_key(s: str) -> bytes:
    return s.encode("utf-16-be")


# ---------------------------------------------------------------- canonical JSON
def canonical_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return format_number(value)
    if isinstance(value, str):
        return format_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_text(v) for v in value) + "]"
    if isinstance(value, dict):
        items: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalError("object keys must be strings")
            nk = nfc(k)
            if nk in items:
                raise CanonicalError(f"duplicate key after NFC: {nk!r}")
            items[nk] = v
        keys = sorted(items, key=_utf16_key)
        return "{" + ",".join(format_string(k) + ":" + canonical_text(items[k]) for k in keys) + "}"
    raise CanonicalError(f"unsupported type {type(value).__name__}")


def canonicalize(value: Any) -> bytes:
    """Canonical UTF-8 bytes of a JSON value (docs/spec/hashing.md §3)."""
    return canonical_text(value).encode("utf-8")


def _no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise CanonicalError(f"duplicate key: {k!r}")
        d[k] = v
    return d


def _bad_constant(name: str) -> Any:
    raise CanonicalError(f"{name} is not valid JSON")


def parse(text: str) -> Any:
    """Parse JSON text strictly (duplicate keys, NaN/Infinity rejected)."""
    return json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_bad_constant)


def canonicalize_text(text: str) -> bytes:
    return canonicalize(parse(text))


# ---------------------------------------------------------------- hashes and IDs (§4, §5)
def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tagged_preimage(tag: str, payload: bytes) -> bytes:
    return tag.encode("ascii") + b"\x00" + payload


def make_id(kind: str, digest_hex: str) -> str:
    return f"{kind}:sha256:{digest_hex}"


def parse_id(id_: str) -> tuple[str, str]:
    if not ID_RE.match(id_):
        raise CanonicalError(f"malformed id: {id_!r}")
    kind, _, hexd = id_.split(":")
    return kind, hexd


def blob_id(data: bytes) -> str:
    """Raw bytes (uploaded files, artifacts). Plain SHA-256, equal to `sha256sum`."""
    return make_id(KIND_BLOB, sha256_hex(data))


def pipeline_version_payload(spec: dict[str, Any]) -> bytes:
    if spec.get("schema") != "nf.pipeline-version/v1":
        raise CanonicalError("schema must be nf.pipeline-version/v1")
    hashed = {k: v for k, v in spec.items() if k != "meta"}
    for i, step in enumerate(hashed.get("steps", [])):
        image = step.get("image", "")
        if not re.match(r"^[^@\s]+@sha256:[0-9a-f]{64}$", image):
            raise CanonicalError(f"step {i}: image must be pinned by digest (name@sha256:...)")
    return canonicalize(hashed)


def pipeline_version_id(spec: dict[str, Any]) -> str:
    pre = tagged_preimage(TAG_PIPELINE_VERSION, pipeline_version_payload(spec))
    return make_id(KIND_PIPELINE_VERSION, sha256_hex(pre))


def chunk_bytes(dtype: str, values: list[Any]) -> bytes:
    if dtype not in DTYPES:
        raise CanonicalError(f"unsupported dtype {dtype}")
    fmt, _ = DTYPES[dtype]
    return struct.pack("<" + fmt * len(values), *values)


def chunk_preimage(dtype: str, shape: list[int], data: bytes) -> bytes:
    if dtype not in DTYPES:
        raise CanonicalError(f"unsupported dtype {dtype}")
    count = math.prod(shape)
    if count * DTYPES[dtype][1] != len(data):
        raise CanonicalError("data length does not match dtype and shape")
    header = canonicalize({"dtype": dtype, "order": "C", "shape": shape})
    return tagged_preimage(TAG_CHUNK, header + b"\n" + data)


def chunk_id(dtype: str, shape: list[int], data: bytes) -> str:
    return make_id(KIND_CHUNK, sha256_hex(chunk_preimage(dtype, shape, data)))


def prov_batch_payload(batch: dict[str, Any]) -> bytes:
    if batch.get("schema") != "nf.prov-batch/v1":
        raise CanonicalError("schema must be nf.prov-batch/v1")
    seq, prev = batch.get("seq"), batch.get("prev")
    if not isinstance(seq, int) or seq < 0:
        raise CanonicalError("seq must be a non-negative integer")
    if (seq == 0) != (prev is None):
        raise CanonicalError("prev must be null exactly when seq == 0")
    if prev is not None and parse_id(prev)[0] != KIND_PROV_BATCH:
        raise CanonicalError("prev must be a provb id")
    if not TIMESTAMP_RE.match(batch.get("created_at", "")):
        raise CanonicalError("created_at must be YYYY-MM-DDTHH:MM:SS.sssZ")
    return canonicalize(batch)


def prov_batch_id(batch: dict[str, Any]) -> str:
    pre = tagged_preimage(TAG_PROV_BATCH, prov_batch_payload(batch))
    return make_id(KIND_PROV_BATCH, sha256_hex(pre))


def verify_chain(batches: list[dict[str, Any]]) -> list[str]:
    """Return batch IDs; raise if seq/prev links are broken."""
    ids: list[str] = []
    for i, b in enumerate(batches):
        if b.get("seq") != i:
            raise CanonicalError(f"batch {i}: seq {b.get('seq')} != {i}")
        expected_prev = ids[-1] if ids else None
        if b.get("prev") != expected_prev:
            raise CanonicalError(f"batch {i}: prev does not match previous batch id")
        ids.append(prov_batch_id(b))
    return ids


def float_from_bits(hex_bits: str) -> float:
    return struct.unpack(">d", bytes.fromhex(hex_bits))[0]
