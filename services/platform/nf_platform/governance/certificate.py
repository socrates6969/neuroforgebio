"""Signed deletion certificates (BUILD-GUIDE 5.5; BLUEPRINT §8.4; SEC-046).

The certificate is canonical JSON (NF-CJSON). ``signature`` = Ed25519 over the canonical JSON of
every other member, so anyone with the published public key can verify it offline
(:func:`verify`), without access to the platform.

Key handling (KMS stub, like the provenance signing key; see docs/security/crypto-inventory.md):
``NF_CERT_SIGNING_KEY`` = base64 of a 32-byte Ed25519 seed (``NF_CERT_SIGNING_KEY_ID`` its id).
Outside ``prod`` a missing key gives an ephemeral per-process key (dev/tests only). A KMS-held
asymmetric key is an infra step.

SEC-046: the certificate names the subject only by the tenant's pseudonym (the subject label);
object keys (which embed platform subject ids) are summarised as counts per bucket.

A PDF rendering is not produced here (optional in 5.5; it would need a PDF library); the JSON is
the signed artifact.
"""

from __future__ import annotations

import base64
import os
import threading
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from nf_platform.audit import _canonical as cj
from nf_platform.config import environment_from_env
from nf_platform.provenance.signing import Ed25519Signer, SigningKeyError

SCHEMA = "nf.deletion-certificate/v1"
ALG = "Ed25519"

_lock = threading.Lock()
_signer: Ed25519Signer | None = None


def configure(signer: Ed25519Signer | None) -> None:
    global _signer
    with _lock:
        _signer = signer


def signer() -> Ed25519Signer:
    global _signer
    with _lock:
        if _signer is None:
            seed = os.environ.get("NF_CERT_SIGNING_KEY")
            if seed:
                _signer = Ed25519Signer.from_seed(
                    base64.b64decode(seed), os.environ.get("NF_CERT_SIGNING_KEY_ID")
                )
            elif environment_from_env() == "prod":
                raise SigningKeyError("NF_CERT_SIGNING_KEY is not set")
            else:
                _signer = Ed25519Signer.generate("dev-ephemeral-cert")
        return _signer


def public_key() -> dict[str, str]:
    s = signer()
    raw = s.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {"alg": ALG, "key_id": s.key_id, "public_key": base64.b64encode(raw).decode()}


def _payload(doc: dict[str, Any]) -> bytes:
    return cj.canonicalize({k: v for k, v in doc.items() if k != "signature"})


def sign(doc: dict[str, Any]) -> dict[str, Any]:
    s = signer()
    sig = s.sign(_payload(doc))
    return {
        **doc,
        "signature": {"alg": ALG, "key_id": s.key_id, "value": base64.b64encode(sig).decode()},
    }


def verify(doc: dict[str, Any], public_key_b64: str) -> bool:
    """Offline verification with the published raw public key (base64)."""
    try:
        sig = doc["signature"]
        if sig.get("alg") != ALG or doc.get("schema") != SCHEMA:
            return False
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        pub.verify(base64.b64decode(sig["value"]), _payload(doc))
        return True
    except (InvalidSignature, KeyError, TypeError, ValueError, cj.CanonicalError):
        return False
