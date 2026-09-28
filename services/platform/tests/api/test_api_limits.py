"""M4 4.8: quotas and rate limits (SEC-075) return 429/403 problem+json; API-key revocation stops a
key within 60 s everywhere, including an open event stream (SEC-017). Also the SSE run-event
endpoint (4.6) and the new list routes (M3 open issue 5).

Clocks are fakes (``app.state.sse_clock``/``sse_sleep``, the limiter's clock); nothing sleeps.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from nf_platform.limits.ratelimit import RateLimiter
from sqlalchemy import text

pytestmark = pytest.mark.postgres


class Clock:
    """Fake clock. ``at(t, fn)`` runs ``fn`` inside the stream's (fake) sleep once the clock passes
    ``t``: the TestClient buffers a streaming body, so a mid-stream change must happen server-side
    while the stream is open, not after the client has read it."""

    def __init__(self) -> None:
        self.t = 0.0
        self.actions: list[tuple[float, object]] = []
        self.fired: list[float] = []

    def __call__(self) -> float:
        return self.t

    def at(self, t: float, fn) -> None:
        self.actions.append((t, fn))

    def sleep(self, s: float) -> None:
        self.t += s
        due = [a for a in self.actions if a[0] <= self.t]
        for a in due:
            self.actions.remove(a)
            a[1]()
            self.fired.append(self.t)


def _key(client, h, roles=("scientist",), scopes=("metadata:read", "data:read", "data:write")):
    r = client.post(
        "/v1/api-keys", json={"name": "k", "roles": list(roles), "scopes": list(scopes)}, headers=h
    )
    assert r.status_code == 201, r.text
    return r.json()


def _events(lines) -> list[tuple[str, dict]]:
    out, event = [], None
    for line in lines:
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: ") and event:
            out.append((event, json.loads(line[6:])))
            event = None
    return out


# ---------------------------------------------------------------- token bucket
def test_token_bucket_unit():
    c = Clock()
    rl = RateLimiter(rate=2.0, burst=3, clock=c)
    assert [rl.take("k") for _ in range(3)] == [0.0, 0.0, 0.0]
    assert rl.take("k") == pytest.approx(0.5)
    assert rl.take("other") == 0.0  # buckets are per key
    c.t += 0.5
    assert rl.take("k") == 0.0
    small = RateLimiter(rate=1.0, burst=1, clock=c, max_keys=2)
    for k in ("a", "b", "c"):
        small.take(k)
    assert len(small._buckets) == 2  # bounded memory


def test_rate_limit_returns_429_problem_with_retry_after(app, client, as_role):
    c = Clock()
    app.state.rate_limiter = RateLimiter(rate=1.0, burst=2, clock=c)
    h = as_role("viewer")
    assert [client.get("/v1/projects", headers=h).status_code for _ in range(2)] == [200, 200]
    r = client.get("/v1/projects", headers=h)
    assert r.status_code == 429
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["type"] == "urn:nf:problem:rate-limited"
    assert r.headers["Retry-After"] == "1"
    # another credential has its own bucket; time refills
    assert client.get("/v1/projects", headers=as_role("scientist")).status_code == 200
    c.t += 1.0
    assert client.get("/v1/projects", headers=h).status_code == 200


# ---------------------------------------------------------------- quotas
def _set_quota(engine, tenant, storage=None, runs=None):
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO tenant_quota (tenant_id, max_storage_bytes, max_active_runs) "
                "VALUES (:t, :s, :r) ON CONFLICT (tenant_id) DO UPDATE "
                "SET max_storage_bytes = :s, max_active_runs = :r"
            ),
            {"t": tenant, "s": storage, "r": runs},
        )


def test_storage_quota_exceeded_is_403_problem(client, as_role, tree, tenants, engine):
    h = as_role("owner")
    q = client.get("/v1/quotas", headers=h).json()
    used = q["storage_bytes"]["used"]
    assert used >= 32  # the tree's open upload is counted as in flight
    _set_quota(engine, tenants.a, storage=used + 40)
    body = {"session_id": tree["session_id"], "filename": "a.edf", "synthetic": True}
    ok = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads", json={**body, "size_bytes": 40}, headers=h
    )
    assert ok.status_code == 201, ok.text
    r = client.post(
        f"/v1/datasets/{tree['dataset_id']}/uploads", json={**body, "size_bytes": 1}, headers=h
    )
    assert r.status_code == 403
    assert r.headers["content-type"] == "application/problem+json"
    p = r.json()
    assert p["type"] == "urn:nf:problem:quota-exceeded" and p["quota"] == "storage_bytes"
    # tenant B is not affected by A's quota
    assert (
        client.get("/v1/quotas", headers=as_role("owner", tenant=tenants.b)).json()[
            "storage_bytes"
        ]["limit"]
        > used + 40
    )


def test_active_run_quota_is_429_and_rolls_back(client, as_role, tree, tenants, engine):
    h = as_role("owner")
    _set_quota(engine, tenants.a, runs=1)  # the tree already has one queued run
    body = {"pipeline": tree["pipeline_ref"], "recording_id": tree["recording_id"]}
    r = client.post("/v1/runs", json=body, headers=h)
    assert r.status_code == 429
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["quota"] == "active_runs" and int(r.headers["Retry-After"]) >= 1
    runs = client.get("/v1/runs", headers=h).json()
    assert len(runs) == 1  # the refused run was rolled back
    sweep = {
        "pipeline": tree["pipeline_ref"],
        "recording_ids": [tree["recording_id"]],
        "grid": {"filter.l_freq": [0.5, 1.0]},
        "metric": {"step": "rereference", "key": "accuracy"},
    }
    assert client.post("/v1/sweeps", json=sweep, headers=h).status_code == 429
    assert client.get("/v1/sweeps", headers=h).json() == []
    # when the run finishes, the quota frees up
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    assert client.post("/v1/runs", json=body, headers=h).status_code == 202
    q = client.get("/v1/quotas", headers=h).json()
    assert q["active_runs"] == {"limit": 1, "used": 1}


def test_list_runs_and_sweeps(client, as_role, tree, tenants):
    h = as_role("viewer")
    runs = client.get("/v1/runs", headers=h).json()
    assert [r["id"] for r in runs] == [tree["run_id"]]
    assert client.get("/v1/runs", params={"state": "succeeded"}, headers=h).json() == []
    assert client.get("/v1/runs", params={"state": "bogus"}, headers=h).status_code == 422
    hb = as_role("viewer", tenant=tenants.b, sub="viewer-b")
    assert client.get("/v1/runs", headers=hb).json() == []  # tenant isolation
    assert client.get("/v1/sweeps", headers=h).json() == []


# ---------------------------------------------------------------- revocation (SEC-017)
def test_revoked_api_key_stops_working_at_once(client, as_role):
    owner = as_role("owner")
    k = _key(client, owner)
    kh = {"Authorization": f"Bearer {k['key']}"}
    assert client.get("/v1/whoami", headers=kh).status_code == 200
    assert client.delete(f"/v1/api-keys/{k['id']}", headers=owner).status_code == 204
    r = client.get("/v1/whoami", headers=kh)
    assert r.status_code == 401 and r.headers["content-type"] == "application/problem+json"


def _stream(client, app, url, headers, clock):
    app.state.sse_clock = clock
    app.state.sse_sleep = clock.sleep
    with client.stream("GET", url, headers=headers) as r:
        assert r.status_code == 200, r.read()
        assert r.headers["content-type"].startswith("text/event-stream")
        return list(r.iter_lines())


def test_sse_stream_of_a_revoked_api_key_is_closed_within_60s(app, client, as_role, tree, engine):
    owner = as_role("owner")
    k = _key(client, owner)
    clock = Clock()

    def revoke():  # what DELETE /v1/api-keys/{id} does (tested above), while the stream is open
        with engine.begin() as c:
            c.execute(text("UPDATE api_key SET revoked_at = now() WHERE id = :i"), {"i": k["id"]})

    clock.at(31.0, revoke)  # just after a re-check: the worst case for detection
    lines = _stream(
        client,
        app,
        f"/v1/runs/{tree['run_id']}/events?wait_s=600",
        {"Authorization": f"Bearer {k['key']}"},
        clock,
    )
    revoked_at = clock.fired
    ev = _events(lines)
    assert ev[0][0] == "run.state" and ev[0][1]["state"] == "queued"
    assert ev[-1] == ("error", {"status": 401, "title": "Unauthorized"})
    assert clock.t - revoked_at[0] <= 60
    assert any(line == ": keepalive" for line in lines)


def test_sse_stream_of_an_expired_user_token_is_closed(
    app, client, idp, tenants, tree, monkeypatch
):
    """The stream re-runs the full token verification, so exp applies (PyJWT's clock is moved
    together with the stream's fake clock)."""
    import jwt.api_jwt as api_jwt

    clock = Clock()
    real = api_jwt.datetime

    class Shifted(real):  # type: ignore[misc, valid-type]
        @classmethod
        def now(cls, tz=None):
            return real.now(tz) + timedelta(seconds=clock.t)

    monkeypatch.setattr(api_jwt, "datetime", Shifted)
    token = idp.token(sub="u-exp", tenant=tenants.a, roles=["viewer"], exp_in=60)
    lines = _stream(
        client,
        app,
        f"/v1/runs/{tree['run_id']}/events?wait_s=600",
        {"Authorization": f"Bearer {token}"},
        clock,
    )
    ev = _events(lines)
    assert ev[-1][0] == "error"
    # exp (60 s) + the verifier's leeway (30 s) + at most one re-check interval (30 s)
    assert 60 + 30 <= clock.t <= 60 + 30 + 30 + 1


def test_sse_ends_with_the_run_and_times_out(app, client, as_role, tree, engine):
    h = as_role("viewer")
    clock = Clock()
    lines = _stream(client, app, f"/v1/runs/{tree['run_id']}/events?wait_s=5", h, clock)
    ev = _events(lines)
    assert [e for e, _ in ev] == ["run.state", "timeout"]
    assert lines[0] == "retry: 3000"
    # a terminal run: one state event, then end
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=as_role("owner"))
    ev = _events(_stream(client, app, f"/v1/runs/{tree['run_id']}/events", h, clock))
    assert [e for e, _ in ev] == ["run.state", "end"] and ev[0][1]["state"] == "cancelled"


