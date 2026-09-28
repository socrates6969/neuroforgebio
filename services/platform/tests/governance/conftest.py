"""Fixtures for m5-ledger tests (5.1-5.5): the m2-core fixtures (real Postgres via pgserver, app,
mock IdP, tree) re-used as in tests/jobs, plus trusted signing keys, a pass-through step library
and an in-process worker."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from nf_platform.governance import certificate, rules
from nf_platform.provenance import signing

_CORE = Path(__file__).resolve().parents[1] / "core" / "conftest.py"
if "nf_core_fixtures" in sys.modules:
    core = sys.modules["nf_core_fixtures"]
else:
    _spec = importlib.util.spec_from_file_location("nf_core_fixtures", _CORE)
    core = importlib.util.module_from_spec(_spec)
    sys.modules["nf_core_fixtures"] = core
    _spec.loader.exec_module(core)

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

from gov_helpers import TEST_LIBRARY  # noqa: E402


@pytest.fixture(autouse=True)
def gov_keys():
    """Trusted provenance/anchor key and a certificate key per test; the repo RuleSet."""
    kr = signing.Keyring(signing.Ed25519Signer.generate("test-prov-key"))
    signing.configure(kr)
    certificate.configure(signing.Ed25519Signer.generate("test-cert-key"))
    rules.configure(None)
    yield kr
    signing.configure(None)
    certificate.configure(None)
    rules.configure(None)


@pytest.fixture
def worker(engine, storage, tmp_path):
    from nf_runner.steprunner import InProcessRunner
    from nf_runner.worker import Worker

    return Worker(
        engine=engine,
        storage=storage,
        runner=InProcessRunner(extra_libraries=(TEST_LIBRARY,)),
        lease_s=30.0,
        heartbeat_s=0.5,
        workdir=tmp_path,
        extra_libraries=(TEST_LIBRARY,),
    )
