"""5.4 acceptance: the single policy function (SEC-024, SEC-026, SEC-142, SEC-146).

- route enumeration: every data-touching endpoint of the app calls ``policy.check``;
- matrix: roles x classifications x consent scopes (function level, one oracle table written
  independently of the implementation);
- a training job on a subject without the ``model_training`` scope is denied;
- fail closed: an exception anywhere in the policy, classification or consent lookup is a 403
  that reveals nothing;
- the ingest hook (replacing the M2 stub): no consent -> quarantined; quarantine review access;
- the worker re-checks at run start (a withdrawal after the request stops the run).
"""

from __future__ import annotations

import importlib.util
import itertools
import sys
import uuid
from pathlib import Path

import pytest
from gov_helpers import (
    ALL_SCOPES,
    EEG,
    EMG,
    make_recording,
    make_subject,
    pass_pipeline,
    principal,
    publish,
    signal,
)
from nf_platform.api.deps import PUBLIC
from nf_platform.db.context import tenant_session
from nf_platform.governance import attributes, consent, derived, policy, rules
from nf_platform.governance.policy import LedgerConsentPolicy
from nf_platform.provenance import api as prov
from sqlalchemy import text

pytestmark = pytest.mark.postgres

_MATRIX = Path(__file__).resolve().parents[1] / "core" / "test_core_authz_matrix.py"
if "nf_core_authz_matrix" in sys.modules:
    mx = sys.modules["nf_core_authz_matrix"]
else:
    _spec = importlib.util.spec_from_file_location("nf_core_authz_matrix", _MATRIX)
    mx = importlib.util.module_from_spec(_spec)
    sys.modules["nf_core_authz_matrix"] = mx
    _spec.loader.exec_module(mx)

# Reviewed independently of policy.py: the route actions that read, process or export subject data.
DATA_TOUCHING = {
    "recording:read",
    "signal:read",
    "run:create",
    "provenance:export",
    "evidence:export",  # m5-evidence (5.8)
    "model:train",  # m6-registry (6.1 register a version, 6.3 retrain)
    "model:publish",  # m6-registry (SEC-143)
    "model:soup-export",  # m6-sisa (6.5)
}


def test_every_data_touching_route_calls_the_policy(app, client, as_role, tree, monkeypatch):
    calls: list[tuple[str, str]] = []
    real = policy.check

    def spy(principal_, action, resource, **kw):
        calls.append((action, resource.type))
        return real(principal_, action, resource, **kw)

    monkeypatch.setattr(policy, "check", spy)
    routes = [(m, p, a) for m, p, a in mx.api_routes(app) if a != PUBLIC]
    data_routes = [(m, p, a) for m, p, a in routes if a in DATA_TOUCHING]
    # a route with a policy data action outside the reviewed set would slip through: refuse it
    assert {a for _, _, a in routes if a in policy.DATA_ACTIONS} <= DATA_TOUCHING
    assert {a for _, _, a in data_routes} == DATA_TOUCHING
    assert len(data_routes) >= 5
    h = as_role("owner")
    ids = {
        **tree,
        "_owner_headers": h,
        "_approver_headers": lambda sub: as_role("data-steward", sub=sub),
    }
    for method, path, action in data_routes:
        kwargs = {"params": mx.params_for(method, path, ids)}
        prep = mx.PREP.get((method, path))
        if prep is not None:
            kwargs.update(prep(client, h, ids))
        body = mx.BODIES.get((method, path))
        if method == "POST":
            kwargs.setdefault("json", body())
        calls.clear()
        r = client.request(method, mx._fill(path, ids), headers=h, **kwargs)
        assert 200 <= r.status_code < 300, (method, path, r.text)
        assert any(a == action for a, _ in calls), (method, path, calls)


# ---------------------------------------------------------------- matrix
ROLES = ("owner", "admin", "data-steward", "auditor", "scientist", "viewer", "device")
RBAC = {  # oracle (BLUEPRINT §4.2 roles, SEC-022/024)
    "signal:read": {"owner", "admin", "data-steward", "auditor", "scientist", "viewer"},
    "run:create": {"owner", "admin", "data-steward", "scientist"},
    "model:train": {"owner", "admin", "data-steward", "scientist"},
    "signal:export": {"owner", "admin", "data-steward"},
}
NEEDS = {
    "signal:read": "processing",
    "run:create": "processing",
    "model:train": "model_training",
    "signal:export": "sharing",
}
VARIANTS = {  # channels -> jurisdictions matched by RuleSet v1
    "central": ([EEG], {"CO", "CA", "CT", "EU"}),
    "peripheral": ([EMG], {"CO", "CA", "EU"}),
    "non-neural EMG": ([{**EMG, "derived_from_non_neural": True}], {"CO", "EU"}),
    "unknown": ([{"name": "X", "modality": "ECG", "sampling_rate": 256.0, "units": "uV"}], set()),
}
SCOPE_SETS = {
    "none": (),
    "collection": ("collection",),
    "processing": ("collection", "processing"),
    "training": ("collection", "processing", "model_training"),
    "all": ALL_SCOPES,
    "withdrawn": "withdrawn",
}


