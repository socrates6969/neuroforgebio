"""Pipeline runs: creation (API side) and the run lifecycle the worker drives (BUILD-GUIDE 3.3).

Lifecycle of one attempt (the worker holds the job lease ``token`` throughout):

1. :func:`start_attempt` -- run ``running``; staged outputs of earlier (dead) attempts are removed
   (rows here, objects by the worker), so a retry starts clean.
2. The worker runs the steps and writes every output, encrypted, under the attempt's staging prefix
   (``t/<tenant>/runs/<run>/<token>/<step>/<name>`` in the ``artifacts`` bucket) and
   :func:`stage_artifact` records it with ``visible_at`` NULL.
3. :func:`finalize` -- ONE transaction: fence on the lease (:func:`queue.lock_lease`), write the
   provenance (run activity used the recording, was associated with the PipelineVersion, generated
   each artifact) with ``provenance.record``, THEN set ``visible_at`` on this attempt's artifacts,
   mark the run ``succeeded`` and complete the job. If the provenance commit fails, nothing of this
   becomes visible (BLUEPRINT §3.5: provenance is a precondition, not a best-effort log).

``UNIQUE (run_id, step, name)`` on ``run_artifact`` plus the lease fencing mean a run never ends up
with duplicate outputs, even when a worker dies mid-run and another one retries it.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from nf_platform.db import models as m
from nf_platform.db.context import Principal
from nf_platform.jobs import queue
from nf_platform.pipelines import spec as pipelines
from nf_platform.provenance import api as prov

RUN_JOB_KIND = "pipeline.run"
INGEST_JOB_KIND = "ingest.upload"
RUN_RECORD_SCHEMA = "nf.run-record/v1"
ARTIFACT_BUCKET = "artifacts"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class RunError(Exception):
    """The run cannot be created or changed (mapped to 404/409/422 by the API)."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class RunInput:
    recording_id: str
    subject_id: str
    zarr_ref: str
    ch_types: list[str]


def _now() -> datetime:
    return datetime.now(UTC)


def artifact_prefix(tenant_id: str, run_id: uuid.UUID | str, token: uuid.UUID | str) -> str:
    return f"t/{tenant_id}/runs/{run_id}/{token}"


def artifact_key(
    tenant_id: str, run_id: uuid.UUID | str, token: uuid.UUID | str, step: str, name: str
) -> str:
    if not (_NAME_RE.match(step) and _NAME_RE.match(name)):
        raise RunError(422, "invalid-artifact", "bad step or artifact name")
    return f"{artifact_prefix(tenant_id, run_id, token)}/{step}/{name}"


# ---------------------------------------------------------------- API side
def create_run(
    session: Session,
    principal: Principal,
    pipeline_ref: str,
    recording_id: uuid.UUID,
    *,
    max_attempts: int = 3,
    timeout_s: int = queue.DEFAULT_TIMEOUT_S,
) -> m.Run:
    """Resolve the pipeline (tenant's published versions), check the input recording, write the
    run with its run record and queue its job -- one transaction (the caller's session)."""
    try:
        pv = pipelines.resolve(session, pipeline_ref)
    except pipelines.PipelineNotFound as e:
        raise RunError(404, "not-found", "pipeline not found") from e
    except pipelines.PipelineError as e:
        raise RunError(422, "invalid-pipeline-ref", str(e)) from e
    rec = session.scalar(select(m.Recording).where(m.Recording.id == recording_id))
    if rec is None:
        raise RunError(404, "not-found", "recording not found")
    if rec.state == "quarantined":
        raise RunError(409, "quarantined", "recording is quarantined until consent allows use")
    if not rec.zarr_ref:
        raise RunError(409, "no-signal", "recording has no stored signal")
    doc = pv.document
    run_id = uuid.uuid4()
    record = {
        "schema": RUN_RECORD_SCHEMA,
        "pipeline": {"ref": pv.ref, "id": pv.pv_id},
        "input": {"recording_id": str(rec.id), "zarr_ref": rec.zarr_ref},
        "seed": doc["seed"],
        # every parameter explicit, defaults included (the published document carries them all;
        # the worker re-resolves them against the step library and refuses any difference)
        "steps": doc["steps"],
    }
    run = m.Run(
        id=run_id,
        tenant_id=uuid.UUID(principal.tenant_id),
        pipeline_version_id=pv.pv_id,
        pipeline_ref=pv.ref,
        recording_id=rec.id,
        state="queued",
        seed=int(doc["seed"]),
        record=record,
        created_by=principal.id,
    )
    job_id = queue.enqueue(
        session,
        RUN_JOB_KIND,
        {"run_id": str(run_id)},
        max_attempts=max_attempts,
        timeout_s=timeout_s,
        dedupe_key=str(run_id),
        created_by=principal.id,
    )
    run.job_id = job_id
    session.add(run)
    session.flush()
    return run


