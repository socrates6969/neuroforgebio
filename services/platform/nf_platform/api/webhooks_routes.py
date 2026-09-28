"""v1 webhook management (BUILD-GUIDE 4.6; SEC-045, SEC-076).

Owner/admin only (a phishing-resistant login; never an API key: ``webhook:*`` has no API-key
scope). The signing secret is returned once, at creation and at rotation; the platform stores it
encrypted. Rotation keeps the previous secret valid for ``Settings.webhook_rotation_overlap_s``
(both signatures are sent meanwhile). Deleting an endpoint disables it (pending deliveries fail);
rows are kept for the delivery history.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import ApiProblem, NotFound
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.webhooks import service as webhooks
from nf_platform.webhooks.payloads import EVENTS

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
EventType = Literal[*EVENTS]  # type: ignore[valid-type]


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


class WebhookIn(BaseModel):
    url: str = Field(
        min_length=12,
        max_length=2048,
        description="https URL with a public DNS name (private, loopback, link-local and "
        "metadata addresses are refused, SEC-076)",
    )
    event_types: list[EventType] = Field(min_length=1, max_length=len(EVENTS))
    description: str | None = Field(default=None, max_length=200)


class KeyVersionOut(BaseModel):
    version: int
    created_at: datetime
    expires_at: datetime | None = Field(description="Set while a rotation overlap runs.")


class WebhookOut(BaseModel):
    id: uuid.UUID
    url: str
    description: str | None
    event_types: list[str]
    created_by: str
    created_at: datetime
    disabled_at: datetime | None
    key_versions: list[KeyVersionOut] = Field(description="Signing keys currently valid.")


class WebhookIssued(WebhookOut):
    signing_secret: str = Field(
        description="Shown once. HMAC-SHA-256 key for NF-Webhook-Signature (use its UTF-8 bytes)."
    )


class RotatedOut(BaseModel):
    signing_secret: str = Field(description="Shown once: the new signing secret.")
    version: int
    previous_valid_until: datetime = Field(
        description="Older secrets keep verifying until then (both signatures are sent)."
    )


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_id: uuid.UUID
    event_type: str
    state: Literal["pending", "delivered", "failed"]
    attempts: int
    next_attempt_at: datetime
    last_status: int | None
    last_error: str | None
    created_at: datetime
    delivered_at: datetime | None


def _invalid(request: Request, e: webhooks.WebhookError) -> ApiProblem:
    return ApiProblem(422, "Invalid request", str(e), kind="invalid-request")


def _load(s, webhook_id: uuid.UUID, ctx: Ctx) -> m.WebhookEndpoint:
    ep = s.scalar(select(m.WebhookEndpoint).where(m.WebhookEndpoint.id == webhook_id))
    if ep is None:  # also another tenant's endpoint (RLS + app filter)
        raise NotFound("webhook")
    ctx.check_tenant(ep)
    return ep


@_route("POST", "/webhooks", "webhook:create", status_code=201, response_model=WebhookIssued)
def create_webhook(body: WebhookIn, request: Request, ctx: CtxDep):
    settings = request.app.state.settings
    try:
        with ctx.session() as s:
            issued = webhooks.create_endpoint(
                s,
                tenant_id=uuid.UUID(ctx.tenant_id),
                created_by=ctx.principal.id,
                url=body.url,
                event_types=list(body.event_types),
                description=body.description,
                secret_provider=settings.secrets,
            )
            view = webhooks.endpoint_view(s, issued.endpoint)
    except webhooks.WebhookError as e:
        raise _invalid(request, e) from None
    ctx.audit(
        audit.ADMIN_ACTION,
        resource_type="webhook",
        resource_id=view["id"],
        event_types=view["event_types"],
    )
    return WebhookIssued(**view, signing_secret=issued.signing_key)


@_route("GET", "/webhooks", "webhook:read", response_model=list[WebhookOut])
def list_webhooks(
    ctx: CtxDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    with ctx.session() as s:
        q = select(m.WebhookEndpoint).order_by(m.WebhookEndpoint.created_at, m.WebhookEndpoint.id)
        rows = [webhooks.endpoint_view(s, ep) for ep in s.scalars(q.limit(limit).offset(offset))]
    ctx.audit(audit.DATA_READ, resource_type="webhook", count=len(rows))
    return rows


@_route("GET", "/webhooks/{webhook_id}", "webhook:read", response_model=WebhookOut)
def get_webhook(webhook_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        view = webhooks.endpoint_view(s, _load(s, webhook_id, ctx))
    ctx.audit(audit.DATA_READ, resource_type="webhook", resource_id=webhook_id)
    return view


@_route("DELETE", "/webhooks/{webhook_id}", "webhook:delete", status_code=204)
def delete_webhook(webhook_id: uuid.UUID, ctx: CtxDep) -> Response:
    with ctx.session() as s:
        webhooks.disable_endpoint(s, _load(s, webhook_id, ctx))
    ctx.audit(audit.ADMIN_ACTION, resource_type="webhook", resource_id=webhook_id, op="disable")
    return Response(status_code=204)


@_route(
    "POST",
    "/webhooks/{webhook_id}/rotate-secret",
    "webhook:update",
    response_model=RotatedOut,
)
def rotate_webhook_secret(webhook_id: uuid.UUID, request: Request, ctx: CtxDep):
    settings = request.app.state.settings
    with ctx.session() as s:
        ep = _load(s, webhook_id, ctx)
        if ep.disabled_at is not None:
            raise ApiProblem(409, "Conflict", "webhook is disabled", kind="conflict")
        key, version, until = webhooks.rotate_key(
            s,
            ep,
            secret_provider=settings.secrets,
            overlap_s=settings.webhook_rotation_overlap_s,
        )
    ctx.audit(
        audit.ADMIN_ACTION,
        resource_type="webhook",
        resource_id=webhook_id,
        op="rotate",
        key_version=version,
    )
    return RotatedOut(signing_secret=key, version=version, previous_valid_until=until)


@_route(
    "GET",
    "/webhooks/{webhook_id}/deliveries",
    "webhook:read",
    response_model=list[DeliveryOut],
)
def list_webhook_deliveries(
    webhook_id: uuid.UUID,
    ctx: CtxDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    with ctx.session() as s:
        _load(s, webhook_id, ctx)
        q = (
            select(m.WebhookDelivery)
            .where(m.WebhookDelivery.endpoint_id == webhook_id)
            .order_by(m.WebhookDelivery.created_at.desc(), m.WebhookDelivery.id)
        )
        rows = [DeliveryOut.model_validate(d) for d in s.scalars(q.limit(limit).offset(offset))]
    ctx.audit(audit.DATA_READ, resource_type="webhook_delivery", count=len(rows))
    return rows
