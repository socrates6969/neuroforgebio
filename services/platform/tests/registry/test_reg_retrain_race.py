"""6.3 "one active retrain per version" under concurrency (BUG-HUNT M2).

Two requests for the same version run in two threads (two transactions) on the real local Postgres.
Both are held until each has checked for an active retrain and found none (the deterministic worst
case), then both insert. The partial unique index ``uq_model_retrain_active``
(``0013m6_retrain_active``) lets exactly one row in; the other request gets the winner's retrain
back, exactly as a sequential second request does, and its job is rolled back with its row (no
orphan ``registry.retrain`` job).
"""

from __future__ import annotations

import threading
import uuid

import pytest
from gov_helpers import principal
from nf_platform.db import migrate
from nf_platform.db.context import tenant_session
from nf_platform.registry import service as svc
from reg_helpers import feature_of, new_model, post, version_body
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.postgres


def _counts(engine, version_id: str) -> tuple[int, int]:
    with engine.connect() as c:  # superuser: sees every row
        rows = c.execute(
            text("SELECT id, job_id FROM model_retrain WHERE version_id = :v"), {"v": version_id}
        ).all()
        jobs = c.execute(
            text("SELECT count(*) FROM job WHERE kind = :k"), {"k": svc.RETRAIN_KIND}
        ).scalar_one()
    return len(rows), int(jobs)


def test_concurrent_retrain_requests_create_one_retrain_and_one_job(
    client, as_role, tree, engine, tenants, monkeypatch
):
    h = as_role("owner")
    node = feature_of(engine, tenants.a, tree["node_id"])
    model = new_model(client, h)
    v = post(client, f"/v1/models/{model['id']}/versions", version_body([node]), h)

    barrier = threading.Barrier(2, timeout=30)
    held = threading.local()
    real = svc._active_retrain

    def racing_lookup(session, version_id):
        found = real(session, version_id)
        if not getattr(held, "done", False):  # hold only each request's first check
            held.done = True
            barrier.wait()
        return found

    monkeypatch.setattr(svc, "_active_retrain", racing_lookup)
    owner = principal(tenants.a, "owner", pid="user-owner")
    results: list[tuple[str, bool]] = []
    errors: list[BaseException] = []

    def request() -> None:
        try:
            with tenant_session(owner, engine=engine) as s:
                row = svc.get_version(s, uuid.UUID(model["id"]), 1)
                rt, created = svc.request_retrain(s, owner, row, recipe=None)
                out = (str(rt.id), created)
            results.append(out)
        except BaseException as e:  # noqa: BLE001 - reported below
            errors.append(e)

    threads = [threading.Thread(target=request) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert not any(t.is_alive() for t in threads), "a request hung"
    assert errors == [], errors
    assert _counts(engine, v["id"]) == (1, 1)  # exactly one retrain row and one job
    assert sorted(c for _i, c in results) == [False, True]
    assert len({i for i, _c in results}) == 1  # the loser got the winner's retrain

    # sequential behaviour unchanged: a third request returns the same active retrain
    monkeypatch.setattr(svc, "_active_retrain", real)
    r = client.post(f"/v1/models/{model['id']}/versions/1/retrain", json={}, headers=h)
    assert r.status_code == 202 and r.json()["id"] == results[0][0]
    assert _counts(engine, v["id"]) == (1, 1)


def test_active_retrain_index_rejects_a_second_active_row(client, as_role, tree, engine, tenants):
    """The database guard on its own: a second queued/running row for one version is refused;
    finished rows do not count."""
    h = as_role("owner")
    node = feature_of(engine, tenants.a, tree["node_id"])
    model = new_model(client, h)
    v = post(client, f"/v1/models/{model['id']}/versions", version_body([node]), h)
    ins = text(
        "INSERT INTO model_retrain (id, tenant_id, version_id, state, excluded_subject_hashes, "
        "input_node_ids, requested_by) VALUES (:id, :t, :v, :st, '{}', '{}', 'x')"
    )
    args = {"t": tenants.a, "v": v["id"]}
    with engine.begin() as c:
        for st in ("succeeded", "failed", "queued"):
            c.execute(ins, dict(args, id=str(uuid.uuid4()), st=st))
    for st in ("queued", "running"):
        with pytest.raises(Exception) as ei, engine.begin() as c:
            c.execute(ins, dict(args, id=str(uuid.uuid4()), st=st))
        assert "uq_model_retrain_active" in str(ei.value)


def test_retrain_active_migration_up_down(pg_url):
    from nf_platform.db import testing

    name = f"nf_m_{uuid.uuid4().hex[:10]}"
    url = testing.create_database(pg_url, name)
    eng = create_engine(url)

    def has_index() -> bool:
        with eng.connect() as c:
            return bool(
                c.execute(
                    text("SELECT 1 FROM pg_indexes WHERE indexname = 'uq_model_retrain_active'")
                ).first()
            )

    try:
        migrate.upgrade(url, "0013m6_retrain_active")
        assert has_index()
        migrate.downgrade(url, "0012m6_key_tombstone")
        assert not has_index()
        migrate.upgrade(url, "0013m6_retrain_active")
        assert has_index()
    finally:
        eng.dispose()
        testing.drop_database(pg_url, name)
