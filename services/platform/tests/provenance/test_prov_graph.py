"""3.1: record / lineage / verify_chain basics, PROV edge rules, append-only, signatures, spec
vectors."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.provenance import chain
from nf_platform.provenance.api import (
    EdgeType,
    NodeNotFound,
    NodeSpec,
    ProvError,
    ProvKind,
    find_node,
    get_node,
    lineage,
    record,
    verify_chain,
)
from prov_helpers import principal
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.postgres

VECTORS = Path(__file__).resolve().parents[4] / "spec" / "test-vectors" / "ids.json"
E, A, G = ProvKind.ENTITY, ProvKind.ACTIVITY, ProvKind.AGENT
BLOB = "blob:sha256:" + "ab" * 32


def ingest_chain(s, p, ref="rec-1"):
    """raw --used-- convert --generated--> recording, convert associated with a converter agent."""
    return record(
        s,
        p,
        [
            NodeSpec(E, "raw_file", f"upload-{ref}", BLOB, {"format": "edf"}),
            NodeSpec(G, "software", f"converter-{ref}", None, {"version": "1.0.0"}),
            NodeSpec(A, "convert", None, None, {"reader": "edf@1"}),
            NodeSpec(E, "recording", ref, None, {}),
        ],
        [
            (2, EdgeType.USED, 0),
            (2, EdgeType.WAS_ASSOCIATED_WITH, 1),
            (3, EdgeType.WAS_GENERATED_BY, 2),
            (3, EdgeType.WAS_DERIVED_FROM, 0),
        ],
    )


def test_spec_vectors_prov_batch_chain():
    """The batch construction reproduces the frozen provb vectors (hashing.md §5.3)."""
    vec = json.loads(VECTORS.read_text(encoding="ascii"))["prov_batch_chain"]
    prev = None
    for case in vec:
        b = case["batch"]
        assert b["prev"] == prev
        doc = chain.batch_doc(b["tenant"], b["seq"], b["prev"], b["created_at"], b["records"])
        assert chain.batch_payload(doc).decode() == case["payload"]
        assert chain.batch_id(doc) == case["id"]
        prev = case["id"]


def test_record_lineage_verify(engine, tenants, prov_keys):
    p = principal(tenants.a)
    with tenant_session(p, engine=engine) as s:
        c = ingest_chain(s, p)
        assert c.batch_seq == 0 and c.batch_id.startswith("provb:sha256:")
        raw, agent, act, rec = c.node_ids
        c2 = record(
            s,
            p,
            [NodeSpec(A, "run"), NodeSpec(E, "artifact", "art-1", BLOB)],
            [(0, EdgeType.USED, rec), (1, EdgeType.WAS_GENERATED_BY, 0)],
        )
        run, art = c2.node_ids
        assert c2.batch_seq == 1
    with tenant_session(p, engine=engine) as s:
        up = lineage(s, art, "up", None)
        assert {n.id: n.depth for n in up.nodes} == {
            art: 0,
            run: 1,
            rec: 2,
            act: 3,
            raw: 3,
            agent: 4,
        }
        assert len(up.edges) == 6
        assert {n.id for n in lineage(s, art, "up", 2).nodes} == {art, run, rec}
        down = lineage(s, raw, "down", None)
        assert {n.id for n in down.nodes} == {raw, act, rec, run, art}
        assert find_node(s, E, "recording", "rec-1") == rec
        assert get_node(s, rec).kind is E
        res = verify_chain(s, tenants.a)
        assert res.ok, res.errors
        assert (res.batches, res.nodes, res.edges) == (2, 6, 6)


def test_edge_rules(engine, tenants, prov_keys):
    p = principal(tenants.a)
    with tenant_session(p, engine=engine) as s:
        with pytest.raises(ProvError, match="connects"):  # entity used entity
            record(s, p, [NodeSpec(E, "x"), NodeSpec(E, "y")], [(1, EdgeType.USED, 0)])
        with pytest.raises(ProvError, match="smaller"):  # forward pointer (could form a cycle)
            record(s, p, [NodeSpec(E, "x"), NodeSpec(E, "y")], [(0, EdgeType.WAS_DERIVED_FROM, 1)])
        with pytest.raises(ProvError, match="index"):
            record(s, p, [NodeSpec(E, "x")], [(uuid.uuid4(), EdgeType.WAS_DERIVED_FROM, 0)])
        with pytest.raises(NodeNotFound):
            record(s, p, [NodeSpec(E, "x")], [(0, EdgeType.WAS_DERIVED_FROM, uuid.uuid4())])
        with pytest.raises(ProvError, match="canonical"):
            record(s, p, [NodeSpec(E, "x", attrs={"v": float("nan")})], [])
        with pytest.raises(ProvError, match="content"):
            record(s, p, [NodeSpec(E, "x", content_hash="md5:abc")], [])
        with pytest.raises(ProvError, match="type"):
            record(s, p, [NodeSpec(E, "Bad Type")], [])


def test_ref_is_unique_per_tenant(engine, tenants, prov_keys):
    pa, pb = principal(tenants.a), principal(tenants.b)
    with tenant_session(pa, engine=engine) as s:
        record(s, pa, [NodeSpec(E, "recording", "r1")], [])
    with pytest.raises(IntegrityError), tenant_session(pa, engine=engine) as s:
        record(s, pa, [NodeSpec(E, "recording", "r1")], [])
    with tenant_session(pb, engine=engine) as s:  # the same ref in another tenant is fine
        record(s, pb, [NodeSpec(E, "recording", "r1")], [])


def test_tables_are_append_only_for_the_app_role(engine, tenants, prov_keys):
    p = principal(tenants.a)
    with tenant_session(p, engine=engine) as s:
        ingest_chain(s, p)
    for sql in (
        "UPDATE prov_node SET attrs = '{}'",
        "DELETE FROM prov_edge",
        "DELETE FROM prov_batch",
        "UPDATE pipeline_version SET name = 'x'",
    ):
        with pytest.raises(DBAPIError), tenant_session(p, engine=engine) as s:
            s.execute(text(sql))
    # even the table owner/superuser hits the trigger unless it disables it explicitly
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE prov_node SET attrs = '{\"x\": 1}'"))
