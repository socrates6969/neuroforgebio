"""Settings for the platform service (12-factor: environment variables, no secrets in the repo;
SEC-050).

Secrets (the API-key pepper) come through a :class:`SecretProvider`. Locally/tests: an in-memory
value. In a deployment the provider decrypts the pepper with the cloud KMS (a KMS stub until the
infra step wires it).
"""

from __future__ import annotations

import base64
import math
import os
from dataclasses import dataclass, field
from typing import Protocol

# Name of the database role the API runs its tenant-scoped transactions as (created by migration
# 0001).
APP_DB_ROLE = "nf_app"
# AppSec M2 (migration 0015_audit_roles): the audit role is split.
# Insert-only writer of audit events (the API and worker event sink). The request path may assume
# only this one of the two (``db.context.role_session``).
AUDIT_WRITER_DB_ROLE = "nf_audit_writer"
# Writer of ``audit_batch`` rows, used ONLY inside the batcher job
# (``audit.chain.batcher_session``).
# Deployment: a separate DB login that is the sole member of this role, passed to the worker as
# NF_AUDIT_BATCHER_DATABASE_URL; the API's login must never be granted it.
AUDIT_BATCHER_DB_ROLE = "nf_audit_batcher"
AUDIT_BATCHER_URL_ENV = "NF_AUDIT_BATCHER_DATABASE_URL"
# Read-only lookup of API keys by their public id, before the tenant is known (created by migration
# 0001).
AUTH_DB_ROLE = "nf_auth"


class SecretProvider(Protocol):
    def api_key_pepper(self) -> tuple[str, bytes]:
        """(pepper version id, pepper bytes >= 32). The version is stored next to each key hash."""
        ...


@dataclass(frozen=True)
class StaticSecretProvider:
    """Pepper held in memory (tests, local dev). Never log it."""

    version: str
    pepper: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.pepper) < 32:
            raise ValueError("API-key pepper must be at least 32 bytes")

    def api_key_pepper(self) -> tuple[str, bytes]:
        return self.version, self.pepper


def pepper_from_env() -> StaticSecretProvider:
    """KMS stub: `NF_API_KEY_PEPPER` (base64, >= 32 bytes) + `NF_API_KEY_PEPPER_VERSION`.

    In a deployment the variable holds a KMS ciphertext and this function becomes a KMS Decrypt
    call.
    """
    raw = os.environ.get("NF_API_KEY_PEPPER")
    if not raw:
        raise RuntimeError("NF_API_KEY_PEPPER is not set")
    return StaticSecretProvider(
        version=os.environ.get("NF_API_KEY_PEPPER_VERSION", "p1"), pepper=base64.b64decode(raw)
    )


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    audience: str
    # JWKS URL of the IdP. Tests may pass a static JWKS to the verifier instead.
    jwks_uri: str | None = None
    tenant_claim: str = "nf_tenant"
    roles_claim: str = "nf_roles"
    # Asymmetric algorithms only; never "none" or HS* (algorithm-confusion defence).
    algorithms: tuple[str, ...] = ("RS256", "PS256", "ES256")
    leeway_s: int = 30


@dataclass(frozen=True)
class Placement:
    """Which service this deployment uses per role (5.7 PHI guard, ``nf_platform.placement``).
    Ids come from the catalog in ``infra/policy/phi-services.json``. The defaults are local dev
    services, which are never BAA-listed, so a phi=true tenant is refused on a dev stack."""

    storage: str = "local_fs"
    database: str = "local_postgres"
    compute: str = "local_process"


# Deployment environments. NF_ENVIRONMENT is read ONLY by `environment_from_env` and normalised
# there: an unknown value is a startup error, never a silent "dev" (a "Prod" or "prod " typo must
# not switch off the prod-only guards: NR-H1 storage, SEC-071 synthetic-only, signing keys).
ENVIRONMENTS = frozenset({"dev", "test", "staging", "prod"})
DEFAULT_ENVIRONMENT = "dev"


def parse_environment(raw: str) -> str:
    """Normalise (strip, lower-case) and validate an environment name."""
    env = raw.strip().lower()
    if env not in ENVIRONMENTS:
        raise ValueError(f"NF_ENVIRONMENT must be one of {sorted(ENVIRONMENTS)}, not {raw!r}")
    return env


def environment_from_env() -> str:
    """The deployment environment: ``NF_ENVIRONMENT`` normalised, ``dev`` only when unset."""
    raw = os.environ.get("NF_ENVIRONMENT")
    return DEFAULT_ENVIRONMENT if raw is None else parse_environment(raw)


# Stream ingest (P7.7 R1): per-stream limit on NEW chunks (token bucket in the gRPC servicer).
# 150/s is 3x an honest live 20 ms stream (50/s), so a backlog drains at about 2x real time, while
# a flood of tiny chunks stays capped per stream (nfb-security, 2026-09-27; counted in chunks, not
# in seconds of signal, which tiny chunks would evade).
STREAM_CHUNK_RATE = 150.0
STREAM_CHUNK_BURST = 300


