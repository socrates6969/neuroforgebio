"""2.2 / SEC-010, SEC-011: OIDC token verification against a mock IdP (static JWKS and a real HTTP
JWKS URL)."""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from conftest import AUDIENCE, ISSUER, MockIdP
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from nf_platform.auth.authorize import Unauthorized
from nf_platform.auth.oidc import OidcVerifier
from nf_platform.config import OidcSettings

TENANT = str(uuid.uuid4())


@pytest.fixture
def verifier(idp):
    return OidcVerifier(OidcSettings(issuer=ISSUER, audience=AUDIENCE), jwks=idp.jwks)


def test_valid_token(verifier, idp):
    p = verifier.verify(idp.token(sub="alice", tenant=TENANT, roles=["admin", "bogus"]))
    assert (p.id, p.tenant_id, p.kind) == ("alice", TENANT, "user")
    assert p.roles == frozenset({"admin"})  # unknown roles dropped
    assert p.mfa_phr is True


@pytest.mark.parametrize(
    "amr,phr", [(["pwd", "hwk"], True), (["phr"], True), (["pwd", "otp"], False), ([], False)]
)
def test_amr_phishing_resistance(verifier, idp, amr, phr):
    assert verifier.verify(idp.token(tenant=TENANT, amr=amr)).mfa_phr is phr


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exp_in": -120},  # expired (beyond 30 s leeway)
        {"aud": "someone-else"},
        {"iss": "https://evil.invalid"},
        {"kid": "unknown"},
        {"drop": ("exp",)},
        {"drop": ("sub",)},
        {"drop": ("nf_tenant",)},
        {"nf_tenant": "not-a-uuid"},
    ],
)
def test_rejected_tokens(verifier, idp, kwargs):
    kwargs.setdefault("tenant", TENANT)
    if "nf_tenant" in kwargs:
        kwargs["tenant"] = kwargs.pop("nf_tenant")
    with pytest.raises(Unauthorized):
        verifier.verify(idp.token(**kwargs))


def test_wrong_signing_key(verifier, idp):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(Unauthorized):
        verifier.verify(idp.token(tenant=TENANT, key=other))


def test_alg_none_and_hmac_confusion_rejected(verifier, idp):
    none_tok = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "x",
            "exp": 9999999999,
            "iat": 1,
            "nf_tenant": TENANT,
        },
        key=None,
        algorithm="none",
        headers={"kid": "k1"},
    )
    with pytest.raises(Unauthorized):
        verifier.verify(none_tok)
    # HS256 signed with the public key bytes (classic algorithm-confusion attack)
    pub = idp.key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    forged = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "x",
            "exp": 9999999999,
            "iat": 1,
            "nf_tenant": TENANT,
        },
        key=pub.decode()[:32]
        + "x" * 32,  # pyjwt refuses PEM as HMAC key; any HS token must fail anyway
        algorithm="HS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(Unauthorized):
        verifier.verify(forged)


def test_tampered_payload(verifier, idp):
    tok = idp.token(tenant=TENANT, roles=["viewer"])
    h, p, s = tok.split(".")
    claims = json.loads(jwt.utils.base64url_decode(p))
    claims["nf_roles"] = ["owner"]
    p2 = jwt.utils.base64url_encode(json.dumps(claims).encode()).decode()
    with pytest.raises(Unauthorized):
        verifier.verify(f"{h}.{p2}.{s}")


class _IdpHandler(BaseHTTPRequestHandler):
    idp: MockIdP

    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path == "/jwks":
            body = json.dumps(self.idp.jwks()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # keep test output quiet
        pass


def test_mock_idp_over_http_jwks(idp):
    """The production path: keys fetched from the IdP's JWKS URL (PyJWKClient)."""
    handler = type("H", (_IdpHandler,), {"idp": idp})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        uri = f"http://127.0.0.1:{srv.server_port}/jwks"
        v = OidcVerifier(OidcSettings(issuer=ISSUER, audience=AUDIENCE, jwks_uri=uri))
        assert v.verify(idp.token(sub="bob", tenant=TENANT)).id == "bob"
        with pytest.raises(Unauthorized):
            v.verify(idp.token(sub="bob", tenant=TENANT, exp_in=-3600))
    finally:
        srv.shutdown()
        srv.server_close()
