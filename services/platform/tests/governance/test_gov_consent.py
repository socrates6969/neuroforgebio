"""5.3 acceptance: consent ledger.

- UPDATE/DELETE/TRUNCATE are rejected at the DB level (real Postgres): ``nf_app`` has no
  privilege, and a trigger rejects them even for the table owner;
- chain verification detects a modified row;
- an anchor mismatch alerts (a consistently rewritten chain passes its own hash checks, but not
  the WORM anchor);
- API: document versioning with hashes, grants/withdrawals, current scopes, tenant isolation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from gov_helpers import make_subject, principal
from nf_platform.db.context import tenant_session
from nf_platform.governance import consent
from nf_platform.governance import jobs as gjobs
from nf_platform.provenance import chain as pchain
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.postgres


def _grant(client, h, sid, scopes, doc):
    r = client.post(
        f"/v1/subjects/{sid}/consents",
        json={"kind": "grant", "scopes": scopes, "document_id": doc},
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_api_documents_grants_withdrawals(client, as_role, tree, tenants, idp):
    h = as_role("data-steward")
    doc = {"name": "adult-consent", "version": "2", "sha256": "12" * 32, "uri": "docs/c-v2.pdf"}
    r = client.post("/v1/consent-documents", json=doc, headers=h)
    assert r.status_code == 201
    did = r.json()["id"]
    assert client.post("/v1/consent-documents", json=doc, headers=h).json()["id"] == did
    r = client.post("/v1/consent-documents", json={**doc, "sha256": "34" * 32}, headers=h)
    assert r.status_code == 409  # a version is bound to its hash
    assert (
        client.post("/v1/consent-documents", json=doc, headers=as_role("scientist")).status_code
        == 403
    )
    s = make_subject(client, h, tree["dataset_id"], "sub-c1", scopes=())
    sid = s["subject_id"]
    g = _grant(client, h, sid, ["collection", "processing", "model_training"], did)
    assert g["document_sha256"] == "12" * 32 and g["collector_id"] == "user-data-steward"
    r = client.post(
        f"/v1/subjects/{sid}/consents",
        json={"kind": "withdraw", "scopes": ["model_training"]},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["prev_hash"] == g["record_hash"] or r.json()["seq"] > g["seq"]
    out = client.get(f"/v1/subjects/{sid}/consents", headers=as_role("scientist")).json()
    assert out["current_scopes"] == ["collection", "processing"] and not out["withdrawn"]
    assert [x["kind"] for x in out["records"]] == ["grant", "withdraw"]
    # invalid input
    bad = [
        {"kind": "grant", "scopes": ["processing"]},
        {"kind": "grant", "scopes": ["telepathy"], "document_id": did},
        {"kind": "withdraw", "scopes": ["processing"], "document_id": did},
    ]
    for b in bad:
        assert client.post(f"/v1/subjects/{sid}/consents", json=b, headers=h).status_code == 422
    assert client.get(f"/v1/subjects/{sid}/consents", headers=as_role("viewer")).status_code == 403
    # another tenant's steward: the subject does not exist for them
    hb = {"Authorization": "Bearer " + idp.token(sub="b", tenant=tenants.b, roles=["data-steward"])}
    assert client.get(f"/v1/subjects/{sid}/consents", headers=hb).status_code == 404
    r = client.post(
        f"/v1/subjects/{sid}/consents",
        json={"kind": "withdraw", "scopes": ["processing"]},
        headers=hb,
    )
    assert r.status_code == 404


def test_update_delete_truncate_rejected_at_db_level(engine, tree):
    for table in ("consent_record", "consent_document"):
        for stmt in (f"UPDATE {table} SET tenant_id = tenant_id", f"DELETE FROM {table}"):
            # the app role: no privilege at all
            with pytest.raises(DBAPIError, match="permission denied"), engine.begin() as c:
                c.execute(text("SET LOCAL ROLE nf_app"))
                c.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tree["_tenant_id"]}
                )
                c.execute(text(stmt))
            # the table owner (superuser here): the append-only trigger
            with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
                c.execute(text(stmt))
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as c:
            c.execute(text(f"TRUNCATE {table} CASCADE"))
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM consent_record")).scalar_one() >= 1


def _rewrite(engine, tid: str, seq: int, scopes: list[str], *, rehash: bool) -> None:
    """Superuser tampering with the trigger disabled (what an attacker with DB access could do)."""
    with engine.begin() as c:
        c.execute(text("ALTER TABLE consent_record DISABLE TRIGGER consent_record_append_only"))
        c.execute(
            text("UPDATE consent_record SET scopes = :s WHERE tenant_id = :t AND seq = :q"),
            {"s": scopes, "t": tid, "q": seq},
        )
        if rehash:  # recompute this and every later hash so the chain is self-consistent
            rows = c.execute(
                text("SELECT * FROM consent_record WHERE tenant_id = :t ORDER BY seq"), {"t": tid}
            ).all()
            prev = None
            for r in rows:
                doc = consent.record_doc(
                    tenant_id=tid,
                    seq=r.seq,
                    prev=prev,
                    record_id=str(r.id),
                    subject_id=str(r.subject_id),
                    kind=r.kind,
                    scopes=r.scopes,
                    document_id=None if r.document_id is None else str(r.document_id),
                    document_sha256=r.document_sha256,
                    basis=r.jurisdiction_basis,
                    collector=r.collector_id,
                    evidence=r.evidence_ref,
                    recorded_at=r.recorded_at,
                )
                h = consent.record_hash(doc)
                c.execute(
                    text(
                        "UPDATE consent_record SET prev_hash = :p, record_hash = :h "
                        "WHERE tenant_id = :t AND seq = :q"
                    ),
                    {"p": prev, "h": h, "t": tid, "q": r.seq},
                )
                prev = h
        c.execute(text("ALTER TABLE consent_record ENABLE TRIGGER consent_record_append_only"))


def _verify(engine, tid):
    with tenant_session(principal(tid, "owner"), engine=engine) as s:
        return consent.verify_chain(s, tid)


def test_chain_verification_detects_a_modified_row(client, as_role, tree, engine):
    h = as_role("data-steward")
    s = make_subject(client, h, tree["dataset_id"], "sub-c2", scopes=("collection",))
    tid = tree["_tenant_id"]
    client.post(
        f"/v1/subjects/{s['subject_id']}/consents",
        json={"kind": "withdraw", "scopes": ["collection"]},
        headers=h,
    )
    res = _verify(engine, tid)
    assert res.ok and res.records >= 3, res.errors
    _rewrite(
        engine,
        tid,
        1,
        ["collection", "processing", "sharing", "model_training", "commercial_use"],
        rehash=False,
    )
    res = _verify(engine, tid)
    assert not res.ok
    assert any("record 1: content does not match" in e for e in res.errors)


def test_anchor_mismatch_alerts(client, as_role, tree, engine, storage, caplog, worker):
    h = as_role("data-steward")
    make_subject(client, h, tree["dataset_id"], "sub-c3", scopes=("collection", "processing"))
    tid = tree["_tenant_id"]
    day1 = datetime(2026, 9, 25, 23, 0, tzinfo=UTC)
    heads = consent.anchor_heads(engine, storage.objects, [tid], now=day1)
    assert heads[tid] is not None
    (ok,) = consent.verify_tenants(engine, storage.objects, [tid])
    assert ok.ok, ok.errors
    # a consistent rewrite of history passes the chain's own checks ...
    _rewrite(engine, tid, 0, ["collection"], rehash=True)  # seq 0 granted every scope
    assert _verify(engine, tid).ok
    # ... but not the anchor in the WORM bucket: the verification alerts
    # import-linter's CLI (test_core_imports) disables existing loggers in this process
    logging.getLogger("nf_platform.governance.consent").disabled = False
    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="nf_platform.governance.consent"):
        (bad,) = consent.verify_tenants(engine, storage.objects, [tid])
    assert not bad.ok and any("anchor mismatch" in e for e in bad.errors)
    alerts = [r for r in caplog.records if getattr(r, "alert", None) == consent.ALERT]
    assert alerts and alerts[0].levelno == logging.ERROR
    # the queued job form (consent.verify) fails without retry
    with tenant_session(principal(tid, "owner"), engine=engine) as s:
        from nf_platform.jobs import queue

        queue.enqueue(
            s,
            gjobs.CONSENT_VERIFY_KIND,
            {},
            dedupe_key=gjobs.dedupe_key(gjobs.CONSENT_VERIFY_KIND, datetime.now(UTC)),
        )
    worker.kinds = (gjobs.CONSENT_VERIFY_KIND,)
    job = worker.run_once()
    with engine.connect() as c:
        row = c.execute(
            text("SELECT state, last_error FROM job WHERE id = :i"), {"i": job.id}
        ).first()
    assert row.state == "failed" and consent.ALERT in row.last_error


def test_anchor_job_on_the_queue(client, as_role, tree, engine, storage, worker):
    tid = tree["_tenant_id"]
    with tenant_session(principal(tid, "owner"), engine=engine) as s:
        from nf_platform.jobs import queue

        now = datetime.now(UTC)
        key = gjobs.dedupe_key(gjobs.CONSENT_ANCHOR_KIND, now)
        a = queue.enqueue(s, gjobs.CONSENT_ANCHOR_KIND, {}, dedupe_key=key)
        assert queue.enqueue(s, gjobs.CONSENT_ANCHOR_KIND, {}, dedupe_key=key) == a  # once a day
    worker.kinds = (gjobs.CONSENT_ANCHOR_KIND,)
    assert worker.run_once() is not None
    keys = list(storage.objects.list("audit", f"consent-anchors/{tid}/"))
    assert keys == [consent.anchor_key(tid, now)]
    doc = consent.latest_anchor(storage.objects, tid)
    with tenant_session(principal(tid, "owner"), engine=engine) as s:
        assert consent.verify_chain(s, tid, expected=(doc["seq"], doc["head"])).ok


def test_two_tenants_have_independent_chains(client, as_role, tree, engine, tenants, idp):
    hb = {"Authorization": "Bearer " + idp.token(sub="b", tenant=tenants.b, roles=["owner"])}
    r = client.post("/v1/projects", json={"name": "pb"}, headers=hb)
    ds = client.post(f"/v1/projects/{r.json()['id']}/datasets", json={"name": "d"}, headers=hb)
    s = make_subject(client, hb, ds.json()["id"], "b-01", scopes=("collection",))
    assert s
    ra, rb = _verify(engine, tenants.a), _verify(engine, tenants.b)
    assert ra.ok and rb.ok and rb.records == 1 and rb.head != ra.head
    with tenant_session(principal(tenants.a, "owner"), engine=engine) as sess:
        n = sess.execute(text("SELECT count(*) FROM consent_record")).scalar_one()
    assert n == ra.records  # RLS: tenant A sees only its own entries


def test_record_hash_covers_every_field():
    base = dict(
        tenant_id=str(uuid.uuid4()),
        seq=3,
        prev="a" * 64,
        record_id=str(uuid.uuid4()),
        subject_id=str(uuid.uuid4()),
        kind="grant",
        scopes=["processing"],
        document_id=str(uuid.uuid4()),
        document_sha256="b" * 64,
        basis="CO",
        collector="u",
        evidence="form",
        recorded_at=pchain.now_ms(),
    )
    h0 = consent.record_hash(consent.record_doc(**base))
    changes = {
        "seq": 4,
        "prev": "c" * 64,
        "kind": "withdraw",
        "scopes": ["sharing"],
        "document_sha256": "d" * 64,
        "basis": "CA",
        "collector": "v",
        "evidence": None,
        "recorded_at": base["recorded_at"] + timedelta(milliseconds=1),
    }
    for k, v in changes.items():
        assert consent.record_hash(consent.record_doc(**{**base, k: v})) != h0, k
