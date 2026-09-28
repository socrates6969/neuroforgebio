"""SEC-105 made operational (AppSec M1): the audit hash chain is built, anchored and verified by
queued jobs, like the consent (5.3) and provenance (SEC-043) chains.

- :func:`batch_and_anchor` (job ``audit.batch``, hourly per tenant): ``AuditBatcher`` writes the
  tenant's and the ``_platform`` scope's due events as the next batch (WORM ``audit`` bucket,
  ``chain/<scope>/<seq>.json``), then :func:`anchor_heads` writes a signed head anchor per scope:
  ``audit-anchors/<scope>/<seq:012d>.json`` = ``{"schema": "nf.audit-anchor/v1", "scope", "seq",
  "head", "anchored_at", "key_id", "sig"}`` (``sig`` = Ed25519 with the provenance keyring over
  the canonical JSON of the other members; the consent/provenance anchor construction). One anchor
  per chain position: the key is the batch seq, so an anchor is never rewritten (Object Lock).
- :func:`verify_scopes` (job ``audit.verify``, daily per tenant): the database head must equal the
  newest validly signed anchor (so the ``audit_batch`` table cannot be swapped on its own), the
  stored objects must form a chain ending at that head and match the ``audit_batch`` rows one to
  one (scope, batch id, prev, event count, first/last event seq), and every batched event must
  still be in ``audit_event`` unchanged. Failures are logged at ERROR with
  ``alert="audit_chain_mismatch"`` (the hook for the SEC-102 alert rules) and fail the job
  without retry.

Roles (AppSec M2): everything here reads and writes the chain as ``nf_audit_batcher``
(``audit.chain.batcher_session``) on :func:`batcher_engine`, the batcher's own DB login
(``NF_AUDIT_BATCHER_DATABASE_URL``); locally and in tests it falls back to the worker's engine.

Limit: an event row removed BEFORE it was batched leaves no trace in the chain (a DB-side per-row
hash chain would close that; see docs/security/SEC-COVERAGE.md).
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import Engine, create_engine

from nf_platform.audit import _canonical as cj
from nf_platform.audit import chain
from nf_platform.config import AUDIT_BATCHER_URL_ENV
from nf_platform.provenance import signing

log = logging.getLogger(__name__)
BUCKET = chain.BUCKET
ANCHOR_SCHEMA = "nf.audit-anchor/v1"
ANCHOR_PREFIX = "audit-anchors"
ALERT = "audit_chain_mismatch"


_engines: dict[str, Engine] = {}
_engines_lock = threading.Lock()


def batcher_engine(default: Engine | None) -> Engine:
    """The engine of the batcher's own login when ``NF_AUDIT_BATCHER_DATABASE_URL`` is set (a
    deployment MUST set it: the API's login must not be a member of ``nf_audit_batcher``), else
    ``default`` (local dev and tests use one login; the code path still assumes the batcher role
    only inside the batcher's session)."""
    url = os.environ.get(AUDIT_BATCHER_URL_ENV)
    if not url:
        if default is None:
            raise RuntimeError(f"no database for the audit batcher ({AUDIT_BATCHER_URL_ENV})")
        return default
    with _engines_lock:
        if url not in _engines:
            _engines[url] = create_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=1)
        return _engines[url]


