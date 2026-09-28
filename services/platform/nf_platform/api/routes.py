"""v1 endpoints: health, whoami, metadata read/create, API-key management, audit export.

Kept small on purpose; M4 formalises the OpenAPI contract. Every read emits a ``data.read`` audit
event, every create a ``data.create`` event, every key operation an ``admin.action`` event (2.8).
SEC-090: no endpoint or field sends anything to devices; data flows device → platform only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from nf_platform import placement as phi_placement
from nf_platform.api.deps import PUBLIC, Ctx, action_extra, emit_for, guard
from nf_platform.api.errors import NotFound
from nf_platform.api.schemas import WhoAmIOut
from nf_platform.audit import log as audit
from nf_platform.auth import api_keys
from nf_platform.auth.authorize import Forbidden, effective_roles
from nf_platform.config import Placement
from nf_platform.db import models as m
from nf_platform.governance import attributes as gattrs
from nf_platform.governance import policy as gpolicy

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def _route(method: str, path: str, action: str, **kw: Any):
    def deco(fn):
        router.add_api_route(
            path,
            fn,
            methods=[method],
            openapi_extra=action_extra(action),
            # Every route runs the guard (cached per request, so CtxDep does not run it twice).
            dependencies=[Depends(guard)],
            **kw,
        )
        return fn

    return deco


# ---------------------------------------------------------------- schemas
Modality = Literal[*m.MODALITIES]
NervousSystem = Literal[*m.NERVOUS_SYSTEMS]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectOut(_Out):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class DatasetIn(ProjectIn):
    pass


class DatasetOut(ProjectOut):
    project_id: uuid.UUID


class SubjectIn(BaseModel):
    label: str = Field(min_length=1, max_length=100, description="Pseudonymous study code")


class SubjectOut(_Out):
    id: uuid.UUID
    dataset_id: uuid.UUID
    label: str
    created_at: datetime


class SessionIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    started_at: datetime | None = None


class SessionOut(_Out):
    id: uuid.UUID
    subject_id: uuid.UUID
    label: str
    started_at: datetime | None
    created_at: datetime


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    modality: Modality
    # 5.1: omitted -> the modality default; other values need data-steward/admin (SEC-022)
    nervous_system: NervousSystem | None = None
    derived_from_non_neural: bool | None = None
    sampling_rate: float = Field(gt=0, description="Hz")
    units: str = Field(min_length=1, max_length=20)
    device_ref: str | None = Field(default=None, max_length=200)


class ChannelOut(_Out):
    index: int
    name: str
    modality: str
    nervous_system: str
    derived_from_non_neural: bool
    sampling_rate: float
    units: str
    device_ref: str | None


class RecordingIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    source_format: str | None = Field(default=None, max_length=40)
    duration_s: float | None = Field(default=None, ge=0)
    channels: list[ChannelIn] = Field(default_factory=list, max_length=4096)


class RecordingOut(_Out):
    id: uuid.UUID
    session_id: uuid.UUID
    label: str
    source_format: str | None
    state: str
    duration_s: float | None
    created_at: datetime
    channels: list[ChannelOut] = []


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    roles: list[str] = Field(min_length=1)
    scopes: list[str] = Field(min_length=1)
    expires_in_days: int | None = Field(default=None, description="1..365, default 90")


class ApiKeyOut(_Out):
    id: uuid.UUID
    public_id: str
    name: str
    owner_id: str
    roles: list[str]
    scopes: list[str]
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class ApiKeyIssued(ApiKeyOut):
    key: str = Field(description="Shown once. Store it in a secret manager.")


class AuditEventOut(_Out):
    seq: int
    id: uuid.UUID
    ts: datetime
    type: str
    action: str | None
    outcome: str
    actor_kind: str | None
    actor_id: str | None
    auth_method: str | None
    resource_type: str | None
    resource_id: str | None
    request_id: str | None
    details: dict[str, Any]


class AuditBatchOut(_Out):
    seq: int
    batch_id: str
    prev_id: str | None
    period_start: datetime
    period_end: datetime
    event_count: int
    object_key: str


# ---------------------------------------------------------------- helpers
def _get(s, model, id_: uuid.UUID, what: str, ctx: Ctx):
    row = s.scalar(select(model).where(model.id == id_))
    if row is None:  # also the answer for rows of another tenant (RLS + app filter hide them)
        raise NotFound(what)
    ctx.check_tenant(row)
    return row


def enforce(ctx: Ctx, action: str, resource: gpolicy.Resource, session=None) -> gpolicy.Decision:
    """5.4: the single policy function (RBAC + quarantine + consent scope + classification) for a
    data-touching route; a denial is audited (``authz.denied``) and becomes a 403."""
    try:
        return gpolicy.check(ctx.principal, action, resource, session=session)
    except Forbidden as e:
        emit_for(
            ctx.principal,
            audit.AUTHZ_DENIED,
            "denied",
            action=action,
            resource_type=resource.type,
            resource_id=resource.id,
            request_id=ctx.request_id,
            details={"reason": e.reason, "method": ctx.method, "route": ctx.route},
        )
        raise


def enforce_placement(
    ctx: Ctx, session, placement: Placement, roles: tuple[str, ...] = phi_placement.ROLES
) -> None:
    """5.7: a phi=true tenant may only write/process data on BAA-listed services. A denial is
    audited (``authz.denied``) and becomes a 403."""
    try:
        phi_placement.check_tenant(session, ctx.tenant_id, placement, roles)
    except phi_placement.PlacementDenied as e:
        emit_for(
            ctx.principal,
            audit.AUTHZ_DENIED,
            "denied",
            action="phi:placement",
            resource_type="tenant",
            resource_id=ctx.tenant_id,
            request_id=ctx.request_id,
            details={"reason": e.reason, "method": ctx.method, "route": ctx.route},
        )
        raise


def recording_resource(ctx: Ctx, rec: m.Recording) -> gpolicy.Resource:
    return gpolicy.Resource("recording", ctx.tenant_id, str(rec.id), recording_id=rec.id)


def require_readable(ctx: Ctx, rec: m.Recording, session=None, action: str = "recording:read"):
    """Policy check for reading a recording (replaces the 2.6 quarantine stub): quarantined
    recordings -> 403 (audited) except for quarantine reviewers; data reads need consent."""
    return enforce(ctx, action, recording_resource(ctx, rec), session)


def _read(ctx: Ctx, resource: str, rid: Any = None, count: int | None = None) -> None:
    extra = {} if count is None else {"count": count}
    ctx.audit(audit.DATA_READ, resource_type=resource, resource_id=rid, **extra)


def _created(ctx: Ctx, resource: str, rid: Any) -> None:
    ctx.audit(audit.DATA_CREATE, resource_type=resource, resource_id=rid)


def _tid(ctx: Ctx) -> uuid.UUID:
    return uuid.UUID(ctx.tenant_id)


# ---------------------------------------------------------------- meta
@_route("GET", "/health", PUBLIC)
def health() -> dict[str, str]:
    return {"status": "ok"}


@_route("GET", "/whoami", "self:read", response_model=WhoAmIOut)
def whoami(ctx: CtxDep) -> dict[str, Any]:
    p = ctx.principal
    _read(ctx, "principal", p.id)
    return {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "kind": p.kind,
        "roles": sorted(effective_roles(p)),
        "scopes": sorted(p.scopes),
        "mfa_phishing_resistant": p.mfa_phr,
        "auth_method": p.auth_method,
    }


# ---------------------------------------------------------------- projects
@_route("POST", "/projects", "project:create", status_code=201, response_model=ProjectOut)
def create_project(body: ProjectIn, ctx: CtxDep):
    with ctx.session() as s:
        row = m.Project(tenant_id=_tid(ctx), created_by=ctx.principal.id, **body.model_dump())
        s.add(row)
        s.flush()
        s.refresh(row)
        out = ProjectOut.model_validate(row)
    _created(ctx, "project", out.id)
    return out


@_route("GET", "/projects", "project:read", response_model=list[ProjectOut])
def list_projects(ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        q = select(m.Project).order_by(m.Project.created_at, m.Project.id)
        rows = [ProjectOut.model_validate(r) for r in s.scalars(q.limit(limit).offset(offset))]
    _read(ctx, "project", count=len(rows))
    return rows


@_route("GET", "/projects/{project_id}", "project:read", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        out = ProjectOut.model_validate(_get(s, m.Project, project_id, "project", ctx))
    _read(ctx, "project", project_id)
    return out


# ---------------------------------------------------------------- datasets
@_route(
    "POST",
    "/projects/{project_id}/datasets",
    "dataset:create",
    status_code=201,
    response_model=DatasetOut,
)
def create_dataset(project_id: uuid.UUID, body: DatasetIn, ctx: CtxDep):
    with ctx.session() as s:
        _get(s, m.Project, project_id, "project", ctx)
        row = m.Dataset(
            tenant_id=_tid(ctx),
            project_id=project_id,
            created_by=ctx.principal.id,
            **body.model_dump(),
        )
        s.add(row)
        s.flush()
        s.refresh(row)
        out = DatasetOut.model_validate(row)
    _created(ctx, "dataset", out.id)
    return out


@_route("GET", "/projects/{project_id}/datasets", "dataset:read", response_model=list[DatasetOut])
def list_datasets(project_id: uuid.UUID, ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        _get(s, m.Project, project_id, "project", ctx)
        q = select(m.Dataset).where(m.Dataset.project_id == project_id)
        q = q.order_by(m.Dataset.created_at, m.Dataset.id).limit(limit).offset(offset)
        rows = [DatasetOut.model_validate(r) for r in s.scalars(q)]
    _read(ctx, "dataset", count=len(rows))
    return rows


@_route("GET", "/datasets/{dataset_id}", "dataset:read", response_model=DatasetOut)
def get_dataset(dataset_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        out = DatasetOut.model_validate(_get(s, m.Dataset, dataset_id, "dataset", ctx))
    _read(ctx, "dataset", dataset_id)
    return out


# ---------------------------------------------------------------- subjects
@_route(
    "POST",
    "/datasets/{dataset_id}/subjects",
    "subject:create",
    status_code=201,
    response_model=SubjectOut,
)
def create_subject(dataset_id: uuid.UUID, body: SubjectIn, ctx: CtxDep):
    with ctx.session() as s:
        _get(s, m.Dataset, dataset_id, "dataset", ctx)
        row = m.Subject(
            tenant_id=_tid(ctx),
            dataset_id=dataset_id,
            created_by=ctx.principal.id,
            label=body.label,
        )
        s.add(row)
        s.flush()
        s.refresh(row)
        out = SubjectOut.model_validate(row)
    _created(ctx, "subject", out.id)
    return out


@_route("GET", "/datasets/{dataset_id}/subjects", "subject:read", response_model=list[SubjectOut])
def list_subjects(dataset_id: uuid.UUID, ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        _get(s, m.Dataset, dataset_id, "dataset", ctx)
        q = select(m.Subject).where(m.Subject.dataset_id == dataset_id)
        q = q.order_by(m.Subject.created_at, m.Subject.id).limit(limit).offset(offset)
        rows = [SubjectOut.model_validate(r) for r in s.scalars(q)]
    _read(ctx, "subject", count=len(rows))
    return rows


@_route("GET", "/subjects/{subject_id}", "subject:read", response_model=SubjectOut)
def get_subject(subject_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        out = SubjectOut.model_validate(_get(s, m.Subject, subject_id, "subject", ctx))
    _read(ctx, "subject", subject_id)
    return out


# ---------------------------------------------------------------- sessions
@_route(
    "POST",
    "/subjects/{subject_id}/sessions",
    "session:create",
    status_code=201,
    response_model=SessionOut,
)
def create_session(subject_id: uuid.UUID, body: SessionIn, ctx: CtxDep):
    with ctx.session() as s:
        _get(s, m.Subject, subject_id, "subject", ctx)
        row = m.Session_(
            tenant_id=_tid(ctx),
            subject_id=subject_id,
            created_by=ctx.principal.id,
            **body.model_dump(),
        )
        s.add(row)
        s.flush()
        s.refresh(row)
        out = SessionOut.model_validate(row)
    _created(ctx, "session", out.id)
    return out


@_route("GET", "/subjects/{subject_id}/sessions", "session:read", response_model=list[SessionOut])
def list_sessions(subject_id: uuid.UUID, ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        _get(s, m.Subject, subject_id, "subject", ctx)
        q = select(m.Session_).where(m.Session_.subject_id == subject_id)
        q = q.order_by(m.Session_.created_at, m.Session_.id).limit(limit).offset(offset)
        rows = [SessionOut.model_validate(r) for r in s.scalars(q)]
    _read(ctx, "session", count=len(rows))
    return rows


@_route("GET", "/sessions/{session_id}", "session:read", response_model=SessionOut)
def get_session(session_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        out = SessionOut.model_validate(_get(s, m.Session_, session_id, "session", ctx))
    _read(ctx, "session", session_id)
    return out


# ---------------------------------------------------------------- recordings (+ channels)
def _recording_out(s, row: m.Recording) -> RecordingOut:
    chans = s.scalars(
        select(m.Channel).where(m.Channel.recording_id == row.id).order_by(m.Channel.index)
    ).all()
    out = RecordingOut.model_validate(row)
    out.channels = [ChannelOut.model_validate(c) for c in chans]
    return out


@_route(
    "POST",
    "/sessions/{session_id}/recordings",
    "recording:create",
    status_code=201,
    response_model=RecordingOut,
)
def create_recording(session_id: uuid.UUID, body: RecordingIn, ctx: CtxDep):
    tid = _tid(ctx)
    with ctx.session() as s:
        _get(s, m.Session_, session_id, "session", ctx)
        row = m.Recording(
            tenant_id=tid,
            session_id=session_id,
            label=body.label,
            source_format=body.source_format,
            duration_s=body.duration_s,
            created_by=ctx.principal.id,
        )
        s.add(row)
        s.flush()
        for i, ch in enumerate(body.channels):
            ns, dfnn = gattrs.resolve_initial(
                ctx.principal, ch.modality, ch.nervous_system, ch.derived_from_non_neural
            )
            vals = ch.model_dump() | {"nervous_system": ns, "derived_from_non_neural": dfnn}
            s.add(m.Channel(tenant_id=tid, recording_id=row.id, index=i, **vals))
        s.flush()
        s.refresh(row)
        out = _recording_out(s, row)
    _created(ctx, "recording", out.id)
    return out


@_route(
    "GET", "/sessions/{session_id}/recordings", "recording:read", response_model=list[RecordingOut]
)
def list_recordings(session_id: uuid.UUID, ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        _get(s, m.Session_, session_id, "session", ctx)
        q = select(m.Recording).where(m.Recording.session_id == session_id)
        q = q.order_by(m.Recording.created_at, m.Recording.id).limit(limit).offset(offset)
        rows = []
        for r in s.scalars(q).all():
            try:  # 5.4: rows the policy denies (e.g. quarantined) are hidden, not errors
                gpolicy.check(
                    ctx.principal, "recording:read", recording_resource(ctx, r), session=s
                )
            except Forbidden:
                continue
            rows.append(_recording_out(s, r))
    _read(ctx, "recording", count=len(rows))
    return rows


@_route("GET", "/recordings/{recording_id}", "recording:read", response_model=RecordingOut)
def get_recording(recording_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        row = _get(s, m.Recording, recording_id, "recording", ctx)
        require_readable(ctx, row, s)
        out = _recording_out(s, row)
    _read(ctx, "recording", recording_id)
    return out


# ---------------------------------------------------------------- API keys (SEC-014)
def _manages_all_keys(ctx: Ctx) -> bool:
    return bool(effective_roles(ctx.principal) & {"owner", "admin"})


@_route("POST", "/api-keys", "apikey:create", status_code=201, response_model=ApiKeyIssued)
def create_api_key(body: ApiKeyIn, request: Request, ctx: CtxDep):
    with ctx.session() as s:
        issued = api_keys.issue(
            s,
            ctx.principal,
            name=body.name,
            roles=body.roles,
            scopes=body.scopes,
            days=body.expires_in_days,
            secret_provider=request.app.state.settings.secrets,
        )
        out = ApiKeyOut.model_validate(issued.row)
    ctx.audit(
        audit.ADMIN_ACTION,
        resource_type="api_key",
        resource_id=out.id,
        key_public_id=out.public_id,
        roles=out.roles,
        scopes=out.scopes,
        expires_at=out.expires_at.isoformat(),
    )
    return ApiKeyIssued(**out.model_dump(), key=issued.plaintext)


@_route("GET", "/api-keys", "apikey:read", response_model=list[ApiKeyOut])
def list_api_keys(ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        q = select(m.ApiKey)
        if not _manages_all_keys(ctx):
            q = q.where(m.ApiKey.owner_id == ctx.principal.id)
        q = q.order_by(m.ApiKey.created_at, m.ApiKey.id).limit(limit).offset(offset)
        rows = [ApiKeyOut.model_validate(r) for r in s.scalars(q)]
    _read(ctx, "api_key", count=len(rows))
    return rows


@_route("DELETE", "/api-keys/{key_id}", "apikey:revoke", status_code=204)
def revoke_api_key(key_id: uuid.UUID, ctx: CtxDep) -> Response:
    with ctx.session() as s:
        row = _get(s, m.ApiKey, key_id, "api key", ctx)
        if row.owner_id != ctx.principal.id and not _manages_all_keys(ctx):
            raise NotFound("api key")
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
        public_id = row.public_id
    ctx.audit(
        audit.ADMIN_ACTION, resource_type="api_key", resource_id=key_id, key_public_id=public_id
    )
    return Response(status_code=204)


# ---------------------------------------------------------------- audit export (SEC-105)
@_route("GET", "/audit/events", "audit:read", response_model=list[AuditEventOut])
def list_audit_events(ctx: CtxDep, after_seq: Offset = 0, limit: Limit = 100):
    with ctx.session() as s:
        q = select(m.AuditEvent).where(m.AuditEvent.seq > after_seq)
        q = q.where(m.AuditEvent.tenant_id == _tid(ctx)).order_by(m.AuditEvent.seq).limit(limit)
        rows = [AuditEventOut.model_validate(r) for r in s.scalars(q)]
    ctx.audit(audit.DATA_EXPORT, resource_type="audit_event", count=len(rows), format="json")
    return rows


@_route("GET", "/audit/batches", "audit:read", response_model=list[AuditBatchOut])
def list_audit_batches(ctx: CtxDep, limit: Limit = 100, offset: Offset = 0):
    with ctx.session() as s:
        q = select(m.AuditBatch).where(m.AuditBatch.tenant_scope == ctx.tenant_id)
        q = q.order_by(m.AuditBatch.seq).limit(limit).offset(offset)
        rows = [AuditBatchOut.model_validate(r) for r in s.scalars(q)]
    ctx.audit(audit.DATA_EXPORT, resource_type="audit_batch", count=len(rows), format="json")
    return rows


@_route(
    "GET",
    "/audit/batches/{seq}/object",
    "audit:read",
    response_class=Response,
    responses={
        200: {
            "content": {"application/json": {}},
            "description": "the stored batch bytes (NF-CJSON; the ID is SHA-256 over them, hashing "
            "spec v2 section 9.1)",
        }
    },
)
def get_audit_batch_object(
    request: Request, ctx: CtxDep, seq: Annotated[int, Path(ge=0)]
) -> Response:
    """AppSec M1: the exact bytes of one of the caller's tenant's audit batches, as stored in the
    WORM ``audit`` bucket, so an auditor can recompute the batch ID and the chain links
    independently (``X-NF-Batch-Id`` is the ID the platform recorded)."""
    with ctx.session() as s:
        row = s.scalar(
            select(m.AuditBatch).where(
                m.AuditBatch.tenant_scope == ctx.tenant_id, m.AuditBatch.seq == seq
            )
        )
        if row is None:
            raise NotFound("audit batch")
        key, bid = row.object_key, row.batch_id
    storage = getattr(request.app.state, "storage", None)
    if storage is None or not key.startswith(f"chain/{ctx.tenant_id}/"):
        raise NotFound("audit batch object")
    try:
        data = storage.objects.get("audit", key)
    except KeyError as e:  # storage.objects.ObjectNotFound
        raise NotFound("audit batch object") from e
    ctx.audit(
        audit.DATA_EXPORT,
        resource_type="audit_batch_object",
        resource_id=bid,
        seq=seq,
        format="nf.audit-batch/v1",
    )
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "X-NF-Batch-Id": bid,
            "Content-Disposition": f'attachment; filename="audit-batch-{seq:012d}.json"',
        },
    )
