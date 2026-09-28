"""v1 model registry (BUILD-GUIDE 6.1-6.3; BLUEPRINT §3.7, §4.4 ``/models``).

Every route declares its action and runs the guard; data-touching routes (``model:train``,
``model:publish``) go through ``policy.check`` (a denial is audited ``authz.denied``); reads emit
``data.read``, writes ``data.create``; deployment decisions emit ``registry.deployment``
(``success`` or ``denied``). Rows of another tenant are 404 (RLS + app filter).

- ``/models`` (list, register), ``/models/{model_id}``;
- ``/models/{model_id}/versions`` (list, register: weights + training-set manifest, 6.1),
  ``/versions/{version}`` (``version`` = the version number), ``.../lineage`` (the model node's
  ancestry: every training subject's source recording), ``.../approvals`` and ``.../publish``
  (SEC-143), ``.../retrain`` (6.3), ``/models/{model_id}/retrains/{retrain_id}``;
- ``/models/{model_id}/deployments`` (6.2): a declared context; a refusal answers 403
  ``deployment-refused`` with machine ``code``/``reasons`` and the stored ``deployment_id``;
- ``/models/{model_id}/use-exceptions``: documented medical/safety exceptions (Art. 5(1)(f));
- ``/registry/vocabulary``: restrictions, settings, outputs and reason codes for forms.

Neutral field names only (SEC-090 surface test). Not intended for real-time or safety-critical
control (SEC-092).
"""

from __future__ import annotations

import base64
import binascii
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nf_platform.api.deps import Ctx, action_extra, emit_for, guard
from nf_platform.api.errors import NotFound
from nf_platform.api.provenance_routes import edge_out, node_out
from nf_platform.audit import log as audit
from nf_platform.auth.authorize import Forbidden
from nf_platform.db import models as m
from nf_platform.ingest.errors import IngestError
from nf_platform.provenance import api as prov
from nf_platform.registry import service as svc
from nf_platform.registry import vocab, weights
from nf_platform.registry.card import ModelCard

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
VersionNo = Annotated[int, Query(ge=1)]
MAX_LINEAGE = 10_000
HEX64 = r"^[0-9a-f]{64}$"


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


# ---------------------------------------------------------------- schemas
class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelIn(_In):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    card: ModelCard


