"""Early-access sign-up with double opt-in (BUILD-GUIDE 4.7; SEC-159). OWNER-GATED.

The feature is OFF unless ``Settings.early_access_enabled`` is true; then the API mounts
``POST /v1/public/early-access`` and ``POST /v1/public/early-access/confirm``. Enabling it in any
deployment, linking it from the website and publishing a privacy policy are owner decisions.

Rules:
- Minimal fields: e-mail, role (a fixed list), optional organisation. No neural or health fields.
- Honeypot field ``website``: a filled honeypot gets the normal 202 and nothing is stored or sent.
- The answer is always the same 202 (no account enumeration).
- Double opt-in: a random token is e-mailed; only its SHA-256 is stored; confirming sets
  ``confirmed_at``. Unconfirmed rows are purged after ``early_access_purge_days`` (30) days by
  :func:`purge_unconfirmed` (run daily by the scheduler) and a token older than that never confirms.
- Rate limits: per client IP and per e-mail address (in-process buckets; the gateway adds its own).
- Storage: schema ``site`` via the ``nf_site`` role only (migration 0011m4).
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import IntegrityError

from nf_platform.db import models as m
from nf_platform.db.context import role_session

SITE_DB_ROLE = "nf_site"
EMAIL_RE = re.compile(
    r"^[^@\s]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?)+$"
)


class Mailer(Protocol):
    def send_confirmation(self, email: str, token: str) -> None:
        """Send the double-opt-in message carrying ``token`` (the site builds the link)."""
        ...


class DisabledMailer:
    """Default: sends nothing. A deployment that enables the feature must configure a real mailer
    (an owner/infra decision); until then no e-mail leaves the platform."""

    def send_confirmation(self, email: str, token: str) -> None:
        return None


def normalise_email(email: str) -> str:
    return email.strip().lower()


def email_key(email: str) -> str:
    """Rate-limit key: a hash, so the limiter never holds addresses in memory."""
    return "ea-email:" + hashlib.sha256(normalise_email(email).encode("utf-8")).hexdigest()


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


@dataclass(frozen=True)
class SignupResult:
    stored: bool  # a row was created or refreshed (and a confirmation sent)


def sign_up(
    *,
    email: str,
    role: str,
    organisation: str | None,
    mailer: Mailer,
    engine: Engine | None = None,
    now: datetime | None = None,
) -> SignupResult:
    """Create (or refresh the token of) an unconfirmed sign-up and send the confirmation. A
    confirmed address is left alone and nothing is sent (the caller answers 202 either way)."""
    now = now or datetime.now(UTC)
    addr = normalise_email(email)
    token = secrets.token_urlsafe(32)
    with role_session(SITE_DB_ROLE, engine=engine) as s:
        row = s.scalar(select(m.EarlyAccessSignup).where(m.EarlyAccessSignup.email == addr))
        if row is not None and row.confirmed_at is not None:
            return SignupResult(stored=False)
        try:
            with s.begin_nested():
                if row is None:
                    s.add(
                        m.EarlyAccessSignup(
                            id=uuid.uuid4(),
                            email=addr,
                            role=role,
                            organisation=organisation,
                            confirm_hash=token_hash(token),
                            created_at=now,
                        )
                    )
                else:
                    row.role, row.organisation = role, organisation
                    row.confirm_hash, row.created_at = token_hash(token), now
        except IntegrityError:  # a concurrent sign-up for the same address won
            return SignupResult(stored=False)
    mailer.send_confirmation(addr, token)
    return SignupResult(stored=True)


def confirm(
    token: str, *, purge_days: int, engine: Engine | None = None, now: datetime | None = None
) -> bool:
    now = now or datetime.now(UTC)
    with role_session(SITE_DB_ROLE, engine=engine) as s:
        row = s.scalar(
            select(m.EarlyAccessSignup).where(m.EarlyAccessSignup.confirm_hash == token_hash(token))
        )
        if row is None or row.created_at < now - timedelta(days=purge_days):
            return False
        if row.confirmed_at is None:
            row.confirmed_at = now
        return True


def purge_unconfirmed(
    *, purge_days: int, engine: Engine | None = None, now: datetime | None = None
) -> int:
    """Delete sign-ups never confirmed within ``purge_days``. Returns the number deleted."""
    now = now or datetime.now(UTC)
    with role_session(SITE_DB_ROLE, engine=engine) as s:
        r = s.execute(
            delete(m.EarlyAccessSignup).where(
                m.EarlyAccessSignup.confirmed_at.is_(None),
                m.EarlyAccessSignup.created_at < now - timedelta(days=purge_days),
            )
        )
        return int(r.rowcount or 0)
