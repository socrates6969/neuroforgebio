"""Session-wide fixtures shared by every test directory under services/platform/tests: ONE real
PostgreSQL cluster (pgserver locally, NF_TEST_DATABASE_URL in CI) and one migrated template
database, cloned per test by ``tests/core/conftest.py``'s ``db_url``. The cluster is stopped at
session end (RAM budget)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from nf_platform.db import testing


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory) -> Iterator[str]:
    try:
        with testing.postgres_server(tmp_path_factory.mktemp("pg")) as url:
            yield url
    except testing.PostgresUnavailable as e:
        if os.environ.get("CI"):
            raise
        pytest.skip(f"no PostgreSQL available: {e}")


@pytest.fixture(scope="session")
def template_db(pg_url) -> Iterator[str]:
    name = testing.migrated_template(pg_url)
    yield name
    testing.drop_database(pg_url, name)
