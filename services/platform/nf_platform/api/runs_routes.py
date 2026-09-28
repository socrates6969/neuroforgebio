"""v1 run endpoints (BUILD-GUIDE 3.3; BLUEPRINT §3.5, §4.4).

``POST /v1/runs`` queues a run of a published PipelineVersion (``name@semver`` or ``pv:sha256:``
ID, resolved in the caller's tenant) on one recording; ``GET /v1/runs/{id}`` returns its state, run
record and the artifacts whose provenance is committed (staged outputs are never listed);
``POST /v1/runs/{id}/cancel`` cancels it. Every route authorizes, audits and is tenant-scoped (RLS +
app filter); another tenant's run or recording is a 404.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import NotFound, problem
from nf_platform.api.routes import enforce, enforce_placement, recording_resource
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.jobs import queue, runs
from nf_platform.limits import quotas

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]


def _route(method: str, path: str, action: str, **kw: Any):
    def deco(fn):
        router.add_api_route(
            path,
            fn,
            methods=[method],
            openapi_extra=action_extra(action),
            dependencies=[Depends(guard)],
            **kw,
        )
        return fn

    return deco


class RunIn(BaseModel):
    pipeline: str = Field(
        min_length=1, max_length=300, description="name@semver or pv:sha256:<64 hex>"
    )
    recording_id: uuid.UUID


class ArtifactOut(BaseModel):
    id: uuid.UUID
    step: str
    name: str
    sha256: str
    size_bytes: int
    visible_at: datetime


class RunOut(BaseModel):
    id: uuid.UUID
    pipeline_ref: str
    pipeline_version_id: str
    recording_id: uuid.UUID
    state: str
    seed: int | None
    attempt: int
    error: str | None
    cancel_requested: bool = False
    record: dict[str, Any]
    prov_activity_id: uuid.UUID | None
    prov_batch_id: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    artifacts: list[ArtifactOut] = []


def _out(s, run) -> RunOut:
    job = queue.state_of(s, run.job_id) if run.job_id else None
    return RunOut(
        id=run.id,
        pipeline_ref=run.pipeline_ref,
        pipeline_version_id=run.pipeline_version_id,
        recording_id=run.recording_id,
        state=run.state,
        seed=run.seed,
        attempt=run.attempt,
        error=run.error,
        cancel_requested=bool(job and job["cancel_requested"]),
        record=run.record,
        prov_activity_id=run.prov_activity_id,
        prov_batch_id=run.prov_batch_id,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        artifacts=[
            ArtifactOut(
                id=a.id,
                step=a.step,
                name=a.name,
                sha256=a.sha256,
                size_bytes=a.size_bytes,
                visible_at=a.visible_at,
            )
            for a in runs.visible_artifacts(s, run.id)
        ],
    )


def _error(request: Request, e: runs.RunError) -> JSONResponse:
    titles = {404: "Not Found", 409: "Conflict", 422: "Unprocessable Content"}
    return problem(request, e.status, titles.get(e.status, "Error"), e.detail, kind=e.code)


@_route("POST", "/runs", "run:create", status_code=202, response_model=RunOut)
def create_run(body: RunIn, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            rec = s.scalar(select(m.Recording).where(m.Recording.id == body.recording_id))
            if rec is not None and rec.state != "quarantined":  # else runs: 404 / 409
                # 5.4: RBAC + consent `processing` + classification, before anything is queued
                enforce(ctx, "run:create", recording_resource(ctx, rec), s)
            # 5.7: PHI tenants only on BAA-listed compute + storage + database
            enforce_placement(ctx, s, request.app.state.settings.placement)
            run = runs.create_run(s, ctx.principal, body.pipeline, body.recording_id)
            # 4.8 active-run quota: 429 quota-exceeded, and this transaction rolls back
            quotas.check_active_runs(s, run.tenant_id, request.app.state.settings)
            out = _out(s, run)
    except runs.RunError as e:
        return _error(request, e)
    ctx.audit(audit.DATA_CREATE, resource_type="run", resource_id=out.id, status=out.state)
    return out


def _load(s, run_id: uuid.UUID, ctx: Ctx):
    run = runs.get_run(s, run_id)
    if run is None:
        raise NotFound("run")
    ctx.check_tenant(run)
    return run


class RunSummaryOut(BaseModel):
    """One row of ``GET /v1/runs`` (no run record, no artifacts: open the run for those)."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pipeline_ref: str
    pipeline_version_id: str
    recording_id: uuid.UUID
    state: str
    attempt: int
    error: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


RunState = Literal["queued", "running", "succeeded", "failed", "cancelled"]


@_route("GET", "/runs", "run:read", response_model=list[RunSummaryOut])
def list_runs(
    ctx: CtxDep,
    state: RunState | None = None,
    recording_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Runs of the caller's tenant, newest first (M3 open issue 5)."""
    with ctx.session() as s:
        q = select(m.Run)
        if state is not None:
            q = q.where(m.Run.state == state)
        if recording_id is not None:
            q = q.where(m.Run.recording_id == recording_id)
        q = q.order_by(m.Run.created_at.desc(), m.Run.id).limit(limit).offset(offset)
        rows = [RunSummaryOut.model_validate(r) for r in s.scalars(q)]
    ctx.audit(audit.DATA_READ, resource_type="run", count=len(rows))
    return rows


@_route("GET", "/runs/{run_id}", "run:read", response_model=RunOut)
def get_run(run_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        out = _out(s, _load(s, run_id, ctx))
    ctx.audit(audit.DATA_READ, resource_type="run", resource_id=run_id)
    return out


@_route("POST", "/runs/{run_id}/cancel", "run:cancel", status_code=202, response_model=RunOut)
def cancel_run(run_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        run = _load(s, run_id, ctx)
        runs.cancel_run(s, run)
        s.flush()
        out = _out(s, run)
    ctx.audit(audit.ADMIN_ACTION, resource_type="run", resource_id=run_id, status=out.state)
    return out
