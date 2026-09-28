"""Wire-level rules of ``neuroforge.ingest.v1`` shared by the server and the edge client.

- ``chunk_id``: hashing spec v1 §5.2 over the sample array, shape ``[n_samples, n_channels]``.
- ``signing_payload``: what the device key signs per chunk (SEC-040). Tag ``nf.stream-chunk.v1``,
  then NF-CJSON of ``{chunk_id, n_channels, n_samples, seq, stream_id, t_first, t_last,
  timing_sha256, n_clock_offsets, n_local_clock}``. ``timing_sha256`` covers the per-sample LSL
  timestamps, the clock-offset pairs and the local clock pairs (float64 little-endian, in that
  order), so the timing series cannot be altered without breaking the signature (SEC-094).
- Device tokens (SEC-016): ``nfd1.<b64url(payload)>.<b64url(sig)>``; payload = NF-CJSON of
  ``{aud, device_id, exp, iat, stream_id, tenant_id}``, signature = Ed25519 over tag
  ``nf.device-token.v1`` 0x00 payload. Short-lived (<= 10 min) and bound to one stream.

The two tags are outside hashing spec v1 (same domain-separation construction); proposed for v2.
"""

from __future__ import annotations

import base64
import hashlib
import struct
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from nf_platform.audit import _canonical as cj

TAG_CHUNK = "nf.chunk.v1"
TAG_CHUNK_SIG = "nf.stream-chunk.v1"
TAG_DEVICE_TOKEN = "nf.device-token.v1"
TOKEN_PREFIX = "nfd1"
TOKEN_AUDIENCE = "nf-ingest/v1"
AUTH_SCHEME = "NFDevice"
MAX_TOKEN_LIFETIME_S = 600
# Status detail of a mid-stream abort for an expired token (SEC-017): the client reconnects with a
# fresh token and resumes from next_seq. A revoked device gets a different detail and must stop.
MIDSTREAM_TOKEN_EXPIRED = "device token expired during the stream"
CLOCK_LEEWAY_S = 30
DTYPES = ("int16", "int32", "float32", "float64")
MAX_VALUES_PER_CHUNK = 1_000_000


class ProtocolError(ValueError):
    """A malformed chunk or token (never includes key material or sample values)."""


def chunk_id_bytes(dtype: str, shape: tuple[int, ...] | list[int], data: bytes) -> str:
    """``chunk:sha256:<hex>`` of little-endian C-order ``data`` (hashing spec v1 §5.2)."""
    if dtype not in (
        "int8",
        "uint8",
        "int16",
        "uint16",
        "int32",
        "uint32",
        "int64",
        "float32",
        "float64",
    ):
        raise ProtocolError(f"unsupported dtype {dtype}")
    item = np.dtype(dtype).itemsize
    if int(np.prod(shape, dtype=np.int64)) * item != len(data):
        raise ProtocolError("data length does not match dtype and shape")
    header = cj.canonicalize({"dtype": dtype, "order": "C", "shape": [int(x) for x in shape]})
    return "chunk:sha256:" + cj.sha256_hex(cj.tagged_preimage(TAG_CHUNK, header + b"\n" + data))


def samples_to_bytes(samples: np.ndarray, dtype: str) -> bytes:
    """(n_samples, n_channels) array -> little-endian C-order bytes."""
    arr = np.ascontiguousarray(samples, dtype=np.dtype(dtype).newbyteorder("<"))
    return arr.tobytes(order="C")


def samples_from_bytes(data: bytes, dtype: str, n_samples: int, n_channels: int) -> np.ndarray:
    if dtype not in DTYPES:
        raise ProtocolError(f"dtype must be one of {DTYPES}")
    if n_samples < 1 or n_channels < 1 or n_samples * n_channels > MAX_VALUES_PER_CHUNK:
        raise ProtocolError("chunk shape out of range")
    le = np.dtype(dtype).newbyteorder("<")
    if len(data) != n_samples * n_channels * le.itemsize:
        raise ProtocolError("sample bytes do not match n_samples x n_channels x dtype")
    return np.frombuffer(data, dtype=le).reshape(n_samples, n_channels).astype(dtype, copy=False)


def _f64(values: Any) -> bytes:
    vals = list(values)
    return struct.pack(f"<{len(vals)}d", *vals)


def timing_sha256(
    lsl_timestamps: Any,
    clock_offsets: list[tuple[float, float]],
    local_clock: list[tuple[float, float]],
) -> str:
    h = hashlib.sha256()
    h.update(_f64(lsl_timestamps))
    h.update(_f64(v for pair in clock_offsets for v in pair))
    h.update(_f64(v for pair in local_clock for v in pair))
    return h.hexdigest()


