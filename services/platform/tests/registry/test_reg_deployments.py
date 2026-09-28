"""6.2 acceptance: use restrictions and deployment checks (``market/regulation.md`` §5; SEC-092,
SEC-144).

- an emotion/cognitive-state model with context ``workplace`` in the EU is refused unless a
  documented medical or safety exception record exists; the refusal is stored and audited;
- SEC-092: ``closed_loop_stimulation``, ``neuromodulation_control`` and ``actuator_control`` are
  always refused and audited, whatever the model, restriction or exception;
- SEC-144: full logits/embeddings outputs are refused.
"""

from __future__ import annotations

import uuid

import pytest
from nf_platform.registry import vocab
from reg_helpers import audit_rows, feature_of, new_model, post, version_body

pytestmark = pytest.mark.postgres
CONTROL = ("closed_loop_stimulation", "neuromodulation_control", "actuator_control")


@pytest.fixture
def input_node(tree, engine, tenants):
    """A feature entity derived from the tree's recording node (subject sub-01, all scopes)."""
    return feature_of(engine, tenants.a, tree["node_id"])


_approver = None


@pytest.fixture(autouse=True)
def _second_approver(as_role):
    """AppSec M3: the versions below are upload-sourced, which need a governance approver other
    than the uploader before any deployment; one is recorded so these tests exercise the context
    rules only (tests/registry/test_reg_upload_lineage.py covers the approval rule)."""
    global _approver
    _approver = as_role("data-steward", sub="second-approver")
    yield
    _approver = None


def _model(client, h, input_node, inferences=("emotion",), **vkw):
    model = new_model(client, h, inferences=inferences)
    v = post(client, f"/v1/models/{model['id']}/versions", version_body([input_node], **vkw), h)
    r = client.post(f"/v1/models/{model['id']}/versions/1/approvals", headers=_approver)
    assert r.status_code == 201, r.text
    return model, v


def _deploy(client, h, model_id, **ctx):
    body = {
        "version": ctx.pop("version", 1),
        "context": {"jurisdiction": "EU", "setting": "research", "purpose": "study", **ctx},
    }
    return client.post(f"/v1/models/{model_id}/deployments", json=body, headers=h)


def test_emotion_model_eu_workplace_refused_unless_exception(client, as_role, input_node, engine):
    h = as_role("scientist")
    model, v = _model(client, h, input_node, inferences=("emotion", "cognitive_state"))
    assert "eu_ai_act_5_1_f" in v["use_restrictions"]  # derived from the card's inferences
    r = _deploy(client, h, model["id"], setting="workplace", purpose="staff focus")
    assert r.status_code == 403, r.text
    p = r.json()
    assert p["code"] == vocab.R_5_1_F and p["reasons"] == [vocab.R_5_1_F]
    assert r.headers["content-type"].startswith("application/problem+json")
    # stored + audited
    deps = client.get(f"/v1/models/{model['id']}/deployments", headers=h).json()
    (d,) = [x for x in deps if x["id"] == p["deployment_id"]]
    assert d["state"] == "refused" and d["effective_state"] == "refused"
    evs = [e for e in audit_rows(engine, type="registry.deployment") if e["outcome"] == "denied"]
    assert any(e["resource_id"] == p["deployment_id"] for e in evs)
    ev = next(e for e in evs if e["resource_id"] == p["deployment_id"])
    assert ev["details"]["decision"] == "refused" and "eu_ai_act_5_1_f" in ev["details"]["reason"]
    # member states count as EU; education too; outside the EU the restriction does not apply
    assert (
        _deploy(client, h, model["id"], jurisdiction="FR", setting="workplace").status_code == 403
    )
    assert _deploy(client, h, model["id"], setting="education").status_code == 403
    assert (
        _deploy(client, h, model["id"], jurisdiction="US-CO", setting="workplace").status_code
        == 201
    )
    assert _deploy(client, h, model["id"], setting="research").status_code == 201

    # a documented medical exception record (governance role) lifts 5(1)(f) for that setting
    steward = as_role("data-steward")
    exc = {
        "basis": "medical",
        "jurisdiction": "EU",
        "setting": "workplace",
        "justification": "occupational fatigue monitoring for pilots under medical supervision",
        "evidence_ref": "DPIA-2026-07, ethics approval EC-19",
    }
    assert (
        client.post(f"/v1/models/{model['id']}/use-exceptions", json=exc, headers=h).status_code
        == 403
    )
    e = post(client, f"/v1/models/{model['id']}/use-exceptions", exc, steward)
    ok = _deploy(client, h, model["id"], setting="workplace", exception_id=e["id"])
    assert ok.status_code == 201, ok.text
    assert ok.json()["state"] == "approved" and ok.json()["exception_id"] == e["id"]
    # the exception covers workplace only, and only this model
    edu = _deploy(client, h, model["id"], setting="education", exception_id=e["id"])
    assert edu.status_code == 403 and vocab.R_EXCEPTION in edu.json()["reasons"]
    other, _ = _model(client, h, input_node)
    r = _deploy(client, h, other["id"], setting="workplace", exception_id=e["id"])
    assert r.status_code == 403 and vocab.R_EXCEPTION in r.json()["reasons"]
    r = _deploy(client, h, other["id"], setting="workplace", exception_id=str(uuid.uuid4()))
    assert r.status_code == 403 and vocab.R_EXCEPTION in r.json()["reasons"]
    listed = client.get(f"/v1/models/{model['id']}/use-exceptions", headers=h).json()
    assert [x["id"] for x in listed] == [e["id"]]


