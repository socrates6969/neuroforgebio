"""The storage bundle a process runs with: object store + keyring (KMS + SQL key store).

`service_session_for` gives the Keyring's `SqlKeyStore` a tenant-scoped session (RLS + app filter)
for a service principal of that tenant, so key rows are isolated per tenant exactly like every
other row (SEC-021).

`storage_from_env` builds the bundle from the environment. Every entrypoint passes it through
`require_durable_storage` (NR-H1): in prod anything but S3 + AWS KMS is refused at startup, since
the dev `LocalKms` loses every KEK (and with it all decryptability) when the process restarts.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from nf_platform.config import ENVIRONMENTS
from nf_platform.db.context import Principal, tenant_session
from nf_platform.storage.keyring import Keyring, default_kek_id
from nf_platform.storage.kms import AwsKms, Kms, LocalKms
from nf_platform.storage.objects import BUCKETS, LocalObjectStore, ObjectStore, S3ObjectStore
from nf_platform.storage.sql_keystore import SqlKeyStore

SERVICE_ID = "svc:platform"
PROD_ENVIRONMENT = "prod"


class StorageConfigError(RuntimeError):
    """Startup refusal: the configured storage cannot hold durable (prod) data."""


def service_principal(tenant_id: str, name: str = SERVICE_ID) -> Principal:
    """A principal for internal work in one tenant (keyring, workers). It holds no role, so it can
    never pass ``authorize()``: it only scopes database sessions."""
    return Principal(
        id=name,
        tenant_id=str(tenant_id),
        roles=frozenset(),
        scopes=frozenset(),
        kind="service",
        mfa_phr=False,
        auth_method="service",
    )


def service_session_for(
    engine: Engine | None = None,
) -> Callable[[str], AbstractContextManager[Session]]:
    @contextmanager
    def session_for(tenant_id: str) -> Iterator[Session]:
        with tenant_session(service_principal(tenant_id), engine=engine) as s:
            yield s

    return session_for


@dataclass(frozen=True)
class Storage:
    objects: ObjectStore
    keyring: Keyring


def local_storage(
    root: str | Path, *, engine: Engine | None = None, kms: Kms | None = None
) -> Storage:
    """Filesystem object store + in-memory LocalKms + key rows in Postgres (dev and tests).

    LocalKms keeps KEKs in memory only: a restarted dev process cannot decrypt earlier data.
    """
    ks = SqlKeyStore(service_session_for(engine))
    return Storage(objects=LocalObjectStore(root), keyring=Keyring(kms or LocalKms(), ks))


def _boto3_client(service: str, **kw: Any) -> Any:
    import boto3  # noqa: PLC0415

    return boto3.client(service, **kw)


def storage_from_env(
    *,
    engine: Engine | None = None,
    client_factory: Callable[..., Any] = _boto3_client,
) -> Storage | None:
    """The storage bundle the environment configures, or None when no object store is configured.

    Object store: ``NF_S3_BUCKET_PREFIX`` selects S3 with physical buckets ``<prefix>-<logical>``
    (the ``bucket_prefix`` of infra/envs; ``NF_S3_ENDPOINT_URL`` optionally points at MinIO).
    Otherwise ``NF_OBJECT_ROOT`` selects the filesystem store (dev only).

    KMS: ``NF_KMS_BACKEND=aws`` selects AWS KMS, a tenant's KEK being the key named
    ``<NF_KMS_KEY_ALIAS_PREFIX>nf/tenant/<tenant_id>`` (prefix default ``alias/``). ``local`` (the
    default) is the in-memory LocalKms (dev only). AWS region and credentials come from the
    standard AWS environment/role chain; ``client_factory`` lets tests pass fakes.
    """
    backend = os.environ.get("NF_KMS_BACKEND", "local")
    if backend not in ("aws", "local"):
        raise StorageConfigError(f"NF_KMS_BACKEND must be 'aws' or 'local', not {backend!r}")
    prefix = os.environ.get("NF_S3_BUCKET_PREFIX")
    root = os.environ.get("NF_OBJECT_ROOT")
    objects: ObjectStore
    if prefix:
        endpoint = os.environ.get("NF_S3_ENDPOINT_URL")
        s3 = client_factory("s3", endpoint_url=endpoint) if endpoint else client_factory("s3")
        objects = S3ObjectStore(s3, {b: f"{prefix}-{b}" for b in BUCKETS})
    elif root:
        objects = LocalObjectStore(root)
    else:
        return None
    ks = SqlKeyStore(service_session_for(engine))
    if backend == "local":
        return Storage(objects=objects, keyring=Keyring(LocalKms(), ks))
    alias = os.environ.get("NF_KMS_KEY_ALIAS_PREFIX", "alias/")
    keyring = Keyring(
        AwsKms(client_factory("kms")), ks, kek_id_for=lambda t: f"{alias}{default_kek_id(t)}"
    )
    return Storage(objects=objects, keyring=keyring)


def required_storage_from_env(
    environment: str,
    *,
    engine: Engine | None = None,
    client_factory: Callable[..., Any] = _boto3_client,
) -> Storage:
    """``storage_from_env`` for processes that cannot run without storage (stream server,
    workers), checked by ``require_durable_storage``."""
    storage = storage_from_env(engine=engine, client_factory=client_factory)
    require_durable_storage(environment, storage)
    if storage is None:
        raise StorageConfigError(
            "no object store: set NF_S3_BUCKET_PREFIX (or NF_OBJECT_ROOT in dev)"
        )
    return storage


def require_durable_storage(environment: str, storage: Storage | None) -> None:
    """Fail closed at startup (NR-H1): in prod the storage must be S3 + AWS KMS.

    An allow-list, not a deny-list: a new store or KMS adapter is refused in prod until it is
    added here on purpose. Outside prod every configuration (including none) is accepted.
    ``environment`` must be an exact name from ``config.ENVIRONMENTS`` (``Settings.environment`` or
    ``environment_from_env()``): anything else ("Prod", "prod ", "production") is refused rather
    than treated as non-prod.
    """
    if environment not in ENVIRONMENTS:
        raise StorageConfigError(
            f"unknown environment {environment!r}: expected one of {sorted(ENVIRONMENTS)}"
        )
    if environment != PROD_ENVIRONMENT:
        return
    if storage is None:
        raise StorageConfigError(
            "prod needs an object store and KMS: set NF_S3_BUCKET_PREFIX and NF_KMS_BACKEND=aws"
        )
    if not isinstance(storage.keyring.kms, AwsKms):
        raise StorageConfigError(
            f"prod refuses the {type(storage.keyring.kms).__name__} key manager (KEKs would not "
            "survive a restart): set NF_KMS_BACKEND=aws"
        )
    if not isinstance(storage.objects, S3ObjectStore):
        raise StorageConfigError(
            f"prod refuses the {type(storage.objects).__name__} object store: set "
            "NF_S3_BUCKET_PREFIX (not NF_OBJECT_ROOT)"
        )
