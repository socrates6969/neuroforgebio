"""SOUP/OTS export per model version (BUILD-GUIDE 6.5; m6-sisa).

- ``PUT /v1/models/{model_id}/versions/{version}/sbom`` (action ``model:sbom-attach``): attach the
  CycloneDX JSON SBOM of the container the version runs in (one per version; re-attaching
  replaces it). Audited ``data.create`` with the SBOM's sha256 and component count.
- ``GET /v1/models/{model_id}/versions/{version}/soup`` (action ``model:soup-export``): the
  deterministic ``nf.model-soup/v1`` document (``nf_platform.registry.soup``): versions, every
  dependency of the attached SBOM, known anomalies, test evidence, intended use, restrictions and
  "Not intended for real-time or safety-critical control." (SEC-092). ``policy.check`` on the
  version's provenance node; audited ``data.export`` with the document's sha256.

Another tenant's model is 404 (RLS + app filter). Labelled "scaffold, not a submission" like the
5.8 evidence kit. Neutral field names only (SEC-090 surface test).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Request, Response
from pydantic import BaseModel

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import NotFound
from nf_platform.api.routes import enforce
from nf_platform.audit import log as audit
from nf_platform.db import models as m
from nf_platform.evidence import kit
from nf_platform.governance import policy as gpolicy
from nf_platform.ingest.errors import IngestError
from nf_platform.registry import service as svc
from nf_platform.registry import soup

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
VersionNo = Annotated[int, Path(ge=1)]
EXPORT = "model:soup-export"
ATTACH = "model:sbom-attach"
MAX_SBOM_BYTES = 16 * 1024 * 1024
MAX_COMPONENTS = 100_000


class SbomOut(BaseModel):
    version_id: uuid.UUID
    sha256: str
    spec_version: str
    component_count: int
    attached_by: str
    attached_at: datetime


def _version(ctx: Ctx, s, model_id: uuid.UUID, version: int) -> tuple[m.Model, m.ModelVersion]:
    try:
        mdl = svc.get_model(s, model_id)
        row = svc.get_version(s, model_id, version)
    except svc.RegistryError as e:
        raise NotFound(e.detail) from e
    ctx.check_tenant(row)
    return mdl, row


def _training(s, row: m.ModelVersion) -> dict[str, Any]:
    obj = s.get(m.DerivedObject, row.derived_object_id)
    params = dict(obj.params or {}) if obj is not None else {}
    man = dict(row.manifest or {})
    out: dict[str, Any] = {
        "algorithm": str(params.get("algorithm") or row.weights_format or "unknown"),
        "subject_count": man.get("n_subjects"),
        "weights_source": svc.weights_source(s, row),  # AppSec M3
    }
    sisa = params.get("sisa")
    if row.recipe == "sisa" and isinstance(sisa, dict):
        cfg = sisa.get("config") or {}
        out["sisa"] = {
            "shards": cfg.get("shards"),
            "slices": cfg.get("slices"),
            "withdrawn_subjects": len(sisa.get("withdrawn") or ()),
        }
    return out


@router.put(
    "/models/{model_id}/versions/{version}/sbom",
    openapi_extra=action_extra(ATTACH),
    dependencies=[Depends(guard)],
    response_model=SbomOut,
)
def attach_sbom(
    model_id: uuid.UUID,
    version: VersionNo,
    ctx: CtxDep,
    body: Annotated[dict[str, Any], Body(description="CycloneDX JSON SBOM of the container")],
) -> SbomOut:
    try:
        deps = soup.sbom_dependencies(body)
    except soup.SoupError as e:
        raise IngestError(422, "sbom", "Invalid SBOM", str(e)) from e
    if len(deps) > MAX_COMPONENTS:
        raise IngestError(413, "sbom", "SBOM too large", f"more than {MAX_COMPONENTS} components")
    data = soup.dumps(body)
    if len(data) > MAX_SBOM_BYTES:
        raise IngestError(413, "sbom", "SBOM too large", f"more than {MAX_SBOM_BYTES} bytes")
    digest = hashlib.sha256(data).hexdigest()
    with ctx.session() as s:
        _mdl, row = _version(ctx, s, model_id, version)
        sb = s.get(m.ModelVersionSbom, (row.tenant_id, row.id))
        sb = sb or m.ModelVersionSbom(tenant_id=row.tenant_id, version_id=row.id)
        sb.sbom = body
        sb.sha256 = digest
        sb.spec_version = str(body.get("specVersion") or "unknown")
        sb.component_count = len(deps)
        sb.attached_by = ctx.principal.id
        sb.attached_at = datetime.now(UTC)
        s.add(sb)
        s.flush()
        out = SbomOut(
            version_id=row.id,
            sha256=digest,
            spec_version=sb.spec_version,
            component_count=len(deps),
            attached_by=sb.attached_by,
            attached_at=sb.attached_at,
        )
    ctx.audit(
        audit.DATA_CREATE,
        resource_type="model_version_sbom",
        resource_id=out.version_id,
        format="cyclonedx-json",
        count=out.component_count,
        sha256=digest,
    )
    return out


@router.get(
    "/models/{model_id}/versions/{version}/soup",
    openapi_extra=action_extra(EXPORT),
    dependencies=[Depends(guard)],
    response_class=Response,
    responses={200: {"content": {"application/json": {}}, "description": "nf.model-soup/v1"}},
)
def export_soup(model_id: uuid.UUID, version: VersionNo, request: Request, ctx: CtxDep) -> Response:
    with ctx.session() as s:
        mdl, row = _version(ctx, s, model_id, version)
        enforce(
            ctx,
            EXPORT,
            gpolicy.Resource(
                "model_version", ctx.tenant_id, str(row.id), node_ids=(row.prov_node_id,)
            ),
            session=s,
        )
        v = {
            "id": str(row.id),
            "version": row.version,
            "created_at": row.created_at.isoformat(),
            "code_commit": row.code_commit,
            "pipeline_version_ids": sorted(row.pipeline_version_ids),
            "weights_sha256": row.weights_sha256,
            "parent_version_id": str(row.parent_version_id) if row.parent_version_id else None,
            "prov_node_id": str(row.prov_node_id),
            "intended_use": row.intended_use,
            "use_restrictions": list(row.use_restrictions),
            "training": _training(s, row),
        }
        model = {"id": str(mdl.id), "name": mdl.name, "card": mdl.card}
        flags = tuple(
            {
                "deletion_job_id": str(f.deletion_job_id),
                "created_at": f.created_at.isoformat(),
                "block_deployments": f.block_deployments,
                "reason": f.reason,
            }
            for f in svc.taint(s, row)
        )
        sb = s.get(m.ModelVersionSbom, (row.tenant_id, row.id))
        sbom, sbom_sha = (sb.sbom, sb.sha256) if sb is not None else (None, None)
    base = getattr(request.app.state, "evidence_inputs", None) or kit.inputs_from_env()
    data = soup.build(
        soup.SoupInputs(
            model=model,
            version=v,
            retrain_flags=flags,
            sbom=sbom,
            sbom_sha256=sbom_sha,
            repo_root=base.repo_root,
            junit=base.junit,
            release=base.release,
        )
    )
    digest = hashlib.sha256(data).hexdigest()
    ctx.audit(
        audit.DATA_EXPORT,
        resource_type="model_version",
        resource_id=v["id"],
        format="model-soup-v1",
        count=0 if sbom is None else len(soup.sbom_dependencies(sbom)),
        sha256=digest,
    )
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="model-soup-{digest[:12]}.json"',
            "X-NF-Label": "scaffold-not-a-submission",
        },
    )
