"""Fixtures for m4-api tests (4.1 contract, 4.6 webhooks/SSE, 4.7 early access, 4.8 limits).

Reuses m2-core's fixtures (template-DB Postgres clone per test, mock IdP, app, client, ``tree``) by
loading ``tests/core/conftest.py`` under the shared module name, as tests/ingest does.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parents[1] / "core" / "conftest.py"
if "nf_core_fixtures" in sys.modules:
    core = sys.modules["nf_core_fixtures"]
else:
    _spec = importlib.util.spec_from_file_location("nf_core_fixtures", _CORE)
    core = importlib.util.module_from_spec(_spec)
    sys.modules["nf_core_fixtures"] = core
    _spec.loader.exec_module(core)

db_url = core.db_url
engine = core.engine
tenants = core.tenants
idp = core.idp
settings = core.settings
storage = core.storage
app = core.app
client = core.client
as_role = core.as_role
tree = core.tree
bearer = core.bearer
ISSUER = core.ISSUER
AUDIENCE = core.AUDIENCE


@pytest.fixture
def audit_events(engine):
    from sqlalchemy import text

    def fetch(type_: str | None = None) -> list[dict]:
        sql = "SELECT * FROM audit_event WHERE true"
        params: dict = {}
        if type_ is not None:
            sql += " AND type = :t"
            params["t"] = type_
        with engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(text(sql + " ORDER BY seq"), params)]

    return fetch
