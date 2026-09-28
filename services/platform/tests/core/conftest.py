"""Fixtures for m2-core tests: real Postgres (pgserver or NF_TEST_DATABASE_URL), a mock OIDC IdP,
the app."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from nf_platform.app import create_app
from nf_platform.config import OidcSettings, Settings, StaticSecretProvider
from nf_platform.db import testing
from nf_platform.db.context import tenant_session
from nf_platform.ingest import recording_store as rs
from nf_platform.signals.zarr_store import write_recording
from nf_platform.storage.runtime import local_storage
from sqlalchemy import Engine, create_engine, text

ISSUER = "https://idp.test.invalid/realms/nf"
AUDIENCE = "nf-api"
ALL_ROLES = ("owner", "admin", "data-steward", "auditor", "scientist", "viewer", "device")


# ---------------------------------------------------------------- Postgres
# pg_url / template_db (session-scoped, one cluster for every test directory): tests/conftest.py
@pytest.fixture
def db_url(pg_url, template_db) -> Iterator[str]:
    name = f"nf_t_{uuid.uuid4().hex[:10]}"
    url = testing.create_database(pg_url, name, template=template_db)
    yield url
    testing.drop_database(pg_url, name)


@pytest.fixture
def engine(db_url) -> Iterator[Engine]:
    eng = create_engine(db_url, pool_size=2, max_overflow=2)
    yield eng
    eng.dispose()


@dataclass(frozen=True)
class Tenants:
    a: str
    b: str


@pytest.fixture
def tenants(engine) -> Tenants:
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as c:  # superuser: provisioning bypasses RLS by design
        for tid, name in ((a, "tenant-a"), (b, "tenant-b")):
            c.execute(text("INSERT INTO tenant (id, name) VALUES (:i, :n)"), {"i": tid, "n": name})
    return Tenants(a, b)


# ---------------------------------------------------------------- mock IdP
class MockIdP:
    """An in-process OIDC provider: RSA signing key, JWKS, token minting."""

    def __init__(self, issuer: str = ISSUER, kid: str = "k1") -> None:
        self.issuer = issuer
        self.kid = kid
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwks(self) -> dict[str, Any]:
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        jwk.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        return {"keys": [jwk]}

    def token(
        self,
        *,
        sub: str = "user-1",
        tenant: str,
        roles: list[str] | tuple[str, ...] = (),
        amr: list[str] | None = None,
        exp_in: int = 300,
        aud: str = AUDIENCE,
        iss: str | None = None,
        kid: str | None = None,
        key=None,
        alg: str = "RS256",
        drop: tuple[str, ...] = (),
        **extra: Any,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": iss or self.issuer,
            "aud": aud,
            "sub": sub,
            "iat": now,
            "exp": now + exp_in,
            "nf_tenant": tenant,
            "nf_roles": list(roles),
            "amr": ["pwd", "hwk"] if amr is None else amr,
            **extra,
        }
        for k in drop:
            claims.pop(k, None)
        return jwt.encode(claims, key or self.key, algorithm=alg, headers={"kid": kid or self.kid})


@pytest.fixture(scope="session")
def idp() -> MockIdP:
    return MockIdP()


@pytest.fixture
def settings(db_url) -> Settings:
    return Settings(
        database_url=db_url,
        oidc=OidcSettings(issuer=ISSUER, audience=AUDIENCE),
        secrets=StaticSecretProvider(version="p1", pepper=os.urandom(32)),
        upload_part_min=16,  # small parts so upload tests stay tiny
    )


@pytest.fixture
def storage(engine, tmp_path):
    """Object store in tmp + LocalKms + key rows in this test's Postgres (RLS)."""
    return local_storage(tmp_path / "objects", engine=engine)


@pytest.fixture
def app(settings, engine, idp, storage):
    return create_app(settings, engine=engine, jwks=idp.jwks, storage=storage)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def as_role(idp, tenants):
    """Headers for a user of tenant A (or ``tenant=``) holding ``roles``; phishing-resistant MFA by
    default."""

    def make(*roles: str, tenant: str | None = None, phr: bool = True, sub: str | None = None):
        amr = ["pwd", "hwk"] if phr else ["pwd", "otp"]
        sub = sub or f"user-{'-'.join(roles) or 'none'}"
        return bearer(idp.token(sub=sub, tenant=tenant or tenants.a, roles=list(roles), amr=amr))

    return make


