"""Fixtures for m3-exec tests (3.3 queue, runs, workers): m2-core fixtures reused as in
tests/provenance, plus a synthetic 8-channel EEG recording (tools/synth ground truth, with event
markers), pipeline documents and an in-process worker."""

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

from jobs_helpers import TEST_LIBRARY, make_synth_recording  # noqa: E402


@pytest.fixture(autouse=True)
def prov_keys():
    kr = signing.Keyring(signing.Ed25519Signer.generate("test-key-1"))
    signing.configure(kr)
    yield kr
    signing.configure(None)


@pytest.fixture
def synth_rec(client, as_role, tree, storage, engine, tenants) -> dict[str, Any]:
    """An 8-channel synthetic EEG recording (256 Hz, 20 s, events every 2 s) in tenant A. The
    ``tree`` fixture's queued run is cancelled first, so each test's worker sees only its own
    jobs."""
    r = client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=as_role("owner"))
    assert r.status_code == 202 and r.json()["state"] == "cancelled", r.text
    return make_synth_recording(client, as_role("owner"), tree, storage, engine, tenants.a)


@pytest.fixture
def worker(engine, storage, tmp_path):
    from nf_runner.steprunner import InProcessRunner
    from nf_runner.worker import Worker

    return Worker(
        engine=engine,
        storage=storage,
        runner=InProcessRunner(extra_libraries=(TEST_LIBRARY,)),
        lease_s=10.0,
        heartbeat_s=0.2,
        workdir=tmp_path,
        extra_libraries=(TEST_LIBRARY,),
    )
