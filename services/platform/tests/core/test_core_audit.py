"""2.8 acceptance / SEC-100, SEC-103, SEC-105, SEC-147: audit events, append-only table,
hash-chained hourly
batches, chain verification, and no secrets in audit payloads or logs."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from conftest import audit_batch_ids, bearer, registry_ids
from nf_platform.api.deps import PUBLIC
from nf_platform.audit import _canonical as cj
from nf_platform.audit import chain
from nf_platform.audit import log as audit
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_core_authz_matrix import _fill, api_routes, params_for

pytestmark = pytest.mark.postgres


class MemoryStore:
    """BatchStore double with WORM semantics like the real `audit` bucket."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put(self, bucket: str, key: str, data: bytes, *, metadata=None) -> None:
        if (bucket, key) in self.objects:
            raise PermissionError("WORM: object exists")
        self.objects[(bucket, key)] = data

    def get(self, bucket: str, key: str) -> bytes:
        return self.objects[(bucket, key)]

    def list(self, bucket: str, prefix: str) -> Iterator[str]:
        return iter(sorted(k for b, k in self.objects if b == bucket and k.startswith(prefix)))


def _events(engine, **where) -> list[dict]:
    sql = "SELECT row_to_json(e) FROM audit_event e"
    if where:
        sql += " WHERE " + " AND ".join(f"{k} = :{k}" for k in where)
    with engine.connect() as c:
        return [r[0] for r in c.execute(text(sql + " ORDER BY seq"), where)]


def test_every_data_read_route_emits_an_event(app, client, as_role, tree, engine):
    """Enumerates the routes: every GET (except health) must write a data.read/data.export event."""
    h = as_role("owner")
    ids = dict(tree)
    k = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": ["viewer"], "scopes": ["metadata:read"]},
        headers=h,
    )
    ids["key_id"] = k.json()["id"]
    # m5-ledger: a deletion job to read (withdrawal of an extra subject; not executed here)
    r = client.post(
        f"/v1/datasets/{ids['dataset_id']}/subjects", json={"label": "audit-w"}, headers=h
    )
    r = client.post(f"/v1/subjects/{r.json()['id']}/withdrawals", json={}, headers=h)
    ids["deletion_id"] = r.json()["id"]
    # m3-sweeps (3.6): one sweep over the tree's pipeline + recording
    sw = client.post(
        "/v1/sweeps",
        json={
            "pipeline": ids["pipeline_ref"],
            "recording_ids": [ids["recording_id"]],
            "grid": {"filter.l_freq": [0.5]},
            "metric": {"step": "rereference", "key": "accuracy"},
        },
        headers=h,
    )
    assert sw.status_code == 202, sw.text
    ids["sweep_id"] = sw.json()["id"]
    # m4-api (4.6): one webhook endpoint
    wh = client.post(
        "/v1/webhooks",
        json={"url": "https://hooks.example.com/nf", "event_types": ["run.finished"]},
        headers=h,
    )
    assert wh.status_code == 201, wh.text
    ids["webhook_id"] = wh.json()["id"]
    # m6-registry: a model with version 1 and a queued retrain
    registry_ids(client, h, ids)
    # AppSec M1: an audit batch for the auditor download route
    audit_batch_ids(client, ids)
    reads = [(m, p, a) for m, p, a in api_routes(app) if m == "GET" and a != PUBLIC]
    assert len(reads) >= 12
    for _method, path, action in reads:
        r = client.get(_fill(path, ids), params=params_for("GET", path, ids), headers=h)
        assert r.status_code == 200, (path, r.text)
        rid = r.headers["x-request-id"]
        evs = _events(engine, request_id=rid)
        kinds = {(e["type"], e["action"], e["outcome"]) for e in evs}
        assert (audit.AUTH_SUCCESS, action, "success") in kinds, path
        assert any(
            t in (audit.DATA_READ, audit.DATA_EXPORT) and a == action for t, a, _ in kinds
        ), path


