"""OIDC access-token verification (SEC-010, SEC-011).

The console does the Authorization Code + PKCE flow with the IdP (D4); the API only verifies the
resulting JWT: signature against the IdP's JWKS (asymmetric algorithms only), ``iss``, ``aud``,
``exp``, ``iat``, ``sub``, the tenant and role claims, and the ``amr`` claim for phishing-resistant
MFA. No passwords, ever.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from typing import Any

import jwt

from nf_platform.auth.authorize import ROLES, Unauthorized
from nf_platform.config import OidcSettings
from nf_platform.db.context import Principal

# amr values accepted as phishing-resistant (SEC-011): RFC 8176 "hwk" (hardware-bound key) and the
# "phr"/"phrh" values IdPs use for passkeys/WebAuthn.
PHISHING_RESISTANT_AMR = frozenset({"hwk", "phr", "phrh"})

JwksProvider = Callable[[], Mapping[str, Any]]


class OidcVerifier:
    def __init__(self, settings: OidcSettings, jwks: JwksProvider | None = None) -> None:
        self.settings = settings
        if jwks is not None:
            self._key_for = self._static_keys(jwks)
        elif settings.jwks_uri:
            client = jwt.PyJWKClient(settings.jwks_uri, cache_keys=True, lifespan=300, timeout=5)
            self._key_for = lambda token: client.get_signing_key_from_jwt(token).key
        else:
            raise ValueError("OIDC needs a jwks_uri or a JWKS provider")

    def _static_keys(self, jwks: JwksProvider) -> Callable[[str], Any]:
        def key_for(token: str) -> Any:
            kid = jwt.get_unverified_header(token).get("kid")
            for k in jwt.PyJWKSet.from_dict(dict(jwks())).keys:
                if k.key_id == kid:
                    return k.key
            raise Unauthorized("unknown signing key")

        return key_for

    def verify(self, token: str) -> Principal:
        s = self.settings
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in s.algorithms:
                raise Unauthorized("token algorithm not allowed")
            key = self._key_for(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=list(s.algorithms),
                audience=s.audience,
                issuer=s.issuer,
                leeway=s.leeway_s,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except Unauthorized:
            raise
        except (jwt.PyJWTError, ValueError, KeyError) as e:
            # Never echo the token or library internals.
            raise Unauthorized(f"invalid token ({type(e).__name__})") from None
        tenant = claims.get(s.tenant_claim)
        try:
            tenant = str(uuid.UUID(str(tenant)))
        except ValueError:
            raise Unauthorized("token has no valid tenant") from None
        raw_roles = claims.get(s.roles_claim, [])
        if not isinstance(raw_roles, list):
            raise Unauthorized("roles claim must be a list")
        amr = claims.get("amr", [])
        amr_set = (
            frozenset(a for a in amr if isinstance(a, str)) if isinstance(amr, list) else set()
        )
        return Principal(
            id=str(claims["sub"]),
            tenant_id=tenant,
            roles=frozenset(r for r in raw_roles if r in ROLES),
            scopes=frozenset(),
            kind="user",
            mfa_phr=bool(amr_set & PHISHING_RESISTANT_AMR),
            auth_method="oidc",
        )
