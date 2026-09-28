"""Signing keys for provenance batches (SEC-043; see docs/security/crypto-inventory.md).

Every batch ID (``provb:sha256:...``) is signed with Ed25519. The signature covers the ASCII bytes
of the batch ID, which already commits to the tenant, sequence number, previous batch and every
record.

Key handling (KMS stub, M2-CONTRACTS §2):

- ``NF_PROV_SIGNING_KEY``: base64 of a 32-byte Ed25519 seed; ``NF_PROV_SIGNING_KEY_ID``: its id.
  In a deployment this becomes a KMS-held asymmetric key (the private key never leaves the KMS;
  ``sign`` becomes a KMS Sign call). That wiring is an infra step; nothing here claims it exists.
- ``NF_PROV_VERIFY_KEYS``: optional ``id=<base64 raw public key>,...`` for retired keys, so old
  batches still verify after a rotation.
- Without the variables, outside ``prod``, an ephemeral per-process key is generated (dev/tests
  only). Batches signed with it verify only in the same process. In ``prod`` a missing key is an
  error.

Verification uses only the configured public keys, never a key stored next to the data: whoever
can rewrite the tables cannot also re-sign the chain with a key of their choosing.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import threading
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from nf_platform.config import environment_from_env

log = logging.getLogger(__name__)
ALG = "Ed25519"


class SigningKeyError(RuntimeError):
    """No usable signing key (misconfiguration)."""


def public_key_id(pub: Ed25519PublicKey) -> str:
    """Stable id for a public key when none is configured: ``ed25519:<16 hex of its sha256>``."""
    raw = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return "ed25519:" + hashlib.sha256(raw).hexdigest()[:16]


@dataclass(frozen=True)
class Ed25519Signer:
    key_id: str
    _key: Ed25519PrivateKey = field(repr=False)

    @staticmethod
    def generate(key_id: str | None = None) -> Ed25519Signer:
        k = Ed25519PrivateKey.generate()
        return Ed25519Signer(key_id or public_key_id(k.public_key()), k)

    @staticmethod
    def from_seed(seed: bytes, key_id: str | None = None) -> Ed25519Signer:
        if len(seed) != 32:
            raise SigningKeyError("an Ed25519 seed is 32 bytes")
        k = Ed25519PrivateKey.from_private_bytes(seed)
        return Ed25519Signer(key_id or public_key_id(k.public_key()), k)

    def public_key(self) -> Ed25519PublicKey:
        return self._key.public_key()

    def sign(self, data: bytes) -> bytes:
        return self._key.sign(data)


@dataclass
class Keyring:
    """The active signer plus every trusted public key (by id)."""

    signer: Ed25519Signer
    trusted: dict[str, Ed25519PublicKey] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.trusted.setdefault(self.signer.key_id, self.signer.public_key())

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        pub = self.trusted.get(key_id)
        if pub is None:
            return False
        try:
            pub.verify(signature, data)
        except InvalidSignature:
            return False
        return True


_lock = threading.Lock()
_keyring: Keyring | None = None


def configure(keyring: Keyring | None) -> None:
    """Set (or with ``None`` reset) the process-wide keyring."""
    global _keyring
    with _lock:
        _keyring = keyring


def _parse_verify_keys(spec: str) -> dict[str, Ed25519PublicKey]:
    out: dict[str, Ed25519PublicKey] = {}
    for item in filter(None, (x.strip() for x in spec.split(","))):
        kid, _, b64 = item.partition("=")
        out[kid] = Ed25519PublicKey.from_public_bytes(base64.b64decode(b64))
    return out


def keyring_from_env() -> Keyring:
    seed = os.environ.get("NF_PROV_SIGNING_KEY")
    env = environment_from_env()
    if seed:
        signer = Ed25519Signer.from_seed(
            base64.b64decode(seed), os.environ.get("NF_PROV_SIGNING_KEY_ID")
        )
    elif env == "prod":
        raise SigningKeyError("NF_PROV_SIGNING_KEY is not set")
    else:
        signer = Ed25519Signer.generate("dev-ephemeral")
        log.warning("provenance: using an ephemeral dev signing key", extra={"key_id": "dev"})
    return Keyring(signer, _parse_verify_keys(os.environ.get("NF_PROV_VERIFY_KEYS", "")))


def keyring() -> Keyring:
    global _keyring
    with _lock:
        if _keyring is None:
            _keyring = keyring_from_env()
        return _keyring
