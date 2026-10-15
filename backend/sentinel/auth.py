"""Clerk session-token verification (RS256 via JWKS). Fail closed: no issuer configured => the API answers 503, never 'open'.

A Clerk session JWT carries `sub` (user id), `iss` (the Clerk frontend API URL), `exp`/`nbf`, and `azp` (the browser origin that
requested it). We verify the signature against Clerk's published keys; no Clerk secret key is needed or stored.
"""
from __future__ import annotations

import jwt
from jwt import PyJWKClient

from sentinel.config import Settings


class TokenError(Exception):
    pass


class Verifier:
    def __init__(self, settings: Settings, jwks_client=None):
        self.issuer = settings.clerk_issuer
        self.azp = {o.strip().rstrip("/") for o in settings.clerk_authorized_parties.split(",") if o.strip()}
        url = settings.clerk_jwks_url or (f"{self.issuer}/.well-known/jwks.json" if self.issuer else "")
        self._jwks = jwks_client or (PyJWKClient(url, cache_keys=True, lifespan=3600) if url else None)

    def verify(self, token: str) -> str:
        if not self.issuer or self._jwks is None:
            raise TokenError("auth not configured")
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.issuer,
                                options={"require": ["exp", "iss", "sub"], "verify_aud": False}, leeway=10)
        except jwt.PyJWTError as e:
            raise TokenError(f"invalid token: {type(e).__name__}") from e
        except Exception as e:  # JWKS fetch problems etc.: never let a verifier bug turn into access
            raise TokenError(f"token could not be verified: {type(e).__name__}") from e
        azp = str(claims.get("azp") or "").rstrip("/")
        if self.azp and azp and azp not in self.azp:
            raise TokenError("token was issued for a different origin")
        sub = str(claims.get("sub") or "")
        if not sub or len(sub) > 64:
            raise TokenError("token has no usable subject")
        return sub