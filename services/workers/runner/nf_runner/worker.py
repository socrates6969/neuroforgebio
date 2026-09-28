"""The worker process (BUILD-GUIDE 3.3): claim jobs from the Postgres queue and run them.

One loop iteration (:meth:`Worker.run_once`):

1. ``reap`` (worker session): attempts whose lease expired -- their worker died -- or that ran past
   their timeout are re-queued with backoff (or failed/cancelled); runs of jobs that ended are
   aligned in their tenant;
2. ``claim`` the next due job (``FOR UPDATE SKIP LOCKED``) with a fresh lease token;
3. run it while a heartbeat thread extends the lease; the thread also notices a cancel request, a
   timeout or a lost lease, and the job stops at the next step boundary (subprocess steps are
   killed at once);
4. map the outcome onto the queue: complete / fail (retryable or not) / ack cancel / nothing (the
   lease was lost: another worker owns the job now, so this one touches nothing).

Job kinds: ``pipeline.run`` (:mod:`nf_runner.pipeline_job`), ``ingest.upload`` (M2's upload
conversion, formerly driven by ``process_pending``), and the SEC-043 job bodies
``provenance.anchor`` (daily) / ``provenance.verify`` (hourly) per tenant, and the M5 compliance
jobs ``governance.deletion`` (5.5 DeletionJob), ``consent.anchor`` / ``consent.verify`` (5.3), the
audit chain jobs ``audit.batch`` / ``audit.verify`` (SEC-105, AppSec M1), and
the M6 ``registry.retrain`` (6.3: retrain a tainted model version without the withdrawn subjects).
Workers import ``nf_platform`` but never its API layer (``services/workers/.importlinter``).
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nf_platform.audit import log as audit
from nf_platform.db.context import tenant_session
from nf_platform.jobs import queue, runs
from nf_platform.storage.runtime import Storage, service_principal
from sqlalchemy import Engine, text

from nf_runner import pipeline_job
from nf_runner.steprunner import InProcessRunner, StepFailed, StepRunner, StepStopped

log = logging.getLogger(__name__)
PROV_ANCHOR_KIND = "provenance.anchor"
PROV_VERIFY_KIND = "provenance.verify"
GOVERNANCE_KINDS = (
    "governance.deletion",
    "consent.anchor",
    "consent.verify",
    "audit.batch",  # AppSec M1 (SEC-105): hourly audit batches + signed head anchors
    "audit.verify",  # daily audit-chain verification (alert audit_chain_mismatch)
)
REGISTRY_RETRAIN_KIND = "registry.retrain"  # M6 6.3 (m6-registry)
DEFAULT_KINDS = (
    runs.RUN_JOB_KIND,
    runs.INGEST_JOB_KIND,
    PROV_ANCHOR_KIND,
    PROV_VERIFY_KIND,
    *GOVERNANCE_KINDS,
    REGISTRY_RETRAIN_KIND,
)


class Stop(StepStopped):
    def __init__(self, beat: queue.Beat) -> None:
        super().__init__(beat.value)
        self.beat = beat


class Lease:
    """Heartbeats for one claimed job on a background thread (own DB connection)."""

    def __init__(self, engine: Engine, job: queue.Job, lease_s: float, every_s: float) -> None:
        self.engine, self.job, self.lease_s, self.every_s = engine, job, lease_s, every_s
        self.status = queue.Beat.OK
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name=f"lease-{job.id}", daemon=True)

    def __enter__(self) -> Lease:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self.every_s + 5)

    def beat(self) -> queue.Beat:
        with queue.worker_session(self.engine) as s:
            self.status = queue.heartbeat(
                s, self.job.id, self.job.lease_token, lease_s=self.lease_s
            )
        return self.status

    def _loop(self) -> None:
        while not self._stop.wait(self.every_s):
            try:
                if self.beat() is not queue.Beat.OK:
                    return
            except Exception:  # noqa: BLE001 - a DB hiccup: try again next tick (lease still valid)
                log.warning("heartbeat failed", extra={"job_id": str(self.job.id)})

    def should_stop(self) -> bool:
        return self.status is not queue.Beat.OK

    def raise_stop(self) -> None:
        raise Stop(self.status)


Handler = Callable[["Worker", queue.Job, Lease], None]


def _ingest_upload(worker: Worker, job: queue.Job, lease: Lease) -> None:
    """M2 upload conversion as a queued job (one job per upload, dedupe key = upload id)."""
    from nf_platform.ingest.uploads.worker import process_upload  # noqa: PLC0415

    upload_id = str(job.payload["upload_id"])
    svc = service_principal(job.tenant_id, "svc:ingest-worker")
    if job.attempts > 1:  # a previous attempt died mid-conversion: make the upload claimable again
        with tenant_session(svc, engine=worker.engine) as s:
            s.execute(
                text("UPDATE upload SET state = 'uploaded' WHERE id = :u AND state = 'processing'"),
                {"u": upload_id},
            )
    ids = process_upload(
        worker.storage, job.tenant_id, upload_id, engine=worker.engine, policy=worker.consent_policy
    )
    with queue.worker_session(worker.engine) as s:
        queue.complete(s, job.id, job.lease_token, {"recording_ids": ids})


def _prov_anchor(worker: Worker, job: queue.Job, lease: Lease) -> None:
    """SEC-043: anchor the tenant's provenance chain head in the WORM ``audit`` bucket (daily)."""
    from nf_platform.provenance import integrity  # noqa: PLC0415

    heads = integrity.anchor_heads(worker.engine, worker.storage.objects, [job.tenant_id])
    with queue.worker_session(worker.engine) as s:
        queue.complete(s, job.id, job.lease_token, {"head": heads.get(job.tenant_id)})


