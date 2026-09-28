"""NR-H1: prod entrypoints refuse dev storage (LocalKms / filesystem objects) at startup.

No database and no cloud: the app is built without connecting (as in test_hw_guard_surface), and
S3/KMS clients are placeholder objects handed out by a fake ``client_factory`` (the adapters only
store the client until a call is made).
"""

from __future__ import annotations

import base64
import sys

import pytest
from nf_platform.config import (
    OidcSettings,
    Settings,
    StaticSecretProvider,
    environment_from_env,
)
from nf_platform.storage import InMemoryKeyStore, Keyring, LocalKms
from nf_platform.storage.kms import AwsKms
from nf_platform.storage.objects import LocalObjectStore, S3ObjectStore
from nf_platform.storage.runtime import (
    Storage,
    StorageConfigError,
    require_durable_storage,
    required_storage_from_env,
    storage_from_env,
)

STORAGE_ENV = (
    "NF_OBJECT_ROOT",
    "NF_S3_BUCKET_PREFIX",
    "NF_S3_ENDPOINT_URL",
    "NF_KMS_BACKEND",
    "NF_KMS_KEY_ALIAS_PREFIX",
    "NF_ENVIRONMENT",
)


class FakeClients:
    """Records which boto3 clients were requested; never talks to anything."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, service: str, **kw):
        self.calls.append((service, kw))
        return object()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in STORAGE_ENV:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def build_app(monkeypatch):
    """``create_app`` without a database; the process-wide engine and audit sink it sets are
    restored afterwards."""
    from nf_platform.app import create_app
    from nf_platform.audit import log as audit
    from nf_platform.db import context

    monkeypatch.setattr(context, "_engine", context._engine)
    monkeypatch.setattr(audit, "_sink", audit._sink)

    class NullSink:
        def write(self, event) -> None:  # pragma: no cover - never called here
            pass

    def build(environment: str, **kw):
        settings = Settings(
            database_url="postgresql+psycopg://nobody@127.0.0.1:9/none",
            oidc=OidcSettings(issuer="https://idp.test.invalid/realms/nf", audience="nf-api"),
            secrets=StaticSecretProvider(version="p1", pepper=b"\0" * 32),
            environment=environment,
        )
        return create_app(settings, jwks=lambda: {"keys": []}, audit_sink=NullSink(), **kw)

    return build


def _storage(objects, kms) -> Storage:
    return Storage(objects=objects, keyring=Keyring(kms, InMemoryKeyStore()))


# ---------------------------------------------------------------- create_app
def test_prod_app_refuses_object_root_with_local_kms(build_app, monkeypatch, tmp_path):
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    with pytest.raises(StorageConfigError, match="LocalKms"):
        build_app("prod")


def test_prod_app_refuses_object_root_even_with_aws_kms(build_app, monkeypatch, tmp_path):
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    local_objects = _storage(LocalObjectStore(tmp_path), AwsKms(object()))
    with pytest.raises(StorageConfigError, match="LocalObjectStore"):
        build_app("prod", storage=local_objects)


def test_prod_app_refuses_injected_local_kms(build_app):
    s3_local_kms = _storage(S3ObjectStore(object()), LocalKms())
    with pytest.raises(StorageConfigError, match="LocalKms"):
        build_app("prod", storage=s3_local_kms)


def test_prod_app_refuses_missing_storage(build_app):
    with pytest.raises(StorageConfigError, match="NF_S3_BUCKET_PREFIX"):
        build_app("prod")


def test_prod_app_accepts_s3_and_aws_kms(build_app):
    good = _storage(S3ObjectStore(object()), AwsKms(object()))
    assert build_app("prod", storage=good).state.storage is good


def test_dev_app_unchanged_with_object_root(build_app, monkeypatch, tmp_path):
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    storage = build_app("dev").state.storage
    assert isinstance(storage.objects, LocalObjectStore)
    assert isinstance(storage.keyring.kms, LocalKms)


def test_dev_and_test_app_without_storage(build_app):
    assert build_app("dev").state.storage is None
    assert build_app("test").state.storage is None


# ---------------------------------------------------------------- storage_from_env
def test_storage_from_env_builds_s3_and_aws_kms(monkeypatch):
    monkeypatch.setenv("NF_S3_BUCKET_PREFIX", "nf-prod-eu")
    monkeypatch.setenv("NF_S3_ENDPOINT_URL", "http://minio.test.invalid:9000")
    monkeypatch.setenv("NF_KMS_BACKEND", "aws")
    clients = FakeClients()
    storage = storage_from_env(client_factory=clients)
    assert isinstance(storage.objects, S3ObjectStore)
    assert isinstance(storage.keyring.kms, AwsKms)
    assert storage.objects._names["raw"] == "nf-prod-eu-raw"
    assert storage.objects._names["audit"] == "nf-prod-eu-audit"
    assert storage.keyring._kek_id_for("t1") == "alias/nf/tenant/t1"
    assert sorted(s for s, _ in clients.calls) == ["kms", "s3"]
    assert ("s3", {"endpoint_url": "http://minio.test.invalid:9000"}) in clients.calls
    require_durable_storage("prod", storage)  # accepted


def test_storage_from_env_alias_prefix(monkeypatch):
    monkeypatch.setenv("NF_S3_BUCKET_PREFIX", "nf-prod-eu")
    monkeypatch.setenv("NF_KMS_BACKEND", "aws")
    monkeypatch.setenv("NF_KMS_KEY_ALIAS_PREFIX", "alias/eu-")
    storage = storage_from_env(client_factory=FakeClients())
    assert storage.keyring._kek_id_for("t1") == "alias/eu-nf/tenant/t1"


def test_storage_from_env_s3_defaults_to_local_kms_and_prod_refuses(monkeypatch):
    monkeypatch.setenv("NF_S3_BUCKET_PREFIX", "nf-dev")
    storage = storage_from_env(client_factory=FakeClients())
    assert isinstance(storage.keyring.kms, LocalKms)
    require_durable_storage("dev", storage)
    with pytest.raises(StorageConfigError, match="LocalKms"):
        require_durable_storage("prod", storage)


def test_storage_from_env_nothing_configured():
    clients = FakeClients()
    assert storage_from_env(client_factory=clients) is None
    assert clients.calls == []


def test_storage_from_env_rejects_unknown_kms_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("NF_KMS_BACKEND", "vault")
    with pytest.raises(StorageConfigError, match="NF_KMS_BACKEND"):
        storage_from_env(client_factory=FakeClients())


def test_required_storage_from_env(monkeypatch, tmp_path):
    with pytest.raises(StorageConfigError, match="no object store"):
        required_storage_from_env("dev", client_factory=FakeClients())
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    assert isinstance(required_storage_from_env("dev").objects, LocalObjectStore)
    with pytest.raises(StorageConfigError):
        required_storage_from_env("prod")


# ---------------------------------------------------------------- process entrypoints
def test_stream_server_main_refuses_local_storage_in_prod(monkeypatch, tmp_path):
    pytest.importorskip("grpc")
    from nf_platform.ingest.stream import server

    served: list[object] = []
    monkeypatch.setattr(server, "configure_engine", lambda url: None)
    monkeypatch.setattr(server.audit, "configure", lambda sink: None)
    monkeypatch.setattr(server.audit, "PostgresAuditSink", lambda eng: None)
    monkeypatch.setattr(server, "serve", lambda *a, **kw: served.append(a))
    monkeypatch.setattr(sys, "argv", ["server"])
    monkeypatch.setenv("NF_DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:9/none")
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))

    monkeypatch.setenv("NF_ENVIRONMENT", "prod")
    with pytest.raises(StorageConfigError, match="LocalKms"):
        server.main()
    assert served == []

    monkeypatch.setenv("NF_ENVIRONMENT", "dev")
    server.main()  # dev still starts with NF_OBJECT_ROOT
    assert len(served) == 1


def test_upload_worker_main_refuses_local_storage_in_prod(monkeypatch, tmp_path):
    from nf_platform.db import context
    from nf_platform.ingest.uploads import worker

    monkeypatch.setattr(context, "configure_engine", lambda url: None)
    monkeypatch.setattr(worker.audit, "configure", lambda sink: None)
    monkeypatch.setattr(worker.audit, "PostgresAuditSink", lambda eng: None)
    monkeypatch.setattr(worker, "process_pending", lambda *a, **kw: {})
    monkeypatch.setattr(sys, "argv", ["worker", "--tenant", "t1"])
    monkeypatch.setenv("NF_DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:9/none")
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("NF_ENVIRONMENT", "prod")
    with pytest.raises(StorageConfigError, match="LocalKms"):
        worker.main()


# ---------------------------------------------------------------- NF_ENVIRONMENT (review finding)
def _settings_env(monkeypatch, environment: str | None) -> None:
    monkeypatch.setenv("NF_DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:9/none")
    monkeypatch.setenv("NF_OIDC_ISSUER", "https://idp.test.invalid/realms/nf")
    monkeypatch.setenv("NF_OIDC_AUDIENCE", "nf-api")
    monkeypatch.setenv("NF_API_KEY_PEPPER", base64.b64encode(b"\0" * 32).decode())
    if environment is None:
        monkeypatch.delenv("NF_ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("NF_ENVIRONMENT", environment)


def test_unset_environment_defaults_to_dev(monkeypatch):
    _settings_env(monkeypatch, None)
    assert environment_from_env() == "dev"
    assert Settings.from_env().environment == "dev"


@pytest.mark.parametrize("raw", ["Prod", "PROD", " prod ", "prod\n"])
def test_prod_spelling_variants_fail_closed(monkeypatch, tmp_path, raw):
    """Case/whitespace variants normalise to prod, so the guard still refuses dev storage."""
    from nf_platform.app import create_app
    from nf_platform.audit import log as audit
    from nf_platform.db import context

    monkeypatch.setattr(context, "_engine", context._engine)
    monkeypatch.setattr(audit, "_sink", audit._sink)
    _settings_env(monkeypatch, raw)
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    settings = Settings.from_env()
    assert settings.environment == "prod"
    with pytest.raises(StorageConfigError, match="LocalKms"):
        create_app(settings, jwks=lambda: {"keys": []}, audit_sink=object())


@pytest.mark.parametrize("raw", ["PRODUCTION", "production", "prd", "", "prod-eu"])
def test_unknown_environment_is_a_startup_error(monkeypatch, raw):
    _settings_env(monkeypatch, raw)
    with pytest.raises(ValueError, match="NF_ENVIRONMENT"):
        Settings.from_env()
    with pytest.raises(ValueError, match="NF_ENVIRONMENT"):
        environment_from_env()


@pytest.mark.parametrize("raw", ["Prod", "prod ", "production"])
def test_unnormalised_environment_refused_everywhere(raw):
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql+psycopg://nobody@127.0.0.1:9/none",
            oidc=OidcSettings(issuer="https://idp.test.invalid/realms/nf", audience="nf-api"),
            secrets=StaticSecretProvider(version="p1", pepper=b"\0" * 32),
            environment=raw,
        )
    good = _storage(S3ObjectStore(object()), AwsKms(object()))
    with pytest.raises(StorageConfigError, match="unknown environment"):
        require_durable_storage(raw, good)


@pytest.mark.parametrize(("raw", "error"), [("Prod", StorageConfigError), ("prd", ValueError)])
def test_stream_server_main_environment_variants(monkeypatch, tmp_path, raw, error):
    pytest.importorskip("grpc")
    from nf_platform.ingest.stream import server

    served: list[object] = []
    monkeypatch.setattr(server, "configure_engine", lambda url: None)
    monkeypatch.setattr(server.audit, "configure", lambda sink: None)
    monkeypatch.setattr(server.audit, "PostgresAuditSink", lambda eng: None)
    monkeypatch.setattr(server, "serve", lambda *a, **kw: served.append(a))
    monkeypatch.setattr(sys, "argv", ["server"])
    monkeypatch.setenv("NF_DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:9/none")
    monkeypatch.setenv("NF_OBJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("NF_ENVIRONMENT", raw)
    with pytest.raises(error):
        server.main()
    assert served == []


@pytest.mark.parametrize(("raw", "error"), [("Prod", "SigningKeyError"), ("prd", "ValueError")])
def test_signing_keys_environment_variants(monkeypatch, raw, error):
    """Provenance and certificate signers: a prod variant needs the real key (no ephemeral one),
    an unknown value is refused."""
    from nf_platform.governance import certificate
    from nf_platform.provenance import signing

    for k in ("NF_PROV_SIGNING_KEY", "NF_CERT_SIGNING_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NF_ENVIRONMENT", raw)
    monkeypatch.setattr(certificate, "_signer", None)
    exc = signing.SigningKeyError if error == "SigningKeyError" else ValueError
    with pytest.raises(exc):
        signing.keyring_from_env()
    with pytest.raises(exc):
        certificate.signer()


# ---------------------------------------------------------------- real boto3 factory (moto)
def test_storage_from_env_default_boto3_factory_roundtrip(monkeypatch):
    """The real ``_boto3_client`` path, against moto's mocked AWS (no network): the S3 client gets
    the endpoint, and the tenant alias resolves to a KMS key that wraps and unwraps a DEK."""
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(k, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.setenv("NF_S3_BUCKET_PREFIX", "nf-prod-eu")
    monkeypatch.setenv("NF_S3_ENDPOINT_URL", "http://minio.test.invalid:9000")
    monkeypatch.setenv("NF_KMS_BACKEND", "aws")
    with moto.mock_aws():
        kms = boto3.client("kms", region_name="eu-west-1")
        key_id = kms.create_key(Description="tenant t1")["KeyMetadata"]["KeyId"]
        kms.create_alias(AliasName="alias/nf/tenant/t1", TargetKeyId=key_id)

        storage = storage_from_env()  # default client_factory = boto3.client
        require_durable_storage("prod", storage)
        assert storage.objects._s3.meta.endpoint_url == "http://minio.test.invalid:9000"
        assert storage.keyring.kms._kms.meta.region_name == "eu-west-1"

        kek_id_for = storage.keyring._kek_id_for
        kr = Keyring(storage.keyring.kms, InMemoryKeyStore(), kek_id_for=kek_id_for)
        blob = kr.encrypt("t1", "s1", "raw/x", 1, b"payload")
        assert kr.decrypt("t1", "s1", "raw/x", 1, blob) == b"payload"
