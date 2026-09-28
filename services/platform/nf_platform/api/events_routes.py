"""Server-sent events for run status (BUILD-GUIDE 4.6; BLUEPRINT §4.1) and the quota read (4.8).

``GET /v1/runs/{run_id}/events`` streams ``text/event-stream``:

- ``event: run.state`` with ``data`` = the run's state JSON, once at connect and on every change
  (``id`` = a counter, so ``Last-Event-ID`` reconnects are cheap; the first event always carries
  the current state, nothing is replayed);
- ``: keepalive`` comments while nothing changes;
- ``event: end`` when the run is terminal, or ``event: timeout`` after ``wait_s`` (clients
  reconnect; EventSource does so on its own);
- ``event: error`` + close when the credential stops being valid (SEC-017): the stream re-runs
  authentication and authorization every ``Settings.reauth_interval_s`` (30 s), so a revoked API
  key, an expired token or a revoked role ends an open stream within 60 s.

The clock and sleep are taken from ``app.state`` when present (tests inject fakes; nothing sleeps).
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from nf_platform.api.deps import Ctx, action_extra, emit_for, guard
from nf_platform.api.errors import NotFound
from nf_platform.audit import log as audit
from nf_platform.auth.authorize import Forbidden, ResourceRef, Unauthorized, authorize
from nf_platform.jobs import queue, runs
from nf_platform.limits import quotas

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
SSE = "text/event-stream"
KEEPALIVE_S = 15.0


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


class EventStreamResponse(StreamingResponse):
    media_type = SSE


class RunStateEvent(BaseModel):
    """``data`` of an ``event: run.state`` message."""

    run_id: uuid.UUID
    state: str
    attempt: int
    error: str | None
    finished_at: str | None = Field(json_schema_extra={"format": "date-time"})


def _frame(event: str, data: dict[str, Any], event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _snapshot(ctx: Ctx, run_id: uuid.UUID) -> dict[str, Any] | None:
    with ctx.session() as s:
        run = runs.get_run(s, run_id)
        if run is None:
            return None
        return RunStateEvent(
            run_id=run.id,
            state=run.state,
            attempt=run.attempt,
            error=run.error,
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
        ).model_dump(mode="json")


def _still_allowed(request: Request, ctx: Ctx) -> bool:
    """SEC-017: re-authenticate the original credential and re-authorize the action."""
    try:
        principal = request.app.state.authenticator(request)
        authorize(
            principal,
            ctx.action,
            ResourceRef(type=ctx.action.split(":")[0], tenant_id=ctx.tenant_id),
        )
    except (Unauthorized, Forbidden):
        return False
    return principal.tenant_id == ctx.tenant_id


def _stream(
    request: Request, ctx: Ctx, run_id: uuid.UUID, first: dict[str, Any], wait_s: float
) -> Iterator[str]:
    settings = request.app.state.settings
    clock = getattr(request.app.state, "sse_clock", time.monotonic)
    sleep = getattr(request.app.state, "sse_sleep", time.sleep)
    start = clock()
    last_auth = last_beat = start
    counter = 1
    state = first
    yield "retry: 3000\n\n"
    yield _frame("run.state", state, counter)
    while True:
        if state["state"] in queue.TERMINAL:
            yield _frame("end", {"reason": "terminal", "state": state["state"]})
            return
        now = clock()
        if now - start >= wait_s:
            yield _frame("timeout", {"reason": "wait_s elapsed; reconnect to continue"})
            return
        if now - last_auth >= settings.reauth_interval_s:
            last_auth = now
            if not _still_allowed(request, ctx):
                emit_for(
                    ctx.principal,
                    audit.AUTHZ_DENIED,
                    "denied",
                    action=ctx.action,
                    resource_type="run",
                    resource_id=str(run_id),
                    request_id=ctx.request_id,
                    details={"reason": "credential no longer valid; stream closed"},
                )
                yield _frame("error", {"status": 401, "title": "Unauthorized"})
                return
        sleep(settings.sse_poll_s)
        cur = _snapshot(ctx, run_id)
        if cur is None:
            yield _frame("error", {"status": 404, "title": "Not Found"})
            return
        if cur != state:
            counter += 1
            state = cur
            yield _frame("run.state", state, counter)
            last_beat = clock()
        elif clock() - last_beat >= KEEPALIVE_S:
            last_beat = clock()
            yield ": keepalive\n\n"


@_route(
    "GET",
    "/runs/{run_id}/events",
    "run:read",
    response_class=EventStreamResponse,
    responses={
        200: {
            "description": "text/event-stream of run.state events (then end, timeout or error).",
            "content": {
                SSE: {
                    "schema": {"type": "string"},
                    "x-nf-event-data": "#/components/schemas/RunStateEvent",
                }
            },
        }
    },
)
def stream_run_events(
    run_id: uuid.UUID,
    request: Request,
    ctx: CtxDep,
    wait_s: Annotated[
        float, Query(ge=0, le=3600, description="close after this many seconds (default 300)")
    ] = 300.0,
):
    first = _snapshot(ctx, run_id)
    if first is None:  # also another tenant's run (RLS + app filter)
        raise NotFound("run")
    ctx.audit(audit.DATA_READ, resource_type="run", resource_id=run_id, stream="sse")
    limit = min(wait_s, request.app.state.settings.sse_max_s)
    return EventStreamResponse(
        _stream(request, ctx, run_id, first, limit),
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------- 4.8 quota read
class QuotaItem(BaseModel):
    limit: int
    used: int


class QuotasOut(BaseModel):
    storage_bytes: QuotaItem = Field(description="Stored objects + uploads in flight.")
    active_runs: QuotaItem = Field(description="Queued + running runs.")


@_route("GET", "/quotas", "quota:read", response_model=QuotasOut)
def get_quotas(request: Request, ctx: CtxDep):
    tid = uuid.UUID(ctx.tenant_id)
    with ctx.session() as s:
        lim = quotas.limits_for(s, tid, request.app.state.settings)
        use = quotas.usage(s, tid)
    ctx.audit(audit.DATA_READ, resource_type="quota")
    return QuotasOut(
        storage_bytes=QuotaItem(limit=lim.storage_bytes, used=use.storage_bytes),
        active_runs=QuotaItem(limit=lim.active_runs, used=use.active_runs),
    )
