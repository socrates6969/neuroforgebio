"""SEC-043 job bodies (m3-prov's provenance.integrity) run on the queue: daily head anchor and
hourly chain verification per tenant, deduplicated per day/hour; a forged anchor fails the
verification job without retry."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from nf_platform.db.context import tenant_session
from nf_platform.jobs import queue
from nf_platform.provenance import integrity
from nf_platform.storage.runtime import service_principal
from nf_runner.worker import PROV_ANCHOR_KIND, PROV_VERIFY_KIND, integrity_dedupe_key
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def _enqueue(engine, tenant, kind, now):
    with tenant_session(service_principal(tenant), engine=engine) as s:
        return queue.enqueue(s, kind, {}, dedupe_key=integrity_dedupe_key(kind, now))


def _state(engine, job_id):
    with engine.connect() as c:
        return c.execute(
            text("SELECT state, last_error, result FROM job WHERE id = :i"), {"i": job_id}
        ).first()


def test_anchor_and_verify_jobs(client, as_role, tree, worker, engine, storage, tenants):
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=as_role("owner"))
    now = datetime.now(UTC)
    anchor = _enqueue(engine, tenants.a, PROV_ANCHOR_KIND, now)
    assert _enqueue(engine, tenants.a, PROV_ANCHOR_KIND, now) == anchor  # once per day
    worker.run_once()
    st = _state(engine, anchor)
    assert st.state == "succeeded" and st.result["head"].startswith("provb:sha256:")
    assert list(storage.objects.list("audit", f"prov-anchors/{tenants.a}/"))

    verify = _enqueue(engine, tenants.a, PROV_VERIFY_KIND, now)
    worker.run_once()
    assert _state(engine, verify).state == "succeeded"

    # a forged (unsigned) newer anchor: the next verification fails, without retries
    forged = {"schema": integrity.SCHEMA, "tenant": tenants.a, "seq": 0, "head": "x",
              "anchored_at": "2999-01-01T00:00:00.000Z", "key_id": "evil", "sig": "00"}  # fmt: skip
    storage.objects.put(
        "audit", f"prov-anchors/{tenants.a}/2999-01-01.json", json.dumps(forged).encode()
    )
    later = datetime(2999, 1, 1, 5, tzinfo=UTC)
    bad = _enqueue(engine, tenants.a, PROV_VERIFY_KIND, later)
    worker.run_once()
    st = _state(engine, bad)
    assert st.state == "failed" and integrity.ALERT in st.last_error
