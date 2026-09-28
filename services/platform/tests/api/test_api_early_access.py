"""M4 4.7 (OWNER-GATED): the early-access endpoint, tested with the flag forced ON inside the test
only. Default (flag off) behaviour is tested in test_api_openapi.py: the route is not mounted.

SEC-159: server-side validation, per-IP and per-email rate limits, double opt-in, minimal fields (no
neural or health fields), honeypot, CORS limited to the site origins; unconfirmed rows are purged
after 30 days.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from nf_contract import Contract
from nf_platform.app import create_app
from nf_platform.db import models as m
from nf_platform.site import early_access
from sqlalchemy import inspect, text

pytestmark = pytest.mark.postgres
SITE = "https://neuroforge.example"
URL = "/v1/public/early-access"
CONTRACT = Contract()


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_confirmation(self, email: str, token: str) -> None:
        self.sent.append((email, token))


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def mailer():
    return FakeMailer()


@pytest.fixture
def ea(settings, engine, idp, storage, mailer):
    on = replace(settings, early_access_enabled=True, early_access_origins=(SITE,))
    app = create_app(on, engine=engine, jwks=idp.jwks, storage=storage, mailer=mailer)
    app.state.early_access_clock = Clock()
    with TestClient(app, raise_server_exceptions=False) as c:
        c.app_state = app.state  # type: ignore[attr-defined]
        yield c


def _post(c, body, origin=SITE, ip=None):
    headers = {"Origin": origin} if origin else {}
    return c.post(URL, json=body, headers=headers)


def _rows(engine):
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text("SELECT * FROM site.early_access_signup"))]


def test_signup_double_opt_in(ea, engine, mailer):
    r = _post(ea, {"email": "Ada@Lab.example", "role": "researcher", "organisation": "Lab"})
    assert r.status_code == 202, r.text
    CONTRACT.check("POST", URL, r)
    assert r.json() == {"status": "pending-confirmation"}
    assert r.headers["Access-Control-Allow-Origin"] == SITE
    rows = _rows(engine)
    assert len(rows) == 1 and rows[0]["email"] == "ada@lab.example"
    assert rows[0]["confirmed_at"] is None
    ((addr, token),) = mailer.sent
    assert addr == "ada@lab.example"
    assert token.encode() not in bytes(rows[0]["confirm_hash"])  # only the hash is stored
    r = ea.post(URL + "/confirm", json={"token": token}, headers={"Origin": SITE})
    assert r.status_code == 200 and r.json() == {"status": "confirmed"}
    CONTRACT.check("POST", URL + "/confirm", r)
    assert _rows(engine)[0]["confirmed_at"] is not None
    # a confirmed address: same 202, nothing sent (no enumeration)
    r = _post(ea, {"email": "ada@lab.example", "role": "engineer"})
    assert r.status_code == 202 and len(mailer.sent) == 1
    bad = ea.post(URL + "/confirm", json={"token": "x" * 40})
    assert bad.status_code == 404 and bad.headers["content-type"] == "application/problem+json"


def test_only_minimal_fields_are_accepted(ea, engine):
    for body in (
        {"email": "a@b.example", "role": "researcher", "diagnosis": "x"},  # no health fields
        {"email": "a@b.example", "role": "researcher", "eeg_channels": 8},  # no neural fields
        {"email": "not-an-email", "role": "researcher"},
        {"email": "a@b.example", "role": "patient"},  # not in the fixed role list
        {"email": "a@b.example"},
    ):
        r = _post(ea, body)
        assert r.status_code == 422, body
        assert r.headers["content-type"] == "application/problem+json"
        assert "a@b.example" not in r.text  # the input is not echoed
    assert _rows(engine) == []
    cols = {c["name"] for c in inspect(engine).get_columns("early_access_signup", schema="site")}
    assert cols == {
        "id",
        "email",
        "role",
        "organisation",
        "confirm_hash",
        "created_at",
        "confirmed_at",
    }


def test_honeypot_gets_202_and_stores_nothing(ea, engine, mailer):
    r = _post(ea, {"email": "bot@spam.example", "role": "other", "website": "http://spam"})
    assert r.status_code == 202 and r.json() == {"status": "pending-confirmation"}
    assert _rows(engine) == [] and mailer.sent == []


def test_rate_limit_per_ip(ea, settings):
    n = settings.early_access_ip_per_hour
    codes = [
        _post(ea, {"email": f"u{i}@x.example", "role": "student"}).status_code for i in range(n + 1)
    ]
    assert codes[:n] == [202] * n
    assert codes[n] == 429
    r = _post(ea, {"email": "late@x.example", "role": "student"})
    assert r.headers["content-type"] == "application/problem+json" and "Retry-After" in r.headers
    ea.app_state.early_access_clock.t += 3600  # an hour later the bucket has refilled
    assert _post(ea, {"email": "later@x.example", "role": "student"}).status_code == 202


def test_rate_limit_per_email(ea, settings, mailer):
    # several IPs cannot bypass the per-address limit: the e-mail bucket is shared
    n = settings.early_access_email_per_day
    ea.app_state.early_access_limiters = None
    codes = []
    for _ in range(n + 1):
        codes.append(_post(ea, {"email": "same@x.example", "role": "other"}).status_code)
        ea.app_state.early_access_clock.t += 3600  # the IP bucket refills, the e-mail one not
    assert codes[:n] == [202] * n and codes[n] == 429
    assert len(mailer.sent) == n


def test_cors_only_site_origins(ea):
    r = _post(ea, {"email": "c@x.example", "role": "other"}, origin="https://evil.example")
    assert r.status_code == 403 and "Access-Control-Allow-Origin" not in r.headers
    pre = ea.options(URL, headers={"Origin": SITE, "Access-Control-Request-Method": "POST"})
    assert pre.status_code == 204
    assert pre.headers["Access-Control-Allow-Origin"] == SITE
    assert pre.headers["Access-Control-Allow-Methods"] == "POST, OPTIONS"
    assert "Access-Control-Allow-Credentials" not in pre.headers  # no cookies, no credentials
    bad = ea.options(URL, headers={"Origin": "https://evil.example"})
    assert bad.status_code == 403
    # no Origin (server-to-server, curl): allowed, no CORS headers
    r = _post(ea, {"email": "d@x.example", "role": "other"}, origin=None)
    assert r.status_code == 202 and "Access-Control-Allow-Origin" not in r.headers


def test_unconfirmed_signups_are_purged_after_30_days(ea, engine, mailer, settings):
    now = datetime.now(UTC)
    for e in ("old@x.example", "new@x.example", "kept@x.example"):
        _post(ea, {"email": e, "role": "other"})
    tokens = dict(mailer.sent)
    assert early_access.confirm(tokens["kept@x.example"], purge_days=30, engine=engine)
    with engine.begin() as c:  # age two of them past 30 days
        c.execute(
            text(
                "UPDATE site.early_access_signup SET created_at = :t "
                "WHERE email IN ('old@x.example', 'kept@x.example')"
            ),
            {"t": now - timedelta(days=31)},
        )
    # an old token can no longer confirm, even before the purge runs
    assert not early_access.confirm(tokens["old@x.example"], purge_days=30, engine=engine)
    n = early_access.purge_unconfirmed(purge_days=settings.early_access_purge_days, engine=engine)
    assert n == 1
    assert sorted(r["email"] for r in _rows(engine)) == ["kept@x.example", "new@x.example"]


def test_the_site_role_is_the_only_one_with_access(engine):
    """nf_app (the tenant API role) cannot read the sign-up list."""
    from sqlalchemy.exc import ProgrammingError

    with (
        engine.connect() as c,
        pytest.raises(ProgrammingError, match="permission denied"),
        c.begin(),
    ):
        c.execute(text("SET LOCAL ROLE nf_app"))
        c.execute(text("SELECT count(*) FROM site.early_access_signup"))


def test_site_model_matches_the_migration(db_url):
    """The site schema is outside Base (tenant tables); check its drift separately."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    eng = create_engine(db_url)
    with eng.connect() as c:
        ctx = MigrationContext.configure(
            c,
            opts={
                "compare_type": True,
                "include_schemas": True,
                "include_name": lambda name, type_, parent: (type_ != "schema" or name == "site"),
            },
        )
        diff = compare_metadata(ctx, m.SiteBase.metadata)
    eng.dispose()
    assert diff == []