def _prov_verify(worker: Worker, job: queue.Job, lease: Lease) -> None:
    """SEC-043: verify the tenant's chain against its latest anchor (hourly). A mismatch fails the
    job without retry (``verify_tenants`` also logs the alert)."""
    from nf_platform.provenance import integrity  # noqa: PLC0415

    (res,) = integrity.verify_tenants(worker.engine, worker.storage.objects, [job.tenant_id])
    if not res.ok:
        raise StepFailed(f"{integrity.ALERT}: {'; '.join(res.errors)[:500]}", retryable=False)
    with queue.worker_session(worker.engine) as s:
        queue.complete(s, job.id, job.lease_token, {"head": res.head, "batches": res.batches})


def _governance(worker: Worker, job: queue.Job, lease: Lease) -> None:
    """M5 compliance jobs (m5-ledger): DeletionJob, consent-chain anchor and verification."""
    from nf_platform.governance import jobs as gjobs  # noqa: PLC0415

    try:
        result = gjobs.run(
            job.kind,
            worker.engine,
            worker.storage,
            job.tenant_id,
            job.payload,
            last_attempt=job.attempts >= job.max_attempts,
        )
    except gjobs.JobFailed as e:
        raise StepFailed(str(e), retryable=e.retryable) from e
    with queue.worker_session(worker.engine) as s:
        queue.complete(s, job.id, job.lease_token, result)


def _registry_retrain(worker: Worker, job: queue.Job, lease: Lease) -> None:
    """M6 6.3 (m6-registry): retrain a tainted model version without the withdrawn subjects."""
    from nf_platform.registry import retrain  # noqa: PLC0415

    try:
        result = retrain.execute(
            worker.engine, worker.storage, job.tenant_id, uuid.UUID(str(job.payload["retrain_id"]))
        )
    except retrain.RetrainError as e:
        raise StepFailed(str(e), retryable=False) from e
    with queue.worker_session(worker.engine) as s:
        queue.complete(s, job.id, job.lease_token, result)


def integrity_dedupe_key(kind: str, now) -> str:
    """One anchor per tenant and UTC day, one verification per tenant and UTC hour: a scheduler
    (cron, not built) may enqueue as often as it likes; the queue's dedupe key keeps one job."""
    return f"{now:%Y-%m-%d}" if kind == PROV_ANCHOR_KIND else f"{now:%Y-%m-%dT%H}"


