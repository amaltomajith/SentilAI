import base64
import json
import secrets
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sentinel.api.app import create_app
from sentinel.auth import TokenError
from sentinel.config import Settings
from sentinel.db import make_engine, make_session_factory, normalize_url, session_scope
from sentinel.db.models import WaAuthBlob
from sentinel.llm import FakeLLM
from sentinel.security import sign
from sentinel.security.vault import CryptoError, load_key, open_, seal

SECRET = "b" * 48
KEY = secrets.token_hex(32)


def signed(c, path, body, secret=SECRET):
    raw = json.dumps(body).encode()
    ts, nonce = int(time.time()), secrets.token_hex(8)
    return c.post(path, content=raw, headers={"X-Bridge-Timestamp": str(ts), "X-Bridge-Nonce": nonce, "X-Bridge-Signature": sign(secret, "POST", path, ts, nonce, raw), "Content-Type": "application/json"})


def mk(key=KEY):
    f = make_session_factory(make_engine("sqlite://"))
    app = create_app(Settings(bridge_shared_secret=SECRET, session_enc_key=key), f, FakeLLM(), verify_token=lambda t: (_ for _ in ()).throw(TokenError("x")))
    return TestClient(app), f


# ---------------- vault ----------------
def test_seal_roundtrip_and_context_binding():
    k = load_key(KEY)
    blob = seal(k, "alice", "creds", '{"secret":"value"}')
    assert "secret" not in blob and open_(k, "alice", "creds", blob) == '{"secret":"value"}'
    for u, n in (("bob", "creds"), ("alice", "other")):                 # moved to another user or name: must fail
        with pytest.raises(CryptoError):
            open_(k, u, n, blob)
    with pytest.raises(CryptoError):
        open_(load_key(secrets.token_hex(32)), "alice", "creds", blob)  # wrong key
    assert seal(k, "a", "n", "x") != seal(k, "a", "n", "x")             # fresh nonce every time


def test_key_parsing():
    assert load_key("") is None
    assert len(load_key(KEY)) == 32 and len(load_key(base64.b64encode(bytes(32)).decode())) == 32
    with pytest.raises(CryptoError):
        load_key("tooshort")


def test_database_urls_are_normalised_for_the_driver():
    assert normalize_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("sqlite:///x.db") == "sqlite:///x.db"


# ---------------- endpoints ----------------
def test_auth_blobs_roundtrip_are_encrypted_at_rest_and_per_user():
    c, f = mk()
    assert signed(c, "/bridge/auth/set", {"user_id": "alice", "items": {"creds": '{"noiseKey":"PLAINTEXT-SECRET"}', "pre-key-1": "k1"}}).status_code == 200
    got = signed(c, "/bridge/auth/get", {"user_id": "alice", "names": ["creds", "pre-key-1", "missing"]}).json()["items"]
    assert got == {"creds": '{"noiseKey":"PLAINTEXT-SECRET"}', "pre-key-1": "k1", "missing": None}
    with session_scope(f) as db:
        rows = list(db.scalars(select(WaAuthBlob)))
        assert len(rows) == 2 and all("PLAINTEXT-SECRET" not in r.data for r in rows)    # stored encrypted
    assert signed(c, "/bridge/auth/get", {"user_id": "bob", "names": ["creds"]}).json()["items"] == {"creds": None}   # isolation
    assert signed(c, "/bridge/auth/users", {}).json() == {"users": ["alice"]}
    assert signed(c, "/bridge/auth/set", {"user_id": "alice", "items": {"pre-key-1": None}}).status_code == 200      # delete one
    assert signed(c, "/bridge/auth/get", {"user_id": "alice", "names": ["pre-key-1"]}).json()["items"] == {"pre-key-1": None}
    assert signed(c, "/bridge/auth/wipe", {"user_id": "alice"}).status_code == 200                                    # logout wipes everything
    assert signed(c, "/bridge/auth/users", {}).json() == {"users": []}


def test_row_moved_to_another_user_is_unreadable():
    c, f = mk()
    signed(c, "/bridge/auth/set", {"user_id": "alice", "items": {"creds": "alice-secret"}})
    with session_scope(f) as db:
        r = db.get(WaAuthBlob, ("alice", "creds"))
        db.add(WaAuthBlob(user_id="mallory", name="creds", data=r.data))      # attacker with DB write access copies the row
    assert signed(c, "/bridge/auth/get", {"user_id": "mallory", "names": ["creds"]}).json()["items"] == {"creds": None}


def test_auth_endpoints_need_signature_key_and_valid_ids():
    c, _ = mk()
    assert c.post("/bridge/auth/get", json={"user_id": "a", "names": []}).status_code == 401
    assert signed(c, "/bridge/auth/get", {"user_id": "a", "names": []}, secret="x" * 48).status_code == 401
    assert signed(c, "/bridge/auth/get", {"user_id": "../etc", "names": []}).status_code == 422
    assert signed(c, "/bridge/auth/get", {"user_id": "a" * 65, "names": []}).status_code == 422
    nokey, _ = mk(key="")
    assert signed(nokey, "/bridge/auth/get", {"user_id": "alice", "names": ["creds"]}).status_code == 503   # fail closed without a key


def test_replayed_nonce_is_rejected_without_a_database_write():
    c, f = mk()
    raw = json.dumps({"user_id": "alice", "names": []}).encode()
    ts = int(time.time())
    h = {"X-Bridge-Timestamp": str(ts), "X-Bridge-Nonce": "fixed-nonce-1", "X-Bridge-Signature": sign(SECRET, "POST", "/bridge/auth/get", ts, "fixed-nonce-1", raw), "Content-Type": "application/json"}
    assert c.post("/bridge/auth/get", content=raw, headers=h).status_code == 200
    assert c.post("/bridge/auth/get", content=raw, headers=h).status_code == 401
    from sentinel.db.models import BridgeSeen
    with session_scope(f) as db:
        assert not [k for k in db.scalars(select(BridgeSeen.key)) if k.startswith("n:")]