"""2.2 acceptance / SEC-014: hashed API keys with scopes and expiry. Expired → 401, wrong scope →
403,
revoked → 401, shown once, no plaintext in the database."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from conftest import bearer
from nf_platform.auth import api_keys
from nf_platform.db.context import Principal, tenant_session
from sqlalchemy import inspect, text

pytestmark = pytest.mark.postgres

KEY_RE = re.compile(r"^nfb_live_[a-z2-7]{16}_[A-Za-z0-9_-]{43}$")


def _issue(client, h, **body):
    body = {"name": "k", "roles": ["scientist"], "scopes": ["metadata:read"], **body}
    r = client.post("/v1/api-keys", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_key_format_default_expiry_and_use(client, as_role, tree):
    out = _issue(client, as_role("scientist"))
    assert KEY_RE.match(out["key"])
    lifetime = datetime.fromisoformat(out["expires_at"]) - datetime.fromisoformat(out["created_at"])
    assert lifetime == timedelta(days=90)
    r = client.get("/v1/whoami", headers=bearer(out["key"]))
    assert r.status_code == 200
    assert r.json()["kind"] == "api_key" and r.json()["roles"] == ["scientist"]
    assert (
        client.get(f"/v1/projects/{tree['project_id']}", headers=bearer(out["key"])).status_code
        == 200
    )


def test_key_shown_once(client, as_role):
    h = as_role("scientist")
    out = _issue(client, h)
    listed = client.get("/v1/api-keys", headers=h).json()
    assert [k["id"] for k in listed] == [out["id"]]
    assert "key" not in listed[0]
    assert out["key"] not in client.get("/v1/api-keys", headers=h).text


def test_wrong_scope_is_403(client, as_role, tree):
    key = _issue(client, as_role("scientist"), scopes=["metadata:read"])["key"]
    r = client.post(
        f"/v1/projects/{tree['project_id']}/datasets", json={"name": "d"}, headers=bearer(key)
    )
    assert r.status_code == 403
    assert r.json()["missing_scope"] == "metadata:write"
    key_w = _issue(client, as_role("scientist"), scopes=["metadata:read", "metadata:write"])["key"]
    r = client.post(
        f"/v1/projects/{tree['project_id']}/datasets", json={"name": "d"}, headers=bearer(key_w)
    )
    assert r.status_code == 201


def test_expired_key_is_401(client, engine, settings, tenants):
    p = Principal("u1", tenants.a, frozenset({"scientist"}), frozenset(), "user", False)
    past = datetime.now(UTC) - timedelta(days=10)
    with tenant_session(p, engine=engine) as s:
        issued = api_keys.issue(
            s,
            p,
            name="old",
            roles=["scientist"],
            scopes=["metadata:read"],
            days=1,
            secret_provider=settings.secrets,
            now=past,
        )
    r = client.get("/v1/whoami", headers=bearer(issued.plaintext))
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")


def test_revoked_key_is_401(client, as_role):
    h = as_role("scientist")
    out = _issue(client, h)
    assert client.get("/v1/whoami", headers=bearer(out["key"])).status_code == 200
    assert client.delete(f"/v1/api-keys/{out['id']}", headers=h).status_code == 204
    assert client.get("/v1/whoami", headers=bearer(out["key"])).status_code == 401


def test_wrong_secret_same_public_id_is_401(client, as_role):
    key = _issue(client, as_role("scientist"))["key"]
    forged = key[:-4] + ("AAAA" if not key.endswith("AAAA") else "BBBB")
    assert client.get("/v1/whoami", headers=bearer(forged)).status_code == 401


@pytest.mark.parametrize("days", [0, 366, -1])
def test_expiry_bounds(client, as_role, days):
    r = client.post(
        "/v1/api-keys",
        json={
            "name": "k",
            "roles": ["viewer"],
            "scopes": ["metadata:read"],
            "expires_in_days": days,
        },
        headers=as_role("scientist"),
    )
    assert r.status_code == 422


def test_365_days_is_allowed(client, as_role):
    out = _issue(client, as_role("scientist"), expires_in_days=365)
    lifetime = datetime.fromisoformat(out["expires_at"]) - datetime.fromisoformat(out["created_at"])
    assert lifetime == timedelta(days=365)


@pytest.mark.parametrize("roles", [["admin"], ["owner"], ["auditor"], ["data-steward"]])
def test_admin_class_roles_cannot_be_delegated(client, as_role, roles):
    r = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": roles, "scopes": ["metadata:read"]},
        headers=as_role("owner"),
    )
    assert r.status_code == 403


def test_cannot_escalate_via_key(client, as_role):
    # a viewer cannot mint a scientist key; unknown scopes are rejected
    r = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": ["scientist"], "scopes": ["metadata:read"]},
        headers=as_role("viewer"),
    )
    assert r.status_code == 403
    r = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": ["viewer"], "scopes": ["root"]},
        headers=as_role("viewer"),
    )
    assert r.status_code == 422


def test_keys_cannot_manage_keys_or_read_audit(client, as_role):
    key = _issue(
        client, as_role("owner"), roles=["scientist"], scopes=["metadata:read", "metadata:write"]
    )
    h = bearer(key["key"])
    assert client.get("/v1/api-keys", headers=h).status_code == 403
    assert (
        client.post(
            "/v1/api-keys",
            json={"name": "x", "roles": ["viewer"], "scopes": ["metadata:read"]},
            headers=h,
        ).status_code
        == 403
    )  # noqa: E501
    assert client.delete(f"/v1/api-keys/{key['id']}", headers=h).status_code == 403
    assert client.get("/v1/audit/events", headers=h).status_code == 403


def test_device_key_can_only_whoami(client, as_role, tree):
    key = _issue(client, as_role("admin"), roles=["device"], scopes=["metadata:read"])["key"]
    assert client.get("/v1/whoami", headers=bearer(key)).status_code == 200
    assert client.get("/v1/projects", headers=bearer(key)).status_code == 403


def test_other_users_keys_are_invisible_and_unrevocable(client, as_role):
    alice = as_role("scientist", sub="alice")
    bob = as_role("scientist", sub="bob")
    k = _issue(client, alice)
    assert client.get("/v1/api-keys", headers=bob).json() == []
    assert client.delete(f"/v1/api-keys/{k['id']}", headers=bob).status_code == 404
    # tenant admins see and can revoke every key of their tenant
    admin = as_role("admin")
    assert [x["id"] for x in client.get("/v1/api-keys", headers=admin).json()] == [k["id"]]
    assert client.delete(f"/v1/api-keys/{k['id']}", headers=admin).status_code == 204


def test_database_holds_no_plaintext_key(client, as_role, engine):
    """SEC-014 grep test: neither the key nor its secret part appears in any column of any table."""
    key = _issue(client, as_role("scientist"))["key"]
    client.get("/v1/whoami", headers=bearer(key))  # also exercise the audit path
    # nfb_live_<public id>_<secret>; the base64url secret may itself contain "_"
    secret = key.split("_", 3)[3]
    assert len(secret) == 43, key
    insp = inspect(engine)
    with engine.connect() as c:
        for table in insp.get_table_names():
            for (row,) in c.execute(text(f"SELECT row_to_json(t)::text FROM {table} t")):
                assert key not in row and secret not in row, table
    assert uuid.UUID  # keep import used
