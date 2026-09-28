"""API keys (SEC-014): 256-bit random secret, shown once, stored as HMAC-SHA-256 with a server
pepper.

Format: ``nfb_live_<public id: 16 base32 chars>_<secret: 43 base64url chars>``. The prefix lets
secret scanners find leaked keys. The public id locates the row; the HMAC of the whole key is
compared in constant time. Expiry is at most 365 days (default 90).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from nf_platform.auth.authorize import SCOPES, Forbidden, Unauthorized, delegable_roles
from nf_platform.config import AUTH_DB_ROLE, SecretProvider
from nf_platform.db.context import Principal, role_session
from nf_platform.db.models import ApiKey

PREFIX = "nfb_live_"
PUBLIC_ID_LEN = 16
SECRET_BYTES = 32  # 256 bits (SEC-014 asks for >= 128)
MAX_DAYS = 365
DEFAULT_DAYS = 90


class ApiKeyRequestError(ValueError):
    """Invalid key request (422)."""


@dataclass(frozen=True)
class IssuedKey:
    row: ApiKey
    plaintext: str  # returned to the caller exactly once; never stored or logged


def _public_id() -> str:
    return base64.b32encode(secrets.token_bytes(10)).decode("ascii").lower()


def hash_key(key: str, pepper: bytes) -> bytes:
    return hmac.new(pepper, key.encode("utf-8"), hashlib.sha256).digest()


def parse_public_id(key: str) -> str:
    if not key.startswith(PREFIX):
        raise Unauthorized("not an API key")
    rest = key[len(PREFIX) :]
    if len(rest) != PUBLIC_ID_LEN + 1 + 43 or rest[PUBLIC_ID_LEN] != "_":
        raise Unauthorized("malformed API key")
    return rest[:PUBLIC_ID_LEN]


def issue(
    session: Session,
    principal: Principal,
    *,
    name: str,
    roles: list[str],
    scopes: list[str],
    days: int | None,
    secret_provider: SecretProvider,
    now: datetime | None = None,
) -> IssuedKey:
    days = DEFAULT_DAYS if days is None else days
    if not 1 <= days <= MAX_DAYS:
        raise ApiKeyRequestError(f"expiry must be 1..{MAX_DAYS} days")
    if not roles or not scopes:
        raise ApiKeyRequestError("a key needs at least one role and one scope")
    unknown = set(scopes) - set(SCOPES)
    if unknown:
        raise ApiKeyRequestError(f"unknown scopes: {sorted(unknown)}")
    if not set(roles) <= delegable_roles(principal):
        raise Forbidden("cannot delegate these roles to an API key")
    now = now or datetime.now(UTC)
    public_id = _public_id()
    secret = base64.urlsafe_b64encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")
    plaintext = f"{PREFIX}{public_id}_{secret}"
    version, pepper = secret_provider.api_key_pepper()
    row = ApiKey(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(principal.tenant_id),
        public_id=public_id,
        owner_id=principal.id,
        name=name,
        key_hash=hash_key(plaintext, pepper),
        pepper_version=version,
        roles=sorted(set(roles)),
        scopes=sorted(set(scopes)),
        created_at=now,
        expires_at=now + timedelta(days=days),
    )
    session.add(row)
    session.flush()
    return IssuedKey(row=row, plaintext=plaintext)


def verify(
    key: str, *, engine: Engine | None, secret_provider: SecretProvider, now: datetime | None = None
) -> Principal:
    """Resolve an API key to a Principal or raise Unauthorized (unknown, wrong, expired,
    revoked)."""
    public_id = parse_public_id(key)
    with role_session(AUTH_DB_ROLE, engine=engine) as s:
        row = s.scalar(select(ApiKey).where(ApiKey.public_id == public_id))
        if row is None:
            raise Unauthorized("unknown API key")
        version, pepper = secret_provider.api_key_pepper()
        if row.pepper_version != version or not hmac.compare_digest(
            hash_key(key, pepper), row.key_hash
        ):
            raise Unauthorized("invalid API key")
        now = now or datetime.now(UTC)
        if row.revoked_at is not None:
            raise Unauthorized("API key revoked")
        if row.expires_at <= now:
            raise Unauthorized("API key expired")
        return Principal(
            id=row.owner_id,
            tenant_id=str(row.tenant_id),
            roles=frozenset(row.roles),
            scopes=frozenset(row.scopes),
            kind="api_key",
            mfa_phr=False,
            auth_method="api_key",
            credential_id=row.public_id,
        )