@pytest.fixture
def matrix_world(client, as_role, tree, storage, engine, tenants):
    h = as_role("owner")
    recs = {}
    for sname, scopes in SCOPE_SETS.items():
        s = make_subject(
            client,
            h,
            tree["dataset_id"],
            f"m-{sname}",
            scopes=ALL_SCOPES if scopes == "withdrawn" else scopes,
        )
        if scopes == "withdrawn":
            r = client.post(
                f"/v1/subjects/{s['subject_id']}/consents",
                json={"kind": "withdraw", "scopes": list(ALL_SCOPES)},
                headers=h,
            )
            assert r.status_code == 201
        for vname, (chans, _) in VARIANTS.items():
            recs[(sname, vname)] = make_recording(
                client,
                h,
                s["session_id"],
                storage=storage,
                engine=engine,
                tenant_id=tenants.a,
                subject_id=s["subject_id"],
                channels=chans,
            )
    return recs


def test_policy_matrix(matrix_world, engine, tenants):
    tid = tenants.a
    stewards = policy.approvals_from(
        [principal(tid, "data-steward", pid="st-1"), principal(tid, "admin", pid="ad-2")]
    )
    n = 0
    with tenant_session(principal(tid, "owner"), engine=engine) as s:
        for role, (sname, scopes), (vname, (_, matched)), action in itertools.product(
            ROLES, SCOPE_SETS.items(), VARIANTS.items(), RBAC
        ):
            p = principal(tid, role, pid=f"req-{role}")
            rid = uuid.UUID(matrix_world[(sname, vname)])
            res = policy.Resource("recording", tid, str(rid), recording_id=rid)
            held = set() if scopes == "withdrawn" else set(scopes)
            expected = role in RBAC[action] and NEEDS[action] in held
            try:
                d = policy.check(p, action, res, session=s, approvals=stewards)
                allowed = True
            except policy.PolicyDenied:
                allowed = False
            except policy.Forbidden:
                allowed = False
            assert allowed == expected, (role, sname, vname, action)
            if allowed:
                assert set(d.classification["matched_jurisdictions"]) == matched, vname
                assert ("limit_use" in d.obligations) == ("CA" in matched)
                assert ("attributes_need_review" in d.obligations) == (vname == "unknown")
                assert ("four_eyes_approved" in d.obligations) == (action == "signal:export")
            n += 1
    assert n == len(ROLES) * len(SCOPE_SETS) * len(VARIANTS) * len(RBAC)


def test_four_eyes_for_raw_export(matrix_world, engine, tenants):
    tid = tenants.a
    rid = uuid.UUID(matrix_world[("all", "peripheral")])
    res = policy.Resource("recording", tid, str(rid), recording_id=rid)
    req = principal(tid, "data-steward", pid="st-req")
    cases = [
        ((), False),
        ((req, principal(tid, "admin", pid="a1")), False),  # the requester does not count
        ((principal(tid, "viewer", pid="v1"), principal(tid, "admin", pid="a1")), False),
        ((principal(tid, "admin", pid="a1"), principal(tid, "admin", pid="a1")), False),
        ((principal(tid, "admin", pid="a1"), principal(tid, "data-steward", pid="s2")), True),
    ]
    for approvers, ok in cases:
        try:
            policy.check(req, "signal:export", res, approvals=policy.approvals_from(approvers))
            assert ok
        except policy.PolicyDenied as e:
            assert not ok and "four-eyes" in e.reason