@pytest.fixture
def tree(client, as_role, tenants, storage, engine):
    """A project → dataset → subject → session → recording chain in tenant A (created by an
    owner). The recording has a small canonical signal (2 ch x 4096 samples at 256 Hz, int16;
    long enough for pyramid level 1) so the data endpoint answers, and the owner has one open
    upload (``upload_id``/``part_number``)."""
    ids = make_tree(client, as_role("owner"))
    # m5-ledger (5.4): data reads and runs need consent; the tree's subject consented to every
    # scope on a registered consent document.
    ids["consent_document_id"] = grant_consent(client, as_role("owner"), ids["subject_id"])
    attach_signal(storage, engine, tenants.a, ids)
    ids["upload_id"] = make_upload(client, as_role("owner"), ids)
    ids["part_number"] = "1"
    # m3-prov: a provenance node for the recording and one published PipelineVersion
    ids["node_id"] = attach_provenance(engine, tenants.a, ids)
    ids["_tenant_id"] = tenants.a
    r = client.post("/v1/pipelines", json=EXAMPLE_PIPELINE, headers=as_role("owner"))
    assert r.status_code in (200, 201), r.text
    ids["pipeline_ref"] = r.json()["ref"]
    # m3-exec: one queued run of that pipeline on the recording (3.3)
    r = client.post(
        "/v1/runs",
        json={"pipeline": ids["pipeline_ref"], "recording_id": ids["recording_id"]},
        headers=as_role("owner"),
    )
    assert r.status_code == 202, r.text
    ids["run_id"] = r.json()["id"]
    return ids


# m3-prov (3.2): the example PipelineVersion document (validates against
# docs/spec/pipeline-version.schema.json).
EXAMPLE_PIPELINE_PATH = (
    Path(__file__).resolve().parents[4] / "docs" / "spec" / "pipeline-version.example.json"
)
EXAMPLE_PIPELINE = json.loads(EXAMPLE_PIPELINE_PATH.read_text(encoding="utf-8"))


def attach_artifact_node(app_state, ids: dict[str, str]) -> str:
    """m5-ledger: record a derived artifact entity (wasDerivedFrom the tree's recording node);
    returns its node id. Uses the app's engine (the test database)."""
    from nf_platform.db.context import get_engine
    from nf_platform.provenance import api as prov
    from nf_platform.storage.runtime import service_principal

    tid = ids["_tenant_id"]
    svc = service_principal(tid, "svc:test-fixture")
    with tenant_session(svc, engine=get_engine()) as s:
        c = prov.record(
            s,
            svc,
            [prov.NodeSpec(prov.ProvKind.ENTITY, "feature", None, None, {"fixture": True})],
            [(0, prov.EdgeType.WAS_DERIVED_FROM, uuid.UUID(ids["node_id"]))],
        )
    return str(c.node_ids[0])


def attach_provenance(engine, tenant_id: str, ids: dict[str, str]) -> str:
    """Record ``raw_file --> convert --> recording`` for ``ids['recording_id']``; returns the
    recording's provenance node id."""
    from nf_platform.provenance import api as prov
    from nf_platform.storage.runtime import service_principal

    svc = service_principal(tenant_id, "svc:test-fixture")
    with tenant_session(svc, engine=engine) as s:
        c = prov.record(
            s,
            svc,
            [
                prov.NodeSpec(prov.ProvKind.ENTITY, "raw_file", f"fixture-{ids['recording_id']}"),
                prov.NodeSpec(prov.ProvKind.ACTIVITY, "convert"),
                prov.NodeSpec(prov.ProvKind.ENTITY, "recording", ids["recording_id"]),
            ],
            [(1, prov.EdgeType.USED, 0), (2, prov.EdgeType.WAS_GENERATED_BY, 1)],
        )
    return str(c.node_ids[2])


TREE_SIGNAL = (np.arange(2 * 4096, dtype=np.int64).reshape(2, 4096) % 2000 - 1000).astype(np.int16)
UPLOAD_BYTES = b"0123456789abcdef0123456789abcdef"  # 32 bytes = one part at the test part size


def attach_signal(storage, engine, tenant_id: str, ids: dict[str, str], data=TREE_SIGNAL) -> str:
    """Write ``data`` as the canonical signal of ``ids['recording_id']`` and link it."""
    prefix = rs.stream_prefix(tenant_id, ids["subject_id"], ids["recording_id"])
    store = rs.open_store(storage, tenant_id, ids["subject_id"], prefix)
    write_recording(store, "signal", data, 256.0, ["Cz", "EMG1"], ["uV", "uV"])
    ref = rs.make_ref(prefix, "signal")
    with engine.begin() as c:
        c.execute(
            text("UPDATE recording SET zarr_ref = :r WHERE id = :i"),
            {"r": ref, "i": ids["recording_id"]},
        )
    return ref


