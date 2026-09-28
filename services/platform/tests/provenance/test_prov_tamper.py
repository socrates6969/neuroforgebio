"""3.1 acceptance / SEC-043: tampering with one node, edge or batch fails verification; an
attacker who can rewrite the tables cannot re-sign; a removed tail is caught by the WORM anchor;
the verification job raises an alert."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.provenance import chain, integrity, signing
from nf_platform.provenance.api import EdgeType, NodeSpec, ProvKind, record, verify_chain
from nf_platform.storage.objects import LocalObjectStore
from prov_helpers import principal
from sqlalchemy import text

pytestmark = pytest.mark.postgres
E, A = ProvKind.ENTITY, ProvKind.ACTIVITY


@pytest.fixture
def graph(engine, tenants):
    """Three batches in tenant A: raw -> convert -> recording, a run, an artifact."""
    p = principal(tenants.a)
    with tenant_session(p, engine=engine) as s:
        c1 = record(
            s,
            p,
            [NodeSpec(E, "raw_file", "u1"), NodeSpec(A, "convert"), NodeSpec(E, "recording", "r1")],
            [(1, EdgeType.USED, 0), (2, EdgeType.WAS_GENERATED_BY, 1)],
        )
        c2 = record(
            s,
            p,
            [NodeSpec(A, "run", "run1", attrs={"seed": 42})],
            [(0, EdgeType.USED, c1.node_ids[2])],
        )
        c3 = record(
            s,
            p,
            [NodeSpec(E, "artifact", "a1", "blob:sha256:" + "cd" * 32)],
            [(0, EdgeType.WAS_GENERATED_BY, c2.node_ids[0])],
        )
    return {"nodes": c1.node_ids + c2.node_ids + c3.node_ids, "heads": [c1, c2, c3]}


def tamper(engine, sql: str, **params) -> None:
    """Write as the superuser with triggers (append-only, FKs) disabled: the strongest DB
    attacker."""
    with engine.begin() as c:
        c.execute(text("SET LOCAL session_replication_role = replica"))
        n = c.execute(text(sql), params).rowcount
    assert n >= 1, sql


def verify(engine, tenant, **kw):
    with tenant_session(principal(tenant), engine=engine) as s:
        return verify_chain(s, tenant, **kw)


def test_untouched_chain_verifies(engine, tenants, graph):
    res = verify(engine, tenants.a)
    assert res.ok and (res.batches, res.nodes, res.edges) == (3, 5, 4), res.errors
    assert res.head == graph["heads"][-1].batch_id


@pytest.mark.parametrize(
    ("sql", "expect"),
    [
        ("UPDATE prov_node SET attrs = '{\"seed\": 43}' WHERE ref_id = 'run1'", "node hash"),
        ("UPDATE prov_node SET ref_id = 'r-other' WHERE ref_id = 'r1'", "node hash"),
        (
            "UPDATE prov_node SET content_hash = 'blob:sha256:' || repeat('ee', 32) "
            "WHERE ref_id = 'a1'",
            "node hash",
        ),
        (
            "UPDATE prov_edge SET rel = 'wasDerivedFrom' WHERE rel = 'wasGeneratedBy' "
            "AND batch_seq = 0",
            "recomputed id",
        ),
        ("DELETE FROM prov_edge WHERE batch_seq = 1", "records"),
        (
            "UPDATE prov_batch SET created_at = created_at + interval '1 ms' WHERE seq = 1",
            "recomputed id",
        ),
        (
            "UPDATE prov_batch SET prev_id = (SELECT batch_id FROM prov_batch WHERE seq = 0) "
            "WHERE seq = 2",
            "prev",
        ),
        ("DELETE FROM prov_batch WHERE seq = 1", "gap"),
    ],
    ids=[
        "node-attrs",
        "node-ref",
        "node-content",
        "edge-rel",
        "edge-deleted",
        "batch-time",
        "batch-prev",
        "batch-deleted",
    ],
)
def test_tampering_fails_verification(engine, tenants, graph, sql, expect):
    tamper(engine, sql)
    res = verify(engine, tenants.a)
    assert not res.ok
    assert any(expect in e for e in res.errors), res.errors


def test_consistent_rewrite_without_the_key_fails(engine, tenants, graph):
    """The attacker edits a node, recomputes the node hash AND the batch id: the signature (over
    the old id, by a trusted key) no longer matches; re-signing with their own key is untrusted."""
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT id, kind, type, ref_id, content_hash, batch_seq FROM prov_node "
                "WHERE ref_id = 'run1'"
            )
        ).one()
    rec = chain.node_record(
        str(row.id), row.kind, row.type, row.ref_id, row.content_hash, {"seed": 7}
    )
    tamper(
        engine,
        "UPDATE prov_node SET attrs = '{\"seed\": 7}', node_hash = :h WHERE id = :i",
        h=chain.node_hash(rec),
        i=row.id,
    )
    # rebuild batch 1's id as verify_chain would, and store it
    with tenant_session(principal(tenants.a), engine=engine) as s:
        res = verify_chain(s, tenants.a)
    assert any("recomputed id" in e for e in res.errors)
    attacker = signing.Ed25519Signer.generate("attacker")
    with engine.connect() as c:
        b = c.execute(text("SELECT batch_id FROM prov_batch WHERE seq = 1")).scalar_one()
    tamper(
        engine,
        "UPDATE prov_batch SET key_id = 'attacker', signature = :s WHERE seq = 1",
        s=attacker.sign(b.encode()),
    )
    res = verify(engine, tenants.a)
    assert any("not trusted" in e for e in res.errors), res.errors


def test_rotated_key_still_verifies_old_batches(engine, tenants, graph, prov_keys):
    new = signing.Ed25519Signer.generate("test-key-2")
    signing.configure(signing.Keyring(new, {"test-key-1": prov_keys.signer.public_key()}))
    p = principal(tenants.a)
    with tenant_session(p, engine=engine) as s:
        record(s, p, [NodeSpec(E, "note")], [])
    res = verify(engine, tenants.a)
    assert res.ok and res.batches == 4, res.errors
    # without the retired public key the old batches fail
    res = verify(engine, tenants.a, keyring=signing.Keyring(new))
    assert sum("not trusted" in e for e in res.errors) == 3


def test_removed_tail_is_caught_by_the_worm_anchor(engine, tenants, graph, tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    heads = integrity.anchor_heads(engine, store, [tenants.a, tenants.b])
    assert heads == {tenants.a: graph["heads"][-1].batch_id, tenants.b: None}
    ok = integrity.verify_tenants(engine, store, [tenants.a, tenants.b])
    assert all(r.ok for r in ok)
    # the attacker drops the newest batch and its rows: the remaining chain is self-consistent ...
    tamper(engine, "DELETE FROM prov_edge WHERE batch_seq = 2")
    tamper(engine, "DELETE FROM prov_node WHERE batch_seq = 2")
    tamper(engine, "DELETE FROM prov_batch WHERE seq = 2")
    assert verify(engine, tenants.a).ok
    # ... but not against the anchored head, and the job alerts
    seen: list[logging.LogRecord] = []
    handler = logging.Handler(logging.ERROR)
    handler.emit = seen.append  # type: ignore[method-assign]
    # import-linter's CLI (tests/core/test_core_imports.py) calls logging.config.dictConfig, which
    # disables every logger that already exists in this test process; re-enable ours here.
    was_disabled, integrity.log.disabled = integrity.log.disabled, False
    integrity.log.addHandler(handler)
    try:
        (res,) = integrity.verify_tenants(engine, store, [tenants.a])
    finally:
        integrity.log.removeHandler(handler)
        integrity.log.disabled = was_disabled
    assert not res.ok and any("anchored head" in e for e in res.errors)
    alerts = [r for r in seen if getattr(r, "alert", None) == integrity.ALERT]
    assert alerts and alerts[0].tenant_id == tenants.a


def test_forged_anchor_is_rejected(engine, tenants, graph, tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    attacker = signing.Keyring(signing.Ed25519Signer.generate("attacker"))
    integrity.anchor_heads(
        engine, store, [tenants.a], now=datetime(2030, 1, 1, tzinfo=UTC), keyring=attacker
    )
    (res,) = integrity.verify_tenants(engine, store, [tenants.a])
    assert not res.ok and any("anchor" in e for e in res.errors)
