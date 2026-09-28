"""v1 ingest endpoints: window reads (2.4), upload sessions (2.6), devices and streams (2.7).

Every route declares its action and runs the guard; every read emits ``data.read``, every write
``data.create`` (2.8). Quarantined recordings (2.6) are readable only by owner/admin/data-steward.
SEC-090: nothing here sends anything to devices; the stream endpoints only register a device key
and open a device → platform stream.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from nf_platform.api.deps import Ctx, action_extra, emit_for, guard
from nf_platform.api.errors import NotFound
from nf_platform.api.routes import enforce_placement, require_readable
from nf_platform.api.schemas import WindowJsonOut
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.governance import attributes as gattrs
from nf_platform.ingest import recording_store as rs
from nf_platform.ingest.errors import IngestError, invalid, too_large
from nf_platform.ingest.policy import initial_state
from nf_platform.ingest.stream import protocol as stream_protocol
from nf_platform.ingest.stream._proto import ingest_pb2 as stream_pb
from nf_platform.ingest.uploads import service as uploads
from nf_platform.jobs import queue as jobs_queue
from nf_platform.jobs.runs import INGEST_JOB_KIND
from nf_platform.limits import quotas

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def _route(method: str, path: str, action: str, **kw: Any):
    extra = {**kw.pop("openapi_extra", {}), **action_extra(action)}

    def deco(fn):
        router.add_api_route(
            path,
            fn,
            methods=[method],
            openapi_extra=extra,
            dependencies=[Depends(guard)],
            **kw,
        )
        return fn

    return deco


def _get(s, model, id_: uuid.UUID, what: str, ctx: Ctx):
    row = s.scalar(select(model).where(model.id == id_))
    if row is None:
        raise NotFound(what)
    ctx.check_tenant(row)
    return row


# ---------------------------------------------------------------- 2.4 window reads
@_route(
    "GET",
    "/recordings/{recording_id}/data",
    "signal:read",
    responses={
        200: {
            "model": WindowJsonOut,
            "content": {rs.WINDOW_MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
def read_recording_data(
    recording_id: uuid.UUID,
    request: Request,
    ctx: CtxDep,
    start: Annotated[float, Query(ge=0, description="window start [s]")],
    end: Annotated[float, Query(gt=0, description="window end [s], exclusive")],
    channels: Annotated[
        str | None, Query(max_length=65536, description="comma-separated names or indices")
    ] = None,
    level: Annotated[int, Query(ge=0, le=11)] = 0,
    kind: Literal["mean", "min", "max"] = "mean",
    format: Literal["json", "binary"] = "json",  # noqa: A002 (query parameter name)
):
    """Read the window ``[start, end)`` seconds of a recording (step 2.4).

    Decrypted server-side with the subject's DEK. Response format ``nf-window/1`` (see
    ``nf_platform.ingest.recording_store``): a header (channels, units, scale/offset, dtype,
    shape [channels, samples], level, decimation, sfreq, start_s, chunk_id) plus the samples,
    as JSON (``format=json``, at most ``window_json_max_values`` values) or as
    ``application/vnd.nf.window.v1`` bytes (``format=binary``, at most ``window_max_values``).
    Larger windows get 422 ``window-too-large``: use a pyramid ``level`` or a shorter window.
    Quarantined recordings: 403 except for owner/admin/data-steward.
    """
    with ctx.session() as s:
        rec = _get(s, m.Recording, recording_id, "recording", ctx)
        require_readable(ctx, rec, s, action="signal:read")  # 5.4 policy: consent `processing`
        subject_id = s.scalar(select(m.Session_.subject_id).where(m.Session_.id == rec.session_id))
        ref = rec.zarr_ref
    if ref is None:
        raise NotFound("recording data")
    settings = request.app.state.settings
    w = rs.read_window_for(
        request.app.state.storage,
        ctx.tenant_id,
        str(subject_id),
        ref,
        start_s=start,
        end_s=end,
        channels=channels,
        level=level,
        kind=kind,
        max_values=settings.window_max_values,
        max_json_values=settings.window_json_max_values,
        fmt=format,
    )
    ctx.audit(
        audit.DATA_READ,
        resource_type="recording_data",
        resource_id=recording_id,
        count=w.n_values,
        format=format,
    )
    headers = {"X-NF-Chunk-Id": w.header["chunk_id"]}
    if format == "binary":
        return Response(rs.encode_binary(w), media_type=rs.WINDOW_MEDIA_TYPE, headers=headers)
    return JSONResponse(rs.to_json(w), headers=headers)


# ---------------------------------------------------------------- 2.6 uploads
class UploadIn(BaseModel):
    session_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(gt=0)
    part_size: int | None = Field(default=None, gt=0)
    synthetic: bool = Field(
        default=False,
        description="SEC-071: true for synthetic or licence-checked public data (required "
        "outside prod and for synthetic-only tenants)",
    )


class PartTargetOut(BaseModel):
    part_number: int
    method: str
    url: str
    expires_at: datetime | None
    auth: str


class ReceivedPartOut(BaseModel):
    part_number: int
    size_bytes: int
    sha256: str


class UploadOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    session_id: uuid.UUID
    filename: str
    size_bytes: int
    part_size: int
    n_parts: int
    state: str
    synthetic: bool
    parts: list[PartTargetOut]
    received_parts: list[ReceivedPartOut]
    server_sha256: str | None
    error: str | None
    recording_ids: list[str]
    created_at: datetime
    completed_at: datetime | None


class CompleteIn(BaseModel):
    sha256: str = Field(min_length=64, max_length=64, description="client SHA-256 (hex)")


def _backend(request: Request):
    return request.app.state.upload_backend


@_route(
    "POST",
    "/datasets/{dataset_id}/uploads",
    "upload:create",
    status_code=201,
    response_model=UploadOut,
)
def create_upload(dataset_id: uuid.UUID, body: UploadIn, request: Request, ctx: CtxDep):
    backend = _backend(request)
    with ctx.session() as s:
        # 4.8 storage quota (403 quota-exceeded), checked before the session is created
        quotas.check_storage(
            s, uuid.UUID(ctx.tenant_id), body.size_bytes, request.app.state.settings
        )
        # 5.7: PHI tenants only on BAA-listed storage + database
        enforce_placement(ctx, s, request.app.state.settings.placement, ("storage", "database"))
        up = uploads.create(
            s,
            ctx.principal,
            dataset_id,
            uploads.UploadRequest(**body.model_dump()),
            request.app.state.settings,
            backend,
        )
        out = UploadOut(**uploads.status(s, up, backend))
    ctx.audit(audit.DATA_CREATE, resource_type="upload", resource_id=out.id)
    return out


@_route("GET", "/uploads/{upload_id}", "upload:read", response_model=UploadOut)
def get_upload(upload_id: uuid.UUID, request: Request, ctx: CtxDep):
    with ctx.session() as s:
        up = uploads.get_visible(s, ctx.principal, upload_id, write=False)
        out = UploadOut(**uploads.status(s, up, _backend(request)))
    ctx.audit(audit.DATA_READ, resource_type="upload", resource_id=upload_id)
    return out


@_route(
    "PUT",
    "/uploads/{upload_id}/parts/{part_number}",
    "upload:create",
    response_model=ReceivedPartOut,
    openapi_extra={"requestBody": {"content": {"application/octet-stream": {}}}},
)
async def put_upload_part(
    upload_id: uuid.UUID,
    part_number: Annotated[int, Path(ge=1, le=10000)],
    request: Request,
    ctx: CtxDep,
):
    """Local signed-URL shim: the part body is sealed under the subject DEK before storage."""
    limit = request.app.state.settings.upload_part_max
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise too_large("part exceeds the part size limit", max_part_size=limit)
    data = bytearray()
    async for block in request.stream():
        data += block
        if len(data) > limit:
            raise too_large("part exceeds the part size limit", max_part_size=limit)

    def work() -> ReceivedPartOut:
        with ctx.session() as s:
            row = uploads.put_part(
                s, request.app.state.storage, ctx.principal, upload_id, part_number, bytes(data)
            )
            return ReceivedPartOut(
                part_number=row.part_number, size_bytes=row.size_bytes, sha256=row.sha256
            )

    out = await run_in_threadpool(work)
    await run_in_threadpool(
        ctx.audit, audit.DATA_CREATE, resource_type="upload", resource_id=upload_id
    )
    return out


@_route(
    "POST",
    "/uploads/{upload_id}/complete",
    "upload:create",
    status_code=202,
    response_model=UploadOut,
)
def complete_upload(upload_id: uuid.UUID, body: CompleteIn, request: Request, ctx: CtxDep):
    backend = _backend(request)
    with ctx.session() as s:
        up = uploads.complete(
            s, request.app.state.storage, ctx.principal, upload_id, body.sha256, backend
        )
        if up.state == "uploaded":
            # 3.3: conversion runs on the job queue (one job per upload; a repeated complete call
            # finds the same job through the dedupe key)
            jobs_queue.enqueue(
                s,
                INGEST_JOB_KIND,
                {"upload_id": str(up.id)},
                dedupe_key=str(up.id),
                created_by=ctx.principal.id,
            )
        out = UploadOut(**uploads.status(s, up, backend))
    if out.state == "rejected":
        emit_for(
            ctx.principal,
            audit.DATA_CREATE,
            "failure",
            action=ctx.action,
            resource_type="upload",
            resource_id=str(upload_id),
            request_id=ctx.request_id,
            details={"method": ctx.method, "route": ctx.route, "reason": "sha256 mismatch"},
        )
        raise IngestError(
            422,
            "hash-mismatch",
            "Hash mismatch",
            "the server-side SHA-256 differs from the client value; the upload was rejected",
            extra={"server_sha256": out.server_sha256},
        )
    ctx.audit(audit.DATA_CREATE, resource_type="upload", resource_id=upload_id, status=out.state)
    return out


# ---------------------------------------------------------------- 2.7 devices + streams
class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    public_key: str = Field(description="Ed25519 public key, 32 bytes, base64")


class DeviceOut(BaseModel):
    id: uuid.UUID
    name: str
    alg: str
    public_key: str
    created_at: datetime
    revoked_at: datetime | None


def _device_out(d: m.Device) -> DeviceOut:
    return DeviceOut(
        id=d.id,
        name=d.name,
        alg=d.alg,
        public_key=base64.b64encode(bytes(d.public_key)).decode(),
        created_at=d.created_at,
        revoked_at=d.revoked_at,
    )


@_route("POST", "/devices", "device:create", status_code=201, response_model=DeviceOut)
def register_device(body: DeviceIn, ctx: CtxDep):
    """SEC-016: the key pair is generated on the device; only the public key is registered."""
    try:
        key = base64.b64decode(body.public_key, validate=True)
    except (binascii.Error, ValueError) as e:
        raise invalid("public_key must be base64") from e
    if len(key) != 32:
        raise invalid("public_key must be a 32-byte Ed25519 key")
    with ctx.session() as s:
        row = m.Device(
            tenant_id=uuid.UUID(ctx.tenant_id),
            name=body.name,
            public_key=key,
            created_by=ctx.principal.id,
        )
        s.add(row)
        s.flush()
        s.refresh(row)
        out = _device_out(row)
    ctx.audit(audit.ADMIN_ACTION, resource_type="device", resource_id=out.id)
    return out


@_route("GET", "/devices", "device:read", response_model=list[DeviceOut])
def list_devices(ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        q = select(m.Device).order_by(m.Device.created_at, m.Device.id)
        rows = [_device_out(d) for d in s.scalars(q.limit(limit).offset(offset))]
    ctx.audit(audit.DATA_READ, resource_type="device", count=len(rows))
    return rows


Modality = Literal[*m.MODALITIES]


class StreamChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    modality: Modality
    # 5.1: omitted -> the modality default; other values need data-steward/admin (SEC-022)
    nervous_system: Literal[*m.NERVOUS_SYSTEMS] | None = None
    derived_from_non_neural: bool | None = None
    units: str = Field(min_length=1, max_length=20)
    scale: float = Field(default=1.0, allow_inf_nan=False)
    offset: float = Field(default=0.0, allow_inf_nan=False)


class StreamIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    device_id: uuid.UUID
    sfreq: float = Field(gt=0, le=100_000, allow_inf_nan=False)
    dtype: Literal[*stream_protocol.DTYPES]
    channels: list[StreamChannelIn] = Field(min_length=1, max_length=4096)
    synthetic: bool = False


GRPC_SERVICE = stream_pb.DESCRIPTOR.services_by_name["IngestService"].full_name


class StreamOut(BaseModel):
    stream_id: uuid.UUID
    recording_id: uuid.UUID
    recording_state: str
    next_seq: int
    grpc_service: str = Field(
        default=GRPC_SERVICE,
        description="Fully qualified gRPC service to stream chunks to.",
        # no default in the published schema: the name is a (not yet fixed) brand code identifier
        json_schema_extra=lambda s: s.pop("default", None),
    )
    token_audience: str = stream_protocol.TOKEN_AUDIENCE
    ack_timing: str = Field(
        default="none",
        description="SEC-093: acknowledgements carry no timing guarantee; never block "
        "acquisition on them",
    )


@_route(
    "POST",
    "/sessions/{session_id}/streams",
    "stream:create",
    status_code=201,
    response_model=StreamOut,
)
def open_stream(session_id: uuid.UUID, body: StreamIn, request: Request, ctx: CtxDep):
    names = [c.name for c in body.channels]
    if len(set(names)) != len(names):
        raise invalid("channel names must be unique")
    tid = uuid.UUID(ctx.tenant_id)
    with ctx.session() as s:
        sess = _get(s, m.Session_, session_id, "session", ctx)
        dev = s.scalar(select(m.Device).where(m.Device.id == body.device_id))
        if dev is None or dev.revoked_at is not None:
            raise NotFound("device")
        uploads.require_synthetic(s, ctx.principal, body.synthetic, request.app.state.settings)
        # 5.7: PHI tenants only on BAA-listed storage + database
        enforce_placement(ctx, s, request.app.state.settings.placement, ("storage", "database"))
        rid = uuid.uuid4()
        prefix = rs.stream_prefix(ctx.tenant_id, str(sess.subject_id), str(rid))
        rec = m.Recording(
            id=rid,
            tenant_id=tid,
            session_id=session_id,
            label=body.label,
            source_format="stream",
            state=initial_state(
                request.app.state.consent_policy, ctx.tenant_id, str(sess.subject_id), str(rid)
            ),
            zarr_ref=rs.make_ref(prefix, "signal"),
            created_by=ctx.principal.id,
        )
        s.add(rec)
        s.flush()
        for i, c in enumerate(body.channels):
            ns, dfnn = gattrs.resolve_initial(
                ctx.principal, c.modality, c.nervous_system, c.derived_from_non_neural
            )
            s.add(
                m.Channel(
                    tenant_id=tid,
                    recording_id=rid,
                    index=i,
                    name=c.name,
                    modality=c.modality,
                    nervous_system=ns,
                    derived_from_non_neural=dfnn,
                    sampling_rate=body.sfreq,
                    units=c.units,
                    device_ref=str(dev.id),
                )
            )
        st = m.IngestStream(
            tenant_id=tid,
            recording_id=rid,
            subject_id=sess.subject_id,
            device_id=dev.id,
            sfreq=body.sfreq,
            n_channels=len(body.channels),
            dtype=body.dtype,
            ch_scale=[c.scale for c in body.channels],
            ch_offset=[c.offset for c in body.channels],
            synthetic=body.synthetic,
            created_by=ctx.principal.id,
        )
        s.add(st)
        s.flush()
        out = StreamOut(stream_id=st.id, recording_id=rid, recording_state=rec.state, next_seq=0)
    ctx.audit(audit.DATA_CREATE, resource_type="stream", resource_id=out.stream_id)
    return out
