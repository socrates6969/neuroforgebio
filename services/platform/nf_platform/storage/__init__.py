"""Object storage with client-side envelope encryption (BUILD-GUIDE 2.3, BLUEPRINT §8.1).

Key hierarchy: KMS root -> tenant KEK (one KMS key per tenant) -> per-subject DEK (AES-256-GCM).
Every object is encrypted with its subject's DEK before it reaches the object store, so the store
(and every backup copy of it) only ever holds ciphertext. Destroying a subject's wrapped DEK
crypto-shreds all copies (SEC-034).
"""

from nf_platform.storage.keyring import (
    DecryptionError,
    EnvelopeHeader,
    InMemoryKeyStore,
    Keyring,
    KeyringError,
    KeyStore,
    SubjectKeyUnavailable,
    WrappedDek,
    parse_header,
)
from nf_platform.storage.kms import Kms, KmsError, KmsKeyUnavailable, LocalKms
from nf_platform.storage.objects import (
    BUCKETS,
    InvalidObjectKey,
    LocalObjectStore,
    ObjectNotFound,
    ObjectStore,
    ObjectStoreError,
    WormViolation,
)

__all__ = [
    "BUCKETS",
    "DecryptionError",
    "EnvelopeHeader",
    "InMemoryKeyStore",
    "InvalidObjectKey",
    "KeyStore",
    "Keyring",
    "KeyringError",
    "Kms",
    "KmsError",
    "KmsKeyUnavailable",
    "LocalKms",
    "LocalObjectStore",
    "ObjectNotFound",
    "ObjectStore",
    "ObjectStoreError",
    "SubjectKeyUnavailable",
    "WormViolation",
    "WrappedDek",
    "parse_header",
]
