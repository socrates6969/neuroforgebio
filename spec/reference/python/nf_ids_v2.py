"""Reference implementation of the hashing spec v2 registrations (docs/spec/hashing.md §8-§10).

Standard library only, like ``nf_canonical`` (whose v1 rules it reuses unchanged). Every function
mirrors the platform code that builds the tag today; ``spec/test-vectors/ids-v2.json`` is generated
from this module and ``services/platform/tests/spec_v2`` checks the platform code against the same
file, so the spec and the code cannot drift apart.

Ed25519 (RFC 8032 §5.1) is implemented here from the RFC's §6 reference code so the signature
vectors do not depend on the library the platform uses (``cryptography``); the RFC's own §7.1 test
vectors check it (``test_vectors_v2.py``). It is slow and NOT constant-time: test use only.
"""

from __future__ import annotations

import hashlib
import re
import struct
from typing import Any

import nf_canonical as nc

# ---------------------------------------------------------------- v2 registry (§8)
# Hash tags: SHA-256(TAG 0x00 payload), the v1 §4 construction.
TAG_AUDIT_BATCH = "nf.audit-batch.v1"
TAG_PROV_NODE = "nf.prov-node.v1"
TAG_CONSENT_RECORD = "nf.consent-record.v1"
TAG_RULESET = "nf.ruleset.v1"
TAG_SWEEP_VARIANT = "nf.sweep-variant.v1"
# Signature tags: Ed25519 over TAG 0x00 payload.
TAG_STREAM_CHUNK = "nf.stream-chunk.v1"
TAG_DEVICE_TOKEN = "nf.device-token.v1"
# AEAD associated-data tag (edge WAL).
TAG_WAL = "nf.wal.v1"
# M6 registry (training-set manifests).
TAG_TRAINING_SUBJECT = "nf.training-subject.v1"
TAG_TRAINING_MANIFEST = "nf.training-manifest.v1"

