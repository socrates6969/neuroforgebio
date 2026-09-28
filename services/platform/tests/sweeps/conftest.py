"""Fixtures for m3-sweeps tests (3.6 sweeps + report, 3.9 study scaffold): m2-core fixtures reused
as in tests/jobs, the provenance signing key, an in-process worker, and the planted-effect
recording."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

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

# Re-export every public name of the core conftest (see tests/provenance/conftest.py).
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

from sweeps_helpers import make_planted_recording  # noqa: E402


@pytest.fixture(autouse=True)
def prov_keys():
    kr = signing.Keyring(signing.Ed25519Signer.generate("test-key-sweeps"))
    signing.configure(kr)
    yield kr
    signing.configure(None)


@pytest.fixture
def quiet_tree(client, as_role, tree) -> dict[str, str]:
    """The core ``tree`` with its queued example run cancelled, so a worker sees only the jobs
    a test creates."""
    r = client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=as_role("owner"))
    assert r.status_code == 202 and r.json()["state"] == "cancelled", r.text
    return tree


@pytest.fixture
def planted_rec(client, as_role, quiet_tree, storage, engine, tenants) -> dict[str, Any]:
    return make_planted_recording(client, as_role("owner"), quiet_tree, storage, engine, tenants.a)


@pytest.fixture
def worker(engine, storage, tmp_path):
    from nf_runner.steprunner import InProcessRunner
    from nf_runner.worker import Worker

    return Worker(
        engine=engine,
        storage=storage,
        runner=InProcessRunner(),
        lease_s=30.0,
        heartbeat_s=0.5,
        workdir=tmp_path,
    )
