"""FDA Evidence Kit export (BUILD-GUIDE 5.8): ``POST /v1/exports/fda-evidence``.

Authorize (action ``evidence:export``: owner, admin, data-steward, auditor; not available to API
keys) -> resolve the chosen dataset/model provenance node in the caller's tenant (404 otherwise;
RLS + app filter) -> ``policy.check`` -> build the zip (``nf_platform.evidence.kit``) -> audit
``data.export``. The kit is labelled "scaffold, not a submission" in every document.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import NotFound
from nf_platform.api.routes import enforce
from nf_platform.audit import log as audit
from nf_platform.evidence import kit
from nf_platform.governance import policy as gpolicy
from nf_platform.provenance import api as prov
from nf_platform.provenance import export

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
ACTION = "evidence:export"
MAX_NODES = 10_000


class EvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: uuid.UUID = Field(description="provenance node of the dataset/model to document")
    release: str | None = Field(
        None, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", description="release label"
    )


@router.post(
    "/exports/fda-evidence",
    openapi_extra=action_extra(ACTION),
    dependencies=[Depends(guard)],
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "the kit (zip)"}},
)
def export_fda_evidence(body: EvidenceIn, request: Request, ctx: CtxDep) -> Response:
    with ctx.session() as s:
        try:
            g = prov.lineage(s, body.node_id, "up", None, max_nodes=MAX_NODES)
        except prov.NodeNotFound as e:
            raise NotFound("provenance node") from e
    enforce(
        ctx,
        ACTION,
        gpolicy.Resource(
            "provenance_node", ctx.tenant_id, str(body.node_id), node_ids=(body.node_id,)
        ),
    )
    inputs = getattr(request.app.state, "evidence_inputs", None) or kit.inputs_from_env()
    if body.release:
        inputs = kit.KitInputs(inputs.repo_root, inputs.junit, inputs.sbom, body.release)
    data, contents = kit.build(
        inputs,
        tenant_id=ctx.tenant_id,
        node_id=str(body.node_id),
        prov_json=export.to_prov_json(g),
    )
    digest = hashlib.sha256(data).hexdigest()
    ctx.audit(
        audit.DATA_EXPORT,
        resource_type="provenance_node",
        resource_id=body.node_id,
        format="fda-evidence-kit-v0",
        count=len(g.nodes),
        sha256=digest,
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="fda-evidence-kit-{digest[:12]}.zip"',
            "X-NF-Label": "scaffold-not-a-submission",
            "X-NF-Flagged-Requirements": str(len(contents.flagged)),
        },
    )
