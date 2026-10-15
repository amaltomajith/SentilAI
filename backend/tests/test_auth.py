"""The real Clerk verifier, exercised with locally generated RSA keys (no network)."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from sentinel.auth import TokenError, Verifier
from sentinel.config import Settings

ISS = "https://example.clerk.accounts.dev"
ORIGIN = "http://localhost:5173"


def keypair():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return k, k.public_key()


class FakeJwks:
    def __init__(self, public):
        self.public = public

    def get_signing_key_from_jwt(self, _token):
        return type("K", (), {"key": self.public})()


PRIV, PUB = keypair()
OTHER_PRIV, _ = keypair()


def mint(priv=PRIV, alg="RS256", **over):
    now = int(time.time())
    claims = {"sub": "user_abc", "iss": ISS, "iat": now, "nbf": now - 5, "exp": now + 300, "azp": ORIGIN}
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, priv, algorithm=alg)


@pytest.fixture()
def v():
    return Verifier(Settings(clerk_issuer=ISS, clerk_authorized_parties=ORIGIN), jwks_client=FakeJwks(PUB))


def test_valid_token_yields_the_subject(v):
    assert v.verify(mint()) == "user_abc"


@pytest.mark.parametrize("tok", [
    mint(exp=int(time.time()) - 3600),                       # expired
    mint(iss="https://evil.example.com"),                     # foreign issuer
    mint(priv=OTHER_PRIV),                                     # signed by someone else's key
    mint(azp="https://evil.example.com"),                      # issued for another origin
    mint(sub=None),                                            # no subject
    mint(sub="x" * 65),                                        # absurd subject
    "not.a.jwt",
    "",
])
def test_bad_tokens_are_rejected(v, tok):
    with pytest.raises(TokenError):
        v.verify(tok)


def test_algorithm_confusion_and_none_are_rejected(v):
    pub_pem = PUB.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    # PyJWT refuses to HMAC with a PEM public key by itself, so build the HS256 token by hand like an attacker would
    import base64, hashlib, hmac, json
    b = lambda x: base64.urlsafe_b64encode(x).rstrip(b"=")
    head = b(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b(json.dumps({"sub": "attacker", "iss": ISS, "exp": int(time.time()) + 300}).encode())
    sig = b(hmac.new(pub_pem, head + b"." + body, hashlib.sha256).digest())
    with pytest.raises(TokenError):
        v.verify((head + b"." + body + b"." + sig).decode())
    none_tok = (b(json.dumps({"alg": "none"}).encode()) + b"." + body + b".").decode()
    with pytest.raises(TokenError):
        v.verify(none_tok)


def test_unconfigured_verifier_refuses_everything():
    with pytest.raises(TokenError):
        Verifier(Settings(clerk_issuer="")).verify(mint())


def test_positive_control_a_naive_verifier_would_accept_a_foreign_issuer():
    """Proves the issuer test above can fail: decoding without issuer checking accepts the evil token."""
    tok = mint(iss="https://evil.example.com")
    assert jwt.decode(tok, PUB, algorithms=["RS256"], options={"verify_aud": False})["sub"] == "user_abc"
    with pytest.raises(TokenError):
        Verifier(Settings(clerk_issuer=ISS, clerk_authorized_parties=ORIGIN), jwks_client=FakeJwks(PUB)).verify(tok)