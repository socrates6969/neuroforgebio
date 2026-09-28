"""v1 compliance-ledger endpoints (BUILD-GUIDE 5.1-5.5; BLUEPRINT §8.2-§8.4).

- 5.1 governance attributes: modality defaults, per-recording channel edits, a bulk editor, and
  derived-artifact attributes (effective = explicit or inherited through the lineage). Writes are
  data-steward/admin only (SEC-022, ``governance:write``); every change is audited with the old and
  new values (``governance.attributes``).
- 5.2 ``GET /v1/classifications`` and ``GET /v1/jurisdiction-rules``: never "not regulated", only
  "not matched by RuleSet vN"; every rule carries its review status and a draft badge.
- 5.3 consent documents and ``POST/GET /v1/subjects/{id}/consents`` (append-only ledger).
- 5.5 ``POST /v1/subjects/{id}/withdrawals`` (DeletionJob on the queue), ``GET
  /v1/deletion-jobs/{id}`` (state + signed certificate), the certificate public key, and the
  tenant's withdrawal policy.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import NotFound, problem
from nf_platform.db import models as m
from nf_platform.governance import attributes, certificate, consent, deletion, policy, rules
from nf_platform.provenance import api as prov

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]
AUDIT_ATTRS = "governance.attributes"
AUDIT_CONSENT = "governance.consent"
AUDIT_POLICY = "governance.policy"
TITLES = {404: "Not Found", 409: "Conflict", 422: "Unprocessable Content"}


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


def _err(request: Request, status: int, detail: str) -> JSONResponse:
    kind = {404: "not-found", 409: "conflict"}.get(status, "invalid-request")
    return problem(request, status, TITLES.get(status, "Error"), detail, kind=kind)


def _gov_error(request: Request, e: attributes.GovernanceError) -> JSONResponse:
    if e.not_found:
        return _err(request, 404, f"{e.detail} not found" if " " not in e.detail else e.detail)
    return _err(request, 422, e.detail)


def _tid(ctx: Ctx) -> uuid.UUID:
    return uuid.UUID(ctx.tenant_id)


# ---------------------------------------------------------------- schemas
Modality = Literal[*m.MODALITIES]
NervousSystem = Literal[*m.NERVOUS_SYSTEMS]
Scope = Literal[*m.CONSENT_SCOPES]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovValues(_Strict):
    modality: Modality | None = None
    nervous_system: NervousSystem | None = None
    derived_from_non_neural: bool | None = None


class ChannelEdit(GovValues):
    index: int = Field(ge=0)


class ChannelEditsIn(_Strict):
    changes: list[ChannelEdit] = Field(min_length=1, max_length=4096)
    reason: str | None = Field(default=None, max_length=500)


class BulkIn(_Strict):
    recording_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    modality: Modality | None = Field(default=None, description="only channels of this modality")
    set: GovValues
    reason: str | None = Field(default=None, max_length=500)


class ArtifactGovIn(_Strict):
    modalities: list[Modality] | None = None
    nervous_system: NervousSystem | None = None
    derived_from_non_neural: bool | None = None
    reason: str | None = Field(default=None, max_length=500)


class ConsentDocIn(_Strict):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    sha256: str = Field(min_length=64, max_length=64)
    uri: str | None = Field(default=None, max_length=500)


class ConsentDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: str
    sha256: str
    uri: str | None
    created_at: datetime


class ConsentIn(_Strict):
    kind: Literal["grant", "withdraw"] = "grant"
    scopes: list[Scope] = Field(min_length=1)
    document_id: uuid.UUID | None = None
    jurisdiction_basis: str | None = Field(default=None, max_length=100)
    evidence_ref: str | None = Field(
        default=None, max_length=500, description="e.g. the object key of the signed form"
    )


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    seq: int
    subject_id: uuid.UUID
    kind: str
    scopes: list[str]
    document_id: uuid.UUID | None
    document_sha256: str | None
    jurisdiction_basis: str | None
    collector_id: str
    evidence_ref: str | None
    recorded_at: datetime
    prev_hash: str | None
    record_hash: str


class WithdrawalIn(_Strict):
    evidence_ref: str | None = Field(default=None, max_length=500)


class DeletionOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    state: str
    aggregate_policy: str
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_s: float | None
    error: str | None
    certificate: dict[str, Any] | None


class TenantPolicyIn(_Strict):
    aggregate_on_withdrawal: Literal["rerun", "tombstone"]
    block_deployments_on_retrain: bool = True


def _deletion_out(d: m.DeletionJob) -> DeletionOut:
    return DeletionOut(
        id=d.id,
        subject_id=d.subject_id,
        state=d.state,
        aggregate_policy=d.aggregate_policy,
        requested_at=d.requested_at,
        started_at=d.started_at,
        finished_at=d.finished_at,
        duration_s=d.duration_s,
        error=d.error,
        certificate=d.certificate,
    )


def _audit_changes(ctx: Ctx, resource_type: str, rid: Any, changes: list[dict[str, Any]]) -> None:
    ctx.audit(
        AUDIT_ATTRS,
        resource_type=resource_type,
        resource_id=rid,
        changes=changes,
        count=len(changes),
    )


# ---------------------------------------------------------------- 5.1 attributes
@_route("GET", "/governance/modality-defaults", "governance:read")
def modality_defaults(ctx: CtxDep) -> dict[str, Any]:
    ctx.audit("data.read", resource_type="modality_defaults")
    return {
        "defaults": {
            mod: {"nervous_system": ns, "derived_from_non_neural": d}
            for mod, (ns, d) in attributes.MODALITY_DEFAULTS.items()
        },
        "note": "Defaults are a starting point for a data steward's review, not a legal judgement.",
    }


@_route("PATCH", "/recordings/{recording_id}/channels", "governance:write")
def edit_channels(recording_id: uuid.UUID, body: ChannelEditsIn, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            if s.scalar(select(m.Recording.id).where(m.Recording.id == recording_id)) is None:
                raise NotFound("recording")
            changes = attributes.update_channels(
                s,
                ctx.principal,
                recording_id,
                [c.model_dump(exclude_none=True) for c in body.changes],
            )
    except attributes.GovernanceError as e:
        return _gov_error(request, e)
    _audit_changes(ctx, "recording", recording_id, changes)
    return {"recording_id": str(recording_id), "changes": changes}


@_route("POST", "/governance/channels/bulk", "governance:write")
def bulk_edit(body: BulkIn, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            changes = attributes.bulk_update(
                s,
                ctx.principal,
                body.recording_ids,
                body.set.model_dump(exclude_none=True),
                modality=body.modality,
            )
    except attributes.GovernanceError as e:
        return _gov_error(request, e)
    _audit_changes(ctx, "channel", None, changes)
    return {"changes": changes, "count": len(changes)}


@_route("GET", "/artifacts/{node_id}/governance", "governance:read")
def get_artifact_governance(node_id: uuid.UUID, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            eff = attributes.node_attributes(s, node_id)
    except prov.NodeNotFound as e:
        raise NotFound("provenance node") from e
    except attributes.GovernanceError as e:
        return _gov_error(request, e)
    ctx.audit("data.read", resource_type="provenance_node", resource_id=node_id)
    return {"node_id": str(node_id), **eff}


@_route("PUT", "/artifacts/{node_id}/governance", "governance:write")
def put_artifact_governance(node_id: uuid.UUID, body: ArtifactGovIn, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            changes = attributes.set_node_attributes(
                s,
                ctx.principal,
                node_id,
                body.model_dump(exclude_none=True, exclude={"reason"}),
                body.reason,
            )
            eff = attributes.node_attributes(s, node_id)
    except prov.NodeNotFound as e:
        raise NotFound("provenance node") from e
    except attributes.GovernanceError as e:
        return _gov_error(request, e)
    _audit_changes(ctx, "provenance_node", node_id, changes)
    return {"node_id": str(node_id), **eff, "changes": changes}


# ---------------------------------------------------------------- 5.2 classification
@_route("GET", "/jurisdiction-rules", "classification:read")
def jurisdiction_rules(ctx: CtxDep) -> dict[str, Any]:
    rs = rules.current()
    ctx.audit("data.read", resource_type="ruleset", resource_id=rs.content_sha256)
    return {
        "version": rs.version,
        "label": rs.label,
        "content_sha256": rs.content_sha256,
        "disclaimer": rules.DISCLAIMER,
        "rules": [r.public() for r in rs.rules],
    }


@_route("GET", "/classifications", "classification:read")
def classifications(
    request: Request,
    ctx: CtxDep,
    recording_id: uuid.UUID | None = None,
    node_id: uuid.UUID | None = None,
):
    """Classification per channel of a recording (plus the recording's strictest summary), or per
    derived artifact (``node_id``, inherited through the lineage)."""
    if (recording_id is None) == (node_id is None):
        return _err(request, 422, "give exactly one of recording_id or node_id")
    with ctx.session() as s:
        if recording_id is not None:
            rec = s.scalar(select(m.Recording).where(m.Recording.id == recording_id))
            if rec is None:
                raise NotFound("recording")
            ctx.check_tenant(rec)
            chans = s.scalars(
                select(m.Channel)
                .where(m.Channel.recording_id == recording_id)
                .order_by(m.Channel.index)
            ).all()
            out = {
                "recording_id": str(recording_id),
                "channels": [
                    {
                        "index": c.index,
                        "name": c.name,
                        "classification": rules.classify(
                            {
                                "nervous_system": c.nervous_system,
                                "derived_from_non_neural": c.derived_from_non_neural,
                                "modality": c.modality,
                            }
                        ),
                    }
                    for c in chans
                ],
            }
            summ = attributes.recording_attributes(s, recording_id)
        else:
            try:
                summ = attributes.node_attributes(s, node_id)
            except (prov.NodeNotFound, attributes.GovernanceError) as e:
                raise NotFound("provenance node") from e
            out = {"node_id": str(node_id)}
        if summ is not None:
            out["attributes"] = summ
            out["classification"] = rules.classify(
                {
                    "nervous_system": summ["nervous_system"],
                    "derived_from_non_neural": summ["derived_from_non_neural"],
                    "modality": summ["modalities"],
                }
            )
    ctx.audit(
        "data.read",
        resource_type="recording" if recording_id else "provenance_node",
        resource_id=recording_id or node_id,
    )
    return out


# ---------------------------------------------------------------- 5.3 consent
@_route(
    "POST", "/consent-documents", "consent:create", status_code=201, response_model=ConsentDocOut
)
def create_consent_document(body: ConsentDocIn, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            row, created = consent.create_document(
                s,
                ctx.principal,
                name=body.name,
                version=body.version,
                sha256=body.sha256,
                uri=body.uri,
            )
            out = ConsentDocOut.model_validate(row)
    except consent.ConsentError as e:
        return _err(request, e.status, e.detail)
    ctx.audit(
        AUDIT_CONSENT,
        resource_type="consent_document",
        resource_id=out.id,
        status="created" if created else "exists",
    )
    if not created:
        return JSONResponse(out.model_dump(mode="json"), status_code=200)
    return out


@_route("GET", "/consent-documents", "consent:read", response_model=list[ConsentDocOut])
def list_consent_documents(ctx: CtxDep, limit: Limit = 100, offset: Offset = 0):
    with ctx.session() as s:
        q = select(m.ConsentDocument).order_by(m.ConsentDocument.created_at, m.ConsentDocument.id)
        rows = [ConsentDocOut.model_validate(r) for r in s.scalars(q.limit(limit).offset(offset))]
    ctx.audit("data.read", resource_type="consent_document", count=len(rows))
    return rows


@_route(
    "POST",
    "/subjects/{subject_id}/consents",
    "consent:create",
    status_code=201,
    response_model=ConsentOut,
)
def add_consent(subject_id: uuid.UUID, body: ConsentIn, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            row = consent.append(
                s,
                ctx.principal,
                subject_id,
                kind=body.kind,
                scopes=body.scopes,
                document_id=body.document_id,
                jurisdiction_basis=body.jurisdiction_basis,
                evidence_ref=body.evidence_ref,
            )
            out = ConsentOut.model_validate(row)
    except consent.ConsentError as e:
        return _err(request, e.status, e.detail)
    ctx.audit(
        AUDIT_CONSENT,
        resource_type="subject",
        resource_id=subject_id,
        scopes=out.scopes,
        status=out.kind,
        seq=out.seq,
    )
    return out


@_route("GET", "/subjects/{subject_id}/consents", "consent:read")
def get_consents(subject_id: uuid.UUID, ctx: CtxDep) -> dict[str, Any]:
    with ctx.session() as s:
        if s.scalar(select(m.Subject.id).where(m.Subject.id == subject_id)) is None:
            raise NotFound("subject")
        recs = consent.records_for(s, subject_id)
        out = [ConsentOut.model_validate(r).model_dump(mode="json") for r in recs]
        current = sorted(consent.fold(recs))
        withdrawn = consent.withdrawn(recs)
    ctx.audit("data.read", resource_type="subject", resource_id=subject_id, count=len(out))
    return {
        "subject_id": str(subject_id),
        "current_scopes": current,
        "withdrawn": withdrawn,
        "records": out,
    }


# ---------------------------------------------------------------- 5.5 withdrawals
@_route(
    "POST",
    "/subjects/{subject_id}/withdrawals",
    "withdrawal:create",
    status_code=202,
    response_model=DeletionOut,
)
def withdraw(subject_id: uuid.UUID, body: WithdrawalIn, request: Request, ctx: CtxDep):
    try:
        with ctx.session() as s:
            row, created = deletion.request_withdrawal(
                s, ctx.principal, subject_id, evidence_ref=body.evidence_ref
            )
            out = _deletion_out(row)
    except (deletion.DeletionError, consent.ConsentError) as e:
        return _err(request, e.status, e.detail)
    ctx.audit(
        deletion.AUDIT_TYPE,
        resource_type="subject",
        resource_id=subject_id,
        phase="requested" if created else "already_requested",
        status=out.state,
    )
    return out


@_route("GET", "/deletion-jobs/{deletion_id}", "withdrawal:read", response_model=DeletionOut)
def get_deletion(deletion_id: uuid.UUID, ctx: CtxDep):
    with ctx.session() as s:
        row = s.scalar(select(m.DeletionJob).where(m.DeletionJob.id == deletion_id))
        if row is None:
            raise NotFound("deletion job")
        ctx.check_tenant(row)
        out = _deletion_out(row)
    ctx.audit("data.read", resource_type="deletion_job", resource_id=deletion_id)
    return out


@_route("GET", "/governance/certificate-key", "withdrawal:read")
def certificate_key(ctx: CtxDep) -> dict[str, str]:
    ctx.audit("data.read", resource_type="certificate_key")
    return certificate.public_key()


@_route("GET", "/governance/tenant-policy", "governance:read")
def get_tenant_policy(ctx: CtxDep) -> dict[str, Any]:
    with ctx.session() as s:
        row = s.scalar(select(m.TenantPolicy))
        out = {
            "aggregate_on_withdrawal": row.aggregate_on_withdrawal if row else "rerun",
            "block_deployments_on_retrain": row.block_deployments_on_retrain if row else True,
            "default": row is None,
        }
    ctx.audit("data.read", resource_type="tenant_policy")
    return out


@_route("PUT", "/governance/tenant-policy", "governance:admin")
def put_tenant_policy(body: TenantPolicyIn, ctx: CtxDep) -> dict[str, Any]:
    with ctx.session() as s:
        row = s.get(m.TenantPolicy, _tid(ctx))
        before = None if row is None else row.aggregate_on_withdrawal
        if row is None:
            row = m.TenantPolicy(tenant_id=_tid(ctx))
            s.add(row)
        row.aggregate_on_withdrawal = body.aggregate_on_withdrawal
        row.block_deployments_on_retrain = body.block_deployments_on_retrain
        row.updated_by = ctx.principal.id
        row.updated_at = datetime.now(UTC)
    ctx.audit(
        AUDIT_POLICY,
        resource_type="tenant_policy",
        changes=[
            {"field": "aggregate_on_withdrawal", "old": before, "new": body.aggregate_on_withdrawal}
        ],
    )
    return {**body.model_dump(), "default": False}


# re-exported for the route-enumeration test
DATA_ACTIONS = policy.DATA_ACTIONS
