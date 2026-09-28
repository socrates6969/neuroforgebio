"""3.7 acceptance: GET /v1/provenance/{id}/export?format=prov-json|openlineage.

PROV-JSON is parsed and checked with the W3C PROV Python library (``prov``); OpenLineage events are
validated offline against the published OpenLineage 2-0-2 JSON Schema (vendored, Apache-2.0, see
vendor/README.md). No network calls."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

import jsonschema
import pytest
from nf_platform.db.context import tenant_session
from nf_platform.provenance import api as prov
from nf_platform.provenance import export
from prov.model import (
    ProvActivity,
    ProvAgent,
    ProvAssociation,
    ProvDerivation,
    ProvDocument,
    ProvEntity,
    ProvGeneration,
    ProvUsage,
)
from prov_helpers import principal

pytestmark = pytest.mark.postgres
VENDOR = Path(__file__).resolve().parent / "vendor" / "openlineage-2-0-2.json"
OL_SHA256 = "69f68bee00b9beac88a87059c0102410e7bb05f3f43c46d02a0409831eceb0d2"
E, A, G = prov.ProvKind.ENTITY, prov.ProvKind.ACTIVITY, prov.ProvKind.AGENT


@pytest.fixture(scope="module")
def ol_validator():
    raw = VENDOR.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == OL_SHA256, "vendored schema changed"
    schema = json.loads(raw)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )


@pytest.fixture
def run_graph(engine, tenants, tree):
    """tree's raw -> convert -> recording, plus a pipeline run with two outputs and a derived
    artifact attributed to an agent."""
    p = principal(tenants.a)
    rec = uuid.UUID(tree["node_id"])
    with tenant_session(p, engine=engine) as s:
        c = prov.record(
            s,
            p,
            [
                prov.NodeSpec(G, "pipeline_version", "pv:sha256:" + "11" * 32),
                prov.NodeSpec(A, "run", "run-1", attrs={"seed": 42, "params": {"l_freq": 0.1}}),
                prov.NodeSpec(E, "artifact", "art-1", "blob:sha256:" + "22" * 32),
                prov.NodeSpec(E, "artifact", "art-2", "blob:sha256:" + "33" * 32),
                prov.NodeSpec(E, "figure", "fig-1"),
            ],
            [
                (1, prov.EdgeType.USED, rec),
                (1, prov.EdgeType.WAS_ASSOCIATED_WITH, 0),
                (2, prov.EdgeType.WAS_GENERATED_BY, 1),
                (3, prov.EdgeType.WAS_GENERATED_BY, 1),
                (4, prov.EdgeType.WAS_DERIVED_FROM, 2),
                (4, prov.EdgeType.WAS_ATTRIBUTED_TO, 0),
            ],
        )
    return c.node_ids


def test_prov_json_validates_with_the_prov_library(client, as_role, tree, run_graph, engine):
    fig = run_graph[4]
    r = client.get(f"/v1/provenance/{fig}/export?format=prov-json", headers=as_role("viewer"))
    assert r.status_code == 200, r.text
    doc = ProvDocument.deserialize(content=r.text, format="json")
    kinds = {type(x) for x in doc.get_records()}
    assert {
        ProvEntity,
        ProvActivity,
        ProvAgent,
        ProvUsage,
        ProvGeneration,
        ProvDerivation,
        ProvAssociation,
    } <= kinds
    ents = {str(x.identifier) for x in doc.get_records(ProvEntity)}
    assert f"nfnode:{fig}" in ents and f"nfnode:{tree['node_id']}" in ents
    # every relation refers to declared elements, and a round trip keeps the document
    declared = {x.identifier for x in doc.get_records() if x.is_element()}
    for rel in doc.get_records():
        if rel.is_relation():
            for _, v in rel.formal_attributes[:2]:
                assert v in declared, rel
    again = ProvDocument.deserialize(content=doc.serialize(format="json"), format="json")
    assert again == doc
    provn = doc.get_provn()
    assert "wasDerivedFrom" in provn and "wasAssociatedWith" in provn


def test_openlineage_events_validate_against_the_published_schema(
    client, as_role, tree, run_graph, tenants, ol_validator
):
    fig = run_graph[4]
    r = client.get(f"/v1/provenance/{fig}/export?format=openlineage", headers=as_role("viewer"))
    assert r.status_code == 200, r.text
    events = r.json()
    assert len(events) == 2  # the convert activity and the run
    for ev in events:
        ol_validator.validate(ev)
        datetime.fromisoformat(ev["eventTime"])  # date-time (not checked without extra libs)
    run = next(e for e in events if e["job"]["name"].startswith("run"))
    assert run["run"]["runId"] == str(run_graph[1])
    assert run["job"] == {"namespace": f"nf/{tenants.a}", "name": "run:pv:sha256:" + "11" * 32}
    assert [d["name"] for d in run["inputs"]] == [f"recording/{tree['recording_id']}"]
    assert sorted(d["name"] for d in run["outputs"]) == ["artifact/art-1", "artifact/art-2"]


def test_export_is_audited_and_invalid_format_rejected(client, as_role, tree, engine):
    nid = tree["node_id"]
    h = as_role("auditor")
    r = client.get(f"/v1/provenance/{nid}/export?format=prov-json", headers=h)
    assert r.status_code == 200
    from sqlalchemy import text

    with engine.connect() as c:
        ev = c.execute(
            text("SELECT type, details FROM audit_event WHERE request_id = :r"),
            {"r": r.headers["x-request-id"]},
        ).all()
    assert any(t == "data.export" and d.get("format") == "prov-json" for t, d in ev)
    for q in ("format=rdf", ""):
        assert client.get(f"/v1/provenance/{nid}/export?{q}", headers=h).status_code == 422


def test_bad_openlineage_event_is_caught_by_the_validator(ol_validator, run_graph, engine, tenants):
    """Guard against a vacuous check: a broken event must fail the schema."""
    with tenant_session(principal(tenants.a), engine=engine) as s:
        g = prov.lineage(s, run_graph[4], "up", None)
    ev = export.to_openlineage(g, tenant_id=tenants.a)[0]
    for broken in (
        {**ev, "run": {"runId": "not-a-uuid"}},
        {k: v for k, v in ev.items() if k != "producer"},
    ):
        assert not ol_validator.is_valid(broken)