def test_training_without_model_training_scope_is_denied(
    client, as_role, tree, storage, engine, tenants
):
    h = as_role("owner")
    tid = tenants.a
    s = make_subject(client, h, tree["dataset_id"], "no-train", scopes=("collection", "processing"))
    rid = make_recording(
        client,
        h,
        s["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tid,
        subject_id=s["subject_id"],
    )
    sci = principal(tid, "scientist")
    svc = principal(tid)
    svc = type(svc)(svc.id, tid, frozenset(), frozenset(), "service", False)  # a training worker
    with tenant_session(sci, engine=engine) as sess:
        node = prov.record(
            sess, sci, [prov.NodeSpec(prov.ProvKind.ENTITY, "recording", rid)], []
        ).node_ids[0]
    for who in (sci, svc):
        with tenant_session(who, engine=engine) as sess, pytest.raises(policy.PolicyDenied) as ei:
            derived.train_toy_model(sess, storage, who, [node])
        assert "model_training" in ei.value.reason
    # with the scope granted the policy passes (reading this input then fails: no content)
    doc = client.post(
        "/v1/consent-documents", json={"name": "t", "version": "1", "sha256": "77" * 32}, headers=h
    ).json()
    client.post(
        f"/v1/subjects/{s['subject_id']}/consents",
        json={
            "kind": "grant",
            "scopes": ["collection", "processing", "model_training"],
            "document_id": doc["id"],
        },
        headers=h,
    )
    with tenant_session(sci, engine=engine) as sess, pytest.raises(derived.DerivedError):
        derived.train_toy_model(sess, storage, sci, [node])


@pytest.mark.parametrize(
    "target",
    [
        (consent, "current_scopes"),
        (rules, "classify"),
        (attributes, "recording_attributes"),
        (policy, "_recording_subject"),
    ],
    ids=["consent", "classification", "attributes", "resource"],
)
def test_fail_closed_reveals_nothing(client, as_role, tree, monkeypatch, target):
    """SEC-026: any exception inside the policy function -> 403 problem+json, no internals."""
    mod, name = target

    def boom(*a, **k):
        raise RuntimeError("secret-internal-detail at /srv/db:5432")

    monkeypatch.setattr(mod, name, boom)
    r = client.get(
        f"/v1/recordings/{tree['recording_id']}/data?start=0&end=1", headers=as_role("owner")
    )
    assert r.status_code == 403, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["detail"] == policy.GENERIC_DENIAL
    assert "secret" not in r.text and "RuntimeError" not in r.text and "5432" not in r.text


def test_ingest_hook_replaces_the_stub(client, as_role, tree, engine, tenants, app):
    assert isinstance(app.state.consent_policy, LedgerConsentPolicy)
    h = as_role("owner")
    pol = LedgerConsentPolicy(engine)
    none = make_subject(client, h, tree["dataset_id"], "q-none", scopes=())
    coll = make_subject(client, h, tree["dataset_id"], "q-coll", scopes=("collection",))
    rid = str(uuid.uuid4())
    assert pol.decide(tenants.a, none["subject_id"], rid) == "quarantine"
    assert pol.decide(tenants.a, coll["subject_id"], rid) == "quarantine"
    assert pol.decide(tenants.a, tree["subject_id"], rid) == "allow"
    assert pol.decide(tenants.a, "not-a-uuid", rid) == "quarantine"  # fail closed
    assert pol.decide(tenants.b, tree["subject_id"], rid) == "quarantine"  # other tenant: nothing


def test_quarantine_review_and_denial(client, as_role, tree, engine):
    with engine.begin() as c:
        c.execute(
            text("UPDATE recording SET state = 'quarantined' WHERE id = :i"),
            {"i": tree["recording_id"]},
        )
    url = f"/v1/recordings/{tree['recording_id']}/data?start=0&end=1"
    assert client.get(url, headers=as_role("data-steward")).status_code == 200
    assert client.get(url, headers=as_role("scientist")).status_code == 403
    tid = tree["_tenant_id"]
    rid = uuid.UUID(tree["recording_id"])
    d = policy.check(
        principal(tid, "data-steward"),
        "signal:read",
        policy.Resource("recording", tid, str(rid), recording_id=rid),
    )
    assert d.obligations == ("quarantine_review",)
    with pytest.raises(policy.PolicyDenied, match="quarantined"):
        policy.check(
            principal(tid, "data-steward"),
            "run:create",
            policy.Resource("recording", tid, str(rid), recording_id=rid),
        )


def test_worker_rechecks_consent_at_run_start(
    client, as_role, tree, storage, engine, tenants, worker
):
    h = as_role("owner")
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    rid = make_recording(
        client,
        h,
        tree["session_id"],
        storage=storage,
        engine=engine,
        tenant_id=tenants.a,
        subject_id=tree["subject_id"],
        data=signal(3),
    )
    ref = publish(client, h, pass_pipeline("recheck"))
    run = client.post("/v1/runs", json={"pipeline": ref, "recording_id": rid}, headers=h)
    assert run.status_code == 202, run.text
    r = client.post(
        f"/v1/subjects/{tree['subject_id']}/consents",
        json={"kind": "withdraw", "scopes": ["processing"]},
        headers=as_role("data-steward"),
    )
    assert r.status_code == 201
    assert worker.run_once() is not None
    out = client.get(f"/v1/runs/{run.json()['id']}", headers=h).json()
    assert out["state"] == "failed" and "policy" in out["error"]
    assert out["artifacts"] == []
    # and the API refuses a new run right away
    r = client.post("/v1/runs", json={"pipeline": ref, "recording_id": rid}, headers=h)
    assert r.status_code == 403 and "processing" in r.json()["detail"]