def get_run(session: Session, run_id: uuid.UUID) -> m.Run | None:
    return session.scalar(select(m.Run).where(m.Run.id == run_id))


def visible_artifacts(session: Session, run_id: uuid.UUID) -> list[m.RunArtifact]:
    """Only artifacts whose provenance is committed (``visible_at`` set)."""
    return list(
        session.scalars(
            select(m.RunArtifact)
            .where(m.RunArtifact.run_id == run_id, m.RunArtifact.visible_at.is_not(None))
            .order_by(m.RunArtifact.created_at, m.RunArtifact.step, m.RunArtifact.name)
        )
    )


def _finished(session: Session, run: m.Run) -> None:
    """A run reached a terminal state: queue its ``run.finished`` webhooks (4.6) in the same
    transaction, so an event is sent if and only if the state change commits."""
    from nf_platform.webhooks import service as webhooks

    session.flush()
    webhooks.run_finished(session, run)


def cancel_run(session: Session, run: m.Run) -> str:
    """Cancel the run's job. Returns the run state afterwards (``cancelled`` at once when the job
    was still queued; a running run stops at the worker's next heartbeat)."""
    if run.state in queue.TERMINAL:
        return run.state
    job_state = queue.cancel(session, run.job_id) if run.job_id else "cancelled"
    if job_state == "cancelled":
        run.state = "cancelled"
        run.finished_at = _now()
        _finished(session, run)
    return run.state


# ---------------------------------------------------------------- worker side
def run_input(session: Session, run: m.Run) -> RunInput:
    rec = session.scalar(select(m.Recording).where(m.Recording.id == run.recording_id))
    if rec is None or not rec.zarr_ref:
        raise RunError(409, "no-signal", "recording has no stored signal")
    if rec.state == "quarantined":
        raise RunError(409, "quarantined", "recording is quarantined")
    ses = session.scalar(select(m.Session_).where(m.Session_.id == rec.session_id))
    chans = session.scalars(
        select(m.Channel).where(m.Channel.recording_id == rec.id).order_by(m.Channel.index)
    ).all()
    return RunInput(
        recording_id=str(rec.id),
        subject_id=str(ses.subject_id),
        zarr_ref=rec.zarr_ref,
        ch_types=[c.modality.lower() for c in chans],
    )


def start_attempt(session: Session, run_id: uuid.UUID, job: queue.Job) -> tuple[m.Run, list[str]]:
    """Mark the run running for this attempt; drop staged outputs of earlier attempts. Returns the
    run and the object keys the worker must delete (the dead attempts' staging objects)."""
    queue.lock_lease(session, job.id, job.lease_token)
    run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
    if run is None:
        raise RunError(404, "not-found", "run not found")
    stale = session.scalars(
        select(m.RunArtifact).where(
            m.RunArtifact.run_id == run_id,
            m.RunArtifact.visible_at.is_(None),
            m.RunArtifact.attempt_token != job.lease_token,
        )
    ).all()
    keys = [a.object_key for a in stale]
    if stale:
        session.execute(delete(m.RunArtifact).where(m.RunArtifact.id.in_([a.id for a in stale])))
    run.state = "running"
    run.attempt = job.attempts
    run.error = None
    run.started_at = run.started_at or _now()
    return run, keys


def stage_artifact(
    session: Session,
    run_id: uuid.UUID,
    job: queue.Job,
    *,
    step: str,
    name: str,
    object_key: str,
    sha256: str,
    size_bytes: int,
) -> uuid.UUID:
    """Record one staged (invisible) output of this attempt (after its object was written)."""
    queue.lock_lease(session, job.id, job.lease_token)
    aid = uuid.uuid4()
    session.add(
        m.RunArtifact(
            id=aid,
            tenant_id=uuid.UUID(job.tenant_id),
            run_id=run_id,
            step=step,
            name=name,
            bucket=ARTIFACT_BUCKET,
            object_key=object_key,
            sha256=sha256,
            size_bytes=size_bytes,
            attempt_token=job.lease_token,
        )
    )
    session.flush()
    return aid


