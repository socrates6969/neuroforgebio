"""Queue job bodies of the compliance ledger (run by ``nf_runner``'s worker, 3.3 queue):

- ``governance.deletion``: one DeletionJob (5.5), see :mod:`nf_platform.governance.deletion`;
- ``consent.anchor`` (daily per tenant): anchor the consent-chain head in the WORM bucket;
- ``consent.verify`` (hourly per tenant): verify the chain against the latest anchor; a mismatch
  fails the job without retry and logs the ``consent_chain_mismatch`` alert;
- ``audit.batch`` (hourly per tenant, AppSec M1): batch the tenant's and the ``_platform`` audit
  events into the WORM chain and anchor each head (:mod:`nf_platform.governance.audit_integrity`);
- ``audit.verify`` (daily per tenant): verify those chains against the rows, the events and the
  anchors; a mismatch fails the job without retry and logs the ``audit_chain_mismatch`` alert.

A scheduler (cron) that enqueues the periodic jobs is not built yet (same as the provenance anchor
jobs); :func:`dedupe_key` keeps one job per tenant and period however often it is enqueued.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Engine

from nf_platform.governance import audit_integrity, consent, deletion
from nf_platform.storage.runtime import Storage

DELETION_KIND = deletion.JOB_KIND
CONSENT_ANCHOR_KIND = "consent.anchor"
CONSENT_VERIFY_KIND = "consent.verify"
AUDIT_BATCH_KIND = "audit.batch"
AUDIT_VERIFY_KIND = "audit.verify"
KINDS = (
    DELETION_KIND,
    CONSENT_ANCHOR_KIND,
    CONSENT_VERIFY_KIND,
    AUDIT_BATCH_KIND,
    AUDIT_VERIFY_KIND,
)
DAILY_KINDS = (CONSENT_ANCHOR_KIND, AUDIT_VERIFY_KIND)


class JobFailed(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def dedupe_key(kind: str, now: datetime) -> str:
    return f"{now:%Y-%m-%d}" if kind in DAILY_KINDS else f"{now:%Y-%m-%dT%H}"


def run(
    kind: str,
    engine: Engine | None,
    storage: Storage,
    tenant_id: str,
    payload: dict[str, Any],
    *,
    last_attempt: bool = False,
) -> dict[str, Any]:
    """Run one job body; returns the job result. Raises :class:`JobFailed`."""
    if kind == DELETION_KIND:
        did = uuid.UUID(str(payload["deletion_id"]))
        try:
            cert = deletion.execute(engine, storage, tenant_id, did)
        except deletion.DeletionError as e:
            deletion.mark_failed(engine, tenant_id, did, e.detail)
            raise JobFailed(e.detail, retryable=False) from e
        except Exception as e:
            if last_attempt:
                deletion.mark_failed(engine, tenant_id, did, type(e).__name__)
            raise
        return {
            "deletion_id": str(did),
            "duration_s": cert["duration_s"],
            "nodes": len(cert["nodes"]),
        }
    if kind == CONSENT_ANCHOR_KIND:
        heads = consent.anchor_heads(engine, storage.objects, [tenant_id])
        return {"head": heads.get(tenant_id)}
    if kind == CONSENT_VERIFY_KIND:
        (res,) = consent.verify_tenants(engine, storage.objects, [tenant_id])
        if not res.ok:
            raise JobFailed(f"{consent.ALERT}: {'; '.join(res.errors)[:500]}", retryable=False)
        return {"head": res.head, "records": res.records}
    if kind == AUDIT_BATCH_KIND:
        return audit_integrity.batch_and_anchor(
            audit_integrity.batcher_engine(engine),
            storage.objects,
            audit_integrity.scopes_for_tenant(tenant_id),
        )
    if kind == AUDIT_VERIFY_KIND:
        res = audit_integrity.verify_scopes(
            audit_integrity.batcher_engine(engine),
            storage.objects,
            audit_integrity.scopes_for_tenant(tenant_id),
        )
        errors = [f"{r.scope}: {e}" for r in res for e in r.errors]
        if errors:
            raise JobFailed(f"{audit_integrity.ALERT}: {'; '.join(errors)[:500]}", retryable=False)
        return {
            "scopes": {r.scope: {"ok": r.ok, "batches": r.batches, "head": r.head} for r in res}
        }
    raise JobFailed(f"unknown governance job kind {kind!r}", retryable=False)
