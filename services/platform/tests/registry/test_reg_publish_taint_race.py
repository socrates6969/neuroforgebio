"""SEC-143 "a tainted version is never published" under concurrency (BUG-HUNT M3).

``publish`` reads the version's taint, then checks policy and approvals, then flips the version to
``published``. A withdrawal's DeletionJob can flag the model in between. Deterministic
interleavings on the real local Postgres:

1. publish is paused after its first taint read (inside the ``model:publish`` policy check) while
   a concurrent transaction flags the version (``deletion.flag_models``, the DeletionJob's taint
   writer) and commits. publish then locks the version row, re-reads the taint and refuses (409
   ``retrain_required``); the version stays private.
2. while a transaction holds the version row lock (as publish does from its re-check to its
   commit), the taint writer waits for it: it cannot slip a flag in between publish's final check
   and its commit.
"""

from __future__ import annotations

import threading
import uuid

import pytest
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.governance import deletion, policy
from nf_platform.registry import vocab
from nf_platform.storage.runtime import service_principal
from reg_helpers import feature_of, new_model, post, version_body
from sqlalchemy import select

pytestmark = pytest.mark.postgres


@pytest.fixture
def node(tree, engine, tenants):
    return feature_of(engine, tenants.a, tree["node_id"])


def _publishable(client, as_role, node) -> tuple[str, dict]:
    owner = as_role("owner", sub="publisher")
    model = new_model(client, owner, privacy=True)
    v = post(client, f"/v1/models/{model['id']}/versions", version_body([node]), owner)
    url = f"/v1/models/{model['id']}/versions/1"
    for sub in ("approver-1", "approver-2"):
        r = client.post(f"{url}/approvals", headers=as_role("data-steward", sub=sub))
        assert r.status_code == 201, r.text
    return url, v


def _taint(engine, tid: str, model_node: uuid.UUID) -> uuid.UUID:
    """The DeletionJob's taint writer in its own transaction (a concurrent withdrawal)."""
    dj = uuid.uuid4()
    svc = service_principal(tid, deletion.SERVICE_ID)
    with tenant_session(svc, engine=engine) as s:
        deletion.flag_models(s, tid, [model_node], dj, True)
    return dj


def _flags(engine, tid: str, model_node: uuid.UUID) -> list[uuid.UUID]:
    svc = service_principal(tid, "svc:test")
    with tenant_session(svc, engine=engine) as s:
        return list(
            s.scalars(
                select(m.ModelFlag.deletion_job_id).where(m.ModelFlag.model_node_id == model_node)
            )
        )


def test_withdrawal_between_taint_read_and_commit_blocks_publication(
    client, as_role, node, engine, tenants, monkeypatch
):
    url, v = _publishable(client, as_role, node)
    model_node = uuid.UUID(v["prov_node_id"])
    real = policy.check
    tainted: list[uuid.UUID] = []

    def check(principal, action, *a, **kw):
        out = real(principal, action, *a, **kw)
        if action == "model:publish" and not tainted:
            # publish has read an empty taint; a withdrawal now flags the version and commits
            t = threading.Thread(
                target=lambda: tainted.append(_taint(engine, tenants.a, model_node))
            )
            t.start()
            t.join(30)
            assert not t.is_alive(), "the taint writer was blocked before publish locked anything"
        return out

    monkeypatch.setattr(policy, "check", check)
    owner = as_role("owner", sub="publisher")
    r = client.post(f"{url}/publish", headers=owner)
    assert tainted, "the interleaving did not run"
    assert r.status_code == 409 and r.json()["code"] == vocab.R_RETRAIN, r.text
    monkeypatch.setattr(policy, "check", real)
    out = client.get(url, headers=owner).json()
    assert out["visibility"] == "private" and out["retrain_required"] is True
    assert out["published_at"] is None


def test_taint_writer_waits_for_the_version_row_lock(client, as_role, node, engine, tenants):
    url, v = _publishable(client, as_role, node)
    model_node = uuid.UUID(v["prov_node_id"])
    svc = service_principal(tenants.a, "svc:test-publisher")
    done = threading.Event()

    def writer() -> None:
        _taint(engine, tenants.a, model_node)
        done.set()

    with tenant_session(svc, engine=engine) as s:
        # what publish holds from its final taint check to its commit
        s.scalar(
            select(m.ModelVersion.id)
            .where(m.ModelVersion.id == uuid.UUID(v["id"]))
            .with_for_update()
        )
        t = threading.Thread(target=writer)
        t.start()
        assert not done.wait(1.5), "the taint writer did not wait for the version lock"
        assert _flags(engine, tenants.a, model_node) == []
    t.join(30)
    assert done.is_set() and len(_flags(engine, tenants.a, model_node)) == 1
