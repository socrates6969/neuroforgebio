"""Keyring + SqlKeyStore on real Postgres (pgserver locally, NF_TEST_DATABASE_URL in CI) with RLS:
crypto-shred leaves a tombstone without the wrapped DEK; tenants cannot see each other's keys."""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import pytest

pytest.importorskip("sqlalchemy")
from nf_platform.db import testing  # noqa: E402
from nf_platform.db.context import Principal, tenant_session  # noqa: E402
from nf_platform.storage import Keyring, LocalKms, SubjectKeyUnavailable  # noqa: E402
from nf_platform.storage.sql_keystore import SqlKeyStore  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    try:
        with testing.postgres_server(tmp_path_factory.mktemp("pgk")) as url:
            name = f"nf_k_{uuid.uuid4().hex[:8]}"
            db = testing.create_database(url, name)
            from nf_platform.db import migrate

            migrate.upgrade(db)
            eng = create_engine(db, pool_size=2, max_overflow=2)
            yield eng
            eng.dispose()
            testing.drop_database(url, name)
    except testing.PostgresUnavailable as e:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"no PostgreSQL available: {e}")


def _provision(eng) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    with eng.begin() as c:  # superuser provisioning (bypasses RLS by design)
        for t in ("a", "b"):
            tid, pid, did = (str(uuid.uuid4()) for _ in range(3))
            c.execute(text("INSERT INTO tenant (id, name) VALUES (:i, :n)"), {"i": tid, "n": t})
            c.execute(
                text(
                    "INSERT INTO project (id, tenant_id, name, created_by) VALUES (:p,:t,'p','x')"
                ),
                {"p": pid, "t": tid},
            )
            c.execute(
                text(
                    "INSERT INTO dataset (id, tenant_id, project_id, name, created_by) "
                    "VALUES (:d,:t,:p,'d','x')"
                ),
                {"d": did, "t": tid, "p": pid},
            )
            subs = [str(uuid.uuid4()) for _ in range(2)]
            for i, sid in enumerate(subs):
                c.execute(
                    text(
                        "INSERT INTO subject (id, tenant_id, dataset_id, label, created_by) "
                        "VALUES (:s,:t,:d,:l,'x')"
                    ),
                    {"s": sid, "t": tid, "d": did, "l": f"S{i}"},
                )
            out[tid] = subs
    return out


def test_sql_keystore_shred_and_isolation(pg):
    tenants = _provision(pg)

    @contextmanager
    def session_for(tenant_id):
        p = Principal(
            id="svc-keyring",
            tenant_id=tenant_id,
            roles=frozenset({"service"}),
            scopes=frozenset(),
            kind="api_key",
            mfa_phr=False,
        )
        with tenant_session(p, engine=pg) as s:
            yield s

    ks = SqlKeyStore(session_for)
    kms = LocalKms()
    kr = Keyring(kms, ks)
    (ta, subs_a), (tb, subs_b) = tenants.items()
    blobs = {s: kr.encrypt(ta, s, "raw/x", 1, s.encode()) for s in subs_a}
    blob_b = kr.encrypt(tb, subs_b[0], "raw/x", 1, b"b")
    fresh = Keyring(kms, ks, cache_deks=False)
    for s, b in blobs.items():
        assert fresh.decrypt(ta, s, "raw/x", 1, b) == s.encode()
    assert ks.get_wrapped(ta, subs_a[0]).encryption_count == 1

    # RLS: a tenant-A session sees no tenant-B key rows, even when asking for them explicitly.
    with session_for(ta) as s:
        n = s.execute(
            text("SELECT count(*) FROM subject_key WHERE tenant_id = :t"), {"t": tb}
        ).scalar_one()
        assert n == 0

    assert kr.shred_subject(ta, subs_a[0]) == 1
    with pytest.raises(SubjectKeyUnavailable):
        Keyring(kms, ks).decrypt(ta, subs_a[0], "raw/x", 1, blobs[subs_a[0]])
    assert fresh.decrypt(ta, subs_a[1], "raw/x", 1, blobs[subs_a[1]]) == subs_a[1].encode()
    assert fresh.decrypt(tb, subs_b[0], "raw/x", 1, blob_b) == b"b"
    with pg.begin() as c:
        row = c.execute(
            text("SELECT state, wrapped_dek, shredded_at FROM subject_key WHERE subject_id = :s"),
            {"s": subs_a[0]},
        ).one()
    assert row.state == "shredded" and row.wrapped_dek is None and row.shredded_at is not None

    # KEK rotation re-wraps the tenant's live DEKs in the table.
    assert kr.rotate_tenant_kek(ta) == 1
    assert Keyring(kms, ks).decrypt(ta, subs_a[1], "raw/x", 1, blobs[subs_a[1]])