def test_writes_admin_actions_and_failures_are_audited(client, as_role, tree, engine, tenants):
    h = as_role("owner")
    r = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": ["viewer"], "scopes": ["metadata:read"]},
        headers=h,
    )
    ev = _events(engine, request_id=r.headers["x-request-id"])
    admin = [e for e in ev if e["type"] == audit.ADMIN_ACTION]
    assert admin and admin[0]["details"]["key_public_id"] == r.json()["public_id"]
    r = client.delete(f"/v1/api-keys/{r.json()['id']}", headers=h)
    assert any(
        e["type"] == audit.ADMIN_ACTION
        for e in _events(engine, request_id=r.headers["x-request-id"])
    )
    # create
    r = client.post("/v1/projects", json={"name": "x"}, headers=h)
    assert any(
        e["type"] == audit.DATA_CREATE
        for e in _events(engine, request_id=r.headers["x-request-id"])
    )
    # authentication failure (no tenant known) and authorization denial
    r = client.get("/v1/projects", headers=bearer("garbage"))
    ev = _events(engine, request_id=r.headers["x-request-id"])
    assert [(e["type"], e["outcome"], e["tenant_id"]) for e in ev] == [
        (audit.AUTH_FAILURE, "failure", None)
    ]
    r = client.post("/v1/projects", json={"name": "x"}, headers=as_role("viewer"))
    ev = _events(engine, request_id=r.headers["x-request-id"])
    assert (audit.AUTHZ_DENIED, "denied") in {(e["type"], e["outcome"]) for e in ev}


def test_event_seq_is_monotonic_and_ts_utc(client, as_role, engine, tree):
    for _ in range(3):
        client.get("/v1/whoami", headers=as_role("viewer"))
    with engine.connect() as c:
        rows = c.execute(text("SELECT seq, ts FROM audit_event ORDER BY ts, seq")).all()
    seqs = [r[0] for r in rows]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert all(r[1].utcoffset() == timedelta(0) for r in rows)


def test_audit_table_is_append_only_even_for_the_owner(engine, client, as_role):
    client.get("/v1/whoami", headers=as_role("viewer"))
    for sql in (
        "UPDATE audit_event SET outcome = 'x'",
        "DELETE FROM audit_event",
        "TRUNCATE audit_event",
    ):
        # superuser + table owner: the trigger still refuses
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
            c.execute(text(sql))
    with pytest.raises(DBAPIError, match="permission denied"), engine.begin() as c:
        c.execute(text("SET LOCAL ROLE nf_audit_writer"))
        c.execute(text("UPDATE audit_event SET outcome = 'x'"))


