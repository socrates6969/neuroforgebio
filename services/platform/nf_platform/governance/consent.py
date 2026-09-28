"""Consent ledger (BUILD-GUIDE 5.3; BLUEPRINT §8.3).

- ``consent_record`` is append-only in the database (trigger for every role + ``nf_app`` holds only
  SELECT/INSERT); a change of consent is a new entry, nothing is updated in place.
- Per-tenant hash chain, the same construction as the audit/provenance chains
  (docs/spec/hashing.md §5.3): ``record_hash`` = SHA-256(``nf.consent-record.v1`` 0x00 canonical
  JSON of the record, which includes the tenant, ``seq`` and the previous ``record_hash``). The tag
  is proposed for hashing spec v2, like ``auditb`` and ``provb``.
- Daily anchor of the chain head in the WORM ``audit`` bucket (job ``consent.anchor``):
  ``consent-anchors/<tenant>/<YYYY-MM-DD>.json``, Ed25519-signed with the platform signing key.
  :func:`verify_tenants` (job ``consent.verify``) recomputes the chain and checks it against the
  latest anchor; a mismatch logs an ERROR with ``alert="consent_chain_mismatch"`` (hook for the
  SEC-102 alert rules).
- Scopes: collection, processing, sharing, model_training, commercial_use. A subject's current
  scopes are the scopes of its latest ``grant`` minus every scope withdrawn after it. No record
  means no scope (policy denies).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.db import models as m
from nf_platform.db.context import Principal, tenant_session
from nf_platform.provenance import chain as pchain
from nf_platform.provenance import signing

log = logging.getLogger(__name__)
SCOPES = m.CONSENT_SCOPES
TAG = "nf.consent-record.v1"
SCHEMA = "nf.consent-record/v1"
ANCHOR_SCHEMA = "nf.consent-anchor/v1"
ANCHOR_PREFIX = "consent-anchors"
BUCKET = "audit"
ALERT = "consent_chain_mismatch"
SERVICE_ID = "svc:consent-ledger"
_LOCK_CLASS = 0x4E460005


class ConsentError(ValueError):
    """Invalid consent input (422), a conflict (409) or a missing object (404)."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    tenant_id: str
    records: int
    head_seq: int | None
    head: str | None
    errors: list[str]


