"""Fixtures for m2-stream tests (2.4 data endpoint, 2.6 uploads, 2.7 stream ingest).

Reuses m2-core's fixtures (template-DB Postgres clone per test, mock IdP, app, client, ``tree``)
by loading ``tests/core/conftest.py`` under its own module name; the session-scoped Postgres
cluster itself lives in ``tests/conftest.py`` so both directories share ONE cluster.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parents[1] / "core" / "conftest.py"
_spec = importlib.util.spec_from_file_location("nf_core_fixtures", _CORE)
core = importlib.util.module_from_spec(_spec)
sys.modules["nf_core_fixtures"] = core
_spec.loader.exec_module(core)

# Fixtures (pytest registers fixture objects found as attributes of a conftest module).
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

# Helpers
ALL_ROLES = core.ALL_ROLES
UPLOAD_BYTES = core.UPLOAD_BYTES
TREE_SIGNAL = core.TREE_SIGNAL
attach_signal = core.attach_signal
make_tree = core.make_tree
make_upload = core.make_upload


@pytest.fixture
def audit_events(engine):
    """Return audit rows (as dicts) matching a request id / type."""
    from sqlalchemy import text

    def fetch(request_id: str | None = None, type_: str | None = None) -> list[dict]:
        sql = "SELECT * FROM audit_event WHERE true"
        params: dict = {}
        if request_id is not None:
            sql += " AND request_id = :r"
            params["r"] = request_id
        if type_ is not None:
            sql += " AND type = :t"
            params["t"] = type_
        with engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(text(sql + " ORDER BY seq"), params)]

    return fetch
