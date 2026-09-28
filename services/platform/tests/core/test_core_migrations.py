"""2.1 acceptance: migrations run up and down cleanly; models match the migrated schema; RLS on
every table;
no password column anywhere (SEC-010)."""

from __future__ import annotations

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from nf_platform.db import migrate, testing
from nf_platform.db.models import TENANT_COLUMN, Base
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.postgres


@pytest.fixture
def empty_db(pg_url):
    name = f"nf_m_{uuid.uuid4().hex[:10]}"
    url = testing.create_database(pg_url, name)
    yield url
    testing.drop_database(pg_url, name)


def _tables(url: str) -> set[str]:
    eng = create_engine(url)
    try:
        return set(inspect(eng).get_table_names()) - {"alembic_version"}
    finally:
        eng.dispose()


def test_up_down_up(empty_db):
    migrate.upgrade(empty_db)
    assert _tables(empty_db) == set(TENANT_COLUMN)
    migrate.downgrade(empty_db, "base")
    assert _tables(empty_db) == set()
    eng = create_engine(empty_db)
    with eng.connect() as c:
        funcs = c.execute(
            text(
                "SELECT proname FROM pg_proc "
                "WHERE proname IN ('nf_current_tenant', 'nf_append_only')"
            )
        ).all()
    eng.dispose()
    assert funcs == []
    migrate.upgrade(empty_db)  # and up again (roles already exist: idempotent)
    assert _tables(empty_db) == set(TENANT_COLUMN)


def test_models_match_migrations(db_url):
    """No drift between the ORM models and the hand-written migration (Alembic autogenerate
    diff)."""
    eng = create_engine(db_url)
    with eng.connect() as c:
        ctx = MigrationContext.configure(c, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    eng.dispose()
    assert diff == []


def test_every_table_has_forced_rls_and_a_policy(db_url):
    eng = create_engine(db_url)
    with eng.connect() as c:
        rows = c.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'"
            )
        ).all()
    eng.dispose()
    assert {r[0] for r in rows} == set(TENANT_COLUMN)
    for name, enabled, forced, policies in rows:
        assert enabled and forced, f"{name}: RLS not enabled+forced"
        assert policies >= 1, f"{name}: no policy"


def test_app_roles_are_not_privileged(db_url):
    eng = create_engine(db_url)
    with eng.connect() as c:
        rows = c.execute(
            text(
                "SELECT rolname, rolsuper, rolbypassrls, rolcanlogin FROM pg_roles "
                "WHERE rolname IN ('nf_app', 'nf_audit', 'nf_auth', 'nf_audit_writer', "
                "'nf_audit_batcher')"
            )
        ).all()
    eng.dispose()
    assert len(rows) == 5
    for name, sup, bypass, login in rows:
        assert not sup and not bypass and not login, name


def test_no_password_column(db_url):
    """SEC-010: the platform never stores passwords."""
    eng = create_engine(db_url)
    insp = inspect(eng)
    cols = [(t, c["name"]) for t in insp.get_table_names() for c in insp.get_columns(t)]
    eng.dispose()
    bad = [tc for tc in cols if any(w in tc[1].lower() for w in ("pass", "pwd", "secret"))]
    assert bad == []
