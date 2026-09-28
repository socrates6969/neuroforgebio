"""Structural checks of uploaded weights (SEC-061): only safetensors and ONNX are accepted, and
the registry never deserialises them (no pickle, no ``torch.load``, no framework import). The
bytes are checked for a well-formed container and then sealed as an opaque blob.

- safetensors: an 8-byte little-endian header length, a JSON header object whose tensors have a
  known dtype, an integer shape and ``data_offsets`` that tile the data section exactly.
- ONNX: a protobuf ``ModelProto``; the wire format is walked (no code runs) and must carry
  ``ir_version`` (field 1, varint) and ``graph`` (field 7, length-delimited).
"""

from __future__ import annotations

import json
import math
import struct

FORMATS = ("safetensors", "onnx")
MAX_BYTES = 16 * 1024 * 1024  # inline uploads (JSON/base64); larger weights: a training job
_ST_MAX_HEADER = 100 * 1024 * 1024
_ST_DTYPES = {
    "BOOL": 1,
    "U8": 1,
    "I8": 1,
    "F8_E4M3": 1,
    "F8_E5M2": 1,
    "I16": 2,
    "U16": 2,
    "F16": 2,
    "BF16": 2,
    "I32": 4,
    "U32": 4,
    "F32": 4,
    "I64": 8,
    "U64": 8,
    "F64": 8,
}


class WeightsError(ValueError):
    pass


def check(data: bytes, fmt: str | None) -> str:
    """Return the format when ``data`` is a well-formed container of it; raise WeightsError."""
    if fmt not in FORMATS:
        raise WeightsError("weights are accepted only as safetensors or ONNX (SEC-061)")
    if not data:
        raise WeightsError("weights are empty")
    if len(data) > MAX_BYTES:
        raise WeightsError(f"inline weights are limited to {MAX_BYTES} bytes")
    if fmt == "safetensors":
        _safetensors(data)
    else:
        _onnx(data)
    return fmt


def _safetensors(data: bytes) -> None:
    if len(data) < 8:
        raise WeightsError("not a safetensors file (too short)")
    (n,) = struct.unpack("<Q", data[:8])
    if n < 2 or n > _ST_MAX_HEADER or 8 + n > len(data):
        raise WeightsError("not a safetensors file (bad header length)")
    try:
        header = json.loads(data[8 : 8 + n].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise WeightsError("not a safetensors file (header is not JSON)") from e
    if not isinstance(header, dict):
        raise WeightsError("not a safetensors file (header is not an object)")
    body = len(data) - 8 - n
    spans: list[tuple[int, int]] = []
    for name, t in header.items():
        if name == "__metadata__":
            if not isinstance(t, dict) or not all(isinstance(v, str) for v in t.values()):
                raise WeightsError("safetensors __metadata__ must map strings to strings")
            continue
        if not isinstance(t, dict) or set(t) != {"dtype", "shape", "data_offsets"}:
            raise WeightsError(f"safetensors tensor {name!r} is malformed")
        size = _ST_DTYPES.get(t["dtype"])
        shape, offs = t["shape"], t["data_offsets"]
        if size is None:
            raise WeightsError(f"safetensors tensor {name!r} has an unknown dtype")
        if not isinstance(shape, list) or not all(
            isinstance(d, int) and not isinstance(d, bool) and d >= 0 for d in shape
        ):
            raise WeightsError(f"safetensors tensor {name!r} has a bad shape")
        if (
            not isinstance(offs, list)
            or len(offs) != 2
            or not all(isinstance(o, int) and not isinstance(o, bool) for o in offs)
            or not 0 <= offs[0] <= offs[1] <= body
        ):
            raise WeightsError(f"safetensors tensor {name!r} has bad data offsets")
        if offs[1] - offs[0] != math.prod(shape) * size:
            raise WeightsError(f"safetensors tensor {name!r} size does not match its shape")
        spans.append((offs[0], offs[1]))
    if not spans:
        raise WeightsError("safetensors file holds no tensor")
    pos = 0
    for a, b in sorted(spans):
        if a != pos:
            raise WeightsError("safetensors data section has gaps or overlaps")
        pos = b
    if pos != body:
        raise WeightsError("safetensors data section has trailing bytes")


def _varint(data: bytes, i: int) -> tuple[int, int]:
    out = shift = 0
    while True:
        if i >= len(data) or shift > 63:
            raise WeightsError("not an ONNX model (truncated varint)")
        b = data[i]
        i += 1
        out |= (b & 0x7F) << shift
        if not b & 0x80:
            return out, i
        shift += 7


def _onnx(data: bytes) -> None:
    i, seen = 0, set()
    while i < len(data):
        key, i = _varint(data, i)
        field, wire = key >> 3, key & 7
        if field == 0:
            raise WeightsError("not an ONNX model (field 0)")
        if wire == 0:
            _, i = _varint(data, i)
        elif wire == 1:
            i += 8
        elif wire == 2:
            n, i = _varint(data, i)
            i += n
        elif wire == 5:
            i += 4
        else:
            raise WeightsError("not an ONNX model (unsupported wire type)")
        if i > len(data):
            raise WeightsError("not an ONNX model (truncated field)")
        seen.add((field, wire))
    if (1, 0) not in seen or (7, 2) not in seen:
        raise WeightsError("not an ONNX model (ir_version and graph are required)")
