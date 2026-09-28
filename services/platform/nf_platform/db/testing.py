"""Test helpers: a real PostgreSQL for tests, migrated once, cloned per test.

Order of preference:
1. ``NF_TEST_DATABASE_URL`` (CI: the Postgres 16 service of docker-compose.ci.yml), a superuser URL.
2. ``pgserver`` (pip package with bundled PostgreSQL 16 binaries, works on Windows): a
   throwaway cluster in a temp dir, stopped when the test session ends.
If neither is available the caller skips (``PostgresUnavailable``).

Tests connect as the superuser and switch to the app roles with SET LOCAL ROLE, exactly as the app
does.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from nf_platform.db import migrate


class PostgresUnavailable(RuntimeError):
    pass


@contextmanager
def postgres_server(workdir: Path) -> Iterator[str]:
    """Yield a superuser URL (``postgresql+psycopg://...``); stop a pgserver cluster afterwards."""
    url = os.environ.get("NF_TEST_DATABASE_URL")
    if url:
        yield _sqlalchemy_url(url)
        return
    try:
        import pgserver
    except ImportError as e:
        raise PostgresUnavailable("pgserver not installed and NF_TEST_DATABASE_URL unset") from e
    srv = pgserver.get_server(workdir, cleanup_mode="stop")
    try:
        yield _sqlalchemy_url(srv.get_uri())
    finally:
        srv.cleanup()


def _sqlalchemy_url(url: str) -> str:
    u = make_url(url)
    return str(u.set(drivername="postgresql+psycopg").render_as_string(hide_password=False))


def with_database(url: str, name: str) -> str:
    return make_url(url).set(database=name).render_as_string(hide_password=False)


def _admin(url: str):
    return create_engine(with_database(url, "postgres"), isolation_level="AUTOCOMMIT")


def create_database(url: str, name: str, template: str | None = None) -> str:
    eng = _admin(url)
    try:
        with eng.connect() as c:
            tpl = f" TEMPLATE {_ident(template)}" if template else ""
            c.execute(text(f"CREATE DATABASE {_ident(name)}{tpl}"))
    finally:
        eng.dispose()
    return with_database(url, name)


def drop_database(url: str, name: str) -> None:
    eng = _admin(url)
    try:
        with eng.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {_ident(name)} WITH (FORCE)"))
    finally:
        eng.dispose()


def migrated_template(url: str) -> str:
    """Create a database migrated to head to clone tests from; returns its name."""
    name = f"nf_tpl_{uuid.uuid4().hex[:8]}"
    migrate.upgrade(create_database(url, name))
    return name


def _ident(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"bad database name {name!r}")
    return name
