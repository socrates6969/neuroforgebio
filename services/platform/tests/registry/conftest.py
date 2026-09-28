"""Fixtures for m6-registry tests (6.1-6.3): the m2-core fixtures (real Postgres via pgserver, app,
mock IdP, tree) and the m5-ledger fixtures (signing keys, pass-through step library, in-process
worker) re-used as in tests/governance."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parents[1]
_GOV = _TESTS / "governance"
if str(_GOV) not in sys.path:
    sys.path.insert(0, str(_GOV))  # gov_helpers + the nf_gov_teststeps step library


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("nf_core_fixtures", _TESTS / "core" / "conftest.py")
gov = _load("nf_gov_fixtures", _GOV / "conftest.py")
# test modules elsewhere import helpers with ``from conftest import ...``; whichever conftest pytest
# imported last is ``conftest``, so re-export the core names (as tests/governance does)
globals().update({k: v for k, v in vars(core).items() if not k.startswith("_")})

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
gov_keys = gov.gov_keys
worker = gov.worker

# the M5 5.5 end-to-end scenario (subjects A, B, C; runs; group average; toy model) for 6.3
from test_gov_deletion import world  # noqa: E402, F401