class AnchorStore(Protocol):
    def put(
        self, bucket: str, key: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> None: ...
    def get(self, bucket: str, key: str) -> bytes: ...
    def list(self, bucket: str, prefix: str) -> Iterator[str]: ...


# ---------------------------------------------------------------- documents
def create_document(
    session: Session, principal: Principal, *, name: str, version: str, sha256: str, uri: str | None
) -> tuple[m.ConsentDocument, bool]:
    """Register a document version (idempotent for identical content; 409 if the same name and
    version already has another hash). Returns (row, created)."""
    sha = sha256.lower()
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ConsentError(422, "sha256 must be 64 hex characters")
    row = session.scalar(
        select(m.ConsentDocument).where(
            m.ConsentDocument.name == name, m.ConsentDocument.version == version
        )
    )
    if row is not None:
        if row.sha256 != sha:
            raise ConsentError(409, "this document version is registered with another hash")
        return row, False
    row = m.ConsentDocument(
        tenant_id=uuid.UUID(str(principal.tenant_id)),
        name=name,
        version=version,
        sha256=sha,
        uri=uri,
        created_by=principal.id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row, True


# ---------------------------------------------------------------- records + chain
def record_doc(
    *,
    tenant_id: str,
    seq: int,
    prev: str | None,
    record_id: str,
    subject_id: str,
    kind: str,
    scopes: Iterable[str],
    document_id: str | None,
    document_sha256: str | None,
    basis: str | None,
    collector: str,
    evidence: str | None,
    recorded_at: datetime,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "tenant": tenant_id,
        "seq": seq,
        "prev": prev,
        "id": record_id,
        "subject": subject_id,
        "kind": kind,
        "scopes": sorted(set(scopes)),
        "document": None if document_id is None else {"id": document_id, "sha256": document_sha256},
        "basis": basis,
        "collector": collector,
        "evidence": evidence,
        "recorded_at": pchain.ts(recorded_at),
    }


def record_hash(doc: dict[str, Any]) -> str:
    """Hashing spec v2 §9.3: ``scopes`` are de-duplicated and sorted before hashing (BUG-HUNT L6),
    so a doc built without :func:`record_doc` still gets the canonical hash."""
    canon = dict(doc, scopes=sorted(set(doc["scopes"])))
    return cj.sha256_hex(cj.tagged_preimage(TAG, cj.canonicalize(canon)))


def _row_doc(r: m.ConsentRecord) -> dict[str, Any]:
    return record_doc(
        tenant_id=str(r.tenant_id),
        seq=r.seq,
        prev=r.prev_hash,
        record_id=str(r.id),
        subject_id=str(r.subject_id),
        kind=r.kind,
        scopes=r.scopes,
        document_id=None if r.document_id is None else str(r.document_id),
        document_sha256=r.document_sha256,
        basis=r.jurisdiction_basis,
        collector=r.collector_id,
        evidence=r.evidence_ref,
        recorded_at=r.recorded_at,
    )


def append(
    session: Session,
    principal: Principal,
    subject_id: uuid.UUID,
    *,
    kind: str,
    scopes: Iterable[str],
    document_id: uuid.UUID | None = None,
    jurisdiction_basis: str | None = None,
    evidence_ref: str | None = None,
) -> m.ConsentRecord:
    """Append one ledger entry for ``subject_id`` (in the caller's tenant session)."""
    tid = uuid.UUID(str(principal.tenant_id))
    scopes = sorted(set(scopes))
    if kind not in m.CONSENT_KINDS:
        raise ConsentError(422, "kind must be grant or withdraw")
    if not scopes:
        raise ConsentError(422, "at least one scope is required")
    bad = set(scopes) - set(SCOPES)
    if bad:
        raise ConsentError(422, f"unknown scope(s): {sorted(bad)}")
    if session.scalar(select(m.Subject.id).where(m.Subject.id == subject_id)) is None:
        raise ConsentError(404, "subject")
    doc_sha = None
    if kind == "grant":
        if document_id is None:
            raise ConsentError(422, "a grant needs the consent document it was given on")
        d = session.scalar(select(m.ConsentDocument).where(m.ConsentDocument.id == document_id))
        if d is None:
            raise ConsentError(404, "consent document")
        doc_sha = d.sha256
    elif document_id is not None:
        raise ConsentError(422, "a withdrawal does not reference a document")
    session.execute(
        text("SELECT pg_advisory_xact_lock(:c, hashtext(:t))"), {"c": _LOCK_CLASS, "t": str(tid)}
    )
    head = session.execute(
        select(m.ConsentRecord.seq, m.ConsentRecord.record_hash)
        .where(m.ConsentRecord.tenant_id == tid)
        .order_by(m.ConsentRecord.seq.desc())
        .limit(1)
    ).first()
    seq = 0 if head is None else head.seq + 1
    prev = None if head is None else head.record_hash
    rid = uuid.uuid4()
    now = pchain.now_ms()
    doc = record_doc(
        tenant_id=str(tid),
        seq=seq,
        prev=prev,
        record_id=str(rid),
        subject_id=str(subject_id),
        kind=kind,
        scopes=scopes,
        document_id=None if document_id is None else str(document_id),
        document_sha256=doc_sha,
        basis=jurisdiction_basis,
        collector=principal.id,
        evidence=evidence_ref,
        recorded_at=now,
    )
    row = m.ConsentRecord(
        tenant_id=tid,
        seq=seq,
        id=rid,
        subject_id=subject_id,
        kind=kind,
        scopes=scopes,
        document_id=document_id,
        document_sha256=doc_sha,
        jurisdiction_basis=jurisdiction_basis,
        collector_id=principal.id,
        evidence_ref=evidence_ref,
        recorded_at=now,
        prev_hash=prev,
        record_hash=record_hash(doc),
    )
    session.add(row)
    session.flush()
    return row


def records_for(session: Session, subject_id: uuid.UUID) -> list[m.ConsentRecord]:
    return list(
        session.scalars(
            select(m.ConsentRecord)
            .where(m.ConsentRecord.subject_id == subject_id)
            .order_by(m.ConsentRecord.seq)
        )
    )


def fold(records: Iterable[m.ConsentRecord]) -> frozenset[str]:
    scopes: set[str] = set()
    for r in records:
        if r.kind == "grant":
            scopes = set(r.scopes)
        else:
            scopes -= set(r.scopes)
    return frozenset(scopes)


def current_scopes(
    session: Session, subject_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, frozenset]:
    """Current scopes per subject (subjects without records map to the empty set)."""
    ids = sorted({uuid.UUID(str(s)) for s in subject_ids})
    out: dict[uuid.UUID, list[m.ConsentRecord]] = {s: [] for s in ids}
    if ids:
        rows = session.scalars(
            select(m.ConsentRecord)
            .where(m.ConsentRecord.subject_id.in_(ids))
            .order_by(m.ConsentRecord.seq)
        )
        for r in rows:
            out[r.subject_id].append(r)
    return {s: fold(rs) for s, rs in out.items()}


def withdrawn(records: Iterable[m.ConsentRecord]) -> bool:
    """A full withdrawal (every scope) is the last word about a subject."""
    rs = list(records)
    return bool(rs) and rs[-1].kind == "withdraw" and set(rs[-1].scopes) == set(SCOPES)


def verify_chain(
    session: Session, tenant_id: str, *, expected: tuple[int, str] | None = None
) -> VerifyResult:
    """Recompute every record hash and ``prev`` link of the tenant's chain; with ``expected``
    (an anchored ``(seq, head)``) also check that the anchored entry is unchanged."""
    tid = uuid.UUID(str(tenant_id))
    rows = session.scalars(
        select(m.ConsentRecord)
        .where(m.ConsentRecord.tenant_id == tid)
        .order_by(m.ConsentRecord.seq)
    ).all()
    errors: list[str] = []
    prev: str | None = None
    by_seq: dict[int, str] = {}
    for i, r in enumerate(rows):
        if r.seq != i:
            errors.append(f"record {i}: sequence gap (found seq {r.seq})")
        if r.prev_hash != prev:
            errors.append(f"record {r.seq}: prev does not match the previous record hash")
        if record_hash(_row_doc(r)) != r.record_hash:
            errors.append(f"record {r.seq}: content does not match its hash")
        by_seq[r.seq] = r.record_hash
        prev = r.record_hash
    if expected is not None:
        seq, head = expected
        if by_seq.get(seq) != head:
            errors.append(f"anchor mismatch at seq {seq}: the anchored head is not in the chain")
    return VerifyResult(
        ok=not errors,
        tenant_id=str(tid),
        records=len(rows),
        head_seq=rows[-1].seq if rows else None,
        head=rows[-1].record_hash if rows else None,
        errors=errors,
    )


# ---------------------------------------------------------------- anchors (WORM bucket)
def _svc(tenant_id: str) -> Principal:
    return Principal(SERVICE_ID, str(tenant_id), frozenset(), frozenset(), "service", False)


def _signed_part(doc: dict[str, Any]) -> bytes:
    return cj.canonicalize({k: v for k, v in doc.items() if k != "sig"})


def anchor_key(tenant_id: str, day: datetime) -> str:
    return f"{ANCHOR_PREFIX}/{tenant_id}/{day.astimezone(UTC):%Y-%m-%d}.json"


def anchor_heads(
    engine: Engine,
    store: AnchorStore,
    tenant_ids: Iterable[str],
    now: datetime | None = None,
    keyring: signing.Keyring | None = None,
) -> dict[str, str | None]:
    """Anchor every tenant's current consent-chain head (tenants without records are skipped)."""
    kr = keyring or signing.keyring()
    now = now or datetime.now(UTC)
    out: dict[str, str | None] = {}
    for tid in tenant_ids:
        with tenant_session(_svc(tid), engine=engine) as s:
            head = s.execute(
                select(m.ConsentRecord.seq, m.ConsentRecord.record_hash)
                .order_by(m.ConsentRecord.seq.desc())
                .limit(1)
            ).first()
        if head is None:
            out[str(tid)] = None
            continue
        doc: dict[str, Any] = {
            "schema": ANCHOR_SCHEMA,
            "tenant": str(tid),
            "seq": head.seq,
            "head": head.record_hash,
            "anchored_at": pchain.ts(now),
            "key_id": kr.signer.key_id,
        }
        doc["sig"] = kr.signer.sign(_signed_part(doc)).hex()
        store.put(
            BUCKET, anchor_key(str(tid), now), cj.canonicalize(doc), metadata={"head": head[1]}
        )
        out[str(tid)] = head.record_hash
    return out


def latest_anchor(
    store: AnchorStore, tenant_id: str, keyring: signing.Keyring | None = None
) -> dict[str, Any] | None:
    kr = keyring or signing.keyring()
    keys = sorted(store.list(BUCKET, f"{ANCHOR_PREFIX}/{tenant_id}/"))
    if not keys:
        return None
    doc = cj.parse(store.get(BUCKET, keys[-1]).decode("utf-8"))
    ok = (
        isinstance(doc, dict)
        and doc.get("schema") == ANCHOR_SCHEMA
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
) -> list[VerifyResult]:
    """Verify each tenant's consent chain against its latest anchor; alert on any failure."""
    results = []
    for tid in tenant_ids:
        expected = None
        anchor_error = None
        if store is not None:
            try:
                a = latest_anchor(store, str(tid), keyring)
                expected = None if a is None else (int(a["seq"]), str(a["head"]))
            except (ValueError, KeyError, TypeError) as e:
                anchor_error = str(e)
        with tenant_session(_svc(tid), engine=engine) as s:
            res = verify_chain(s, str(tid), expected=expected)
        if anchor_error:
            res = VerifyResult(
                False,
                res.tenant_id,
                res.records,
                res.head_seq,
                res.head,
                [*res.errors, anchor_error],
            )
        if not res.ok:
            log.error(
                "consent chain verification failed",
                extra={"alert": ALERT, "tenant_id": str(tid), "errors": len(res.errors)},
            )
        results.append(res)
    return results
