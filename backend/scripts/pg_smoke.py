"""Postgres smoke test: runs the real migration, then exercises the API end to end against the database in DATABASE_URL.
   DATABASE_URL=postgresql://... python -m scripts.pg_smoke        (CI runs this against a Postgres service container)"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from sentinel.api.app import create_app
from sentinel.auth import TokenError
from sentinel.config import Settings
from sentinel.db import make_engine, make_session_factory
from sentinel.llm import FakeLLM
from sentinel.security import sign

URL = os.environ["DATABASE_URL"]
SECRET, KEY = "s" * 48, secrets.token_hex(32)


def verify(tok: str) -> str:
    if tok.startswith("user:"):
        return tok[5:]
    raise TokenError("bad")


async def offline(url):
    raise RuntimeError("offline")


def signed(c, path, body):
    raw = json.dumps(body).encode()
    ts, nonce = int(time.time()), secrets.token_hex(8)
    return c.post(path, content=raw, headers={"X-Bridge-Timestamp": str(ts), "X-Bridge-Nonce": nonce, "X-Bridge-Signature": sign(SECRET, "POST", path, ts, nonce, raw), "Content-Type": "application/json"})


def check(cond: bool, what: str) -> None:
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        sys.exit(1)


def main() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")
    check(True, "alembic upgrade head")

    factory = make_session_factory(make_engine(URL))
    app = create_app(Settings(bridge_shared_secret=SECRET, session_enc_key=KEY, public_base_url="http://t"), factory,
                     FakeLLM(["Kindly wait sir, my app shows an error. Please share the UPI again."]), fetch=offline, ip_fetch=offline, verify_token=verify, sim_pace_s=0)
    c = TestClient(app)
    A = {"Authorization": f"Bearer user:pg{secrets.token_hex(4)}"}
    B = {"Authorization": f"Bearer user:pg{secrets.token_hex(4)}"}

    check(c.get("/api/health").json()["ok"], "health")
    check(c.post("/api/consent", headers=A, json={"accept": True}).status_code == 200, "consent")
    r = c.put("/api/profile", headers=A, json={"data": {"alias": "Anita", "age": 58, "occupation": "teacher", "languages": ["English"], "full_name": "Anita Rao"}, "share": {"city": False}})
    check(r.json() == {"complete": True}, "profile JSON columns write")
    check(c.get("/api/profile", headers=A).json()["data"]["languages"] == ["English"], "profile JSON columns read")
    check(c.get("/api/profile", headers=B).json()["data"] == {}, "profile isolation")

    sid = c.post("/api/sessions", headers=A, json={}).json()["session_id"]
    m = c.post(f"/api/sessions/{sid}/messages", headers=A, json={"text": "Dear user your SBI KYC expired. Pay Rs 500 to refund.dept@ybl or account blocked. Call 9876543210"}).json()
    check(m["action"] == "reply", "pipeline reply (ledger, grounding, gate, tool traces)")
    d = c.get(f"/api/sessions/{sid}", headers=A).json()
    check(d["ledger"]["ok"] and {i["kind"] for i in d["iocs"]} >= {"upi", "phone"}, "ledger verifies, IOCs stored")
    check(c.get(f"/api/sessions/{sid}", headers=B).status_code == 404, "session isolation")

    check(c.post("/api/targets", headers=A, json={"number": "98765 43210"}).json()["number"] == "919876543210", "composite-key target insert")
    check(c.get("/api/targets", headers=B).json() == [], "target isolation")
    check(c.delete("/api/targets/919876543210", headers=A).json() == {"ok": True}, "target delete")

    uid = A["Authorization"].split("user:")[1]
    check(signed(c, "/bridge/auth/set", {"user_id": uid, "items": {"creds": "secret-creds", "pre-key-1": "k"}}).status_code == 200, "encrypted auth blob upsert")
    check(signed(c, "/bridge/auth/get", {"user_id": uid, "names": ["creds"]}).json()["items"]["creds"] == "secret-creds", "encrypted auth blob read")
    check(uid in signed(c, "/bridge/auth/users", {}).json()["users"], "auth users listing")
    check(signed(c, "/bridge/auth/wipe", {"user_id": uid}).status_code == 200, "auth wipe")

    check(c.post("/api/whatsapp/link", headers=A).status_code == 200, "link command queued")
    sync = signed(c, "/bridge/sync", {"accounts": []}).json()
    check(any(x["type"] == "link" and x["user_id"] == uid for x in sync["commands"]), "sync returns the command")
    print("POSTGRES SMOKE PASSED")


if __name__ == "__main__":
    main()