def test_sse_reports_a_state_change_while_open(app, client, as_role, tree, engine):
    h = as_role("viewer")
    clock = Clock()

    def later():
        with engine.begin() as c:  # the worker would do this; here the superuser does
            c.execute(
                text("UPDATE run SET state = 'running', attempt = 1 WHERE id = :i"),
                {"i": tree["run_id"]},
            )

    clock.at(3.0, later)
    ev = _events(_stream(client, app, f"/v1/runs/{tree['run_id']}/events?wait_s=10", h, clock))
    assert [(e, d.get("state")) for e, d in ev] == [
        ("run.state", "queued"),
        ("run.state", "running"),
        ("timeout", None),
    ]


def test_sse_of_another_tenants_run_is_404(client, as_role, tenants, tree):
    r = client.get(
        f"/v1/runs/{tree['run_id']}/events",
        headers=as_role("owner", tenant=tenants.b, sub="owner-b"),
    )
    assert r.status_code == 404 and r.headers["content-type"] == "application/problem+json"


def test_quota_read_is_tenant_scoped_and_audited(client, as_role, audit_events):
    r = client.get("/v1/quotas", headers=as_role("auditor"))
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"storage_bytes", "active_runs"}
    assert any(e["resource_type"] == "quota" for e in audit_events("data.read"))
    _ = datetime  # (import used by the expiry test)
