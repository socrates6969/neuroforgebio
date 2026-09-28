"""SEC-043 jobs for the provenance chain: daily head anchors in the WORM ``audit`` bucket and the
verification run that alerts on a mismatch.

- :func:`anchor_heads` writes, per tenant, ``prov-anchors/<tenant>/<YYYY-MM-DD>.json`` =
  ``{"schema": "nf.prov-anchor/v1", "tenant", "seq", "head", "anchored_at", "key_id", "sig"}``
  (``sig`` = Ed25519 over the canonical JSON of the other members). In real S3 the bucket has
  Object Lock, so an anchor cannot be rewritten; locally the ``LocalObjectStore`` stands in.
- :func:`verify_tenants` recomputes each tenant's chain (``api.verify_chain``) against the latest
  valid anchor. A removed or rewritten tail after the anchor is caught by the anchor, anything
  before it by the hashes and signatures. Failures are logged at ERROR with
  ``alert="prov_chain_mismatch"``, the hook for the alert rules (SEC-102, not built yet).

Scheduling (daily anchor, hourly verification) is the job queue's (3.3); these are the job bodies.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import Engine

from nf_platform.audit import _canonical as cj
from nf_platform.db.context import Principal, tenant_session
from nf_platform.provenance import api, chain, signing

log = logging.getLogger(__name__)
BUCKET = "audit"
SCHEMA = "nf.prov-anchor/v1"
ALERT = "prov_chain_mismatch"
SERVICE_ID = "svc:prov-integrity"


class AnchorStore(Protocol):
    """The subset of ``storage.objects.ObjectStore`` used here."""

    def put(
        self, bucket: str, key: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> None: ...
    def get(self, bucket: str, key: str) -> bytes: ...
    def list(self, bucket: str, prefix: str) -> Iterator[str]: ...


def _svc(tenant_id: str) -> Principal:
    return Principal(SERVICE_ID, str(tenant_id), frozenset(), frozenset(), "service", False)


def _signed_part(doc: dict[str, Any]) -> bytes:
    return cj.canonicalize({k: v for k, v in doc.items() if k != "sig"})


def anchor_key(tenant_id: str, day: datetime) -> str:
    return f"prov-anchors/{tenant_id}/{day.astimezone(UTC):%Y-%m-%d}.json"


def anchor_heads(
    engine: Engine,
    store: AnchorStore,
    tenant_ids: Iterable[str],
    now: datetime | None = None,
    keyring: signing.Keyring | None = None,
) -> dict[str, str | None]:
    """Anchor every tenant's current chain head (tenants without batches are skipped)."""
    kr = keyring or signing.keyring()
    now = now or datetime.now(UTC)
    out: dict[str, str | None] = {}
    for tid in tenant_ids:
        with tenant_session(_svc(tid), engine=engine) as s:
            head = api.chain_head(s)
        if head is None:
            out[str(tid)] = None
            continue
        doc: dict[str, Any] = {
            "schema": SCHEMA,
            "tenant": str(tid),
            "seq": head[0],
            "head": head[1],
            "anchored_at": chain.ts(now),
            "key_id": kr.signer.key_id,
        }
        doc["sig"] = kr.signer.sign(_signed_part(doc)).hex()
        store.put(
            BUCKET, anchor_key(str(tid), now), cj.canonicalize(doc), metadata={"head": head[1]}
        )
        out[str(tid)] = head[1]
    return out


def latest_anchor(
    store: AnchorStore, tenant_id: str, keyring: signing.Keyring | None = None
) -> dict[str, Any] | None:
    """The newest anchor of a tenant whose signature verifies (invalid ones raise)."""
    kr = keyring or signing.keyring()
    keys = sorted(store.list(BUCKET, f"prov-anchors/{tenant_id}/"))
    if not keys:
        return None
    doc = cj.parse(store.get(BUCKET, keys[-1]).decode("utf-8"))
    ok = (
        isinstance(doc, dict)
        and doc.get("schema") == SCHEMA
        and doc.get("tenant") == str(tenant_id)
        and kr.verify(str(doc.get("key_id")), _signed_part(doc), bytes.fromhex(str(doc.get("sig"))))
    )
    if not ok:
        raise ValueError(f"anchor {keys[-1]} is invalid or not signed by a trusted key")
    return doc


def verify_tenants(
    engine: Engine,
    store: AnchorStore | None,
    tenant_ids: Iterable[str],
    keyring: signing.Keyring | None = None,
) -> list[api.VerifyResult]:
    """Verify each tenant's chain (against its latest anchor when a store is given); log an alert
    for every failure. Returns all results."""
    results = []
    for tid in tenant_ids:
        expected = None
        anchor_error = None
        if store is not None:
            try:
                a = latest_anchor(store, str(tid), keyring)
                expected = None if a is None else a["head"]
            except ValueError as e:
                anchor_error = str(e)
        with tenant_session(_svc(tid), engine=engine) as s:
            res = api.verify_chain(s, str(tid), expected_head=expected, keyring=keyring)
        if anchor_error:
            res = api.VerifyResult(
                False,
                res.tenant_id,
                res.batches,
                res.nodes,
                res.edges,
                res.head,
                [*res.errors, anchor_error],
            )
        if not res.ok:
            log.error(
                "provenance chain verification failed",
                extra={"alert": ALERT, "tenant_id": str(tid), "errors": len(res.errors)},
            )
        results.append(res)
    return results
