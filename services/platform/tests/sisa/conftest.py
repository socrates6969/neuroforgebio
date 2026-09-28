"""Fixtures for m6-sisa tests (6.4): the m2-core fixtures (real Postgres via pgserver, app,
mock IdP, tree) and the m5-ledger helpers (subjects, recordings, pass-through pipeline,
in-process worker), loaded as tests/governance does. The pure-core tests use none of them."""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest
from nf_platform.governance import certificate, rules
from nf_platform.provenance import signing
from sqlalchemy import text

_TESTS = Path(__file__).resolve().parents[1]
_CORE = _TESTS / "core" / "conftest.py"
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

# gov_helpers + the pass-through step library live in tests/governance (uniquely named modules)
if str(_TESTS / "governance") not in sys.path:
    sys.path.append(str(_TESTS / "governance"))
from gov_helpers import (  # noqa: E402
    TEST_LIBRARY,
    make_recording,
    make_subject,
    pass_pipeline,
    publish,
)
from nf_platform.registry.manifest import subject_hash  # noqa: E402
from nf_train import toydata  # noqa: E402

N_SUBJECTS = 8


@pytest.fixture
def sisa_keys():
    kr = signing.Keyring(signing.Ed25519Signer.generate("test-prov-key"))
    signing.configure(kr)
    certificate.configure(signing.Ed25519Signer.generate("test-cert-key"))
    rules.configure(None)
    yield kr
    signing.configure(None)
    certificate.configure(None)
    rules.configure(None)


@pytest.fixture
def worker(engine, storage, tmp_path, sisa_keys):
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


def _run(client, h, worker, ref: str, rid: str) -> str:
    r = client.post("/v1/runs", json={"pipeline": ref, "recording_id": rid}, headers=h)
    assert r.status_code == 202, r.text
    run_id = r.json()["id"]
    assert worker.run_once() is not None
    out = client.get(f"/v1/runs/{run_id}", headers=h).json()
    assert out["state"] == "succeeded", out["error"]
    return run_id


def _signal_node(engine, run_id: str) -> uuid.UUID:
    with engine.connect() as c:
        return c.execute(
            text(
                "SELECT prov_node_id FROM run_artifact WHERE run_id = :r AND name = 'signal.npy' "
                "AND visible_at IS NOT NULL"
            ),
            {"r": run_id},
        ).scalar_one()


@pytest.fixture
def world(client, as_role, tree, storage, engine, tenants, worker):
    """N single-subject run artifacts, each holding one synthetic subject's feature table."""
    h = as_role("owner")
    tid = tenants.a
    assert client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h).status_code == 202
    ref = publish(client, h, pass_pipeline("sisa-pass"))
    n_feat = toydata.N_CHANNELS * len(toydata.BANDS)
    channels = [
        {"name": f"F{i}", "modality": "EEG", "sampling_rate": 256.0, "units": "uV"}
        for i in range(n_feat + 1)
    ]
    subjects: dict[str, dict] = {}
    for i in range(N_SUBJECTS):
        sub = make_subject(client, h, tree["dataset_id"], f"sub-sisa-{i}")
        x, y = toydata.subject(11, i)
        table = toydata.encode(x, y)
        rid = make_recording(
            client,
            h,
            sub["session_id"],
            storage=storage,
            engine=engine,
            tenant_id=tid,
            subject_id=sub["subject_id"],
            channels=channels,
            data=table,
            label=f"sisa-{i}",
        )
        node = _signal_node(engine, _run(client, h, worker, ref, rid))
        hid = subject_hash(tid, sub["subject_id"])
        subjects[hid] = {**sub, "recording_id": rid, "node": node, "xy": toydata.decode(table)}
    return {"h": h, "tid": tid, "subjects": subjects}
