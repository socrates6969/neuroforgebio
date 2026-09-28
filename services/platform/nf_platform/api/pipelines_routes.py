"""v1 pipeline endpoints (BUILD-GUIDE 3.2; BLUEPRINT §3.5, §4.4; SEC-044).

``POST /v1/pipelines`` publishes a PipelineVersion document
(docs/spec/pipeline-version.schema.json): 201 when new, 200 for an identical re-publish, 409 when
``name@version`` exists with other content.
``GET /v1/pipelines/{pipeline_ref}`` resolves ``name@semver`` (or a ``pv:sha256:`` ID) to the
digest-addressed version. Published versions are immutable (append-only table).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import problem
from nf_platform.api.schemas import PipelineVersionOut
from nf_platform.audit import log as audit
from nf_platform.pipelines import spec as pipelines

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
MAX_SPEC_BYTES = 256 * 1024


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


def version_out(row: pipelines.PipelineVersionRow) -> dict[str, Any]:
    return {
        "id": row.pv_id,
        "name": row.name,
        "version": row.version,
        "ref": row.ref,
        "spec": row.document,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
    }


@_route(
    "POST",
    "/pipelines",
    "pipeline:create",
    status_code=201,
    responses={
        200: {"model": PipelineVersionOut, "description": "Identical re-publish"},
        201: {"model": PipelineVersionOut, "description": "Published"},
    },
)
def publish_pipeline(
    request: Request, ctx: CtxDep, body: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    # Defence in depth: api.body_limit already refuses bodies over MAX_SPEC_BYTES as they stream in
    # (also chunked ones without Content-Length).
    size = int(request.headers.get("content-length") or 0)
    if size > MAX_SPEC_BYTES:
        return problem(request, 413, "Content Too Large", "spec too large", kind="too-large")
    try:
        with ctx.session() as s:
            row = pipelines.publish(s, ctx.principal, body)
    except pipelines.PipelineConflict as e:
        return problem(request, 409, "Conflict", str(e), kind="pipeline-version-exists")
    except pipelines.PipelineError as e:
        return problem(request, 422, "Invalid pipeline spec", str(e), kind="invalid-pipeline")
    if row.created:
        ctx.audit(audit.DATA_CREATE, resource_type="pipeline_version", resource_id=row.pv_id)
    return JSONResponse(version_out(row), status_code=201 if row.created else 200)


@_route(
    "GET",
    "/pipelines/{pipeline_ref}",
    "pipeline:read",
    responses={200: {"model": PipelineVersionOut}},
)
def get_pipeline(pipeline_ref: str, request: Request, ctx: CtxDep) -> JSONResponse:
    try:
        with ctx.session() as s:
            row = pipelines.resolve(s, pipeline_ref)
    except pipelines.PipelineNotFound:
        return problem(request, 404, "Not Found", "pipeline version not found", kind="not-found")
    except pipelines.PipelineError as e:
        return problem(request, 422, "Invalid request", str(e), kind="invalid-request")
    ctx.audit(audit.DATA_READ, resource_type="pipeline_version", resource_id=row.pv_id)
    return JSONResponse(version_out(row))