KIND_AUDIT_BATCH = "auditb"
ID_RE_V2 = re.compile(r"^(blob|pv|chunk|provb|auditb):sha256:[0-9a-f]{64}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP_RE = nc.TIMESTAMP_RE

SCHEMA_AUDIT_BATCH = "nf.audit-batch/v1"
SCHEMA_CONSENT_RECORD = "nf.consent-record/v1"
SCHEMA_PROV_ANCHOR = "nf.prov-anchor/v1"
SCHEMA_CONSENT_ANCHOR = "nf.consent-anchor/v1"
SCHEMA_DELETION_CERT = "nf.deletion-certificate/v1"
SCHEMA_TRAINING_MANIFEST = "nf.training-manifest/v1"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DEVICE_TOKEN_PREFIX = "nfd1"
DEVICE_TOKEN_AUDIENCE = "nf-ingest/v1"


# ---------------------------------------------------------------- §9.1 audit batch (auditb)
def audit_batch_payload(batch: dict[str, Any]) -> bytes:
    if batch.get("schema") != SCHEMA_AUDIT_BATCH:
        raise nc.CanonicalError(f"schema must be {SCHEMA_AUDIT_BATCH}")
    seq, prev = batch.get("seq"), batch.get("prev")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise nc.CanonicalError("seq must be a non-negative integer")
    if (seq == 0) != (prev is None):
        raise nc.CanonicalError("prev must be null exactly when seq == 0")
    if prev is not None and not re.match(r"^auditb:sha256:[0-9a-f]{64}$", prev):
        raise nc.CanonicalError("prev must be an auditb id")
    if not TIMESTAMP_RE.match(str(batch.get("created_at", ""))):
        raise nc.CanonicalError("created_at must be YYYY-MM-DDTHH:MM:SS.sssZ")
    return nc.canonicalize(batch)


def audit_batch_id(batch: dict[str, Any]) -> str:
    pre = nc.tagged_preimage(TAG_AUDIT_BATCH, audit_batch_payload(batch))
    return nc.make_id(KIND_AUDIT_BATCH, nc.sha256_hex(pre))


def verify_audit_chain(batches: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for i, b in enumerate(batches):
        if b.get("seq") != i:
            raise nc.CanonicalError(f"batch {i}: seq {b.get('seq')} != {i}")
        if b.get("prev") != (ids[-1] if ids else None):
            raise nc.CanonicalError(f"batch {i}: prev does not match previous batch id")
        ids.append(audit_batch_id(b))
    return ids


# ---------------------------------------------------------------- §9.2 provenance node hash
def prov_node_hash(record: dict[str, Any]) -> str:
    """Bare 64-hex digest (no ``<kind>:sha256:`` prefix; stored in ``prov_node.node_hash``)."""
    return nc.sha256_hex(nc.tagged_preimage(TAG_PROV_NODE, nc.canonicalize(record)))


# ---------------------------------------------------------------- §9.3 consent record hash
def canonical_consent_record(record: dict[str, Any]) -> dict[str, Any]:
    """A copy with ``scopes`` de-duplicated and sorted (§9.3: canonicalised before hashing)."""
    scopes = record.get("scopes")
    if not isinstance(scopes, list) or not all(isinstance(x, str) for x in scopes):
        raise nc.CanonicalError("scopes must be an array of strings")
    return dict(record, scopes=sorted(set(scopes)))


def consent_record_hash(record: dict[str, Any]) -> str:
    """Bare 64-hex digest; ``prev`` of record n is the bare hash of record n-1. ``scopes`` are
    de-duplicated and sorted before hashing (§9.3), so equal scope sets give equal hashes."""
    if record.get("schema") != SCHEMA_CONSENT_RECORD:
        raise nc.CanonicalError(f"schema must be {SCHEMA_CONSENT_RECORD}")
    seq, prev = record.get("seq"), record.get("prev")
    if (seq == 0) != (prev is None):
        raise nc.CanonicalError("prev must be null exactly when seq == 0")
    if prev is not None and not DIGEST_RE.match(prev):
        raise nc.CanonicalError("prev must be a 64-hex record hash")
    canon = canonical_consent_record(record)
    return nc.sha256_hex(nc.tagged_preimage(TAG_CONSENT_RECORD, nc.canonicalize(canon)))


def verify_consent_chain(records: list[dict[str, Any]]) -> list[str]:
    hashes: list[str] = []
    for i, r in enumerate(records):
        if r.get("seq") != i or r.get("prev") != (hashes[-1] if hashes else None):
            raise nc.CanonicalError(f"record {i}: seq/prev link broken")
        hashes.append(consent_record_hash(r))
    return hashes


# ---------------------------------------------------------------- §9.4 RuleSet content hash
def ruleset_content_sha256(public_rules: list[dict[str, Any]]) -> str:
    """Bare 64-hex digest over the canonical ARRAY of public rule objects (manifest order)."""
    return nc.sha256_hex(nc.tagged_preimage(TAG_RULESET, nc.canonicalize(public_rules)))


# ---------------------------------------------------------------- §9.5 sweep variant label
def sweep_variant_label(base_pv_id: str, params: dict[str, Any]) -> str:
    """First 12 hex (48 bits) of the tagged digest; a label, not an ID."""
    nc.parse_id(base_pv_id)
    payload = nc.canonicalize({"base": base_pv_id, "params": params})
    return nc.sha256_hex(nc.tagged_preimage(TAG_SWEEP_VARIANT, payload))[:12]


# ---------------------------------------------------------------- §9.6 training subject hash
def canonical_uuid(value: str) -> str:
    """The 36-character lowercase hyphenated UUID form; upper-case hex is folded to lower case."""
    v = value.lower()
    if not UUID_RE.match(v):
        raise nc.CanonicalError(f"not a hyphenated UUID: {value!r}")
    return v


def training_subject_hash(tenant_id: str, subject_id: str) -> str:
    """Bare 64-hex digest of TAG 0x00 tenant-uuid 0x00 subject-uuid (ASCII, lowercase)."""
    t = canonical_uuid(tenant_id).encode("ascii")
    s = canonical_uuid(subject_id).encode("ascii")
    return nc.sha256_hex(nc.tagged_preimage(TAG_TRAINING_SUBJECT, t + b"\x00" + s))


# ---------------------------------------------------------------- §9.7 training manifest digest
def training_manifest(
    *,
    tenant_id: str,
    input_node_ids: list[str],
    subject_hashes: list[str],
    n_source_recordings: int,
    shards: dict[str, int] | None,
    excluded_subject_hashes: list[str],
    pipeline_version_ids: list[str],
    code_commit: str,
    recipe: str | None,
    parent_version_id: str | None,
    weights_source: str | None = None,
) -> dict[str, Any]:
    """The manifest document as the registry builds it (sets de-duplicated and sorted).
    ``weights_source`` (``platform`` | ``upload``) is the 2026-09-26 additive amendment (§9.7):
    present when given, absent otherwise (manifests written before it)."""
    subjects = sorted(set(subject_hashes))
    for h in subjects + list(excluded_subject_hashes) + list(shards or {}):
        if not DIGEST_RE.match(h):
            raise nc.CanonicalError("subject hashes are 64 lowercase hex")
    doc: dict[str, Any] = {
        "schema": SCHEMA_TRAINING_MANIFEST,
        "tenant": tenant_id,
        "inputs": sorted({canonical_uuid(i) for i in input_node_ids}),
        "subjects": subjects,
        "n_subjects": len(subjects),
        "n_source_recordings": n_source_recordings,
        "excluded_subjects": sorted(set(excluded_subject_hashes)),
        "pipeline_version_ids": sorted(set(pipeline_version_ids)),
        "code_commit": code_commit,
        "recipe": recipe,
        "parent_version": parent_version_id,
    }
    if shards:
        doc["shards"] = {k: int(v) for k, v in sorted(shards.items())}
    if weights_source is not None:
        if weights_source not in ("platform", "upload"):
            raise nc.CanonicalError("weights_source is platform or upload")
        doc["weights_source"] = weights_source
    return doc


def training_manifest_digest(doc: dict[str, Any]) -> str:
    """Bare 64-hex digest (stored in ``model_version.manifest_sha256``)."""
    if doc.get("schema") != SCHEMA_TRAINING_MANIFEST:
        raise nc.CanonicalError(f"schema must be {SCHEMA_TRAINING_MANIFEST}")
    return nc.sha256_hex(nc.tagged_preimage(TAG_TRAINING_MANIFEST, nc.canonicalize(doc)))


# ---------------------------------------------------------------- §10.1 stream chunk signature
def _f64(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}d", *values)


def timing_sha256(
    lsl_timestamps: list[float],
    clock_offsets: list[list[float]],
    local_clock: list[list[float]],
) -> str:
    """SHA-256 (untagged) of float64-LE timestamps, then offset pairs, then local-clock pairs."""
    return hashlib.sha256(
        _f64(lsl_timestamps)
        + _f64([v for pair in clock_offsets for v in pair])
        + _f64([v for pair in local_clock for v in pair])
    ).hexdigest()


def stream_chunk_body(chunk: dict[str, Any]) -> dict[str, Any]:
    ts = chunk["lsl_timestamps"]
    return {
        "chunk_id": chunk["chunk_id"],
        "n_channels": chunk["n_channels"],
        "n_clock_offsets": len(chunk["clock_offsets"]),
        "n_local_clock": len(chunk["local_clock"]),
        "n_samples": chunk["n_samples"],
        "seq": chunk["seq"],
        "stream_id": chunk["stream_id"],
        "t_first": float(ts[0]) if ts else 0.0,
        "t_last": float(ts[-1]) if ts else 0.0,
        "timing_sha256": timing_sha256(ts, chunk["clock_offsets"], chunk["local_clock"]),
    }


def stream_chunk_preimage(chunk: dict[str, Any]) -> bytes:
    return nc.tagged_preimage(TAG_STREAM_CHUNK, nc.canonicalize(stream_chunk_body(chunk)))


# ---------------------------------------------------------------- §10.2 device token
def _b64url(b: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def device_token_payload(claims: dict[str, Any]) -> bytes:
    if claims.get("aud") != DEVICE_TOKEN_AUDIENCE:
        raise nc.CanonicalError(f"aud must be {DEVICE_TOKEN_AUDIENCE}")
    return nc.canonicalize(claims)


def device_token_preimage(claims: dict[str, Any]) -> bytes:
    return nc.tagged_preimage(TAG_DEVICE_TOKEN, device_token_payload(claims))


def device_token(claims: dict[str, Any], secret: bytes) -> str:
    sig = ed25519_sign(secret, device_token_preimage(claims))
    return f"{DEVICE_TOKEN_PREFIX}.{_b64url(device_token_payload(claims))}.{_b64url(sig)}"


# ---------------------------------------------------------------- §10.3-§10.5 untagged signatures
def provb_signature_message(batch_id: str) -> bytes:
    """Provenance batch signature: Ed25519 over the ASCII bytes of the ``provb`` ID (no tag)."""
    nc.parse_id(batch_id)
    return batch_id.encode("ascii")


def anchor_signed_part(anchor: dict[str, Any]) -> bytes:
    """Prov/consent anchors: NF-CJSON of the document without ``sig`` (no tag)."""
    if anchor.get("schema") not in (SCHEMA_PROV_ANCHOR, SCHEMA_CONSENT_ANCHOR):
        raise nc.CanonicalError("not an anchor document")
    return nc.canonicalize({k: v for k, v in anchor.items() if k != "sig"})


def certificate_signed_part(cert: dict[str, Any]) -> bytes:
    """Deletion certificate: NF-CJSON of the document without ``signature`` (no tag)."""
    if cert.get("schema") != SCHEMA_DELETION_CERT:
        raise nc.CanonicalError(f"schema must be {SCHEMA_DELETION_CERT}")
    return nc.canonicalize({k: v for k, v in cert.items() if k != "signature"})


# ---------------------------------------------------------------- §10.6 edge WAL AAD
def wal_aad(stream_id: str, seq: int) -> bytes:
    return (
        TAG_WAL.encode("ascii")
        + b"\x00"
        + stream_id.encode("utf-8")
        + b"\x00"
        + str(seq).encode("ascii")
    )


# ---------------------------------------------------------------- Ed25519 (RFC 8032 §6)
_P = 2**255 - 19
_Q = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, -1, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _sha512_modq(s: bytes) -> int:
    return int.from_bytes(hashlib.sha512(s).digest(), "little") % _Q


def _add(p1: tuple[int, ...], p2: tuple[int, ...]) -> tuple[int, int, int, int]:
    a = (p1[1] - p1[0]) * (p2[1] - p2[0]) % _P
    b = (p1[1] + p1[0]) * (p2[1] + p2[0]) % _P
    c = 2 * p1[3] * p2[3] * _D % _P
    d = 2 * p1[2] * p2[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(s: int, pt: tuple[int, ...]) -> tuple[int, ...]:
    q: tuple[int, ...] = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            q = _add(q, pt)
        pt = _add(pt, pt)
        s >>= 1
    return q


def _equal(p1: tuple[int, ...], p2: tuple[int, ...]) -> bool:
    return (p1[0] * p2[2] - p2[0] * p1[2]) % _P == 0 and (p1[1] * p2[2] - p2[1] * p1[2]) % _P == 0


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, -1, _P)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * pow(5, -1, _P) % _P
_GX = _recover_x(_GY, 0)
assert _GX is not None
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _compress(pt: tuple[int, ...]) -> bytes:
    zinv = pow(pt[2], -1, _P)
    x, y = pt[0] * zinv % _P, pt[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes) -> tuple[int, ...] | None:
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def _expand(secret: bytes) -> tuple[int, bytes]:
    if len(secret) != 32:
        raise ValueError("an Ed25519 secret key is 32 bytes")
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public_key(secret: bytes) -> bytes:
    a, _ = _expand(secret)
    return _compress(_mul(a, _G))


def ed25519_sign(secret: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(secret)
    pub = _compress(_mul(a, _G))
    r = _sha512_modq(prefix + msg)
    rs = _compress(_mul(r, _G))
    h = _sha512_modq(rs + pub + msg)
    s = (r + h * a) % _Q
    return rs + int.to_bytes(s, 32, "little")


def ed25519_verify(public: bytes, msg: bytes, signature: bytes) -> bool:
    if len(signature) != 64:
        return False
    a_pt = _decompress(public)
    r_pt = _decompress(signature[:32])
    if a_pt is None or r_pt is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _Q:
        return False
    h = _sha512_modq(signature[:32] + public + msg)
    return _equal(_mul(s, _G), _add(r_pt, _mul(h, a_pt)))
