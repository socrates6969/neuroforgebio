"""v1 sweep endpoints (BUILD-GUIDE 3.6; BLUEPRINT §3.5 multiverse runs).

``POST /v1/sweeps`` expands a parameter grid over a published PipelineVersion into one published
PipelineVersion per grid point and queues one run per (grid point, recording) on the 3.3 queue.
``GET /v1/sweeps/{id}`` returns the sweep, its variants and run IDs; ``GET /v1/sweeps/{id}/report``
returns how the chosen metric varies across the grid, every cell linked to its run ID and the
provenance node of the artifact that holds the number. Every route authorizes, audits and is
tenant-scoped (RLS + app filter); another tenant's sweep, pipeline or recording is a 404.
Response shapes: ``nf_platform.sweeps.service.sweep_summary`` and ``report``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import NotFound, problem
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.limits import quotas
from nf_platform.sweeps import service as sweeps

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


# ---------------------------------------------------------------- response shapes (OpenAPI)
class VariantOut(BaseModel):
    variant: int
    params: dict[str, Any] = Field(description='{"<step>.<param>": value}')
    pipeline_ref: str
    pipeline_version_id: str


class SweepOut(BaseModel):
    id: uuid.UUID
    name: str
    state: str = Field(description="queued | running | succeeded | partial | failed")
    run_states: dict[str, int]
    pipeline: str
    pipeline_version_id: str
    recording_ids: list[uuid.UUID]
    grid: dict[str, list[Any]]
    metric: sweeps.MetricSpec
    variants: list[VariantOut]
    run_ids: list[uuid.UUID]
    prov_node_id: uuid.UUID | None
    created_by: str
    created_at: datetime


class ArtifactRef(BaseModel):
    id: uuid.UUID
    step: str
    name: str
    sha256: str


class CellOut(VariantOut):
    run_id: uuid.UUID
    recording_id: uuid.UUID
    state: str
    value: float | None
    prov_activity_id: uuid.UUID | None = Field(description="the run's PROV activity node")
    prov_node_id: uuid.UUID | None = Field(
        description="PROV node of the artifact that carries the value"
    )
    artifact: ArtifactRef | None


class Aggregate(BaseModel):
    mean: float | None
    n: int
    run_ids: list[uuid.UUID] = Field(description="the runs this number is computed from")


class VariantSummary(VariantOut, Aggregate):
    pass


class LevelOut(Aggregate):
    value: Any


class SensitivityOut(BaseModel):
    factor: str
    levels: list[LevelOut]
    range: float | None = Field(description="max - min of the level means")


class MetricOut(BaseModel):
    name: str
    step: str
    key: str
    higher_is_better: bool


class FactorOut(BaseModel):
    name: str
    values: list[Any]


class BestOut(BaseModel):
    variant: int
    params: dict[str, Any]
    mean: float
    run_ids: list[uuid.UUID]


class ReportOut(BaseModel):
    sweep_id: uuid.UUID
    state: str
    complete: bool
    pipeline: str
    pipeline_version_id: str
    metric: MetricOut
    factors: list[FactorOut]
    cells: list[CellOut]
    variants: list[VariantSummary]
    sensitivity: list[SensitivityOut]
    best: BestOut | None
    prov_node_id: uuid.UUID | None


_TITLES = {404: "Not Found", 409: "Conflict", 422: "Unprocessable Content"}


@_route("POST", "/sweeps", "sweep:create", status_code=202, response_model=SweepOut)
def create_sweep(body: sweeps.SweepRequest, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            sweep = sweeps.create_sweep(s, ctx.principal, body)
            # 4.8 active-run quota over all of the sweep's runs (the transaction rolls back)
            quotas.check_active_runs(s, sweep.tenant_id, request.app.state.settings)
            out = sweeps.sweep_summary(s, sweep)
    except sweeps.SweepError as e:
        return problem(request, e.status, _TITLES.get(e.status, "Error"), e.detail, kind=e.code)
    ctx.audit(
        audit.DATA_CREATE,
        resource_type="sweep",
        resource_id=out["id"],
        status=out["state"],
        count=len(out["run_ids"]),
    )
    return SweepOut.model_validate(out)


def _load(s, sweep_id: uuid.UUID, ctx: Ctx):
    sweep = sweeps.get_sweep(s, sweep_id)
    if sweep is None:  # also the answer for another tenant's sweep (RLS + app filter)
        raise NotFound("sweep")
    ctx.check_tenant(sweep)
    return sweep


class SweepSummaryOut(BaseModel):
    """One row of ``GET /v1/sweeps`` (open the sweep for states, variants and run IDs)."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    pipeline_ref: str
    pipeline_version_id: str
    n_variants: int
    n_runs: int
    prov_node_id: uuid.UUID | None
    created_by: str
    created_at: datetime


@_route("GET", "/sweeps", "sweep:read", response_model=list[SweepSummaryOut])
def list_sweeps(
    ctx: CtxDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Sweeps of the caller's tenant, newest first (M3 open issue 5)."""
    with ctx.session() as s:
        q = select(m.Sweep).order_by(m.Sweep.created_at.desc(), m.Sweep.id)
        rows = [SweepSummaryOut.model_validate(r) for r in s.scalars(q.limit(limit).offset(offset))]
    ctx.audit(audit.DATA_READ, resource_type="sweep", count=len(rows))
    return rows


@_route("GET", "/sweeps/{sweep_id}", "sweep:read", response_model=SweepOut)
def get_sweep(sweep_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        out = sweeps.sweep_summary(s, _load(s, sweep_id, ctx))
    ctx.audit(audit.DATA_READ, resource_type="sweep", resource_id=sweep_id)
    return out


@_route("GET", "/sweeps/{sweep_id}/report", "sweep:read", response_model=ReportOut)
def get_sweep_report(sweep_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        out = sweeps.report(s, _load(s, sweep_id, ctx))
    ctx.audit(audit.DATA_READ, resource_type="sweep_report", resource_id=sweep_id)
    return out
