"""v1 provenance endpoints (BUILD-GUIDE 3.1, 3.7; BLUEPRINT §3.6, §4.4).

``GET /v1/provenance/{node_id}``, ``.../lineage?direction=up|down&depth=``,
``.../export?format=prov-json|openlineage``. Every route declares its action and runs the guard;
reads emit ``data.read``, exports ``data.export`` (2.8). Nodes of another tenant are 404 (RLS +
app filter). Graphs are capped at ``MAX_NODES`` nodes (``truncated`` is then true).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from nf_platform.api.deps import Ctx, action_extra, guard
from nf_platform.api.errors import NotFound
from nf_platform.api.routes import enforce
from nf_platform.api.schemas import LineageOut, ProvExportOut, ProvNodeDetailOut
from nf_platform.audit import log as audit
from nf_platform.governance import policy as gpolicy
from nf_platform.provenance import api as prov
from nf_platform.provenance import export

router = APIRouter(prefix="/v1")
CtxDep = Annotated[Ctx, Depends(guard)]
Direction = Annotated[Literal["up", "down"], Query(description="up = ancestry, down = descendants")]
Depth = Annotated[int | None, Query(ge=0, le=1000, description="max hops (default: unbounded)")]
MAX_NODES = 10_000
NEIGHBOUR_LIMIT = 200


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


def node_out(n: prov.GraphNode, *, depth: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(n.id),
        "kind": n.kind.value,
        "type": n.type,
        "ref_id": n.ref_id,
        "content_hash": n.content_hash,
        "node_hash": n.node_hash,
        "attrs": n.attrs,
        "batch_seq": n.batch_seq,
        "created_at": n.created_at.isoformat(),
    }
    if depth:
        out["depth"] = n.depth
    return out


def edge_out(e: prov.GraphEdge) -> dict[str, str]:
    return {"src": str(e.src), "rel": e.rel.value, "dst": str(e.dst)}


def _lineage(ctx: Ctx, node_id: uuid.UUID, direction: str, depth: int | None) -> prov.Graph:
    with ctx.session() as s:
        try:
            return prov.lineage(s, node_id, direction, depth, max_nodes=MAX_NODES)  # type: ignore[arg-type]
        except prov.NodeNotFound as e:
            raise NotFound("provenance node") from e


@_route(
    "GET",
    "/provenance/{node_id}",
    "provenance:read",
    response_model=ProvNodeDetailOut,
    response_model_exclude_unset=True,
)
def get_node(node_id: uuid.UUID, ctx: CtxDep) -> dict[str, Any]:
    with ctx.session() as s:
        n = prov.get_node(s, node_id)
        if n is None:
            raise NotFound("provenance node")
        out_edges, in_edges = prov.neighbours(s, node_id, NEIGHBOUR_LIMIT)
    ctx.audit(audit.DATA_READ, resource_type="provenance_node", resource_id=node_id)
    return {
        "node": node_out(n),
        "edges_out": [edge_out(e) for e in out_edges],
        "edges_in": [edge_out(e) for e in in_edges],
    }


@_route(
    "GET",
    "/provenance/{node_id}/lineage",
    "provenance:read",
    response_model=LineageOut,
    response_model_exclude_unset=True,
)
def get_lineage(
    node_id: uuid.UUID, ctx: CtxDep, direction: Direction = "up", depth: Depth = None
) -> dict[str, Any]:
    g = _lineage(ctx, node_id, direction, depth)
    ctx.audit(
        audit.DATA_READ, resource_type="provenance_node", resource_id=node_id, count=len(g.nodes)
    )
    return {
        "root": str(g.root),
        "direction": g.direction,
        "depth": g.depth,
        "truncated": g.truncated,
        "nodes": [node_out(n, depth=True) for n in g.nodes],
        "edges": [edge_out(e) for e in g.edges],
    }


@_route(
    "GET",
    "/provenance/{node_id}/export",
    "provenance:export",
    responses={200: {"model": ProvExportOut}},
)
def export_lineage(
    node_id: uuid.UUID,
    request: Request,
    ctx: CtxDep,
    format: Annotated[Literal["prov-json", "openlineage"], Query()],  # noqa: A002
    direction: Direction = "up",
    depth: Depth = None,
) -> JSONResponse:
    g = _lineage(ctx, node_id, direction, depth)  # 404 for unknown / other-tenant nodes
    # 5.4: exports go through the policy function (RBAC + classification of the node's sources)
    enforce(
        ctx,
        "provenance:export",
        gpolicy.Resource("provenance_node", ctx.tenant_id, str(node_id), node_ids=(node_id,)),
    )
    if format == "openlineage":
        with ctx.session() as s:
            g = prov.with_activity_io(s, g)
    if format == "prov-json":
        body: Any = export.to_prov_json(g)
        media = "application/json"
    else:
        body = export.to_openlineage(g, tenant_id=ctx.tenant_id)
        media = "application/json"
    ctx.audit(
        audit.DATA_EXPORT,
        resource_type="provenance_node",
        resource_id=node_id,
        format=format,
        count=len(g.nodes),
    )
    return JSONResponse(body, media_type=media)
