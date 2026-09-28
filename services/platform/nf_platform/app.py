"""FastAPI application factory for the platform modular monolith (BLUEPRINT §3.1, BUILD-GUIDE 2.1).

Run (dev): ``uvicorn nf_platform.app:app_from_env --factory`` with the NF_* variables of
``Settings.from_env``.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from sqlalchemy import Engine

from nf_platform.api import errors, versioning
from nf_platform.api.body_limit import BodySizeLimit
from nf_platform.api.deps import Authenticator, new_request_id
from nf_platform.api.events_routes import router as events_router
from nf_platform.api.evidence_routes import router as evidence_router
from nf_platform.api.governance_routes import router as governance_router
from nf_platform.api.ingest_routes import router as ingest_router
from nf_platform.api.pipelines_routes import router as pipelines_router
from nf_platform.api.provenance_routes import router as provenance_router
from nf_platform.api.registry_routes import router as registry_router
from nf_platform.api.routes import router
from nf_platform.api.runs_routes import router as runs_router
from nf_platform.api.soup_routes import router as soup_router
from nf_platform.api.sweeps_routes import router as sweeps_router
from nf_platform.api.webhooks_routes import router as webhooks_router
from nf_platform.audit import log as audit
from nf_platform.auth.oidc import JwksProvider, OidcVerifier
from nf_platform.config import Settings
from nf_platform.db.context import configure_engine
from nf_platform.governance.policy import LedgerConsentPolicy
from nf_platform.ingest.policy import ConsentPolicy
from nf_platform.ingest.uploads.backends import LocalPartBackend, PartBackend
from nf_platform.limits.ratelimit import RateLimiter
from nf_platform.site.early_access import DisabledMailer, Mailer
from nf_platform.storage.runtime import Storage, require_durable_storage, storage_from_env

# Allow-listed log fields only (SEC-147): no tokens, keys, subject labels or signal data are ever
# logged.
log = logging.getLogger("nf_platform")


def create_app(
    settings: Settings,
    *,
    engine: Engine | None = None,
    jwks: JwksProvider | None = None,
    audit_sink: audit.AuditSink | None = None,
    storage: Storage | None = None,
    upload_backend: PartBackend | None = None,
    consent_policy: ConsentPolicy | None = None,
    mailer: Mailer | None = None,
) -> FastAPI:
    """``storage`` defaults to ``storage_from_env()`` (S3 + AWS KMS, or NF_OBJECT_ROOT + LocalKms in
    dev). In prod anything but S3 + AWS KMS raises ``StorageConfigError`` here (NR-H1), before the
    app can accept data it could not decrypt after a restart. ``consent_policy`` defaults to the
    consent ledger (M5 5.4, replacing the M2 stub): a new recording is active only when its subject
    consented to collection and processing."""
    eng = configure_engine(engine or settings.database_url)
    audit.configure(audit_sink or audit.PostgresAuditSink(eng))
    app = bare_app()
    app.state.settings = settings
    app.state.authenticator = Authenticator(settings, OidcVerifier(settings.oidc, jwks))
    if storage is None:
        storage = storage_from_env(engine=eng)
    require_durable_storage(settings.environment, storage)
    app.state.storage = storage
    app.state.upload_backend = upload_backend or LocalPartBackend()
    # 4.8 (SEC-075): local token bucket per credential; the gateway holds the global limit.
    app.state.rate_limiter = RateLimiter(settings.rate_limit_rps, settings.rate_limit_burst)
    app.state.consent_policy = consent_policy or LedgerConsentPolicy(eng)

    # NR-M1: body caps enforced while the body streams in. Added before request_id so it runs
    # inside it (its 413 carries the request ID).
    app.add_middleware(BodySizeLimit)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = new_request_id()
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        # API responses are never cached by intermediaries (they carry tenant data).
        response.headers["Cache-Control"] = "no-store"
        versioning.apply_headers(request, response)
        log.info(
            "request",
            extra={"request_id": rid, "method": request.method, "status": response.status_code},
        )
        return response

    errors.install(app)
    app.state.mailer = mailer or DisabledMailer()
    include_routers(app, early_access=settings.early_access_enabled)
    return app


def bare_app() -> FastAPI:
    # No unauthenticated schema/docs endpoints: the contract is the committed openapi/v1.yaml.
    return FastAPI(
        title="nf-platform",
        version="0.1.0",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        generate_unique_id_function=versioning.operation_id,
    )


def include_routers(app: FastAPI, *, early_access: bool) -> None:
    """Every API router. Also used by ``nf_platform.api.openapi_doc`` to build the contract
    without the side effects of ``create_app`` (engine, audit sink)."""
    app.include_router(router)
    app.include_router(ingest_router)
    app.include_router(provenance_router)
    app.include_router(pipelines_router)
    app.include_router(runs_router)
    app.include_router(governance_router)
    app.include_router(sweeps_router)
    app.include_router(events_router)
    app.include_router(webhooks_router)
    # 4.7 OWNER-GATED: the public early-access routes exist only when the flag is on.
    if early_access:
        from nf_platform.api.public_routes import router as public_router

        app.include_router(public_router)
    app.include_router(evidence_router)
    app.include_router(registry_router)
    app.include_router(soup_router)


def app_from_env() -> FastAPI:
    return create_app(Settings.from_env())
