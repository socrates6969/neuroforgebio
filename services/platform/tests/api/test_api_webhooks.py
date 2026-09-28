"""M4 4.6: signed webhooks (SEC-045), SSRF protection (SEC-076), delivery with retries.

No test touches the network: the resolver and the transport are fakes.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from nf_platform.db import models as m
from nf_platform.db.context import tenant_session
from nf_platform.storage.runtime import service_principal
from nf_platform.webhooks import service as webhooks
from nf_platform.webhooks import signing, ssrf
from nf_platform.webhooks.payloads import RunFinishedData, RunFinishedEvent
from sqlalchemy import select, text

_EX = Path(__file__).resolve().parents[2] / "examples" / "verify_webhook.py"
_spec = importlib.util.spec_from_file_location("verify_webhook_sample", _EX)
sample = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sample)

URL = "https://hooks.customer.example/nf"
PUBLIC_IP = "93.184.215.14"  # a public (global) address; never contacted: the transport is fake


def resolver_for(*addresses: str):
    calls: list[str] = []

    def resolve(host: str, port: int):
        calls.append(host)
        return list(addresses)

    resolve.calls = calls  # type: ignore[attr-defined]
    return resolve


class FakeTransport:
    def __init__(self, *statuses: int | Exception) -> None:
        self.statuses = list(statuses)
        self.sent: list[tuple[ssrf.PinnedTarget, dict[str, str], bytes]] = []

    def post(self, target, headers, body, timeout_s):
        self.sent.append((target, headers, body))
        st = self.statuses.pop(0) if self.statuses else 200
        if isinstance(st, Exception):
            raise st
        return st


# ---------------------------------------------------------------- signing + the sample verifier
KEY = b"nfb_whk_test-key-0123456789"
BODY = b'{"id":"e1","type":"run.finished"}'


def test_valid_signature_passes_the_sample_verifier():
    now = 1_790_000_000
    header = signing.sign([KEY], now, BODY)
    assert sample.verify_webhook(BODY, header, KEY, now=now + 10) == now
    assert signing.verify(header, BODY, KEY, now=now + 10) == now


def test_replay_older_than_5_minutes_is_rejected_by_the_sample_verifier():
    now = 1_790_000_000
    header = signing.sign([KEY], now, BODY)
    assert sample.verify_webhook(BODY, header, KEY, now=now + 300) == now  # exactly 5 min: ok
    with pytest.raises(sample.WebhookRejected, match="stale"):
        sample.verify_webhook(BODY, header, KEY, now=now + 301)
    with pytest.raises(signing.SignatureError):
        signing.verify(header, BODY, KEY, now=now + 301)
    with pytest.raises(sample.WebhookRejected):  # far-future timestamps too
        sample.verify_webhook(BODY, header, KEY, now=now - 301)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda h, b: (h, b + b" "),  # body changed
        lambda h, b: (h.replace("t=", "t=1"), b),  # timestamp changed
        lambda h, b: (h.split(",")[0], b),  # no signature
        lambda h, b: ("garbage", b),
    ],
)
def test_tampering_is_rejected(mutate):
    now = 1_790_000_000
    h, b = mutate(signing.sign([KEY], now, BODY), BODY)
    with pytest.raises(sample.WebhookRejected):
        sample.verify_webhook(b, h, KEY, now=now)


def test_rotation_overlap_both_keys_verify():
    now = 1_790_000_000
    new, old = b"nfb_whk_new-key-000000", b"nfb_whk_old-key-000000"
    header = signing.sign([new, old], now, BODY)
    assert header.count("v1=") == 2
    assert sample.verify_webhook(BODY, header, new, now=now) == now
    assert sample.verify_webhook(BODY, header, old, now=now) == now
    with pytest.raises(sample.WebhookRejected):
        sample.verify_webhook(BODY, header, b"nfb_whk_other", now=now)


# ---------------------------------------------------------------- SSRF (one test per target)
BLOCKED_ADDRESSES = [
    "10.0.0.1",  # RFC 1918
    "172.16.5.4",  # RFC 1918
    "192.168.1.10",  # RFC 1918
    "127.0.0.1",  # loopback
    "127.10.20.30",  # loopback /8
    "169.254.169.254",  # cloud metadata
    "169.254.10.1",  # link-local
    "100.64.0.1",  # CGNAT
    "0.0.0.0",  # this network
    "224.0.0.1",  # multicast
    "255.255.255.255",  # broadcast
    "::1",  # IPv6 loopback
    "::",  # unspecified
    "fe80::1",  # IPv6 link-local
    "fc00::1",  # unique local
    "fd00:ec2::254",  # AWS IPv6 metadata
    "::ffff:127.0.0.1",  # IPv4-mapped loopback
    "::ffff:169.254.169.254",  # IPv4-mapped metadata
    "::ffff:10.0.0.1",  # IPv4-mapped RFC 1918
    "64:ff9b::a9fe:a9fe",  # NAT64 of 169.254.169.254
    "2002:a9fe:a9fe::1",  # 6to4 of 169.254.169.254
    "ff02::1",  # IPv6 multicast
    "2001:db8::1",  # documentation
    # bug hunt H2: deprecated IPv4-compatible IPv6 (::a.b.c.d); is_global is True for these
    "::169.254.169.254",  # IPv4-compatible metadata
    "::127.0.0.1",  # IPv4-compatible loopback
    "::10.0.0.5",  # IPv4-compatible RFC 1918
    "::8.8.8.8",  # the whole deprecated ::/96 range is refused
]


@pytest.mark.parametrize("address", BLOCKED_ADDRESSES)
def test_ssrf_blocked_resolved_address(address):
    with pytest.raises(ssrf.BlockedUrl, match="blocked address"):
        ssrf.resolve_pinned(URL, resolver_for(address))


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.customer.example/nf",  # not https
        "https://10.0.0.1/nf",  # IP literal (RFC 1918)
        "https://169.254.169.254/latest/meta-data/",  # metadata literal
        "https://[::1]/nf",  # IPv6 literal
        "https://2130706433/nf",  # decimal 127.0.0.1
        "https://0x7f000001/nf",  # hex 127.0.0.1
        "https://127.1/nf",  # short form
        "https://localhost/nf",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://printer.local/nf",
        "https://intranet/nf",  # not fully qualified
        "https://user:pw@hooks.customer.example/nf",  # user-info
        "https://hooks.customer.example:22/nf",  # privileged non-443 port
        "https://hooks.customer.example/nf#frag",
        "ftp://hooks.customer.example/nf",
    ],
)
def test_ssrf_blocked_url(url):
    with pytest.raises(ssrf.BlockedUrl):
        ssrf.resolve_pinned(url, resolver_for(PUBLIC_IP))


def test_ssrf_any_blocked_answer_blocks_and_public_is_pinned():
    with pytest.raises(ssrf.BlockedUrl):
        ssrf.resolve_pinned(URL, resolver_for(PUBLIC_IP, "10.1.2.3"))
    t = ssrf.resolve_pinned(URL, resolver_for(PUBLIC_IP))
    assert (t.host, t.port, t.address) == ("hooks.customer.example", 443, PUBLIC_IP)


def test_ssrf_dns_rebinding_resolves_once_and_pins():
    """A resolver that answers public first and private afterwards is consulted exactly once; the
    connection uses the checked address."""
    answers = iter([[PUBLIC_IP], ["127.0.0.1"], ["127.0.0.1"]])
    calls = []

    def rebinding(host, port):
        calls.append(host)
        return next(answers)

    t = ssrf.resolve_pinned(URL, rebinding)
    assert calls == ["hooks.customer.example"] and t.address == PUBLIC_IP


def test_ssrf_unresolvable_host_is_refused():
    def fail(host, port):
        raise OSError("nxdomain")

    with pytest.raises(ssrf.BlockedUrl, match="does not resolve"):
        ssrf.resolve_pinned(URL, fail)


# ---------------------------------------------------------------- API + delivery (Postgres)
pg = pytest.mark.postgres


def _create(client, h, url=URL):
    return client.post(
        "/v1/webhooks", json={"url": url, "event_types": ["run.finished"]}, headers=h
    )


@pg
def test_create_shows_the_secret_once_and_stores_it_encrypted(client, as_role, engine):
    h = as_role("owner")
    r = _create(client, h)
    assert r.status_code == 201, r.text
    body = r.json()
    secret = body["signing_secret"]
    assert secret.startswith("nfb_whk_") and len(secret) >= 40
    assert [k["version"] for k in body["key_versions"]] == [1]
    listed = client.get("/v1/webhooks", headers=h).json()
    assert listed and "signing_secret" not in listed[0]
    one = client.get(f"/v1/webhooks/{body['id']}", headers=h).json()
    assert "signing_secret" not in one
    with engine.connect() as c:
        dump = json.dumps(
            [
                {k: str(v) for k, v in row._mapping.items()}
                for t in ("webhook_endpoint", "webhook_key")
                for row in c.execute(text(f"SELECT * FROM {t}"))
            ]
        )
        raw = b"".join(
            bytes(x) for x in c.execute(text("SELECT key_ciphertext FROM webhook_key")).scalars()
        )
    assert secret not in dump and secret.encode() not in raw


@pg
@pytest.mark.parametrize(
    "url",
    ["http://hooks.customer.example/x", "https://10.0.0.1/x", "https://localhost/x"],
)
def test_create_refuses_unsafe_urls(client, as_role, url):
    r = _create(client, as_role("admin"), url)
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"


@pg
def test_api_keys_and_scientists_cannot_manage_webhooks(client, as_role):
    assert _create(client, as_role("scientist")).status_code == 403
    k = client.post(
        "/v1/api-keys",
        json={"name": "k", "roles": ["scientist"], "scopes": ["metadata:read", "data:write"]},
        headers=as_role("owner"),
    ).json()["key"]
    r = _create(client, {"Authorization": f"Bearer {k}"})
    assert r.status_code == 403


def _run_row(engine, tenant_id: str, tree: dict[str, str]) -> m.Run:
    with tenant_session(service_principal(tenant_id, "svc:test"), engine=engine) as s:
        return s.scalar(select(m.Run).where(m.Run.id == uuid.UUID(tree["run_id"])))


@pg
def test_run_finished_event_is_signed_delivered_and_verifiable(
    client, as_role, tree, tenants, engine, settings
):
    h = as_role("owner")
    created = _create(client, h).json()
    secret = created["signing_secret"].encode()
    # cancel the queued run of the tree: a terminal state -> one pending delivery
    r = client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    assert r.json()["state"] == "cancelled"
    deliveries = client.get(f"/v1/webhooks/{created['id']}/deliveries", headers=h).json()
    assert [d["state"] for d in deliveries] == ["pending"]
    claimed = webhooks.claim_due(10, engine=engine)
    assert [str(d) for _, d in claimed] == [deliveries[0]["id"]]
    assert webhooks.claim_due(10, engine=engine) == []  # leased: a second dispatcher gets nothing
    tr = FakeTransport(200)
    now = datetime.now(UTC)
    st = webhooks.deliver(
        tenants.a,
        claimed[0][1],
        settings=settings,
        transport=tr,
        resolver=resolver_for(PUBLIC_IP),
        clock=lambda: now,
        engine=engine,
    )
    assert st == "delivered"
    target, headers, body = tr.sent[0]
    assert target.address == PUBLIC_IP and target.host == "hooks.customer.example"
    ts = sample.verify_webhook(body, headers["NF-Webhook-Signature"], secret, now=now.timestamp())
    assert ts == int(now.timestamp())
    event = RunFinishedEvent.model_validate_json(body)
    assert str(event.data.run_id) == tree["run_id"] and event.data.state == "cancelled"
    assert headers["NF-Webhook-Id"] == str(event.id)
    # a replay of the same delivery 6 minutes later is rejected by the sample verifier
    with pytest.raises(sample.WebhookRejected):
        sample.verify_webhook(
            body, headers["NF-Webhook-Signature"], secret, now=now.timestamp() + 360
        )


@pg
def test_retries_with_exponential_backoff_then_failed(
    client, as_role, tree, tenants, engine, settings
):
    from dataclasses import replace

    s3 = replace(settings, webhook_max_attempts=3, webhook_backoff_base_s=10.0)
    h = as_role("owner")
    _create(client, h)
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    with engine.connect() as c:
        did = c.execute(text("SELECT id FROM webhook_delivery")).scalar_one()
    t0 = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    tr = FakeTransport(503, OSError("connection refused"), 500)
    common = dict(settings=s3, transport=tr, resolver=resolver_for(PUBLIC_IP), engine=engine)

    assert webhooks.deliver(tenants.a, did, clock=lambda: t0, **common) == "pending"
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM webhook_delivery")).mappings().one()
    assert row["attempts"] == 1 and row["last_status"] == 503
    assert row["next_attempt_at"] == t0 + timedelta(seconds=10)
    assert webhooks.deliver(tenants.a, did, clock=lambda: t0, **common) == "pending"
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM webhook_delivery")).mappings().one()
    assert row["attempts"] == 2 and row["last_error"] == "network: OSError"
    assert row["next_attempt_at"] == t0 + timedelta(seconds=20)  # doubled
    assert webhooks.deliver(tenants.a, did, clock=lambda: t0, **common) == "failed"
    assert len(tr.sent) == 3
    # a failed delivery is never sent again
    assert webhooks.deliver(tenants.a, did, clock=lambda: t0, **common) == "failed"
    assert len(tr.sent) == 3


@pg
def test_delivery_to_a_rebound_private_address_is_refused(
    client, as_role, tree, tenants, engine, settings
):
    h = as_role("owner")
    _create(client, h)
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    with engine.connect() as c:
        did = c.execute(text("SELECT id FROM webhook_delivery")).scalar_one()
    tr = FakeTransport()
    st = webhooks.deliver(
        tenants.a,
        did,
        settings=settings,
        transport=tr,
        resolver=resolver_for("169.254.169.254"),
        engine=engine,
    )
    assert st == "pending" and tr.sent == []  # never connected; retried later
    with engine.connect() as c:
        err = c.execute(text("SELECT last_error FROM webhook_delivery")).scalar_one()
    assert err.startswith("blocked:")


@pg
def test_rotation_keeps_the_old_secret_valid_during_the_overlap(
    client, as_role, tree, tenants, engine, settings
):
    h = as_role("owner")
    created = _create(client, h).json()
    old = created["signing_secret"].encode()
    r = client.post(f"/v1/webhooks/{created['id']}/rotate-secret", headers=h)
    assert r.status_code == 200, r.text
    rot = r.json()
    new = rot["signing_secret"].encode()
    assert rot["version"] == 2 and new != old
    until = datetime.fromisoformat(rot["previous_valid_until"])
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    with engine.connect() as c:
        did = c.execute(text("SELECT id FROM webhook_delivery")).scalar_one()

    def send(at: datetime):
        tr = FakeTransport(500)  # keep it pending so it can be sent again
        webhooks.deliver(
            tenants.a,
            did,
            settings=settings,
            transport=tr,
            resolver=resolver_for(PUBLIC_IP),
            clock=lambda: at,
            engine=engine,
        )
        return tr.sent[0]

    during = until - timedelta(minutes=1)
    _, headers, body = send(during)
    sig = headers["NF-Webhook-Signature"]
    assert sample.verify_webhook(body, sig, new, now=during.timestamp())
    assert sample.verify_webhook(body, sig, old, now=during.timestamp())
    after = until + timedelta(minutes=1)
    _, headers, body = send(after)
    sig = headers["NF-Webhook-Signature"]
    assert sig.count("v1=") == 1
    assert sample.verify_webhook(body, sig, new, now=after.timestamp())
    with pytest.raises(sample.WebhookRejected):
        sample.verify_webhook(body, sig, old, now=after.timestamp())


@pg
def test_disabled_endpoint_gets_no_new_events_and_pending_fail(client, as_role, tree, engine):
    h = as_role("owner")
    created = _create(client, h).json()
    assert client.delete(f"/v1/webhooks/{created['id']}", headers=h).status_code == 204
    assert client.get(f"/v1/webhooks/{created['id']}", headers=h).json()["disabled_at"]
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM webhook_delivery")).scalar_one() == 0
    r = client.post(f"/v1/webhooks/{created['id']}/rotate-secret", headers=h)
    assert r.status_code == 409


@pg
def test_other_tenant_cannot_see_or_touch_webhooks(client, as_role, tenants):
    created = _create(client, as_role("owner")).json()
    hb = as_role("owner", tenant=tenants.b, sub="owner-b")
    assert client.get(f"/v1/webhooks/{created['id']}", headers=hb).status_code == 404
    assert client.delete(f"/v1/webhooks/{created['id']}", headers=hb).status_code == 404
    assert client.get("/v1/webhooks", headers=hb).json() == []


@pg
def test_enqueue_is_idempotent_per_event(engine, tenants, client, as_role, tree):
    _create(client, as_role("owner"))
    event = RunFinishedEvent(
        id=uuid.uuid4(),
        type="run.finished",
        created_at=datetime.now(UTC),
        tenant_id=uuid.UUID(tenants.a),
        data=RunFinishedData(
            run_id=uuid.UUID(tree["run_id"]),
            pipeline_ref="p@1.0.0",
            pipeline_version_id="pv:sha256:" + "0" * 64,
            recording_id=uuid.UUID(tree["recording_id"]),
            state="failed",
            finished_at=None,
        ),
    )
    with tenant_session(service_principal(tenants.a, "svc:test"), engine=engine) as s:
        assert webhooks.enqueue(s, uuid.UUID(tenants.a), event) == 1
        assert webhooks.enqueue(s, uuid.UUID(tenants.a), event) == 0


# ---------------------------------------------------------------- bug hunt H1: one bad row
@pg
def test_retired_pepper_marks_the_delivery_retryable_not_a_crash(
    client, as_role, tree, tenants, engine, settings
):
    """A key sealed under an old pepper version cannot sign: that delivery backs off (and ends
    failed after max attempts); nothing is sent and nothing raises."""
    import os
    from dataclasses import replace

    from nf_platform.config import StaticSecretProvider

    h = as_role("owner")
    _create(client, h)
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    rotated = replace(
        settings,
        secrets=StaticSecretProvider(version="p-rotated", pepper=os.urandom(32)),
        webhook_max_attempts=2,
    )
    tr = FakeTransport()
    counts = webhooks.deliver_due(
        settings=rotated, transport=tr, resolver=resolver_for(PUBLIC_IP), engine=engine
    )
    assert counts == {"pending": 1} and tr.sent == []
    with engine.connect() as c:
        row = c.execute(text("SELECT * FROM webhook_delivery")).mappings().one()
    assert row["attempts"] == 1 and row["last_error"] == "signing key unavailable"
    did = row["id"]
    common = dict(settings=rotated, transport=tr, resolver=resolver_for(PUBLIC_IP), engine=engine)
    assert webhooks.deliver(tenants.a, did, **common) == "failed"
    assert tr.sent == []


@pg
def test_a_crashing_delivery_does_not_abort_the_batch_and_backs_off(
    client, as_role, tree, tenants, engine, settings, monkeypatch
):
    h = as_role("owner")
    _create(client, h, "https://hooks.customer.example/a")
    _create(client, h, "https://hooks.customer.example/b")
    client.post(f"/v1/runs/{tree['run_id']}/cancel", headers=h)
    with engine.connect() as c:
        ids = list(c.execute(text("SELECT id FROM webhook_delivery ORDER BY id")).scalars())
    assert len(ids) == 2
    bad = ids[0]
    real = webhooks.deliver

    def flaky(tenant_id, delivery_id, **kw):
        if delivery_id == bad:
            raise RuntimeError("unexpected")
        return real(tenant_id, delivery_id, **kw)

    monkeypatch.setattr(webhooks, "deliver", flaky)
    t0 = datetime.now(UTC)
    tr = FakeTransport()
    counts = webhooks.deliver_due(
        settings=settings,
        transport=tr,
        resolver=resolver_for(PUBLIC_IP),
        clock=lambda: t0,
        engine=engine,
    )
    assert counts == {"delivered": 1, "error": 1} and len(tr.sent) == 1
    with engine.connect() as c:
        row = (
            c.execute(text("SELECT * FROM webhook_delivery WHERE id = :i"), {"i": bad})
            .mappings()
            .one()
        )
    assert row["state"] == "pending" and row["attempts"] == 1
    assert row["last_error"] == "internal: RuntimeError"
    assert row["next_attempt_at"] > t0  # backs off instead of being re-leased at once forever


# ---------------------------------------------------------------- bug hunt M1: enqueue race
@pg
def test_concurrent_enqueue_of_one_event_is_a_harmless_duplicate(
    engine, tenants, client, as_role, tree
):
    """Both transactions miss each other's uncommitted row in the pre-check; the loser hits the
    unique index and must dedupe inside a savepoint instead of failing its whole transaction."""
    import threading
    import time

    _create(client, as_role("owner"))
    event = RunFinishedEvent(
        id=uuid.uuid4(),
        type="run.finished",
        created_at=datetime.now(UTC),
        tenant_id=uuid.UUID(tenants.a),
        data=RunFinishedData(
            run_id=uuid.UUID(tree["run_id"]),
            pipeline_ref="p@1.0.0",
            pipeline_version_id="pv:sha256:" + "0" * 64,
            recording_id=uuid.UUID(tree["recording_id"]),
            state="failed",
            finished_at=None,
        ),
    )
    p = service_principal(tenants.a, "svc:test")
    out: dict[str, object] = {}

    def second():
        try:
            with tenant_session(p, engine=engine) as s2:
                out["n"] = webhooks.enqueue(s2, uuid.UUID(tenants.a), event)
        except Exception as e:  # pragma: no cover - the failure being tested
            out["error"] = e

    with tenant_session(p, engine=engine) as s1:
        assert webhooks.enqueue(s1, uuid.UUID(tenants.a), event) == 1
        th = threading.Thread(target=second)
        th.start()
        time.sleep(1.0)  # let the second insert block on the unique index
    th.join(timeout=30)
    assert "error" not in out, out.get("error")
    assert out["n"] == 0
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM webhook_delivery")).scalar_one() == 1
