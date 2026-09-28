"""Canonical node records and provenance batches (docs/spec/hashing.md §5.3, kind ``provb``).

Record shapes (the spec leaves them to step 3.1; they only need to be valid NF-CJSON):

- node: ``{"type": "entity"|"activity"|"agent", "id": "<uuid>", "label": "<node type>",
  "ref": "<platform id>"?, "content": "<content ID>"?, "attrs": {...}?}`` (optional members are
  omitted when empty, matching the frozen vector ``prov_batch_chain``).
- edge: ``{"type": "edge", "rel": "<PROV relation>", "from": "<uuid>", "to": "<uuid>"}``.

A batch lists its node records (in insertion order) followed by its edge records. The node hash is
SHA-256(``nf.prov-node.v1`` 0x00 canonical node record): the same construction as the spec's IDs
with its own tag (proposed for hashing spec v2, like ``auditb``).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from nf_platform.audit import _canonical as cj

SCHEMA = "nf.prov-batch/v1"
TAG = "nf.prov-batch.v1"
NODE_TAG = "nf.prov-node.v1"
KIND = "provb"
ID_RE = re.compile(r"^provb:sha256:[0-9a-f]{64}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class ChainError(ValueError):
    """A batch document is malformed."""


def ts(dt: datetime) -> str:
    dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def now_ms() -> datetime:
    """Current UTC time truncated to milliseconds (the precision that is hashed)."""
    n = datetime.now(UTC)
    return n.replace(microsecond=(n.microsecond // 1000) * 1000)


def node_record(
    node_id: str,
    kind: str,
    type_: str,
    ref_id: str | None,
    content_hash: str | None,
    attrs: dict[str, Any] | None,
) -> dict[str, Any]:
    r: dict[str, Any] = {"type": kind, "id": node_id, "label": type_}
    if ref_id is not None:
        r["ref"] = ref_id
    if content_hash is not None:
        r["content"] = content_hash
    if attrs:
        r["attrs"] = attrs
    return r


def edge_record(src: str, rel: str, dst: str) -> dict[str, Any]:
    return {"type": "edge", "rel": rel, "from": src, "to": dst}


def node_hash(record: dict[str, Any]) -> str:
    return cj.sha256_hex(cj.tagged_preimage(NODE_TAG, cj.canonicalize(record)))


def batch_doc(
    tenant: str, seq: int, prev: str | None, created_at: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "tenant": tenant,
        "seq": seq,
        "prev": prev,
        "created_at": created_at,
        "records": records,
    }


def batch_payload(batch: dict[str, Any]) -> bytes:
    if batch.get("schema") != SCHEMA:
        raise ChainError(f"schema must be {SCHEMA}")
    seq, prev = batch.get("seq"), batch.get("prev")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise ChainError("seq must be a non-negative integer")
    if (seq == 0) != (prev is None):
        raise ChainError("prev must be null exactly when seq == 0")
    if prev is not None and not ID_RE.match(prev):
        raise ChainError("prev must be a provb id")
    if not TS_RE.match(str(batch.get("created_at", ""))):
        raise ChainError("created_at must be YYYY-MM-DDTHH:MM:SS.sssZ")
    try:
        return cj.canonicalize(batch)
    except cj.CanonicalError as e:
        raise ChainError(str(e)) from e


def batch_id(batch: dict[str, Any]) -> str:
    """``provb:sha256:`` + SHA-256(``nf.prov-batch.v1`` 0x00 canonical batch)."""
    return f"{KIND}:sha256:" + cj.sha256_hex(cj.tagged_preimage(TAG, batch_payload(batch)))