@pytest.mark.parametrize("setting", CONTROL)
@pytest.mark.parametrize("jurisdiction", ["EU", "US"])
def test_control_contexts_always_refused_and_audited(
    client, as_role, input_node, engine, setting, jurisdiction
):
    """SEC-092 (§G, non-negotiable): no model, restriction or exception lifts it."""
    h = as_role("owner")
    model, _ = _model(client, h, input_node, inferences=("motor_intent",))
    r = _deploy(client, h, model["id"], jurisdiction=jurisdiction, setting=setting)
    assert r.status_code == 403, r.text
    assert r.json()["code"] == vocab.R_CONTROL
    evs = audit_rows(engine, type="registry.deployment", resource_id=r.json()["deployment_id"])
    assert len(evs) == 1 and evs[0]["outcome"] == "denied"
    assert evs[0]["details"]["decision"] == "refused"


def test_control_context_refused_even_with_an_exception(client, as_role, input_node):
    h = as_role("owner")
    model, _ = _model(client, h, input_node)
    e = post(
        client,
        f"/v1/models/{model['id']}/use-exceptions",
        {
            "basis": "safety",
            "jurisdiction": "EU",
            "setting": "workplace",
            "justification": "j",
            "evidence_ref": "e",
        },
        h,
    )
    r = _deploy(client, h, model["id"], setting="actuator_control", exception_id=e["id"])
    assert r.status_code == 403 and vocab.R_CONTROL in r.json()["reasons"]


def test_outputs_restrictions_and_validation(client, as_role, input_node):
    h = as_role("scientist")
    model, _ = _model(client, h, input_node, inferences=("motor_intent",))
    r = _deploy(client, h, model["id"], outputs="logits")
    assert r.status_code == 403 and r.json()["reasons"] == [vocab.R_OUTPUTS]  # SEC-144
    assert _deploy(client, h, model["id"], outputs="coarse_scores").status_code == 201
    assert _deploy(client, h, model["id"], setting="no_such_setting").status_code == 422
    assert _deploy(client, h, model["id"], jurisdiction="europe").status_code == 422
    assert _deploy(client, h, model["id"], version=9).status_code == 404
    ro, _ = _model(
        client, h, input_node, inferences=("motor_intent",), use_restrictions=["research_only"]
    )
    assert _deploy(client, h, ro["id"], setting="consumer_wellness").json()["reasons"] == [
        vocab.R_RESEARCH_ONLY
    ]
    st, _ = _model(client, h, input_node, inferences=("sensitive_trait",))
    assert _deploy(client, h, st["id"], setting="research").json()["reasons"] == [vocab.R_5_1_G]
    ab, _ = _model(
        client, h, input_node, inferences=("motor_intent",), use_restrictions=["eu_ai_act_5_1_a"]
    )
    assert _deploy(client, h, ab["id"], influences_behaviour=True).json()["reasons"] == [
        vocab.R_5_1_A
    ]


def test_vocabulary_lists_no_control_setting(client, as_role):
    out = client.get("/v1/registry/vocabulary", headers=as_role("viewer")).json()
    assert not set(out["settings"]) & set(CONTROL)
    assert "workplace" in out["settings"] and "eu_ai_act_5_1_f" in {
        r["code"] for r in out["restrictions"]
    }
    assert out["statement"] == vocab.CONTROL_STATEMENT


def test_other_tenant_cannot_deploy_or_read(client, as_role, input_node, tenants):
    h = as_role("owner")
    model, _ = _model(client, h, input_node)
    hb = as_role("owner", tenant=tenants.b)
    assert _deploy(client, hb, model["id"]).status_code == 404
    assert client.get(f"/v1/models/{model['id']}/deployments", headers=hb).status_code == 404