def _backdate(engine, hours: int) -> None:
    """Move all events into the past (test only: temporarily disables the append-only trigger)."""
    with engine.begin() as c:
        c.execute(text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_append_only"))
        c.execute(text("UPDATE audit_event SET ts = ts - make_interval(hours => :h)"), {"h": hours})
        c.execute(text("ALTER TABLE audit_event ENABLE TRIGGER audit_event_append_only"))


def test_hourly_batches_chain_and_verify(client, as_role, engine, tenants, tree):
    store = MemoryStore()
    batcher = chain.AuditBatcher(engine, store)
    client.get("/v1/projects", headers=as_role("viewer"))
    client.get("/v1/whoami", headers=bearer("garbage"))  # a _platform-scope event
    _backdate(engine, 3)
    first = batcher.run()
    scopes = {r.scope for r in first}
    assert tenants.a in scopes and chain.PLATFORM_SCOPE in scopes
    assert batcher.run() == []  # nothing new: no empty batches
    # more activity in a later hour → seq 1 linked to seq 0
    client.get("/v1/projects", headers=as_role("viewer"))
    _backdate(engine, 1)
    second = batcher.run()
    a2 = next(r for r in second if r.scope == tenants.a)
    assert a2.seq == 1
    batches = chain.load_chain(store, tenants.a)
    assert [b["seq"] for b in batches] == [0, 1]
    assert batches[1]["prev"] == chain.batch_id(batches[0])
    head = chain.chain_head(engine, tenants.a)
    assert chain.verify_stored_chain(store, tenants.a, expected_head=head)[-1] == head
    # the stored bytes are exactly the canonical JSON that was hashed
    raw = store.get("audit", chain.object_key(tenants.a, 0))
    assert raw == cj.canonicalize(json.loads(raw))
    # events are grouped per tenant: tenant A's chain holds only tenant A's events
    assert all(
        e["actor"]["id"] is not None for b in batches for e in b["events"]
    )  # platform-scope (unauthenticated) events are not in a tenant chain


def _tamper(store: MemoryStore, scope: str, seq: int, fn) -> None:
    key = ("audit", chain.object_key(scope, seq))
    b = json.loads(store.objects[key])
    fn(b)
    store.objects[key] = cj.canonicalize(b)


@pytest.mark.parametrize("target", [0, 1])
def test_modified_batch_fails_verification(client, as_role, engine, tenants, target):
    store = MemoryStore()
    batcher = chain.AuditBatcher(engine, store)
    for hours in (3, 1):
        client.get("/v1/projects", headers=as_role("viewer"))
        _backdate(engine, hours)
        batcher.run()
    head = chain.chain_head(engine, tenants.a)
    assert len(chain.verify_stored_chain(store, tenants.a, expected_head=head)) == 2

    def edit(b):
        b["events"][0]["outcome"] = "denied"

    _tamper(store, tenants.a, target, edit)
    with pytest.raises(chain.AuditChainError):
        chain.verify_stored_chain(store, tenants.a, expected_head=head)


def test_removed_or_reordered_batches_fail(engine, client, as_role, tenants):
    store = MemoryStore()
    batcher = chain.AuditBatcher(engine, store)
    for hours in (5, 3, 1):
        client.get("/v1/whoami", headers=as_role("viewer"))
        _backdate(engine, hours)
        batcher.run()
    batches = chain.load_chain(store, tenants.a)
    assert len(chain.verify_chain(batches)) == 3
    with pytest.raises(chain.AuditChainError):
        chain.verify_chain([batches[0], batches[2]])
    with pytest.raises(chain.AuditChainError):
        chain.verify_chain(batches[:2], expected_head=chain.chain_head(engine, tenants.a))


def test_batches_on_the_local_worm_store(engine, client, as_role, tenants, tmp_path):
    """End to end with storage's LocalObjectStore (the local stand-in for the object-locked
    bucket)."""
    objects = pytest.importorskip("nf_platform.storage.objects")
    store = objects.LocalObjectStore(tmp_path)
    batcher = chain.AuditBatcher(engine, store)
    client.get("/v1/whoami", headers=as_role("viewer"))
    _backdate(engine, 2)
    (res,) = [r for r in batcher.run() if r.scope == tenants.a]
    head = chain.chain_head(engine, tenants.a)
    assert chain.verify_stored_chain(store, tenants.a, expected_head=head) == [head]
    with pytest.raises(objects.WormViolation):
        store.put("audit", res.object_key, b"{}")
    with pytest.raises(objects.WormViolation):
        store.delete("audit", res.object_key)


# ---------------------------------------------------------------- payload and log hygiene
def test_event_with_secret_is_rejected():
    for bad in (
        {"reason": "nfb_live_abcdefghijklmnop_" + "x" * 43},
        {"reason": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.sig"},
        {"reason": "Bearer abcdefghijklmnopqrstuvwxyz"},
    ):
        with pytest.raises(audit.AuditPayloadError):
            audit.validate(audit.AuditEvent(type="x", outcome="success", details=bad))
    with pytest.raises(audit.AuditPayloadError):
        audit.validate(audit.AuditEvent(type="x", outcome="success", details={"password": "x"}))


def test_no_credentials_in_audit_rows_or_logs(client, as_role, idp, tenants, engine, caplog):
    caplog.set_level(logging.DEBUG)
    token = idp.token(sub="carol", tenant=tenants.a, roles=["owner"])
    h = bearer(token)
    key = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": ["viewer"], "scopes": ["metadata:read"]},
        headers=h,
    ).json()["key"]
    client.get("/v1/whoami", headers=bearer(key))
    client.get("/v1/whoami", headers=bearer(key[:-3] + "zzz"))  # failure path
    client.get("/v1/whoami", headers=bearer(token[:-5] + "AAAAA"))  # bad signature
    client.post(
        "/v1/projects", json={"name": key}, headers=h
    )  # a key pasted into a field is data, not audit
    with engine.connect() as c:
        dump = "\n".join(
            r[0] for r in c.execute(text("SELECT row_to_json(e)::text FROM audit_event e"))
        )
    logs = caplog.text
    # the base64url API-key secret may itself contain "_": take everything after the public id
    for secret in (key, key.split("_", 3)[3], token, token.split(".")[2]):
        assert secret not in dump
        assert secret not in logs
    assert "nfb_live_" not in dump


def test_canonical_copy_matches_spec_vectors():
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    vectors = json.loads(
        (root / "spec/test-vectors/canonical-json.json").read_text(encoding="utf-8")
    )
    for case in vectors["cases"]:
        out = cj.canonicalize_text(case["input"])
        assert out.decode("utf-8") == case["canonical"], case["name"]
        assert cj.sha256_hex(out) == case["sha256"], case["name"]


def test_batch_id_is_domain_separated():
    b = {
        "schema": chain.SCHEMA,
        "scope": str(uuid.uuid4()),
        "seq": 0,
        "prev": None,
        "created_at": chain.ts(datetime(2026, 9, 26, 12, tzinfo=UTC)),
        "period": {"start": "x", "end": "y"},
        "events": [],
    }
    bid = chain.batch_id(b)
    assert chain.ID_RE.match(bid)
    assert bid.split(":")[2] != cj.sha256_hex(cj.canonicalize(b))