class AnchorStore(Protocol):
    def put(
        self, bucket: str, key: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> None: ...
    def get(self, bucket: str, key: str) -> bytes: ...
    def list(self, bucket: str, prefix: str) -> Iterator[str]: ...


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    scope: str
    batches: int
    head: str | None
    errors: list[str]


def scopes_for_tenant(tenant_id: str) -> list[str]:
    """The chains a tenant's job looks after: its own and the tenant-less ``_platform`` one (every
    tenant's job covers it; the batcher's per-scope lock keeps that idempotent)."""
    return [str(tenant_id), chain.PLATFORM_SCOPE]


def anchor_key(scope: str, seq: int) -> str:
    return f"{ANCHOR_PREFIX}/{scope}/{seq:012d}.json"


def _signed_part(doc: dict[str, Any]) -> bytes:
    return cj.canonicalize({k: v for k, v in doc.items() if k != "sig"})


def latest_anchor(
    store: AnchorStore, scope: str, keyring: signing.Keyring | None = None
) -> dict[str, Any] | None:
    """The newest anchor of a scope (highest seq). Raises ValueError when it is not a valid
    anchor of this scope signed by a trusted key: a forged newest anchor is an alert, never
    skipped in favour of an older one."""
    kr = keyring or signing.keyring()
    keys = sorted(store.list(BUCKET, f"{ANCHOR_PREFIX}/{scope}/"))
    if not keys:
        return None
    try:
        doc = cj.parse(store.get(BUCKET, keys[-1]).decode("utf-8"))
        ok = (
            isinstance(doc, dict)
            and doc.get("schema") == ANCHOR_SCHEMA
            and doc.get("scope") == scope
            and keys[-1] == anchor_key(scope, int(doc.get("seq", -1)))
            and kr.verify(
                str(doc.get("key_id")), _signed_part(doc), bytes.fromhex(str(doc.get("sig")))
            )
        )
    except (ValueError, TypeError, UnicodeDecodeError):
        ok = False
    if not ok:
        raise ValueError(f"anchor {keys[-1]} is invalid or not signed by a trusted key")
    return doc


def anchor_heads(
    engine: Engine,
    store: AnchorStore,
    scopes: Iterable[str],
    now: datetime | None = None,
    keyring: signing.Keyring | None = None,
) -> dict[str, str | None]:
    """Anchor the current database head of each scope unless the newest anchor already names it.
    Returns scope -> anchored head (None: no batch yet)."""
    kr = keyring or signing.keyring()
    now = now or datetime.now(UTC)
    out: dict[str, str | None] = {}
    for scope in scopes:
        rows = chain.batch_rows(engine, scope)
        if not rows:
            out[scope] = None
            continue
        head = rows[-1]
        try:
            prev = latest_anchor(store, scope, kr)
        except ValueError:
            prev = None  # verification reports it; a new valid anchor is still written
        if prev is not None and prev.get("seq") == head.seq and prev.get("head") == head.batch_id:
            out[scope] = head.batch_id
            continue
        doc: dict[str, Any] = {
            "schema": ANCHOR_SCHEMA,
            "scope": scope,
            "seq": head.seq,
            "head": head.batch_id,
            "anchored_at": chain.ts(now),
            "key_id": kr.signer.key_id,
        }
        doc["sig"] = kr.signer.sign(_signed_part(doc)).hex()
        store.put(
            BUCKET,
            anchor_key(scope, head.seq),
            cj.canonicalize(doc),
            metadata={"head": head.batch_id},
        )
        out[scope] = head.batch_id
    return out


def batch_and_anchor(
    engine: Engine,
    store: AnchorStore,
    scopes: Iterable[str],
    now: datetime | None = None,
    keyring: signing.Keyring | None = None,
) -> dict[str, Any]:
    """Job body of ``audit.batch``: batch the due events of ``scopes``, then anchor their heads."""
    scopes = list(scopes)
    results = chain.AuditBatcher(engine, store).run(now, scopes=scopes)
    heads = anchor_heads(engine, store, scopes, keyring=keyring)
    return {
        "batches": {r.scope: {"seq": r.seq, "events": r.event_count} for r in results},
        "heads": heads,
    }


def _verify_scope(
    engine: Engine, store: AnchorStore, scope: str, keyring: signing.Keyring | None
) -> VerifyResult:
    errors: list[str] = []
    rows = chain.batch_rows(engine, scope)
    db_head = rows[-1] if rows else None
    try:
        anchor = latest_anchor(store, scope, keyring)
    except ValueError as e:
        anchor = None
        errors.append(str(e))
    if anchor is None and not errors and db_head is not None:
        errors.append("no head anchor for a chain that has batches")
    if anchor is not None:
        if db_head is None:
            errors.append(f"anchor names seq {anchor['seq']} but the database has no batch")
        elif (anchor.get("seq"), anchor.get("head")) != (db_head.seq, db_head.batch_id):
            errors.append(
                f"database head (seq {db_head.seq}) does not match the signed anchor "
                f"(seq {anchor.get('seq')})"
            )
    batches: list[dict[str, Any]] = []
    try:
        batches = chain.load_chain(store, scope)
        expected = anchor.get("head") if anchor is not None else None
        chain.verify_chain(batches, expected, scope=scope, rows=rows)
    except chain.AuditChainError as e:
        errors.append(str(e))
    except (KeyError, OSError) as e:
        errors.append(f"stored chain unreadable: {type(e).__name__}")
    errors += chain.check_events(engine, scope, batches)
    return VerifyResult(
        not errors, scope, len(batches), None if db_head is None else db_head.batch_id, errors
    )


def verify_scopes(
    engine: Engine,
    store: AnchorStore,
    scopes: Iterable[str],
    keyring: signing.Keyring | None = None,
) -> list[VerifyResult]:
    """Verify each scope's chain (see the module docstring); log an alert for every failure."""
    results = []
    for scope in scopes:
        res = _verify_scope(engine, store, scope, keyring)
        if not res.ok:
            log.error(
                "audit chain verification failed",
                extra={"alert": ALERT, "scope": scope, "errors": len(res.errors)},
            )
        results.append(res)
    return results
