"""SEC-143: models trained on tenant data are private by default; publication needs a model card
with a privacy-risk section, four-eyes approval (two governance approvers other than the
publisher) and the ``commercial_use`` consent scope of every training subject."""

from __future__ import annotations

import pytest
from reg_helpers import feature_of, new_model, post, version_body

pytestmark = pytest.mark.postgres


@pytest.fixture
def node(tree, engine, tenants):
    return feature_of(engine, tenants.a, tree["node_id"])


def _version(client, h, node, **card_kw):
    model = new_model(client, h, **card_kw)
    post(client, f"/v1/models/{model['id']}/versions", version_body([node]), h)
    return f"/v1/models/{model['id']}/versions/1"


def _approve(client, as_role, url, *subs):
    for sub in subs:
        r = client.post(f"{url}/approvals", headers=as_role("data-steward", sub=sub))
        assert r.status_code == 201, r.text


def test_private_by_default_and_privacy_section_required(client, as_role, node):
    owner = as_role("owner")
    url = _version(client, owner, node)  # card without privacy_risk
    assert client.get(url, headers=owner).json()["visibility"] == "private"
    _approve(client, as_role, url, "approver-1", "approver-2")
    r = client.post(f"{url}/publish", headers=owner)
    assert r.status_code == 422 and r.json()["code"] == "privacy_risk_required", r.text
    assert client.get(url, headers=owner).json()["visibility"] == "private"


def test_four_eyes_then_publish(client, as_role, node):
    owner = as_role("owner", sub="publisher")
    url = _version(client, owner, node, privacy=True)
    r = client.post(f"{url}/publish", headers=owner)
    assert r.status_code == 403 and r.json()["code"] == "four_eyes_required"
    # the publisher's own approval does not count; one other approver is not enough
    assert client.post(f"{url}/approvals", headers=owner).status_code == 201
    _approve(client, as_role, url, "approver-1")
    assert client.post(f"{url}/publish", headers=owner).status_code == 403
    # a scientist cannot approve (governance roles only)
    assert client.post(f"{url}/approvals", headers=as_role("scientist")).status_code == 403
    _approve(client, as_role, url, "approver-2")
    r = client.post(f"{url}/publish", headers=owner)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["visibility"] == "published" and out["published_at"]
    assert client.post(f"{url}/publish", headers=owner).status_code == 200  # idempotent
    # only owner/admin may publish
    assert client.post(f"{url}/publish", headers=as_role("data-steward")).status_code == 403


def test_publication_needs_commercial_use_consent(client, as_role, node, tree):
    owner = as_role("owner", sub="publisher")
    url = _version(client, owner, node, privacy=True)
    _approve(client, as_role, url, "approver-1", "approver-2")
    r = client.post(
        f"/v1/subjects/{tree['subject_id']}/consents",
        json={"kind": "withdraw", "scopes": ["commercial_use"]},
        headers=owner,
    )
    assert r.status_code == 201, r.text
    r = client.post(f"{url}/publish", headers=owner)
    assert r.status_code == 403 and "commercial_use" in r.json()["detail"]
