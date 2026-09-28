"""Deletion propagation, crypto-shredding and the signed certificate (BUILD-GUIDE 5.5; BLUEPRINT
§8.4; SEC-034, SEC-034a, SEC-046, SEC-124).

``POST /v1/subjects/{id}/withdrawals`` -> :func:`request_withdrawal`: a full ``withdraw`` entry in
the consent ledger (every scope; the policy denies all further use at once), a ``deletion_job``
row and a ``governance.deletion`` job on the 3.3 queue. The worker runs :func:`execute`:

1. **Traverse** the provenance graph downward from every entity of the subject (its recordings and
   raw uploads).
2. **Act per node**:
   - raw files, recordings and run artifacts (single-subject by construction): objects deleted;
   - multi-subject aggregates (group averages): marked ``stale``, then per tenant policy either
     re-run without the subject (new node, old one ``superseded``) or ``tombstoned``; in both cases
     the old object is deleted and its own data key destroyed;
   - models: flagged ``retrain_required`` (``model_flag``, the M6 registry hook); deployments are
     blocked when the tenant policy says so. We do not claim certified unlearning;
   - AppSec M3: every model version of the tenant registered from UPLOADED weights before the
     withdrawal is flagged too, whatever its declared lineage (it cannot be verified), with
     deployments blocked; reason :data:`UPLOAD_TAINT_REASON`. Propagation is exact only for
     platform-trained versions (docs/features/model-registry-lineage.md);
   - activities and agents: listed (the graph is append-only, nothing to delete).
3. **Objects**: every object under the subject's prefixes (``raw``, ``zarr``) and every run output
   (``artifacts``) is deleted.
4. **Exports** that already left the platform are listed; they cannot be recalled.
5. **Crypto-shred**: the subject's wrapped DEKs are destroyed; every remaining copy (backups,
   replicas) is unreadable. The subject is tombstoned (SEC-034a). A WORM shred-ledger entry lets a
   restore re-apply the shred (:func:`reapply_shreds`, SEC-124).
6. **Certificate**: signed JSON listing every affected node with the action and time, the key
   destruction and "unrecoverable in all copies after" = shred time + DB backup window (SEC-034).

Every step is idempotent, so a retried attempt finishes the job. Audit events: one per phase.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, any_, select
from sqlalchemy.orm import Session

from nf_platform.audit import _canonical as cj
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.db.context import Principal, tenant_session
from nf_platform.governance import certificate, consent, derived, policy
from nf_platform.jobs import queue
from nf_platform.provenance import api as prov
from nf_platform.storage.objects import ObjectNotFound, WormViolation
from nf_platform.storage.runtime import Storage, service_principal

log = logging.getLogger(__name__)
JOB_KIND = "governance.deletion"
SERVICE_ID = "svc:deletion-job"
AUDIT_TYPE = "governance.deletion"
AUDIT_BUCKET = "audit"
TARGET_S = 24 * 3600  # BLUEPRINT §8.4 target (an ESTIMATE of an acceptable SLA)
DEFAULT_DB_BACKUP_WINDOW_DAYS = 35  # ESTIMATE; set NF_DB_BACKUP_WINDOW_DAYS to the real retention
SUBJECT_ONLY_TYPES = frozenset({"raw_file", "recording", "artifact"})


class DeletionError(ValueError):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass
class NodeAction:
    node_id: uuid.UUID
    kind: str
    type: str
    action: str
    at: str
    replaced_by: uuid.UUID | None = None

    def out(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "node_id": str(self.node_id),
            "kind": self.kind,
            "type": self.type,
            "action": self.action,
            "at": self.at,
        }
        if self.replaced_by is not None:
            d["replaced_by"] = str(self.replaced_by)
        return d


def _ts() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def backup_window_days() -> int:
    days = int(os.environ.get("NF_DB_BACKUP_WINDOW_DAYS", DEFAULT_DB_BACKUP_WINDOW_DAYS))
    if days < 0:
        raise ValueError("NF_DB_BACKUP_WINDOW_DAYS must be >= 0")
    return days


def retention_statement(shredded_at: datetime, window_days: int) -> str:
    """M2-REVIEW F3 (binding policy, SEC-034): database backups taken before the shred still hold
    the wrapped keys until they expire, so the certificate states when the shred is complete in
    every copy. The end date is the UTC calendar day of ``shredded_at + window_days``."""
    ends = (shredded_at.astimezone(UTC) + timedelta(days=window_days)).date().isoformat()
    return (
        "Unrecoverable in all copies after the backup retention window of "
        f"{window_days} days (ends {ends})."
    )


def tenant_aggregate_policy(session: Session) -> m.TenantPolicy | None:
    return session.scalar(select(m.TenantPolicy))


# ---------------------------------------------------------------- request (API side)
def request_withdrawal(
    session: Session, principal: Principal, subject_id: uuid.UUID, *, evidence_ref: str | None
) -> tuple[m.DeletionJob, bool]:
    """Withdraw every consent scope and queue the DeletionJob (one active job per subject).
    Returns (job, created)."""
    if session.scalar(select(m.Subject.id).where(m.Subject.id == subject_id)) is None:
        raise DeletionError(404, "subject")
    active = session.scalar(
        select(m.DeletionJob).where(
            m.DeletionJob.subject_id == subject_id,
            m.DeletionJob.state.in_(("queued", "running")),
        )
    )
    if active is not None:
        return active, False
    consent.append(
        session,
        principal,
        subject_id,
        kind="withdraw",
        scopes=consent.SCOPES,
        evidence_ref=evidence_ref,
    )
    tp = tenant_aggregate_policy(session)
    did = uuid.uuid4()
    job_id = queue.enqueue(
        session,
        JOB_KIND,
        {"deletion_id": str(did)},
        dedupe_key=str(did),
        max_attempts=5,
        timeout_s=TARGET_S,
        created_by=principal.id,
    )
    row = m.DeletionJob(
        id=did,
        tenant_id=uuid.UUID(str(principal.tenant_id)),
        subject_id=subject_id,
        job_id=job_id,
        state="queued",
        aggregate_policy=tp.aggregate_on_withdrawal if tp else "rerun",
        requested_by=principal.id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row, True


# ---------------------------------------------------------------- execution (worker side)
UPLOAD_TAINT_REASON = "unverifiable lineage (uploaded weights)"  # = registry.service's


def upload_version_nodes(s: Session, before: datetime) -> list[uuid.UUID]:
    """Model nodes of the session tenant's versions registered from uploaded weights before
    ``before`` (AppSec M3: their lineage is the uploader's declaration)."""
    return list(
        s.scalars(
            select(m.ModelVersion.prov_node_id)
            .join(m.DerivedObject, m.DerivedObject.id == m.ModelVersion.derived_object_id)
            .where(
                m.DerivedObject.params["source"].astext == "upload",
                m.ModelVersion.created_at < before,
            )
            .order_by(m.ModelVersion.prov_node_id)
        )
    )


def _audit(tenant_id: str, subject_id: str, phase: str, outcome: str = "success", **d: Any) -> None:
    audit.emit(
        audit.AuditEvent(
            type=AUDIT_TYPE,
            outcome=outcome,  # type: ignore[arg-type]
            action="subject:withdraw",
            tenant_id=tenant_id,
            actor_kind="service",
            actor_id=SERVICE_ID,
            auth_method="service",
            resource_type="subject",
            resource_id=subject_id,
            details={"phase": phase, **d},
        )
    )


def _subject_sources(
    session: Session, subject_id: uuid.UUID
) -> tuple[list[uuid.UUID], list[uuid.UUID], list[uuid.UUID]]:
    rec_ids = list(
        session.scalars(
            select(m.Recording.id)
            .join(m.Session_, m.Session_.id == m.Recording.session_id)
            .where(m.Session_.subject_id == subject_id)
        )
    )
    upload_ids = list(session.scalars(select(m.Upload.id).where(m.Upload.subject_id == subject_id)))
    run_ids = (
        list(session.scalars(select(m.Run.id).where(m.Run.recording_id.in_(rec_ids))))
        if rec_ids
        else []
    )
    return rec_ids, upload_ids, run_ids


def _roots(session: Session, rec_ids, upload_ids) -> list[uuid.UUID]:
    out = []
    E = prov.ProvKind.ENTITY
    for rid in rec_ids:
        n = prov.find_node(session, E, "recording", str(rid))
        if n is not None:
            out.append(n)
    for uid in upload_ids:
        n = prov.find_node(session, E, "raw_file", str(uid))
        if n is not None:
            out.append(n)
    return out


def _descendants(session: Session, roots: Iterable[uuid.UUID]) -> dict[uuid.UUID, prov.GraphNode]:
    nodes: dict[uuid.UUID, prov.GraphNode] = {}
    for r in roots:
        for n in prov.lineage(session, r, "down", None).nodes:
            nodes.setdefault(n.id, n)
    return nodes


def _subjects_of(session: Session, node_id: uuid.UUID) -> set[uuid.UUID]:
    return policy.subjects_of_recordings(session, policy.source_recordings(session, [node_id]))


def _delete(storage: Storage, bucket: str, key: str) -> bool:
    try:
        storage.objects.delete(bucket, key)
        return True
    except ObjectNotFound:
        return False


def _worm_put(storage: Storage, key: str, doc: dict[str, Any]) -> None:
    with contextlib.suppress(WormViolation):
        storage.objects.put(AUDIT_BUCKET, key, cj.canonicalize(doc))


def flag_models(
    s: Session,
    tenant_id: str,
    model_node_ids: Iterable[uuid.UUID],
    deletion_id: uuid.UUID,
    block: bool,
) -> None:
    """Flag every model node ``retrain_required`` for this DeletionJob (the M6 registry's taint;
    idempotent).

    Takes the row lock of every registered model version of those nodes first (the lock
    ``registry.service.publish`` holds from its final taint check to its commit), so a flag can
    never land between that check and the publication (BUG-HUNT M3; a tainted version is never
    published)."""
    tid = uuid.UUID(str(tenant_id))
    ids = sorted(set(model_node_ids))
    if not ids:
        return
    s.execute(
        select(m.ModelVersion.id)
        .where(m.ModelVersion.prov_node_id.in_(ids))
        .order_by(m.ModelVersion.id)
        .with_for_update()
    ).all()
    for nid in ids:
        if s.get(m.ModelFlag, (tid, nid, deletion_id)) is None:
            s.add(
                m.ModelFlag(
                    tenant_id=tid,
                    model_node_id=nid,
                    deletion_job_id=deletion_id,
                    block_deployments=block,
                )
            )
    s.flush()


def execute(
    engine: Engine | None, storage: Storage, tenant_id: str, deletion_id: uuid.UUID
) -> dict[str, Any]:
    """Run (or finish) one DeletionJob. Returns the signed certificate."""
    t0 = time.perf_counter()
    tid = str(tenant_id)
    svc = service_principal(tid, SERVICE_ID)

    # ---- phase 1: plan + mark (one transaction)
    with tenant_session(svc, engine=engine) as s:
        dj = s.scalar(select(m.DeletionJob).where(m.DeletionJob.id == deletion_id))
        if dj is None:
            raise DeletionError(404, "deletion job")
        if dj.state == "succeeded" and dj.certificate:
            return dj.certificate
        dj.state = "running"
        dj.started_at = dj.started_at or datetime.now(UTC)
        sid = dj.subject_id
        subj = s.scalar(select(m.Subject).where(m.Subject.id == sid))
        pseudonym = subj.label
        agg_policy = dj.aggregate_policy
        tp = tenant_aggregate_policy(s)
        block = tp.block_deployments_on_retrain if tp else True
        requested_at = dj.requested_at
        started_at = dj.started_at
        rec_ids, upload_ids, run_ids = _subject_sources(s, sid)
        roots = _roots(s, rec_ids, upload_ids)
        desc = _descendants(s, roots)
        done = {
            r.node_id: r
            for r in s.scalars(
                select(m.ArtifactStatus).where(m.ArtifactStatus.node_id.in_(list(desc)))
            )
        }
        actions: dict[uuid.UUID, NodeAction] = {}
        aggregates: list[prov.GraphNode] = []
        models: list[prov.GraphNode] = []
        for n in sorted(desc.values(), key=lambda x: (x.batch_seq, str(x.id))):
            kind = n.kind.value
            if n.kind is not prov.ProvKind.ENTITY:
                actions[n.id] = NodeAction(n.id, kind, n.type, "listed (provenance kept)", _ts())
            elif n.type in SUBJECT_ONLY_TYPES:
                actions[n.id] = NodeAction(n.id, kind, n.type, "objects deleted", _ts())
            elif n.type == "model":
                models.append(n)
            elif n.type == "group_average":
                aggregates.append(n)
            else:
                actions[n.id] = NodeAction(n.id, kind, n.type, "marked stale", _ts())
        for n in aggregates + [
            x for x in desc.values() if x.id in actions and actions[x.id].action == "marked stale"
        ]:
            if n.id not in done:
                s.add(
                    m.ArtifactStatus(
                        tenant_id=uuid.UUID(tid),
                        node_id=n.id,
                        status="stale",
                        deletion_job_id=deletion_id,
                    )
                )
        flag_models(s, tid, [n.id for n in models], deletion_id, block)
        for n in models:
            actions[n.id] = NodeAction(
                n.id,
                n.kind.value,
                n.type,
                "flagged retrain_required" + ("; deployments blocked" if block else ""),
                _ts(),
            )
        # AppSec M3: uploaded-weights versions registered before the withdrawal, whatever they
        # declared; deployments always blocked (the tenant policy assumes a verified lineage)
        lineage_models = {n.id for n in models}
        upload_nodes = [n for n in upload_version_nodes(s, requested_at) if n not in lineage_models]
        flag_models(s, tid, upload_nodes, deletion_id, True)
        for nid in upload_nodes:
            actions[nid] = NodeAction(
                nid,
                "entity",
                "model",
                f"flagged retrain_required ({UPLOAD_TAINT_REASON}); deployments blocked",
                _ts(),
            )
        run_arts = (
            list(s.scalars(select(m.RunArtifact).where(m.RunArtifact.run_id.in_(run_ids))))
            if run_ids
            else []
        )
        art_keys = [(a.bucket, a.object_key) for a in run_arts]
        exports = [
            {
                "export_id": str(e.id),
                "destination": e.destination,
                "exported_at": e.exported_at.isoformat(),
                "action": "cannot be recalled; listed for the customer's follow-up",
            }
            for e in s.scalars(
                select(m.DataExport)
                .where(
                    (sid == any_(m.DataExport.subject_ids))
                    | m.DataExport.node_ids.overlap(list(desc) or [uuid.uuid4()])
                )
                .order_by(m.DataExport.exported_at, m.DataExport.id)
            )
        ]
    _audit(tid, str(sid), "started", count=len(desc), policy=agg_policy)

    # ---- phase 2: delete the subject's objects (idempotent)
    deleted: dict[str, int] = {"raw": 0, "zarr": 0, "artifacts": 0, "models": 0}
    for bucket in ("raw", "zarr"):
        for key in list(storage.objects.list(bucket, f"t/{tid}/s/{sid}/")):
            deleted[bucket] += _delete(storage, bucket, key)
    for bucket, key in art_keys:
        deleted[bucket] += _delete(storage, bucket, key)
    for rid in run_ids:  # staging leftovers of dead attempts
        for key in list(storage.objects.list("artifacts", f"t/{tid}/runs/{rid}/")):
            deleted["artifacts"] += _delete(storage, "artifacts", key)
    _audit(tid, str(sid), "objects_deleted", count=sum(deleted.values()))

    # ---- phase 3: aggregates -> re-run without the subject, or tombstone
    with tenant_session(svc, engine=engine) as s:
        for n in aggregates:
            st = s.get(m.ArtifactStatus, (uuid.UUID(tid), n.id))
            if st is not None and st.status in ("superseded", "tombstoned"):
                actions[n.id] = NodeAction(
                    n.id, "entity", n.type, f"{st.status} (earlier)", _ts(), st.replaced_by
                )
                continue
            row = s.scalar(select(m.DerivedObject).where(m.DerivedObject.node_id == n.id))
            new_node = None
            how = "tombstoned"
            if agg_policy == "rerun" and row is not None:
                keep = [i for i in row.input_node_ids if i not in desc]
                if keep:
                    try:
                        with s.begin_nested():
                            new = derived.create_group_average(
                                s,
                                storage,
                                svc,
                                keep,
                                extra={"revision_of": str(n.id), "deletion_job": str(deletion_id)},
                            )
                        new_node = new.node_id
                        how = "superseded"
                    except (policy.PolicyDenied, derived.DerivedError) as e:
                        log.warning(
                            "aggregate re-run refused; tombstoning",
                            extra={"reason": type(e).__name__},
                        )
            if row is not None:
                _delete(storage, row.bucket, row.object_key)
                deleted[row.bucket] += 1
                derived.shred(s, row)
                _worm_put(
                    storage,
                    f"shred-ledger/{tid}/derived-{row.id}.json",
                    {
                        "schema": "nf.shred-ledger/v1",
                        "tenant": tid,
                        "derived_object": str(row.id),
                        "deletion_job": str(deletion_id),
                        "at": _ts(),
                    },
                )
            st = st or m.ArtifactStatus(tenant_id=uuid.UUID(tid), node_id=n.id)
            st.status, st.replaced_by, st.deletion_job_id = how, new_node, deletion_id
            st.updated_at = datetime.now(UTC)
            s.merge(st)
            actions[n.id] = NodeAction(
                n.id,
                "entity",
                n.type,
                "marked stale; re-run without the subject; object deleted, key destroyed"
                if how == "superseded"
                else "marked stale; tombstoned; object deleted, key destroyed",
                _ts(),
                new_node,
            )
        for nid, a in actions.items():
            if (
                a.kind == "entity"
                and a.action == "objects deleted"
                and s.get(m.ArtifactStatus, (uuid.UUID(tid), nid)) is None
            ):
                s.add(
                    m.ArtifactStatus(
                        tenant_id=uuid.UUID(tid),
                        node_id=nid,
                        status="deleted",
                        deletion_job_id=deletion_id,
                    )
                )
    _audit(tid, str(sid), "aggregates", count=len(aggregates), policy=agg_policy)
    if models or upload_nodes:
        _audit(tid, str(sid), "models_flagged", count=len(models) + len(upload_nodes))

    # ---- phase 4: crypto-shred (SEC-034, SEC-034a) + WORM shred ledger (SEC-124)
    dek_count = storage.keyring.shred_subject(tid, str(sid))
    shredded_at = datetime.now(UTC)
    _worm_put(
        storage,
        f"shred-ledger/{tid}/subject-{sid}.json",
        {
            "schema": "nf.shred-ledger/v1",
            "tenant": tid,
            "subject": str(sid),
            "deletion_job": str(deletion_id),
            "at": _ts(),
        },
    )
    _audit(tid, str(sid), "key_shredded", count=dek_count)

    # ---- phase 5: certificate
    finished = datetime.now(UTC)
    duration = time.perf_counter() - t0
    window = backup_window_days()
    retention = retention_statement(shredded_at, window)
    doc = {
        "schema": certificate.SCHEMA,
        "certificate_id": str(deletion_id),
        "tenant": tid,
        "subject_pseudonym": pseudonym,
        "requested_at": requested_at.isoformat(),
        "started_at": started_at.isoformat(),
        "completed_at": finished.isoformat(),
        "duration_s": round(duration, 3),
        "target_s": TARGET_S,
        "aggregate_policy": agg_policy,
        "nodes": [a.out() for a in sorted(actions.values(), key=lambda a: str(a.node_id))],
        "objects_deleted": deleted,
        "models_flagged": sorted([str(n.id) for n in models] + [str(n) for n in upload_nodes]),
        "external_exports": exports,
        "key_destruction": {
            "method": "crypto-shred (subject data keys destroyed; subject tombstoned)",
            "dek_versions_destroyed": dek_count,
            "at": shredded_at.isoformat(),
            "db_backup_window_days": window,
            "unrecoverable_in_all_copies_after": (shredded_at + timedelta(days=window)).isoformat(),
            "restore_rule": "a restore re-applies the shred ledger before serving (SEC-124)",
            "statement": retention,
        },
        "statement": (
            "Objects of the subject are deleted and its data keys destroyed; aggregates are "
            "re-run without the subject or tombstoned as listed; models are flagged for "
            "retraining. No certified unlearning is claimed. " + retention
        ),
    }
    signed = certificate.sign(doc)
    with tenant_session(svc, engine=engine) as s:
        dj = s.scalar(select(m.DeletionJob).where(m.DeletionJob.id == deletion_id))
        dj.state = "succeeded"
        dj.finished_at = finished
        dj.duration_s = duration
        dj.certificate = signed
    _worm_put(storage, f"deletion-certificates/{tid}/{deletion_id}.json", signed)
    _audit(tid, str(sid), "completed", count=len(actions), duration_s=round(duration, 3))
    return signed


def mark_failed(engine: Engine | None, tenant_id: str, deletion_id: uuid.UUID, error: str) -> None:
    svc = service_principal(str(tenant_id), SERVICE_ID)
    with tenant_session(svc, engine=engine) as s:
        dj = s.scalar(select(m.DeletionJob).where(m.DeletionJob.id == deletion_id))
        if dj is not None and dj.state != "succeeded":
            dj.state = "failed"
            dj.error = error[:500]


def reapply_shreds(storage: Storage, engine: Engine | None, tenant_ids: Iterable[str]) -> int:
    """SEC-124: after a database restore, re-apply every shred recorded in the WORM shred ledger
    (subject keys and derived-object keys) before the platform serves data. Returns the number of
    ledger entries applied."""
    n = 0
    for tid in tenant_ids:
        for key in list(storage.objects.list(AUDIT_BUCKET, f"shred-ledger/{tid}/")):
            doc = cj.parse(storage.objects.get(AUDIT_BUCKET, key).decode("utf-8"))
            if doc.get("subject"):
                storage.keyring.shred_subject(str(tid), str(doc["subject"]))
            elif doc.get("derived_object"):
                with tenant_session(service_principal(str(tid), SERVICE_ID), engine=engine) as s:
                    row = s.scalar(
                        select(m.DerivedObject).where(
                            m.DerivedObject.id == uuid.UUID(doc["derived_object"])
                        )
                    )
                    if row is not None and row.key_state != "shredded":
                        derived.shred(s, row)
            n += 1
    return n
