"""3.1 API: GET /v1/provenance/{id} and /lineage (authorize + audit + tenant session), two-tenant
isolation on the provenance tables (API 404, RLS in the functions, no cross-tenant edges)."""

from __future__ import annotations

import uuid

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.provenance import api as prov
from prov_helpers import principal
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def _events(engine, request_id):
    with engine.connect() as c:
        rows = c.execute(
            text(
                "SELECT type, action, resource_type, resource_id, details FROM audit_event "
                "WHERE request_id = :r ORDER BY seq"
            ),
            {"r": request_id},
        ).all()
    return [dict(r._mapping) for r in rows]


def test_get_node_and_lineage(client, as_role, tree, engine):
    h = as_role("viewer")
    nid = tree["node_id"]
    r = client.get(f"/v1/provenance/{nid}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["node"]["type"] == "recording" and body["node"]["ref_id"] == tree["recording_id"]
    assert len(body["node"]["node_hash"]) == 64
    assert [e["rel"] for e in body["edges_out"]] == ["wasGeneratedBy"]
    assert body["edges_in"] == []
    ev = _events(engine, r.headers["x-request-id"])
    assert any(
        e["type"] == "data.read" and e["resource_id"] == nid and e["action"] == "provenance:read"
        for e in ev
    )
    up = client.get(f"/v1/provenance/{nid}/lineage", params={"direction": "up"}, headers=h).json()
    assert [(n["type"], n["depth"]) for n in up["nodes"]] == [
        ("recording", 0),
        ("convert", 1),
        ("raw_file", 2),
    ]
    assert len(up["edges"]) == 2 and up["truncated"] is False
    one = client.get(f"/v1/provenance/{nid}/lineage?direction=up&depth=1", headers=h).json()
    assert len(one["nodes"]) == 2 and one["depth"] == 1
    raw = up["nodes"][2]["id"]
    down = client.get(f"/v1/provenance/{raw}/lineage?direction=down", headers=h).json()
    assert {n["id"] for n in down["nodes"]} == {n["id"] for n in up["nodes"]}


@pytest.mark.parametrize("query", ["direction=sideways", "depth=-1", "depth=100000", "depth=x"])
def test_lineage_parameter_validation(client, as_role, tree, query):
    r = client.get(f"/v1/provenance/{tree['node_id']}/lineage?{query}", headers=as_role("viewer"))
    assert r.status_code == 422


def test_unknown_node_is_404(client, as_role, tree):
    for suffix in ("", "/lineage", "/export?format=prov-json"):
        r = client.get(f"/v1/provenance/{uuid.uuid4()}{suffix}", headers=as_role("owner"))
        assert r.status_code == 404, suffix


def test_two_tenant_isolation(client, as_role, tree, tenants, engine):
    """Tenant B cannot read, traverse, export, find or link to tenant A's nodes."""
    nid = tree["node_id"]
    hb = as_role("owner", tenant=tenants.b)
    for suffix in (
        "",
        "/lineage?direction=up",
        "/lineage?direction=down",
        "/export?format=prov-json",
        "/export?format=openlineage",
    ):
        assert client.get(f"/v1/provenance/{nid}{suffix}", headers=hb).status_code == 404
    pb = principal(tenants.b)
    with tenant_session(pb, engine=engine) as s:
        assert prov.get_node(s, uuid.UUID(nid)) is None
        assert prov.find_node(s, prov.ProvKind.ENTITY, "recording", tree["recording_id"]) is None
        with pytest.raises(prov.NodeNotFound):
            prov.lineage(s, uuid.UUID(nid), "up", None)
        with pytest.raises(prov.NodeNotFound):  # an edge into another tenant's graph
            prov.record(
                s,
                pb,
                [prov.NodeSpec(prov.ProvKind.ENTITY, "copy")],
                [(0, prov.EdgeType.WAS_DERIVED_FROM, uuid.UUID(nid))],
            )
        # B's own chain starts at seq 0 and is independent of A's
        c = prov.record(s, pb, [prov.NodeSpec(prov.ProvKind.ENTITY, "x")], [])
        assert c.batch_seq == 0
        assert prov.verify_chain(s, tenants.b).batches == 1
    # a principal of B cannot write into A's chain through a session scoped to A
    with pytest.raises(prov.ProvError), tenant_session(principal(tenants.a), engine=engine) as s:
        prov.record(s, pb, [prov.NodeSpec(prov.ProvKind.ENTITY, "x")], [])
    # RLS itself: as nf_app with tenant B set, no row of A in any provenance table
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE nf_app"))
        c.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenants.b})
        for t in ("prov_node", "prov_edge", "prov_batch", "pipeline_version"):
            n = c.execute(
                text(f"SELECT count(*) FROM {t} WHERE tenant_id = :a"), {"a": tenants.a}
            ).scalar_one()
            assert n == 0, t


@pytest.mark.parametrize(("fmt", "kind"), [("prov-json", dict), ("openlineage", list)])
def test_export_response_matches_the_contract_for_each_format(client, as_role, tree, fmt, kind):
    """Bug hunt H3: openlineage returns an array; the committed spec must allow it."""
    from nf_contract import Contract

    r = client.get(
        f"/v1/provenance/{tree['node_id']}/export?format={fmt}", headers=as_role("owner")
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), kind)
    Contract().check("GET", "/v1/provenance/{node_id}/export", r)
