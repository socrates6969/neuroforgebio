"""2.2 acceptance / SEC-020, SEC-011: role × endpoint matrix generated from the app's routes.

The EXPECTED table below is the reviewed policy, written independently of ``authorize.PERMISSIONS``.
Every route must declare an action that is in this table (or be public); a new route without one
fails ``test_every_route_is_mapped``, and a route whose behaviour differs from the table fails the
matrix.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from conftest import ALL_ROLES, UPLOAD_BYTES, make_upload
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.routing import APIRoute
from nf_contract import Contract
from nf_platform.api.deps import ACTION_KEY, PUBLIC

pytestmark = pytest.mark.postgres
EXAMPLE_PIPELINE = json.loads(
    (Path(__file__).resolve().parents[4] / "docs/spec/pipeline-version.example.json").read_text()
)

READ = {"owner", "admin", "data-steward", "auditor", "scientist", "viewer"}
WRITE = {"owner", "admin", "data-steward", "scientist"}
KEYS = {"owner", "admin", "data-steward", "scientist", "viewer"}
GOV = {"owner", "admin", "data-steward"}
EXPECTED: dict[str, set[str]] = {
    "self:read": set(ALL_ROLES),
    "project:read": READ,
    "project:create": {"owner", "admin"},
    "dataset:read": READ,
    "dataset:create": WRITE,
    "subject:read": READ,
    "subject:create": WRITE,
    "session:read": READ,
    "session:create": WRITE,
    "recording:read": READ,
    "recording:create": WRITE,
    "apikey:create": KEYS,
    "apikey:read": KEYS,
    "apikey:revoke": KEYS,
    "audit:read": {"owner", "admin", "auditor"},
    # m2-stream: window reads (2.4), uploads (2.6), devices + streams (2.7)
    "signal:read": READ,
    "upload:create": WRITE,
    "upload:read": WRITE,
    "device:create": WRITE,
    "device:read": WRITE,
    "stream:create": WRITE,
    # m3-prov: provenance reads + export (3.1, 3.7), PipelineVersions (3.2)
    "provenance:read": READ,
    "provenance:export": READ,
    "pipeline:read": READ,
    "pipeline:create": WRITE,
    # m3-exec: pipeline runs (3.3)
    "run:read": READ,
    "run:create": WRITE,
    "run:cancel": WRITE,
    # m5-ledger (M5): SEC-022 governance writes = data-steward/admin (owner included)
    "governance:read": READ,
    "governance:write": GOV,
    "governance:admin": {"owner", "admin"},
    "classification:read": READ,
    "consent:read": {"owner", "admin", "data-steward", "auditor", "scientist"},
    "consent:create": GOV,
    "withdrawal:create": GOV,
    "withdrawal:read": {"owner", "admin", "data-steward", "auditor"},
    # m3-sweeps: multiverse sweeps + report (3.6)
    "sweep:read": READ,
    "sweep:create": WRITE,
    # m4-api: quotas (4.8); webhooks (4.6) are tenant configuration: owner/admin only
    "quota:read": READ,
    "webhook:read": {"owner", "admin"},
    "webhook:create": {"owner", "admin"},
    "webhook:update": {"owner", "admin"},
    "webhook:delete": {"owner", "admin"},
    # m5-evidence: FDA Evidence Kit (5.8): compliance roles only
    "evidence:export": {"owner", "admin", "data-steward", "auditor"},
    # m6-registry (M6 6.1-6.3): versions/retrains are model:train, publication model:publish
    # (owner/admin, SEC-143), approvals + Art. 5(1)(f) exception records are governance decisions
    "model:read": READ,
    "model:create": WRITE,
    "model:train": WRITE,
    "model:deploy": WRITE,
    "model:approve": GOV,
    "model:exception": GOV,
    "model:publish": {"owner", "admin"},
    # m6-sisa (6.5): SOUP export = model readers; SBOM attach = owner/admin
    "model:soup-export": READ,
    "model:sbom-attach": {"owner", "admin"},
}
# M4 4.1: every response of the matrix is also checked against openapi/v1.yaml.
CONTRACT = Contract()
ADMIN_CLASS = {"owner", "admin", "data-steward", "auditor"}

BODIES: dict[tuple[str, str], Any] = {
    ("POST", "/v1/projects"): lambda: {"name": "p"},
    ("POST", "/v1/projects/{project_id}/datasets"): lambda: {"name": "d"},
    ("POST", "/v1/datasets/{dataset_id}/subjects"): lambda: {"label": f"s-{uuid.uuid4().hex[:8]}"},
    ("POST", "/v1/subjects/{subject_id}/sessions"): lambda: {"label": "ses"},
    ("POST", "/v1/sessions/{session_id}/recordings"): lambda: {
        "label": "r",
        "channels": [{"name": "Cz", "modality": "EEG", "sampling_rate": 250, "units": "uV"}],
    },
    ("POST", "/v1/api-keys"): lambda: {
        "name": "k",
        "roles": ["viewer"],
        "scopes": ["metadata:read"],
    },
    # Placeholders (the matrix fills real ids through PREP below).
    ("POST", "/v1/datasets/{dataset_id}/uploads"): lambda: {
        "session_id": str(uuid.uuid4()),
        "filename": "rec.edf",
        "size_bytes": 32,
        "synthetic": True,
    },
    ("POST", "/v1/uploads/{upload_id}/complete"): lambda: {"sha256": "0" * 64},
    ("POST", "/v1/devices"): lambda: {"name": "lab-pc", "public_key": new_device_key()[1]},
    ("POST", "/v1/sessions/{session_id}/streams"): lambda: stream_body(str(uuid.uuid4())),
    # identical re-publish is idempotent (200), the first publish is in the tree fixture
    ("POST", "/v1/pipelines"): lambda: EXAMPLE_PIPELINE,
    # m3-exec: filled with the tree's pipeline + recording through PREP
    ("POST", "/v1/runs"): lambda: {"pipeline": "x@1.0.0", "recording_id": str(uuid.uuid4())},
    ("POST", "/v1/runs/{run_id}/cancel"): lambda: {},
    # m5-ledger (ids filled through PREP where needed)
    ("PATCH", "/v1/recordings/{recording_id}/channels"): lambda: {
        "changes": [{"index": 1, "nervous_system": "peripheral"}]
    },
    ("POST", "/v1/governance/channels/bulk"): lambda: {
        "recording_ids": [str(uuid.uuid4())],
        "set": {"derived_from_non_neural": False},
    },
    ("PUT", "/v1/artifacts/{node_id}/governance"): lambda: {
        "derived_from_non_neural": True,
        "reason": "matrix",
    },
    ("PUT", "/v1/governance/tenant-policy"): lambda: {"aggregate_on_withdrawal": "tombstone"},
    ("POST", "/v1/consent-documents"): lambda: {
        "name": "matrix-doc",
        "version": "1",
        "sha256": "cd" * 32,
    },
    ("POST", "/v1/subjects/{subject_id}/consents"): lambda: {
        "kind": "withdraw",
        "scopes": ["commercial_use"],
    },
    ("POST", "/v1/subjects/{subject_id}/withdrawals"): lambda: {},
    # m3-sweeps: filled with the tree's pipeline + recording through PREP
    ("POST", "/v1/sweeps"): lambda: {
        "pipeline": "x@1.0.0",
        "recording_ids": [str(uuid.uuid4())],
        "grid": {"filter.l_freq": [0.5]},
        "metric": {"step": "rereference", "key": "accuracy"},
    },
    # m4-api (4.6)
    ("POST", "/v1/webhooks"): lambda: {
        "url": "https://hooks.example.com/nf",
        "event_types": ["run.finished"],
    },
    ("POST", "/v1/webhooks/{webhook_id}/rotate-secret"): lambda: {},
    # m5-evidence: the tree's provenance node is filled through PREP
    ("POST", "/v1/exports/fda-evidence"): lambda: {"node_id": str(uuid.uuid4())},
    # m6-registry: model ids + the input node are filled through PREP (_prep_registry)
    ("POST", "/v1/models"): lambda: {
        "name": f"m-{uuid.uuid4().hex[:8]}",
        "card": core_fixtures().REGISTRY_CARD,
    },
    ("POST", "/v1/models/{model_id}/versions"): lambda: core_fixtures().registry_version_body(
        str(uuid.uuid4())
    ),
    ("POST", "/v1/models/{model_id}/versions/{version}/approvals"): lambda: {},
    ("POST", "/v1/models/{model_id}/versions/{version}/publish"): lambda: {},
    ("POST", "/v1/models/{model_id}/versions/{version}/retrain"): lambda: {},
    # m6-sisa (6.5): a minimal CycloneDX SBOM of the model's container
    ("PUT", "/v1/models/{model_id}/versions/{version}/sbom"): lambda: {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [{"type": "library", "name": "numpy", "version": "2.3.3"}],
    },
    ("POST", "/v1/models/{model_id}/deployments"): lambda: {
        "version": 1,
        "context": {"jurisdiction": "US", "setting": "research", "purpose": "matrix"},
    },
    ("POST", "/v1/models/{model_id}/use-exceptions"): lambda: {
        "basis": "medical",
        "jurisdiction": "EU",
        "setting": "workplace",
        "justification": "matrix",
        "evidence_ref": "matrix-ref",
    },
}
# Extra query parameters a route needs to succeed.
QUERY: dict[tuple[str, str], dict[str, Any]] = {
    ("GET", "/v1/recordings/{recording_id}/data"): {"start": 0, "end": 1},
    ("GET", "/v1/provenance/{node_id}/export"): {"format": "prov-json"},
    # m4-api: the SSE stream closes at once (first event, then timeout)
    ("GET", "/v1/runs/{run_id}/events"): {"wait_s": 0},
    ("GET", "/v1/classifications"): {"recording_id": "{recording_id}"},
}


def params_for(method: str, path: str, ids: dict[str, str]) -> dict[str, Any] | None:
    """QUERY with ``{id}`` placeholders filled from the fixture ids."""
    q = QUERY.get((method, path))
    if q is None:
        return None
    return {k: (_fill(v, ids) if isinstance(v, str) and "{" in v else v) for k, v in q.items()}


def new_device_key() -> tuple[Ed25519PrivateKey, str]:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return key, base64.b64encode(pub).decode()


def stream_body(device_id: str, **kw: Any) -> dict[str, Any]:
    return {
        "label": "live",
        "device_id": device_id,
        "sfreq": 1000.0,
        "dtype": "float32",
        "channels": [{"name": f"C{i}", "modality": "EEG", "units": "uV"} for i in range(4)],
        "synthetic": True,
        **kw,
    }


def _prep_upload_owned(client, creator, ids) -> dict[str, Any]:
    ids["upload_id"] = make_upload(client, creator, ids)
    return {}


def _prep_put_part(client, creator, ids) -> dict[str, Any]:
    ids["upload_id"] = make_upload(client, creator, ids)
    return {"content": UPLOAD_BYTES}


def _prep_complete(client, creator, ids) -> dict[str, Any]:
    ids["upload_id"] = make_upload(client, creator, ids)
    r = client.put(f"/v1/uploads/{ids['upload_id']}/parts/1", content=UPLOAD_BYTES, headers=creator)
    assert r.status_code == 200, r.text
    return {"json": {"sha256": hashlib.sha256(UPLOAD_BYTES).hexdigest()}}


def _prep_create_upload(client, creator, ids) -> dict[str, Any]:
    body = BODIES[("POST", "/v1/datasets/{dataset_id}/uploads")]()
    return {"json": {**body, "session_id": ids["session_id"]}}


def _prep_stream(client, creator, ids) -> dict[str, Any]:
    r = client.post("/v1/devices", json=BODIES[("POST", "/v1/devices")](), headers=creator)
    assert r.status_code == 201, r.text
    return {"json": stream_body(r.json()["id"])}


# (method, path) -> fn(client, creator_headers, ids) -> request kwargs. The creator is the caller
# when its role may create the object, else an owner (the caller's 403 comes first anyway).
def _run_body(ids) -> dict[str, Any]:
    return {"pipeline": ids["pipeline_ref"], "recording_id": ids["recording_id"]}


def _prep_create_run(client, creator, ids) -> dict[str, Any]:
    return {"json": _run_body(ids)}


def _prep_run_owned(client, creator, ids) -> dict[str, Any]:
    r = client.post("/v1/runs", json=_run_body(ids), headers=creator)
    assert r.status_code == 202, r.text
    ids["run_id"] = r.json()["id"]
    return {}


def _prep_bulk(client, creator, ids) -> dict[str, Any]:
    body = BODIES[("POST", "/v1/governance/channels/bulk")]()
    return {"json": {**body, "recording_ids": [ids["recording_id"]]}}


def _prep_artifact_node(client, creator, ids) -> dict[str, Any]:
    """A derived artifact (entity wasDerivedFrom the tree's recording node)."""
    import importlib
    import sys

    core = sys.modules.get("nf_core_fixtures") or importlib.import_module("conftest")
    ids["node_id"] = core.attach_artifact_node(client.app.state, ids)
    return {}


def _prep_withdrawal(client, creator, ids) -> dict[str, Any]:
    owner = ids["_owner_headers"]
    r = client.post(
        f"/v1/datasets/{ids['dataset_id']}/subjects",
        json={"label": f"w-{uuid.uuid4().hex[:8]}"},
        headers=owner,
    )
    assert r.status_code == 201, r.text
    ids["subject_id"] = r.json()["id"]
    return {}


def _prep_deletion(client, creator, ids) -> dict[str, Any]:
    owner = ids["_owner_headers"]
    r = client.post(
        f"/v1/datasets/{ids['dataset_id']}/subjects",
        json={"label": f"d-{uuid.uuid4().hex[:8]}"},
        headers=owner,
    )
    assert r.status_code == 201, r.text
    r = client.post(f"/v1/subjects/{r.json()['id']}/withdrawals", json={}, headers=owner)
    assert r.status_code == 202, r.text
    ids["deletion_id"] = r.json()["id"]
    return {}


def _sweep_body(ids) -> dict[str, Any]:
    return {
        "pipeline": ids["pipeline_ref"],
        "recording_ids": [ids["recording_id"]],
        "grid": {"filter.l_freq": [0.5]},
        "metric": {"step": "rereference", "key": "accuracy"},
    }


def _prep_create_sweep(client, creator, ids) -> dict[str, Any]:
    return {"json": _sweep_body(ids)}


def _prep_sweep_owned(client, creator, ids) -> dict[str, Any]:
    r = client.post("/v1/sweeps", json=_sweep_body(ids), headers=creator)
    assert r.status_code == 202, r.text
    ids["sweep_id"] = r.json()["id"]
    return {}


def _prep_webhook_owned(client, creator, ids) -> dict[str, Any]:
    r = client.post("/v1/webhooks", json=BODIES[("POST", "/v1/webhooks")](), headers=creator)
    assert r.status_code == 201, r.text
    ids["webhook_id"] = r.json()["id"]
    return {}


def _prep_evidence(client, creator, ids) -> dict[str, Any]:
    return {"json": {"node_id": ids["node_id"]}}


def core_fixtures():
    import importlib
    import sys

    return sys.modules.get("nf_core_fixtures") or importlib.import_module("conftest")


def _prep_registry(client, creator, ids) -> dict[str, Any]:
    """m6-registry: a model with version 1 (+ a queued retrain), created by an owner."""
    core_fixtures().registry_ids(client, ids["_owner_headers"], ids)
    return {}


def _prep_audit_batch(client, creator, ids) -> dict[str, Any]:
    """AppSec M1: tenant A's audit batch 0 exists in the WORM store."""
    core_fixtures().audit_batch_ids(client, ids)
    return {}


def _prep_register_version(client, creator, ids) -> dict[str, Any]:
    _prep_registry(client, creator, ids)
    return {"json": core_fixtures().registry_version_body(ids["reg_node"])}


def _prep_deploy(client, creator, ids) -> dict[str, Any]:
    """AppSec M3: the fixture version is upload-sourced; a governance approver other than the
    uploader makes it deployable."""
    _prep_registry(client, creator, ids)
    url = f"/v1/models/{ids['model_id']}/versions/{ids['version']}/approvals"
    r = client.post(url, headers=dict(ids["_approver_headers"]("matrix-approver-0")))
    assert r.status_code == 201, r.text
    return {}


def _prep_publish(client, creator, ids) -> dict[str, Any]:
    """Four-eyes (SEC-143): two governance approvers other than the publisher."""
    _prep_registry(client, creator, ids)
    for sub in ("matrix-approver-1", "matrix-approver-2"):
        h = dict(ids["_approver_headers"](sub))
        url = f"/v1/models/{ids['model_id']}/versions/{ids['version']}/approvals"
        r = client.post(url, headers=h)
        assert r.status_code == 201, r.text
    return {}


REGISTRY_ROUTES = (
    ("GET", "/v1/models/{model_id}"),
    ("GET", "/v1/models/{model_id}/versions"),
    ("GET", "/v1/models/{model_id}/versions/{version}"),
    ("GET", "/v1/models/{model_id}/versions/{version}/lineage"),
    ("POST", "/v1/models/{model_id}/versions/{version}/approvals"),
    ("POST", "/v1/models/{model_id}/versions/{version}/retrain"),
    ("GET", "/v1/models/{model_id}/retrains/{retrain_id}"),
    ("GET", "/v1/models/{model_id}/deployments"),
    ("POST", "/v1/models/{model_id}/deployments"),
    ("GET", "/v1/models/{model_id}/use-exceptions"),
    ("POST", "/v1/models/{model_id}/use-exceptions"),
    # m6-sisa (6.5)
    ("GET", "/v1/models/{model_id}/versions/{version}/soup"),
    ("PUT", "/v1/models/{model_id}/versions/{version}/sbom"),
)


PREP: dict[tuple[str, str], Any] = {
    **dict.fromkeys(REGISTRY_ROUTES, _prep_registry),
    ("POST", "/v1/models/{model_id}/versions"): _prep_register_version,
    ("POST", "/v1/models/{model_id}/versions/{version}/publish"): _prep_publish,
    ("POST", "/v1/models/{model_id}/deployments"): _prep_deploy,
    ("POST", "/v1/exports/fda-evidence"): _prep_evidence,
    ("GET", "/v1/audit/batches/{seq}/object"): _prep_audit_batch,
    ("POST", "/v1/governance/channels/bulk"): _prep_bulk,
    ("PUT", "/v1/artifacts/{node_id}/governance"): _prep_artifact_node,
    ("POST", "/v1/subjects/{subject_id}/withdrawals"): _prep_withdrawal,
    ("GET", "/v1/deletion-jobs/{deletion_id}"): _prep_deletion,
    ("DELETE", "/v1/webhooks/{webhook_id}"): _prep_webhook_owned,
    ("GET", "/v1/webhooks/{webhook_id}"): _prep_webhook_owned,
    ("GET", "/v1/webhooks/{webhook_id}/deliveries"): _prep_webhook_owned,
    ("POST", "/v1/webhooks/{webhook_id}/rotate-secret"): _prep_webhook_owned,
    ("POST", "/v1/sweeps"): _prep_create_sweep,
    ("GET", "/v1/sweeps/{sweep_id}"): _prep_sweep_owned,
    ("GET", "/v1/sweeps/{sweep_id}/report"): _prep_sweep_owned,
    ("POST", "/v1/runs"): _prep_create_run,
    ("GET", "/v1/runs/{run_id}"): _prep_run_owned,
    ("POST", "/v1/runs/{run_id}/cancel"): _prep_run_owned,
    ("GET", "/v1/uploads/{upload_id}"): _prep_upload_owned,
    ("PUT", "/v1/uploads/{upload_id}/parts/{part_number}"): _prep_put_part,
    ("POST", "/v1/uploads/{upload_id}/complete"): _prep_complete,
    ("POST", "/v1/datasets/{dataset_id}/uploads"): _prep_create_upload,
    ("POST", "/v1/sessions/{session_id}/streams"): _prep_stream,
}
PREP_CREATOR_ACTION = {
    ("DELETE", "/v1/webhooks/{webhook_id}"): "webhook:create",
    ("GET", "/v1/webhooks/{webhook_id}"): "webhook:create",
    ("GET", "/v1/webhooks/{webhook_id}/deliveries"): "webhook:create",
    ("POST", "/v1/webhooks/{webhook_id}/rotate-secret"): "webhook:create",
    **dict.fromkeys(REGISTRY_ROUTES, "self:read"),  # created by the owner in _prep_registry
    ("POST", "/v1/models/{model_id}/versions"): "self:read",
    ("POST", "/v1/models/{model_id}/versions/{version}/publish"): "self:read",
    ("POST", "/v1/exports/fda-evidence"): "self:read",
    ("GET", "/v1/audit/batches/{seq}/object"): "self:read",
    ("POST", "/v1/governance/channels/bulk"): "self:read",
    ("PUT", "/v1/artifacts/{node_id}/governance"): "self:read",
    ("POST", "/v1/subjects/{subject_id}/withdrawals"): "self:read",
    ("GET", "/v1/deletion-jobs/{deletion_id}"): "self:read",
    ("POST", "/v1/sweeps"): "sweep:create",
    ("GET", "/v1/sweeps/{sweep_id}"): "sweep:create",
    ("GET", "/v1/sweeps/{sweep_id}/report"): "sweep:create",
    ("POST", "/v1/runs"): "run:create",
    ("GET", "/v1/runs/{run_id}"): "run:create",
    ("POST", "/v1/runs/{run_id}/cancel"): "run:create",
    ("GET", "/v1/uploads/{upload_id}"): "upload:create",
    ("PUT", "/v1/uploads/{upload_id}/parts/{part_number}"): "upload:create",
    ("POST", "/v1/uploads/{upload_id}/complete"): "upload:create",
    ("POST", "/v1/datasets/{dataset_id}/uploads"): "upload:create",
    ("POST", "/v1/sessions/{session_id}/streams"): "device:create",
}


def _walk(routes) -> list:
    out = []
    for r in routes:
        inner = getattr(r, "original_router", None)
        out.extend(_walk(inner.routes) if inner is not None else [r])
    return out


def api_routes(app: FastAPI) -> list[tuple[str, str, str | None]]:
    """(method, path, action) for every operation, generated from the app's OpenAPI document
    (SEC-020)."""
    # Every endpoint must be a FastAPI APIRoute (a raw Starlette route would bypass the guard +
    # schema).
    plain = [getattr(r, "path", r) for r in _walk(app.routes) if not isinstance(r, APIRoute)]
    assert plain == [], f"non-API routes: {plain}"
    app.openapi_schema = None  # rebuild: routes may have been added
    out = []
    for path, ops in app.openapi()["paths"].items():
        for method, op in ops.items():
            out.append((method.upper(), path, op.get(ACTION_KEY)))
    return sorted(out)


def assert_all_mapped(app: FastAPI) -> None:
    unmapped = [(m, p) for m, p, a in api_routes(app) if a != PUBLIC and a not in EXPECTED]
    assert unmapped == [], f"routes without a reviewed action: {unmapped}"


def test_every_route_is_mapped(app):
    assert_all_mapped(app)
    assert len(api_routes(app)) >= 20


def test_route_enumeration_catches_an_unmapped_route(app, client, as_role):
    """An added route without an action fails the enumeration AND is denied at runtime (deny by
    default)."""

    @app.get("/v1/sneaky")
    def sneaky():
        return {"ok": True}

    with pytest.raises(AssertionError, match="sneaky"):
        assert_all_mapped(app)
    # It has no guard dependency (it bypassed _route), so the check that matters is the enumeration
    # test; routes built through api.routes._route always run the guard, which denies a missing
    # action:
    from fastapi import Depends
    from nf_platform.api.deps import guard

    @app.get("/v1/sneaky2", dependencies=[Depends(guard)])
    def sneaky2():
        return {"ok": True}

    r = client.get("/v1/sneaky2", headers=as_role("owner"))
    assert r.status_code == 403


def _fill(path: str, ids: dict[str, str]) -> str:
    for k, v in ids.items():
        if isinstance(v, str):
            path = path.replace("{" + k + "}", v)
    assert "{" not in path, f"no fixture id for {path}"
    return path


@pytest.mark.parametrize("role", ALL_ROLES)
def test_matrix(app, client, as_role, tree, role):
    h = as_role(role, sub=f"user-{role}")
    ids = dict(tree)
    owner_h = as_role("owner")
    ids["_owner_headers"] = owner_h
    ids["_approver_headers"] = lambda sub: as_role("data-steward", sub=sub)
    for method, path, action in api_routes(app):
        if action == PUBLIC:
            continue
        allowed = role in EXPECTED[action]
        if method == "DELETE" and path == "/v1/api-keys/{key_id}":
            # revoke needs a key: the caller's own if it may create one, else any key (403 comes
            # first)
            creator = h if role in EXPECTED["apikey:create"] else owner_h
            r = client.post(
                "/v1/api-keys", json=BODIES[("POST", "/v1/api-keys")](), headers=creator
            )
            assert r.status_code == 201, r.text
            ids["key_id"] = r.json()["id"]
        kwargs: dict[str, Any] = {"params": params_for(method, path, ids)}
        prep = PREP.get((method, path))
        if prep is not None:
            creator = h if role in EXPECTED[PREP_CREATOR_ACTION[(method, path)]] else owner_h
            kwargs.update(prep(client, creator, ids))
        url = _fill(path, ids)
        body = BODIES.get((method, path))
        if method in ("POST", "PUT", "PATCH") and "content" not in kwargs:
            assert body is not None, f"add a body for {method} {path}"
            kwargs.setdefault("json", body())
        r = client.request(method, url, headers=h, **kwargs)
        CONTRACT.check(method, path, r)
        if allowed:
            assert 200 <= r.status_code < 300, (role, method, path, r.status_code, r.text)
        else:
            assert r.status_code == 403, (role, method, path, r.status_code, r.text)
            assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize("role", sorted(ADMIN_CLASS))
def test_admin_roles_without_phishing_resistant_mfa_get_403_everywhere(
    app, client, as_role, tree, role
):
    """SEC-011: an admin-class token without a phishing-resistant amr → 403 on every (non-public)
    route."""
    h = as_role(role, phr=False)
    ids = {
        **tree,
        "key_id": str(uuid.uuid4()),
        "deletion_id": str(uuid.uuid4()),
        "sweep_id": str(uuid.uuid4()),
        "webhook_id": str(uuid.uuid4()),
        "model_id": str(uuid.uuid4()),
        "version": "1",
        "retrain_id": str(uuid.uuid4()),
        "seq": "0",
    }
    for method, path, action in api_routes(app):
        if action == PUBLIC:
            continue
        body = BODIES.get((method, path))
        r = client.request(
            method,
            _fill(path, ids),
            json=body() if body else None,
            params=params_for(method, path, ids),
            headers=h,
        )
        CONTRACT.check(method, path, r)
        assert r.status_code == 403, (role, method, path, r.status_code)
    # with passkey/WebAuthn (amr hwk) the same role works
    assert client.get("/v1/whoami", headers=as_role(role, phr=True)).status_code == 200


def test_non_admin_roles_do_not_need_phr(client, as_role, tree):
    assert client.get("/v1/projects", headers=as_role("scientist", phr=False)).status_code == 200


def test_no_roles_is_denied(client, as_role):
    assert client.get("/v1/whoami", headers=as_role()).status_code == 403