def make_upload(client: TestClient, h: dict[str, str], ids: dict[str, str], **kw: Any) -> str:
    body = {
        "session_id": ids["session_id"],
        "filename": "rec.edf",
        "size_bytes": len(UPLOAD_BYTES),
        "synthetic": True,
        **kw,
    }
    r = client.post(f"/v1/datasets/{ids['dataset_id']}/uploads", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


ALL_SCOPES = ("collection", "processing", "sharing", "model_training", "commercial_use")
CONSENT_DOC = {"name": "fixture-consent", "version": "1", "sha256": "ab" * 32}


def grant_consent(client: TestClient, h: dict[str, str], subject_id: str, scopes=ALL_SCOPES) -> str:
    """m5-ledger: register the fixture consent document (idempotent) and grant ``scopes`` for the
    subject. Returns the document id."""
    r = client.post("/v1/consent-documents", json=CONSENT_DOC, headers=h)
    assert r.status_code in (200, 201), r.text
    doc = r.json()["id"]
    r = client.post(
        f"/v1/subjects/{subject_id}/consents",
        json={"kind": "grant", "scopes": list(scopes), "document_id": doc},
        headers=h,
    )
    assert r.status_code == 201, r.text
    return doc


def make_tree(client: TestClient, h: dict[str, str]) -> dict[str, str]:
    def post(path: str, body: dict[str, Any]) -> str:
        r = client.post(path, json=body, headers=h)
        assert r.status_code == 201, r.text
        return r.json()["id"]

    ids: dict[str, str] = {}
    ids["project_id"] = post("/v1/projects", {"name": "p"})
    ids["dataset_id"] = post(f"/v1/projects/{ids['project_id']}/datasets", {"name": "d"})
    ids["subject_id"] = post(f"/v1/datasets/{ids['dataset_id']}/subjects", {"label": "sub-01"})
    ids["session_id"] = post(f"/v1/subjects/{ids['subject_id']}/sessions", {"label": "ses-1"})
    ids["recording_id"] = post(
        f"/v1/sessions/{ids['session_id']}/recordings",
        {
            "label": "run-1",
            "channels": [
                {
                    "name": "Cz",
                    "modality": "EEG",
                    "nervous_system": "central",
                    "sampling_rate": 256.0,
                    "units": "uV",
                },
                {"name": "EMG1", "modality": "EMG", "sampling_rate": 1000.0, "units": "uV"},
            ],
        },
    )
    return ids


# ---------------------------------------------------------------- m6-registry (M6 6.1-6.3)
REGISTRY_CARD = {
    "summary": "fixture model",
    "task": "decoding",
    "inferences": ["motor_intent"],
    "modalities": ["EEG"],
    "limitations": "fixture",
    "robustness": {
        k: {"method": "fixture", "metric": "accuracy", "value": 0.5}
        for k in ("noise", "channel_dropout", "adversarial")
    },
    "privacy_risk": {
        "membership_inference": {"method": "fixture", "metric": "auc", "value": 0.5},
        "held_out_split": "fixture",
    },
}
# a minimal safetensors file: one F32 tensor of shape [1]
_ST_HEADER = b'{"w":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}'
REGISTRY_WEIGHTS = len(_ST_HEADER).to_bytes(8, "little") + _ST_HEADER + b"\x00" * 4


def registry_version_body(node_id: str) -> dict[str, Any]:
    import base64

    return {
        "weights": {
            "format": "safetensors",
            "data_base64": base64.b64encode(REGISTRY_WEIGHTS).decode(),
        },
        "training_manifest": {"input_node_ids": [node_id]},
        "code_commit": "0123456789abcdef0123456789abcdef01234567",
        "intended_use": "fixture",
    }


def audit_batch_ids(client: TestClient, ids: dict[str, Any]) -> dict[str, Any]:
    """AppSec M1: tenant A's first audit batch (seq 0) in the app's WORM store, for
    ``GET /v1/audit/batches/{seq}/object``. Moves the events so far into the previous hour (test
    only: the append-only trigger is off meanwhile). Sets ``seq`` (idempotent per ids dict)."""
    if "seq" in ids:
        return ids
    from nf_platform.audit import chain  # noqa: PLC0415
    from nf_platform.db.context import get_engine  # noqa: PLC0415

    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("ALTER TABLE audit_event DISABLE TRIGGER audit_event_append_only"))
        c.execute(text("UPDATE audit_event SET ts = ts - interval '2 hours'"))
        c.execute(text("ALTER TABLE audit_event ENABLE TRIGGER audit_event_append_only"))
    chain.AuditBatcher(eng, client.app.state.storage.objects).run(scopes=[ids["_tenant_id"]])
    ids["seq"] = "0"
    return ids


def registry_ids(client: TestClient, h: dict[str, str], ids: dict[str, Any]) -> dict[str, Any]:
    """m6-registry: a model (card with privacy section) with version 1 trained on a feature derived
    from the tree's recording node, and one queued retrain of it. Sets ``reg_node``, ``model_id``,
    ``version`` and ``retrain_id`` in ``ids`` (idempotent per ids dict)."""
    if "model_id" in ids:
        return ids
    ids["reg_node"] = attach_artifact_node(client.app.state, ids)
    r = client.post(
        "/v1/models", json={"name": f"m-{uuid.uuid4().hex[:8]}", "card": REGISTRY_CARD}, headers=h
    )
    assert r.status_code == 201, r.text
    ids["model_id"] = r.json()["id"]
    r = client.post(
        f"/v1/models/{ids['model_id']}/versions",
        json=registry_version_body(ids["reg_node"]),
        headers=h,
    )
    assert r.status_code == 201, r.text
    ids["version"] = str(r.json()["version"])
    r = client.post(
        f"/v1/models/{ids['model_id']}/versions/{ids['version']}/retrain", json={}, headers=h
    )
    assert r.status_code == 202, r.text
    ids["retrain_id"] = r.json()["id"]
    return ids