def stream_chunk_limits_from_env() -> tuple[float, int]:
    """``(rate, burst)`` from ``NF_STREAM_CHUNK_RATE`` (chunks/s, finite > 0) and
    ``NF_STREAM_CHUNK_BURST`` (>= 1); the defaults when unset. Invalid values raise."""
    rate = float(os.environ.get("NF_STREAM_CHUNK_RATE", STREAM_CHUNK_RATE))
    burst = int(os.environ.get("NF_STREAM_CHUNK_BURST", STREAM_CHUNK_BURST))
    if not (math.isfinite(rate) and rate > 0):
        raise ValueError(f"NF_STREAM_CHUNK_RATE must be finite and > 0, not {rate}")
    if burst < 1:
        raise ValueError(f"NF_STREAM_CHUNK_BURST must be >= 1, not {burst}")
    return rate, burst


@dataclass(frozen=True)
class Settings:
    database_url: str
    oidc: OidcSettings
    secrets: SecretProvider = field(repr=False)
    api_key_default_days: int = 90
    api_key_max_days: int = 365
    # Deployment environment (SEC-071): outside "prod" only synthetic uploads/streams are accepted.
    # One of ENVIRONMENTS, already normalised (checked in __post_init__).
    environment: str = DEFAULT_ENVIRONMENT
    # Upload sessions (2.6). S3 needs parts >= 5 MiB except the last one; tests lower the minimum.
    upload_max_bytes: int = 2 * 1024**3
    upload_part_min: int = 5 * 1024**2
    upload_part_max: int = 64 * 1024**2
    # Window reads (2.4 endpoint): at most this many values (samples x channels) per response.
    window_max_values: int = 4_000_000
    # JSON is ~10x larger than binary per value: a lower cap for format=json.
    window_json_max_values: int = 250_000
    # ---- M4 (4.8, SEC-075): local token bucket per credential (the gateway enforces the global,
    # per-tenant limit; docs/platform/rate-limits.md). Configuration defaults, not measurements.
    rate_limit_rps: float = 50.0
    rate_limit_burst: int = 200
    # Per-tenant quotas when the tenant has no ``tenant_quota`` row.
    quota_storage_bytes: int = 100 * 1024**3
    quota_active_runs: int = 50
    quota_retry_after_s: int = 30
    # ---- M4 (4.6): webhooks (SEC-045, SEC-076) and server-sent events.
    webhook_timeout_s: float = 10.0
    webhook_max_attempts: int = 8
    webhook_backoff_base_s: float = 30.0
    webhook_backoff_max_s: float = 3600.0
    # Old signing keys stay valid this long after a rotation (both signatures are sent).
    webhook_rotation_overlap_s: int = 24 * 3600
    sse_poll_s: float = 1.0
    sse_max_s: float = 300.0
    # SEC-017: an open stream (SSE) re-checks its credential at least this often.
    reauth_interval_s: float = 30.0
    # Stream ingest (P7.7 R1): per-stream token bucket on NEW chunks (NF_STREAM_CHUNK_RATE/_BURST).
    stream_chunk_rate: float = STREAM_CHUNK_RATE
    stream_chunk_burst: int = STREAM_CHUNK_BURST
    # ---- M4 (4.7) OWNER-GATED: the public early-access endpoint. OFF by default: the route is
    # not mounted at all until the owner approves go-live (BUILD-GUIDE 4.7).
    early_access_enabled: bool = False
    early_access_origins: tuple[str, ...] = ()
    early_access_ip_per_hour: int = 5
    early_access_email_per_day: int = 3
    early_access_purge_days: int = 30
    # 5.7: services holding storage/database/compute (NF_PLACEMENT_*); PHI tenants need BAA-listed
    placement: Placement = field(default_factory=Placement)

    def __post_init__(self) -> None:
        # Exact match: callers pass a normalised name (from_env does); "Prod" here is a bug.
        if self.environment not in ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {sorted(ENVIRONMENTS)}, not {self.environment!r}"
            )

    @staticmethod
    def from_env() -> Settings:
        rate, burst = stream_chunk_limits_from_env()
        return Settings(
            stream_chunk_rate=rate,
            stream_chunk_burst=burst,
            database_url=os.environ["NF_DATABASE_URL"],
            oidc=OidcSettings(
                issuer=os.environ["NF_OIDC_ISSUER"],
                audience=os.environ["NF_OIDC_AUDIENCE"],
                jwks_uri=os.environ.get("NF_OIDC_JWKS_URI"),
            ),
            secrets=pepper_from_env(),
            environment=environment_from_env(),
            early_access_enabled=os.environ.get("NF_EARLY_ACCESS_ENABLED", "") == "true",
            early_access_origins=tuple(
                o.strip()
                for o in os.environ.get("NF_EARLY_ACCESS_ORIGINS", "").split(",")
                if o.strip()
            ),
            placement=Placement(
                storage=os.environ.get("NF_PLACEMENT_STORAGE", Placement.storage),
                database=os.environ.get("NF_PLACEMENT_DATABASE", Placement.database),
                compute=os.environ.get("NF_PLACEMENT_COMPUTE", Placement.compute),
            ),
        )