class WeightsIn(_In):
    """EITHER a model derived object produced by a platform training job OR inline uploaded
    weights (base64; safetensors or ONNX only, SEC-061; never deserialised)."""

    derived_object_id: uuid.UUID | None = None
    format: Literal["safetensors", "onnx"] | None = None
    data_base64: str | None = Field(default=None, max_length=(weights.MAX_BYTES * 4) // 3 + 8)


class ManifestIn(_In):
    input_node_ids: list[uuid.UUID] = Field(
        max_length=svc.MAX_INPUTS, description="provenance entities the model was trained on"
    )
    subject_hashes: list[Annotated[str, Field(pattern=HEX64)]] | None = Field(
        default=None, description="optional; must equal the subjects resolved from the lineage"
    )
    shards: dict[str, Annotated[int, Field(ge=0)]] | None = Field(
        default=None, description="SISA: subject hash -> shard"
    )
    excluded_subject_hashes: list[Annotated[str, Field(pattern=HEX64)]] = Field(
        default_factory=list
    )
    recipe: str | None = Field(default=None, max_length=64)


class VersionIn(_In):
    weights: WeightsIn
    training_manifest: ManifestIn | None = Field(
        default=None, description="required: registering without a manifest fails"
    )
    pipeline_version_ids: list[Annotated[str, Field(max_length=300)]] = Field(
        default_factory=list, max_length=64, description="pv:sha256:... ids or name@version"
    )
    code_commit: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    intended_use: str = Field(min_length=1, max_length=4000)
    use_restrictions: list[Annotated[str, Field(max_length=64)]] = Field(
        default_factory=list, max_length=32
    )
    parent_version: int | None = Field(default=None, ge=1)


class ContextIn(_In):
    """The declared deployment context. ``setting`` takes the values listed by
    ``GET /v1/registry/vocabulary``; any other value is refused or rejected."""

    jurisdiction: str = Field(pattern=r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$", examples=["EU", "US-CO"])
    setting: str = Field(pattern=r"^[a-z][a-z_]{1,63}$", examples=["research"])
    purpose: str = Field(min_length=1, max_length=500)
    exception_id: uuid.UUID | None = None
    outputs: Literal["labels", "coarse_scores", "logits", "embeddings"] = "labels"
    rate_limit_per_minute: int = Field(default=60, ge=1, le=vocab.RATE_LIMIT_MAX)
    influences_behaviour: bool = False
    extra: dict[Annotated[str, Field(max_length=64)], Annotated[str, Field(max_length=500)]] = (
        Field(default_factory=dict, max_length=16)
    )


class DeploymentIn(_In):
    version: int = Field(ge=1)
    context: ContextIn


class ExceptionIn(_In):
    basis: Literal["medical", "safety"]
    jurisdiction: str = Field(pattern=r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$")
    setting: Literal["workplace", "education"]
    justification: str = Field(min_length=1, max_length=4000)
    evidence_ref: str = Field(min_length=1, max_length=500)


class RetrainIn(_In):
    recipe: str | None = Field(default=None, max_length=64)


class FlagOut(BaseModel):
    deletion_job_id: uuid.UUID
    created_at: datetime
    block_deployments: bool
    reason: str = Field(
        description="why the version is flagged: a training subject withdrew consent, or "
        "'unverifiable lineage (uploaded weights)' (AppSec M3)"
    )


WeightsSource = Literal["platform", "upload"]
_WS_DESC = (
    "platform: trained on the platform (exact lineage); upload: uploaded weights whose training "
    "lineage is the uploader's declaration (withdrawal propagation is conservative, four-eyes)"
)


class ManifestSummary(BaseModel):
    schema_id: str
    n_subjects: int
    n_source_recordings: int
    n_inputs: int
    n_excluded_subjects: int
    n_shards: int | None
    recipe: str | None


class VersionSummary(BaseModel):
    id: uuid.UUID
    version: int
    visibility: str
    weights_source: WeightsSource = Field(description=_WS_DESC)
    created_at: datetime
    retrain_required: bool
    deployments_blocked: bool


class VersionOut(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    version: int
    derived_object_id: uuid.UUID
    weights_source: WeightsSource = Field(description=_WS_DESC)
    weights_format: str
    weights_sha256: str
    prov_node_id: uuid.UUID
    manifest_sha256: str
    manifest_summary: ManifestSummary
    manifest: dict[str, Any] | None = Field(
        default=None, description="full manifest (hashed subject IDs) with include_manifest=true"
    )
    pipeline_version_ids: list[str]
    code_commit: str
    intended_use: str
    use_restrictions: list[str]
    recipe: str | None
    parent_version_id: uuid.UUID | None
    parent_version: int | None
    visibility: str
    published_at: datetime | None
    created_by: str
    created_at: datetime
    retrain_required: bool
    deployments_blocked: bool
    taint: list[FlagOut]


class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    card: ModelCard
    card_sha256: str
    created_by: str
    created_at: datetime
    latest_version: VersionSummary | None
    retrain_required: bool


class ModelDetailOut(ModelOut):
    versions: list[VersionSummary]


class DeploymentOut(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    version_id: uuid.UUID
    version: int
    jurisdiction: str
    setting: str
    purpose: str
    context: dict[str, Any]
    exception_id: uuid.UUID | None
    state: Literal["approved", "refused"]
    effective_state: Literal["approved", "refused", "blocked"]
    reasons: list[str]
    requested_by: str
    created_at: datetime


class ExceptionOut(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    basis: str
    jurisdiction: str
    setting: str
    justification: str
    evidence_ref: str
    recorded_by: str
    created_at: datetime


class ApprovalOut(BaseModel):
    version_id: uuid.UUID
    approver_id: str
    approver_roles: list[str]
    created_at: datetime


class RetrainOut(BaseModel):
    id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID | None
    state: str
    recipe: str | None
    new_version_id: uuid.UUID | None
    n_excluded_subjects: int
    requested_by: str
    requested_at: datetime
    finished_at: datetime | None
    error: str | None


class ModelLineageOut(BaseModel):
    root: uuid.UUID
    direction: str
    depth: int | None
    truncated: bool
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]
    n_training_subjects: int


class RestrictionOut(BaseModel):
    code: str
    description: str


class VocabularyOut(BaseModel):
    restrictions: list[RestrictionOut]
    settings: list[str]
    outputs: list[str]
    allowed_outputs: list[str]
    reason_codes: list[str]
    statement: str


# ---------------------------------------------------------------- helpers
@contextmanager
def _errors(ctx: Ctx) -> Iterator[None]:
    """RegistryError -> problem+json; policy denials are audited (``authz.denied``)."""
    try:
        yield
    except svc.RegistryError as e:
        if e.status == 404:
            raise NotFound(e.detail) from e
        extra = {"code": e.code} if e.code else None
        title = {403: "Forbidden", 409: "Conflict"}.get(e.status, "Invalid request")
        raise IngestError(e.status, "registry", title, e.detail, extra=extra) from e
    except Forbidden as e:
        emit_for(
            ctx.principal,
            audit.AUTHZ_DENIED,
            "denied",
            action=ctx.action,
            resource_type="model",
            request_id=ctx.request_id,
            details={"reason": e.reason, "method": ctx.method, "route": ctx.route},
        )
        raise


def _summary(doc: dict[str, Any]) -> ManifestSummary:
    return ManifestSummary(
        schema_id=str(doc.get("schema")),
        n_subjects=int(doc.get("n_subjects", 0)),
        n_source_recordings=int(doc.get("n_source_recordings", 0)),
        n_inputs=len(doc.get("inputs", [])),
        n_excluded_subjects=len(doc.get("excluded_subjects", [])),
        n_shards=len(set(doc["shards"].values())) if doc.get("shards") else None,
        recipe=doc.get("recipe"),
    )


def _vsummary(s: Session, v: m.ModelVersion) -> VersionSummary:
    flags = svc.taint(s, v)
    return VersionSummary(
        id=v.id,
        version=v.version,
        visibility=v.visibility,
        weights_source=svc.weights_source(s, v),
        created_at=v.created_at,
        retrain_required=bool(flags),
        deployments_blocked=any(f.block_deployments for f in flags),
    )


def _vout(s: Session, v: m.ModelVersion, *, include_manifest: bool = False) -> VersionOut:
    flags = svc.taint(s, v)
    parent_no = None
    if v.parent_version_id is not None:
        parent_no = s.scalar(
            select(m.ModelVersion.version).where(m.ModelVersion.id == v.parent_version_id)
        )
    return VersionOut(
        id=v.id,
        model_id=v.model_id,
        version=v.version,
        derived_object_id=v.derived_object_id,
        weights_source=svc.weights_source(s, v),
        weights_format=v.weights_format,
        weights_sha256=v.weights_sha256,
        prov_node_id=v.prov_node_id,
        manifest_sha256=v.manifest_sha256,
        manifest_summary=_summary(v.manifest),
        manifest=v.manifest if include_manifest else None,
        pipeline_version_ids=list(v.pipeline_version_ids),
        code_commit=v.code_commit,
        intended_use=v.intended_use,
        use_restrictions=list(v.use_restrictions),
        recipe=v.recipe,
        parent_version_id=v.parent_version_id,
        parent_version=parent_no,
        visibility=v.visibility,
        published_at=v.published_at,
        created_by=v.created_by,
        created_at=v.created_at,
        retrain_required=bool(flags),
        deployments_blocked=any(f.block_deployments for f in flags),
        taint=[FlagOut(**f.__dict__) for f in flags],
    )


def _versions(s: Session, model_id: uuid.UUID) -> list[m.ModelVersion]:
    return list(
        s.scalars(
            select(m.ModelVersion)
            .where(m.ModelVersion.model_id == model_id)
            .order_by(m.ModelVersion.version)
        )
    )


def _mout(s: Session, row: m.Model, *, detail: bool = False) -> ModelOut:
    vs = [_vsummary(s, v) for v in _versions(s, row.id)]
    base = {
        "id": row.id,
        "name": row.name,
        "card": ModelCard.model_validate(row.card),
        "card_sha256": row.card_sha256,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "latest_version": vs[-1] if vs else None,
        "retrain_required": any(v.retrain_required for v in vs),
    }
    return ModelDetailOut(**base, versions=vs) if detail else ModelOut(**base)


def _dout(s: Session, d: m.ModelDeployment, number: int, blocked: bool) -> DeploymentOut:
    return DeploymentOut(
        id=d.id,
        model_id=d.model_id,
        version_id=d.version_id,
        version=number,
        jurisdiction=d.jurisdiction,
        setting=d.setting,
        purpose=d.purpose,
        context=d.context,
        exception_id=d.exception_id,
        state=d.state,  # type: ignore[arg-type]
        effective_state=svc.effective_state(s, d, blocked),  # type: ignore[arg-type]
        reasons=list(d.reasons),
        requested_by=d.requested_by,
        created_at=d.created_at,
    )


def _rout(s: Session, r: m.ModelRetrain) -> RetrainOut:
    job = s.scalar(select(m.Job).where(m.Job.id == r.job_id)) if r.job_id else None
    return RetrainOut(
        id=r.id,
        version_id=r.version_id,
        job_id=r.job_id,
        state=r.state,
        recipe=(job.payload or {}).get("recipe") if job else None,
        new_version_id=r.new_version_id,
        n_excluded_subjects=len(r.excluded_subject_hashes),
        requested_by=r.requested_by,
        requested_at=r.requested_at,
        finished_at=r.finished_at,
        error=r.error,
    )


def _read(ctx: Ctx, resource: str, rid: Any = None, count: int | None = None) -> None:
    extra = {} if count is None else {"count": count}
    ctx.audit(audit.DATA_READ, resource_type=resource, resource_id=rid, **extra)


def _created(ctx: Ctx, resource: str, rid: Any) -> None:
    ctx.audit(audit.DATA_CREATE, resource_type=resource, resource_id=rid)


# ---------------------------------------------------------------- vocabulary
@_route("GET", "/registry/vocabulary", "model:read", response_model=VocabularyOut)
def get_vocabulary(ctx: CtxDep):
    out = VocabularyOut(
        restrictions=[RestrictionOut(code=k, description=v) for k, v in vocab.RESTRICTIONS.items()],
        settings=sorted(vocab.SETTINGS - vocab.CONTROL_SETTINGS),
        outputs=list(vocab.OUTPUTS),
        allowed_outputs=sorted(vocab.ALLOWED_OUTPUTS),
        reason_codes=[
            vocab.R_CONTROL,
            vocab.R_5_1_F,
            vocab.R_5_1_G,
            vocab.R_5_1_A,
            vocab.R_RESEARCH_ONLY,
            vocab.R_NO_CLINICAL,
            vocab.R_OUTPUTS,
            vocab.R_RETRAIN,
            vocab.R_EXCEPTION,
            vocab.R_UPLOAD_APPROVAL,
        ],
        statement=vocab.CONTROL_STATEMENT,
    )
    _read(ctx, "registry_vocabulary")
    return out


# ---------------------------------------------------------------- models
@_route("POST", "/models", "model:create", status_code=201, response_model=ModelDetailOut)
def register_model(body: ModelIn, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        row = svc.register_model(s, ctx.principal, name=body.name, card=body.card)
        out = _mout(s, row, detail=True)
    _created(ctx, "model", out.id)
    return out


@_route("GET", "/models", "model:read", response_model=list[ModelOut])
def list_models(ctx: CtxDep, limit: Limit = 50, offset: Offset = 0):
    with ctx.session() as s:
        q = select(m.Model).order_by(m.Model.created_at, m.Model.id).limit(limit).offset(offset)
        rows = [_mout(s, r) for r in s.scalars(q)]
    _read(ctx, "model", count=len(rows))
    return rows


@_route("GET", "/models/{model_id}", "model:read", response_model=ModelDetailOut)
def get_model(model_id: uuid.UUID, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        row = svc.get_model(s, model_id)
        ctx.check_tenant(row)
        out = _mout(s, row, detail=True)
    _read(ctx, "model", model_id)
    return out


# ---------------------------------------------------------------- versions (6.1)
def _weights(body: WeightsIn) -> svc.ObjectRef:
    data = None
    if body.data_base64 is not None:
        try:
            data = base64.b64decode(body.data_base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise svc.RegistryError(422, "weights: data_base64 is not base64") from e
    return svc.ObjectRef(derived_object_id=body.derived_object_id, data=data, format=body.format)


@_route(
    "POST",
    "/models/{model_id}/versions",
    "model:train",
    status_code=201,
    response_model=VersionOut,
)
def register_version(model_id: uuid.UUID, body: VersionIn, request: Request, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        man = body.training_manifest
        parent = None
        if body.parent_version is not None:
            parent = svc.get_version(s, model_id, body.parent_version).id
        row = svc.register_version(
            s,
            ctx.principal,
            model_id,
            weights_object=_weights(body.weights),
            training_manifest=None
            if man is None
            else svc.TrainingManifest(
                input_node_ids=tuple(man.input_node_ids),
                subject_hashes=None if man.subject_hashes is None else tuple(man.subject_hashes),
                shards=man.shards,
                excluded_subject_hashes=tuple(man.excluded_subject_hashes),
                recipe=man.recipe,
            ),
            pipeline_version_ids=body.pipeline_version_ids,
            code_commit=body.code_commit,
            intended_use=body.intended_use,
            use_restrictions=body.use_restrictions,
            parent_version_id=parent,
            storage=request.app.state.storage,
        )
        out = _vout(s, row)
    _created(ctx, "model_version", out.id)
    return out


@_route("GET", "/models/{model_id}/versions", "model:read", response_model=list[VersionOut])
def list_versions(model_id: uuid.UUID, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        svc.get_model(s, model_id)
        rows = [_vout(s, v) for v in _versions(s, model_id)]
    _read(ctx, "model_version", count=len(rows))
    return rows


@_route("GET", "/models/{model_id}/versions/{version}", "model:read", response_model=VersionOut)
def get_version(model_id: uuid.UUID, version: int, ctx: CtxDep, include_manifest: bool = False):
    with _errors(ctx), ctx.session() as s:
        row = svc.get_version(s, model_id, version)
        ctx.check_tenant(row)
        out = _vout(s, row, include_manifest=include_manifest)
    _read(ctx, "model_version", out.id)
    return out


@_route(
    "GET",
    "/models/{model_id}/versions/{version}/lineage",
    "model:read",
    response_model=ModelLineageOut,
)
def get_version_lineage(model_id: uuid.UUID, version: int, ctx: CtxDep):
    """The ancestry of the version's model node: every training input, run and source recording
    (and its raw file) of every training subject (6.1)."""
    with _errors(ctx), ctx.session() as s:
        row = svc.get_version(s, model_id, version)
        g = prov.lineage(s, row.prov_node_id, "up", None, max_nodes=MAX_LINEAGE)
        n_subjects = len(svc.lineage_subjects(s, row))
        vid = row.id
    _read(ctx, "model_version", vid, count=len(g.nodes))
    return ModelLineageOut(
        root=g.root,
        direction=g.direction,
        depth=g.depth,
        truncated=g.truncated,
        nodes=[node_out(n, depth=True) for n in g.nodes],
        edges=[edge_out(e) for e in g.edges],
        n_training_subjects=n_subjects,
    )


# ---------------------------------------------------------------- publication (SEC-143)
@_route(
    "POST",
    "/models/{model_id}/versions/{version}/approvals",
    "model:approve",
    status_code=201,
    response_model=list[ApprovalOut],
)
def approve_version(model_id: uuid.UUID, version: int, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        row = svc.get_version(s, model_id, version)
        svc.approve(s, ctx.principal, row)
        out = [
            ApprovalOut(
                version_id=a.version_id,
                approver_id=a.approver_id,
                approver_roles=list(a.approver_roles),
                created_at=a.created_at,
            )
            for a in svc.approvals(s, row)
        ]
        vid = row.id
    _created(ctx, "model_approval", vid)
    return out


@_route(
    "POST",
    "/models/{model_id}/versions/{version}/publish",
    "model:publish",
    response_model=VersionOut,
)
def publish_version(model_id: uuid.UUID, version: int, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        row = svc.publish(s, ctx.principal, svc.get_version(s, model_id, version))
        out = _vout(s, row)
    ctx.audit(audit.ADMIN_ACTION, resource_type="model_version", resource_id=out.id)
    return out


# ---------------------------------------------------------------- retrain (6.3)
@_route(
    "POST",
    "/models/{model_id}/versions/{version}/retrain",
    "model:train",
    status_code=202,
    response_model=RetrainOut,
)
def request_retrain(model_id: uuid.UUID, version: int, body: RetrainIn, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        row = svc.get_version(s, model_id, version)
        rt, _created_now = svc.request_retrain(s, ctx.principal, row, recipe=body.recipe)
        out = _rout(s, rt)
    _created(ctx, "model_retrain", out.id)
    return out


@_route("GET", "/models/{model_id}/retrains/{retrain_id}", "model:read", response_model=RetrainOut)
def get_retrain(model_id: uuid.UUID, retrain_id: uuid.UUID, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        svc.get_model(s, model_id)
        rt = s.scalar(select(m.ModelRetrain).where(m.ModelRetrain.id == retrain_id))
        if rt is None:
            raise NotFound("retrain")
        v = s.scalar(select(m.ModelVersion).where(m.ModelVersion.id == rt.version_id))
        if v is None or v.model_id != model_id:
            raise NotFound("retrain")
        out = _rout(s, rt)
    _read(ctx, "model_retrain", retrain_id)
    return out


# ---------------------------------------------------------------- deployments (6.2)
@_route(
    "POST",
    "/models/{model_id}/deployments",
    "model:deploy",
    status_code=201,
    response_model=DeploymentOut,
    responses={403: {"description": "refused (problem+json with code, reasons, deployment_id)"}},
)
def request_deployment(model_id: uuid.UUID, body: DeploymentIn, ctx: CtxDep):
    c = body.context
    context = svc.DeploymentContext(
        jurisdiction=c.jurisdiction,
        setting=c.setting,
        purpose=c.purpose,
        exception_id=c.exception_id,
        outputs=c.outputs,
        rate_limit_per_minute=c.rate_limit_per_minute,
        influences_behaviour=c.influences_behaviour,
        extra=c.extra,
    )
    with _errors(ctx), ctx.session() as s:
        v = svc.get_version(s, model_id, body.version)
        dep = svc.request_deployment(s, ctx.principal, v.id, context=context)
        out = _dout(s, dep, v.version, svc.deployments_blocked(s, v))
    # committed: a refusal is stored and audited (registry.deployment, denied) before answering
    if out.state == "refused":
        raise IngestError(
            403,
            "deployment-refused",
            "Deployment refused",
            "The declared context is prohibited for this model version: " + ", ".join(out.reasons),
            extra={"code": out.reasons[0], "reasons": out.reasons, "deployment_id": str(out.id)},
        )
    _created(ctx, "model_deployment", out.id)
    return out


@_route("GET", "/models/{model_id}/deployments", "model:read", response_model=list[DeploymentOut])
def list_deployments(
    model_id: uuid.UUID,
    ctx: CtxDep,
    version: VersionNo | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    with _errors(ctx), ctx.session() as s:
        svc.get_model(s, model_id)
        versions = {v.id: v for v in _versions(s, model_id)}
        blocked = {vid: svc.deployments_blocked(s, v) for vid, v in versions.items()}
        q = select(m.ModelDeployment).where(m.ModelDeployment.model_id == model_id)
        if version is not None:
            q = q.where(
                m.ModelDeployment.version_id.in_(
                    [vid for vid, v in versions.items() if v.version == version]
                )
            )
        q = q.order_by(m.ModelDeployment.created_at, m.ModelDeployment.id)
        rows = [
            _dout(s, d, versions[d.version_id].version, blocked[d.version_id])
            for d in s.scalars(q.limit(limit).offset(offset))
        ]
    _read(ctx, "model_deployment", count=len(rows))
    return rows


# ---------------------------------------------------------------- use exceptions (Art. 5(1)(f))
def _eout(r: m.ModelUseException) -> ExceptionOut:
    return ExceptionOut(
        id=r.id,
        model_id=r.model_id,
        basis=r.basis,
        jurisdiction=r.jurisdiction,
        setting=r.setting,
        justification=r.justification,
        evidence_ref=r.evidence_ref,
        recorded_by=r.recorded_by,
        created_at=r.created_at,
    )


@_route(
    "POST",
    "/models/{model_id}/use-exceptions",
    "model:exception",
    status_code=201,
    response_model=ExceptionOut,
)
def record_exception(model_id: uuid.UUID, body: ExceptionIn, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        row = svc.record_exception(
            s,
            ctx.principal,
            model_id,
            basis=body.basis,
            jurisdiction=body.jurisdiction,
            setting=body.setting,
            justification=body.justification,
            evidence_ref=body.evidence_ref,
        )
        out = _eout(row)
    _created(ctx, "model_use_exception", out.id)
    return out


@_route("GET", "/models/{model_id}/use-exceptions", "model:read", response_model=list[ExceptionOut])
def list_exceptions(model_id: uuid.UUID, ctx: CtxDep):
    with _errors(ctx), ctx.session() as s:
        svc.get_model(s, model_id)
        rows = [
            _eout(r)
            for r in s.scalars(
                select(m.ModelUseException)
                .where(m.ModelUseException.model_id == model_id)
                .order_by(m.ModelUseException.created_at, m.ModelUseException.id)
            )
        ]
    _read(ctx, "model_use_exception", count=len(rows))
    return rows
