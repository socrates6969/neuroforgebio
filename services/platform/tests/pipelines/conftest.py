"""Fixtures for m3-prov pipeline tests (3.2): m2-core fixtures reused as in tests/provenance."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from nf_platform.provenance import signing

_CORE = Path(__file__).resolve().parents[1] / "core" / "conftest.py"
if "nf_core_fixtures" in sys.modules:
    core = sys.modules["nf_core_fixtures"]
else:
    _spec = importlib.util.spec_from_file_location("nf_core_fixtures", _CORE)
    core = importlib.util.module_from_spec(_spec)
    sys.modules["nf_core_fixtures"] = core
    _spec.loader.exec_module(core)

# Re-export every public name of the core conftest: when several test directories run in one
# session, ``from conftest import ...`` in tests/core may resolve to this module.
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


@pytest.fixture(autouse=True)
def prov_keys():
    """A fresh Ed25519 signing keyring for every test (autouse: set before ``tree`` records its
    fixture provenance), reset afterwards."""
    kr = signing.Keyring(signing.Ed25519Signer.generate("test-key-1"))
    signing.configure(kr)
    yield kr
    signing.configure(None)
