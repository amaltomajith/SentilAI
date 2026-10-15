"""At-rest encryption for WhatsApp credentials stored in the database (AES-256-GCM).

The key comes only from the environment (SESSION_ENC_KEY, 32 bytes as hex or base64). No key means the auth-store endpoints are
disabled. Each blob is bound to its (user, name) as associated data, so a row copied to another user or name fails to decrypt.
"""
from __future__ import annotations

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoError(Exception):
    pass


def load_key(raw: str) -> bytes | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for dec in (bytes.fromhex, lambda s: base64.b64decode(s, validate=True), lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))):
        try:
            k = dec(raw)
        except (ValueError, binascii.Error):
            continue
        if len(k) == 32:
            return k
    raise CryptoError("SESSION_ENC_KEY must decode to exactly 32 bytes (hex or base64)")


def seal(key: bytes, user_id: str, name: str, plaintext: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), f"{user_id}\x00{name}".encode())
    return base64.b64encode(nonce + ct).decode("ascii")


def open_(key: bytes, user_id: str, name: str, blob: str) -> str:
    raw = base64.b64decode(blob)
    try:
        return AESGCM(key).decrypt(raw[:12], raw[12:], f"{user_id}\x00{name}".encode()).decode("utf-8")
    except InvalidTag as e:
        raise CryptoError("blob failed authentication (wrong key, or moved between users or names)") from e