@dataclass
class Worker:
    engine: Engine
    storage: Storage
    runner: StepRunner = field(default_factory=InProcessRunner)
    kinds: tuple[str, ...] = DEFAULT_KINDS
    worker_id: str = field(
        default_factory=lambda: f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
    )
    lease_s: float = queue.DEFAULT_LEASE_S
    heartbeat_s: float = 10.0
    workdir: str | Path | None = None
    extra_libraries: tuple[str, ...] = ()
    consent_policy: Any = None
    handlers: dict[str, Handler] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.handlers = {
            runs.RUN_JOB_KIND: pipeline_job.execute,
            runs.INGEST_JOB_KIND: _ingest_upload,
            PROV_ANCHOR_KIND: _prov_anchor,
            PROV_VERIFY_KIND: _prov_verify,
            **dict.fromkeys(GOVERNANCE_KINDS, _governance),
            REGISTRY_RETRAIN_KIND: _registry_retrain,
            **self.handlers,
        }

    # -------------------------------------------------------------- loop
    def reap(self) -> list[queue.Settled]:
        with queue.worker_session(self.engine) as s:
            settled = queue.reap(s)
        for j in settled:
            if j.kind == runs.RUN_JOB_KIND and j.state in ("failed", "cancelled", "queued"):
                svc = service_principal(j.tenant_id, pipeline_job.WORKER_PRINCIPAL)
                with tenant_session(svc, engine=self.engine) as s:
                    runs.sync_after_reap(s, uuid.UUID(j.payload["run_id"]))
        return settled

    def claim(self) -> queue.Job | None:
        with queue.worker_session(self.engine) as s:
            return queue.claim(s, self.worker_id, self.kinds, lease_s=self.lease_s)

    def run_once(self) -> queue.Job | None:
        """Reap, claim one job, run it. Returns the job (None when nothing was due)."""
        self.reap()
        job = self.claim()
        if job is not None:
            self.handle(job)
        return job

    def run_forever(self, *, idle_s: float = 1.0, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        while not stop.is_set():
            if self.run_once() is None:
                stop.wait(idle_s)

    # -------------------------------------------------------------- one job
    def handle(self, job: queue.Job) -> None:
        handler = self.handlers.get(job.kind)
        if handler is None:
            self._fail(job, f"no handler for job kind {job.kind!r}", retryable=False)
            return
        try:
            with Lease(self.engine, job, self.lease_s, self.heartbeat_s) as lease:
                handler(self, job, lease)
            self._audit(job, "success")
        except queue.LeaseLost:
            log.warning("lease lost; leaving the job to its new owner", extra={"job": str(job.id)})
        except queue.JobCancelled:
            self._cancelled(job)
        except Stop as e:
            if e.beat is queue.Beat.CANCELLED:
                self._cancelled(job)
            elif e.beat is queue.Beat.TIMED_OUT:
                self._fail(job, "timed out", retryable=True)
            # LOST: touch nothing
        except StepStopped:
            beat = self._current_beat(job)
            if beat is queue.Beat.CANCELLED:
                self._cancelled(job)
            elif beat is queue.Beat.TIMED_OUT:
                self._fail(job, "timed out", retryable=True)
        except StepFailed as e:
            self._fail(job, str(e), retryable=e.retryable)
        except runs.RunError as e:
            self._fail(job, e.detail, retryable=False)
        except Exception as e:  # noqa: BLE001 - any other failure is a retryable attempt failure
            log.exception("job attempt failed", extra={"job": str(job.id)})
            self._fail(job, f"{type(e).__name__}: {e}", retryable=True)

    def _current_beat(self, job: queue.Job) -> queue.Beat:
        with queue.worker_session(self.engine) as s:
            return queue.heartbeat(s, job.id, job.lease_token, lease_s=self.lease_s)

    def _fail(self, job: queue.Job, error: str, *, retryable: bool) -> None:
        try:
            if job.kind == runs.RUN_JOB_KIND:
                svc = service_principal(job.tenant_id, pipeline_job.WORKER_PRINCIPAL)
                with tenant_session(svc, engine=self.engine) as s:
                    runs.fail_attempt(
                        s, uuid.UUID(job.payload["run_id"]), job, error, retryable=retryable
                    )
            else:
                with queue.worker_session(self.engine) as s:
                    queue.fail(s, job.id, job.lease_token, error, retryable=retryable)
        except queue.LeaseLost:
            return
        self._audit(job, "failure", reason=error[:200])

    def _cancelled(self, job: queue.Job) -> None:
        try:
            if job.kind == runs.RUN_JOB_KIND:
                svc = service_principal(job.tenant_id, pipeline_job.WORKER_PRINCIPAL)
                with tenant_session(svc, engine=self.engine) as s:
                    runs.cancel_attempt(s, uuid.UUID(job.payload["run_id"]), job)
            else:
                with queue.worker_session(self.engine) as s:
                    queue.ack_cancel(s, job.id, job.lease_token)
        except queue.LeaseLost:
            return
        self._audit(job, "failure", reason="cancelled")

    def _audit(self, job: queue.Job, outcome: audit.Outcome, **details: Any) -> None:
        run_id = job.payload.get("run_id")
        try:
            audit.emit(
                audit.AuditEvent(
                    type=audit.DATA_CREATE,
                    outcome=outcome,
                    action=f"job:{job.kind}",
                    tenant_id=job.tenant_id,
                    actor_kind="service",
                    actor_id=self.worker_id,
                    auth_method="service",
                    resource_type="run" if run_id else "job",
                    resource_id=str(run_id or job.id),
                    # allow-listed detail keys only (audit.log.DETAIL_KEYS)
                    details={"count": job.attempts, **details},
                )
            )
        except Exception:  # noqa: BLE001 - audit sink not configured in a bare worker: log only
            log.warning("audit emit failed", extra={"job": str(job.id)})