def signing_payload(msg: Any) -> bytes:
    """Payload the device signs for a ``Chunk`` message (see module docstring)."""
    offsets = [(c.collection_time, c.offset) for c in msg.clock_offsets]
    local = [(c.lsl_time, c.monotonic_time) for c in msg.local_clock]
    ts = list(msg.lsl_timestamps)
    body = {
        "chunk_id": msg.chunk_id,
        "n_channels": int(msg.n_channels),
        "n_clock_offsets": len(offsets),
        "n_local_clock": len(local),
        "n_samples": int(msg.n_samples),
        "seq": int(msg.seq),
        "stream_id": msg.stream_id,
        "t_first": float(ts[0]) if ts else 0.0,
        "t_last": float(ts[-1]) if ts else 0.0,
        "timing_sha256": timing_sha256(ts, offsets, local),
    }
    try:
        return cj.tagged_preimage(TAG_CHUNK_SIG, cj.canonicalize(body))
    except cj.CanonicalError as e:  # NaN/Inf timestamps, seq beyond 2**53
        raise ProtocolError(f"chunk cannot be canonicalised: {e}") from e


def sign_chunk(msg: Any, key: Ed25519PrivateKey) -> None:
    msg.signature = key.sign(signing_payload(msg))


def verify_chunk_signature(msg: Any, public_key: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            bytes(msg.signature), signing_payload(msg)
        )
    except (InvalidSignature, ValueError):
        return False
    return True


# ---------------------------------------------------------------- device tokens (SEC-016)
def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    except (ValueError, TypeError) as e:
        raise ProtocolError("token is not base64url") from e


@dataclass(frozen=True)
class DeviceClaims:
    tenant_id: str
    device_id: str
    stream_id: str
    iat: int
    exp: int


def make_device_token(
    key: Ed25519PrivateKey,
    *,
    tenant_id: str,
    device_id: str,
    stream_id: str,
    lifetime_s: int = 300,
    now: float | None = None,
) -> str:
    iat = int(now if now is not None else time.time())
    payload = cj.canonicalize(
        {
            "aud": TOKEN_AUDIENCE,
            "device_id": device_id,
            "exp": iat + int(lifetime_s),
            "iat": iat,
            "stream_id": stream_id,
            "tenant_id": tenant_id,
        }
    )
    sig = key.sign(cj.tagged_preimage(TAG_DEVICE_TOKEN, payload))
    return f"{TOKEN_PREFIX}.{_b64e(payload)}.{_b64e(sig)}"


def parse_device_token(token: str) -> tuple[DeviceClaims, bytes, bytes]:
    """Split a token into (unverified claims, signed payload, signature). Verify before trusting."""
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX or len(token) > 2048:
        raise ProtocolError("malformed device token")
    payload, sig = _b64d(parts[1]), _b64d(parts[2])
    try:
        c = cj.parse(payload.decode("utf-8"))
        if cj.canonicalize(c) != payload:
            raise ProtocolError("device token payload is not canonical")
        claims = DeviceClaims(
            tenant_id=str(c["tenant_id"]),
            device_id=str(c["device_id"]),
            stream_id=str(c["stream_id"]),
            iat=int(c["iat"]),
            exp=int(c["exp"]),
        )
        if c["aud"] != TOKEN_AUDIENCE:
            raise ProtocolError("device token has the wrong audience")
    except (UnicodeDecodeError, ValueError, KeyError, TypeError) as e:
        if isinstance(e, ProtocolError):
            raise
        raise ProtocolError("malformed device token payload") from e
    return claims, payload, sig


def verify_device_token(
    claims: DeviceClaims, payload: bytes, sig: bytes, public_key: bytes, *, now: float | None = None
) -> None:
    t = time.time() if now is None else now
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            sig, cj.tagged_preimage(TAG_DEVICE_TOKEN, payload)
        )
    except (InvalidSignature, ValueError) as e:
        raise ProtocolError("device token signature does not verify") from e
    if claims.exp - claims.iat > MAX_TOKEN_LIFETIME_S or claims.exp <= claims.iat:
        raise ProtocolError("device token lifetime out of range")
    if claims.iat > t + CLOCK_LEEWAY_S or claims.exp < t - CLOCK_LEEWAY_S:
        raise ProtocolError("device token expired or not yet valid")