def finalize(
    session: Session,
    principal: Principal,
    run_id: uuid.UUID,
    job: queue.Job,
    execution: dict[str, Any],
) -> prov.ProvCommit:
    """Provenance, then visibility, then state -- all in the caller's single transaction."""
    queue.lock_lease(session, job.id, job.lease_token)
    run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
    if run is None:
        raise RunError(404, "not-found", "run not found")
    arts = session.scalars(
        select(m.RunArtifact)
        .where(m.RunArtifact.run_id == run_id, m.RunArtifact.attempt_token == job.lease_token)
        .order_by(m.RunArtifact.step, m.RunArtifact.name)
    ).all()
    if not arts:
        raise RunError(409, "no-outputs", "the attempt staged no outputs")

    E, A, G = prov.ProvKind.ENTITY, prov.ProvKind.ACTIVITY, prov.ProvKind.AGENT
    rid = str(run.recording_id)
    nodes: list[prov.NodeSpec] = []
    rec_ref: prov.NodeRef | None = prov.find_node(session, E, "recording", rid)
    if rec_ref is None:
        rec_ref = len(nodes)
        nodes.append(prov.NodeSpec(E, "recording", rid, None, {}))
    pv_ref: prov.NodeRef | None = prov.find_node(
        session, G, "pipeline_version", run.pipeline_version_id
    )
    if pv_ref is None:
        pv_ref = len(nodes)
        nodes.append(
            prov.NodeSpec(G, "pipeline_version", run.pipeline_version_id, run.pipeline_version_id)
        )
    act = len(nodes)
    nodes.append(
        prov.NodeSpec(
            A,
            "run",
            str(run.id),
            None,
            {
                "pipeline_version_id": run.pipeline_version_id,
                "pipeline_ref": run.pipeline_ref,
                "seed": run.seed,
                "attempt": job.attempts,
            },
        )
    )
    edges: list[tuple[prov.NodeRef, prov.EdgeType, prov.NodeRef]] = [
        (act, prov.EdgeType.USED, rec_ref),
        (act, prov.EdgeType.WAS_ASSOCIATED_WITH, pv_ref),
    ]
    first_art = len(nodes)
    for a in arts:
        i = len(nodes)
        nodes.append(
            prov.NodeSpec(
                E,
                "artifact",
                str(a.id),
                f"blob:sha256:{a.sha256}",
                {"run_id": str(run.id), "step": a.step, "name": a.name, "size": a.size_bytes},
            )
        )
        edges.append((i, prov.EdgeType.WAS_GENERATED_BY, act))
        edges.append((i, prov.EdgeType.WAS_DERIVED_FROM, rec_ref))

    commit = prov.record(session, principal, nodes, edges)  # provenance FIRST

    now = _now()
    for k, a in enumerate(arts):
        session.execute(
            update(m.RunArtifact)
            .where(m.RunArtifact.id == a.id)
            .values(visible_at=now, prov_node_id=commit.node_ids[first_art + k])
        )
    run.state = "succeeded"
    run.finished_at = now
    run.prov_activity_id = commit.node_ids[act]
    run.prov_batch_id = commit.batch_id
    run.record = {**run.record, "execution": execution}
    queue.complete(
        session,
        job.id,
        job.lease_token,
        {"run_id": str(run.id), "artifacts": len(arts), "prov_batch_id": commit.batch_id},
    )
    _finished(session, run)
    return commit


def fail_attempt(
    session: Session, run_id: uuid.UUID, job: queue.Job, error: str, *, retryable: bool
) -> str:
    """End the attempt as failed (job re-queued with backoff while attempts remain). Staged
    outputs stay invisible and are removed by the next attempt. Returns the job state."""
    state = queue.fail(session, job.id, job.lease_token, error, retryable=retryable)
    run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
    if run is not None:
        run.error = str(error)[: queue.MAX_ERROR_LEN]
        run.state = {"queued": "queued", "cancelled": "cancelled"}.get(state, "failed")
        if run.state != "queued":
            run.finished_at = _now()
            _finished(session, run)
    return state


def cancel_attempt(session: Session, run_id: uuid.UUID, job: queue.Job) -> None:
    queue.ack_cancel(session, job.id, job.lease_token)
    run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
    if run is not None:
        run.state = "cancelled"
        run.finished_at = _now()
        _finished(session, run)


def sync_after_reap(session: Session, run_id: uuid.UUID) -> None:
    """Align a run with its job after the reaper settled a dead attempt (worker side, tenant
    session): a job that ended failed/cancelled ends the run the same way."""
    run = session.scalar(select(m.Run).where(m.Run.id == run_id).with_for_update())
    if run is None or run.job_id is None or run.state in queue.TERMINAL:
        return
    st = queue.state_of(session, run.job_id)
    if st and st["state"] in ("failed", "cancelled"):
        run.state = st["state"]
        run.error = st["last_error"]
        run.finished_at = _now()
        _finished(session, run)
