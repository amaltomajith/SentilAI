import json
import secrets
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from sentinel import ledger
from sentinel.api.app import create_app
from sentinel.auth import TokenError
from sentinel.config import Settings
from sentinel.db import make_engine, make_session_factory, session_scope
from sentinel.db.models import BridgeOutbox, LedgerEvent, Session
from sentinel.llm import FakeLLM
from sentinel.security import sign

SECRET = "b" * 48
ALICE = {"Authorization": "Bearer user:alice"}
BOB = {"Authorization": "Bearer user:bob"}
SCAM = "Dear user, your SBI KYC is expired. Pay Rs 500 to refund.dept@ybl immediately or account blocked. Visit http://sbi-update.com/kyc call 9876543210"
CHROME = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36",
          "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-IN", "Sec-Fetch-Mode": "navigate"}


async def offline(url):
    raise RuntimeError("offline")


def fake_verify(token: str) -> str:
    if token.startswith("user:"):
        return token[5:]
    raise TokenError("invalid token")


@pytest.fixture()
def env():
    settings = Settings(bridge_shared_secret=SECRET, public_base_url="http://testserver", max_linked_accounts=2)
    factory = make_session_factory(make_engine("sqlite://"))
    app = create_app(settings, factory, FakeLLM(["Kindly wait sir, my app shows error. Please share UPI again."]), fetch=offline, ip_fetch=offline,
                     sim_pace_s=0, verify_token=fake_verify)
    return TestClient(app), factory, settings


def signed(client, method, path, body: dict | None = None, *, secret=SECRET, ts=None, nonce=None):
    raw = json.dumps(body).encode() if body is not None else b""
    ts = ts if ts is not None else int(time.time())
    nonce = nonce or secrets.token_hex(8)
    sig = sign(secret, method, path, ts, nonce, raw)
    hdr = {"X-Bridge-Timestamp": str(ts), "X-Bridge-Nonce": nonce, "X-Bridge-Signature": sig, "Content-Type": "application/json"}
    return client.request(method, path, content=raw, headers=hdr)


def consent(c, h=ALICE):
    assert c.post("/api/consent", headers=h, json={"accept": True}).status_code == 200


def target(c, number="919876543210", h=ALICE):
    consent(c, h)
    return c.post("/api/targets", headers=h, json={"number": number})


def inbound(c, text=SCAM, inbound_id="1", peer="919876543210", user="alice", **kw):
    return signed(c, "POST", "/bridge/inbound", {"user_id": user, "peer": peer, "inbound_id": inbound_id, "text": text, **kw})


# ---------------- authentication ----------------
def test_api_requires_a_valid_user_token(env):
    c, _, _ = env
    assert c.get("/api/sessions").status_code == 401
    assert c.get("/api/sessions", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert c.get("/api/sessions", headers=ALICE).status_code == 200
    assert c.get("/api/health").json()["bridge_auth_configured"] is True


def test_auth_not_configured_is_refused_not_open():
    app = create_app(Settings(clerk_issuer="", bridge_shared_secret=""), make_session_factory(make_engine("sqlite://")), FakeLLM())
    c = TestClient(app)
    assert c.get("/api/sessions", headers=ALICE).status_code == 503
    assert c.get("/api/health").json()["auth_configured"] is False


# ---------------- tenant isolation (positive control: owner CAN, everyone else cannot) ----------------
def test_users_cannot_see_or_touch_each_others_data(env):
    c, f, _ = env
    sid = c.post("/api/sessions", headers=ALICE, json={}).json()["session_id"]
    assert c.post(f"/api/sessions/{sid}/messages", headers=ALICE, json={"text": SCAM}).json()["action"] == "reply"
    # control: the owner can read everything
    assert c.get(f"/api/sessions/{sid}", headers=ALICE).status_code == 200
    assert c.get(f"/api/sessions/{sid}/proof.json", headers=ALICE).status_code == 200
    assert c.get(f"/api/sessions/{sid}/report.pdf", headers=ALICE).status_code == 200
    drafts = c.post(f"/api/sessions/{sid}/takedowns/draft", headers=ALICE).json()
    assert drafts
    # bob gets 404 (not 403) on every route that names alice's resources, and sees empty collections
    for path in (f"/api/sessions/{sid}", f"/api/sessions/{sid}/proof.json", f"/api/sessions/{sid}/report.pdf"):
        assert c.get(path, headers=BOB).status_code == 404, path
    assert c.post(f"/api/sessions/{sid}/messages", headers=BOB, json={"text": "hi"}).status_code == 404
    assert c.post(f"/api/sessions/{sid}/takedowns/draft", headers=BOB).status_code == 404
    assert c.post(f"/api/takedowns/{drafts[0]['id']}/approve", headers=BOB).status_code == 404
    assert c.get("/api/sessions", headers=BOB).json() == []
    assert c.get("/api/takedowns", headers=BOB).json() == []
    assert c.get("/api/graph", headers=BOB).json()["nodes"] == []
    assert c.get("/api/targets", headers=BOB).json() == []
    with session_scope(f) as db:
        assert db.get(Session, sid).user_id == "alice"       # the stored owner never changed


def test_sessions_created_without_owner_are_never_served(env):
    c, f, _ = env
    with session_scope(f) as db:
        db.add(Session(kind="manual", user_id=""))
    assert c.get("/api/sessions", headers=ALICE).json() == []


def test_event_bus_events_carry_their_owner(env):
    c, _, _ = env
    eng = c.app.state.engine
    q = c.app.state.bus.subscribe()
    sid = eng.create_session("manual", user_id="alice")
    ev = q.get_nowait()
    assert ev["session_id"] == sid and ev["user_id"] == "alice"
    c.app.state.bus.owner.clear()                      # simulate a restart: owner is re-resolved from the database
    c.app.state.bus.publish("turn", sid, {})
    assert q.get_nowait()["user_id"] == "alice"


# ---------------- consent, targets ----------------
def test_targets_require_consent_and_are_per_user(env):
    c, _, _ = env
    assert c.post("/api/targets", headers=ALICE, json={"number": "919876543210"}).status_code == 403
    assert target(c).json()["number"] == "919876543210"
    assert c.get("/api/targets", headers=ALICE).json() == ["919876543210"]
    assert c.get("/api/targets", headers=BOB).json() == []
    assert c.delete("/api/targets/919876543210", headers=BOB).json() == {"ok": True}      # bob's delete is a no-op for alice's row
    assert c.get("/api/targets", headers=ALICE).json() == ["919876543210"]
    assert c.delete("/api/targets/919876543210", headers=ALICE).json() == {"ok": True}
    assert c.get("/api/targets", headers=ALICE).json() == []


def test_number_normalization_validation_and_cap(env):
    c, _, _ = env
    assert target(c, "98765 43210").json() == {"number": "919876543210", "assumed_country_code_91": True}
    assert c.post("/api/targets", headers=ALICE, json={"number": "+91 98765 43211"}).json()["assumed_country_code_91"] is False
    assert c.post("/api/targets", headers=ALICE, json={"number": "0091 98765 43212"}).json()["number"] == "919876543212"
    assert c.post("/api/targets", headers=ALICE, json={"number": "12345"}).status_code == 422
    assert c.post("/api/targets", headers=ALICE, json={"number": "919876543299"}).status_code == 429    # MAX_TARGETS_PER_USER=3


# ---------------- bridge auth + exactly-once ----------------
def test_bridge_rejects_unsigned_bad_stale_and_replayed(env):
    c, _, _ = env
    assert c.post("/bridge/inbound", json={"user_id": "alice", "peer": "1", "inbound_id": "x"}).status_code == 401
    assert signed(c, "POST", "/bridge/inbound", {"user_id": "alice", "peer": "919876543210", "inbound_id": "1", "text": "hi"}, secret="w" * 48).status_code == 401
    assert signed(c, "POST", "/bridge/inbound", {"user_id": "alice", "peer": "919876543210", "inbound_id": "1", "text": "hi"}, ts=int(time.time()) - 600).status_code == 401
    n = "fixednonce123"
    target(c)
    body = {"user_id": "alice", "peer": "919876543210", "inbound_id": "r1", "text": SCAM}
    assert signed(c, "POST", "/bridge/inbound", body, nonce=n).status_code == 200
    assert signed(c, "POST", "/bridge/inbound", body, nonce=n).status_code == 401  # replay


def test_inbound_is_only_accepted_for_that_users_own_targets(env):
    c, f, _ = env
    target(c, "919876543210", ALICE)
    # bob's WhatsApp receives a message from alice's target number: bob never authorised it, so it is dropped
    r = inbound(c, user="bob").json()
    assert r["accepted"] is False
    # a stranger number for alice is dropped too, and nothing is stored
    assert inbound(c, peer="911111111111", inbound_id="u1").json()["accepted"] is False
    with session_scope(f) as db:
        assert db.scalars(select(Session)).all() == []
    # control: alice's own target is accepted and the session belongs to alice
    assert inbound(c).json()["accepted"] is True
    with session_scope(f) as db:
        assert [s.user_id for s in db.scalars(select(Session))] == ["alice"]


def test_one_inbound_one_outbound_no_duplicates_at_most_once(env):
    c, f, _ = env
    target(c, "+91 98765 43210")
    assert inbound(c, inbound_id="WA-A").json()["action"] == "reply"
    assert inbound(c, inbound_id="WA-A").json()["action"] == "duplicate"   # redelivery of same WhatsApp id
    job = signed(c, "POST", "/bridge/outbox/next", {"users": ["alice"]}).json()["job"]
    assert job["kind"] == "text" and job["peer"] == "919876543210" and job["user_id"] == "alice" and job["payload"]["text"]
    assert signed(c, "POST", "/bridge/outbox/next", {"users": ["alice"]}).json()["job"] is None   # leased job is not re-offered
    assert signed(c, "POST", f"/bridge/outbox/{job['id']}/ack", {"ok": True}).status_code == 200
    with session_scope(f) as db:
        assert [j.status for j in db.scalars(select(BridgeOutbox))] == ["sent"]


def test_voice_without_stt_key_degrades_safely(env):
    c, _, _ = env
    target(c)
    r = inbound(c, kind="voice", audio_b64="AAAA", inbound_id="v1", text="").json()
    assert r["accepted"] and r["action"] == "halted"        # untranscribed audio is never engaged blindly


# ---------------- WhatsApp link state (per user) ----------------
def sync(c, accounts=None):
    return signed(c, "POST", "/bridge/sync", {"accounts": accounts or []})


def test_whatsapp_link_flow_and_commands_are_per_user(env):
    c, _, _ = env
    assert c.get("/api/whatsapp").status_code == 401
    assert c.get("/api/whatsapp", headers=ALICE).json()["state"] == "not_linked"
    assert c.post("/api/whatsapp/link", headers=ALICE).status_code == 403          # consent first
    consent(c)
    assert c.post("/api/whatsapp/link", headers=ALICE).status_code == 200
    assert c.get("/api/whatsapp", headers=ALICE).json()["state"] == "linking"
    r = sync(c).json()                                                              # bridge heartbeat receives alice's link command once
    assert r["commands"] == [{"user_id": "alice", "type": "link"}]
    assert sync(c).json()["commands"] == []
    sync(c, [{"user_id": "alice", "state": "qr", "qr": "2@abc"}])
    st = c.get("/api/whatsapp", headers=ALICE).json()
    assert st["bridge_online"] and st["state"] == "qr" and st["qr"] == "2@abc"
    assert c.get("/api/whatsapp", headers=BOB).json()["qr"] is None                  # bob can never see alice's QR
    assert c.post("/api/whatsapp/pairing-code", headers=ALICE, json={"phone": "+91 98765 43210"}).status_code == 200
    assert sync(c, [{"user_id": "alice", "state": "qr", "qr": "2@abc"}]).json()["commands"] == [{"user_id": "alice", "type": "pairing_code", "phone": "919876543210"}]
    sync(c, [{"user_id": "alice", "state": "qr", "qr": "2@abc", "pairing_code": "ABCD-1234"}])
    assert c.get("/api/whatsapp", headers=ALICE).json()["pairing_code"] == "ABCD-1234"
    sync(c, [{"user_id": "alice", "state": "open", "me": "919000000000"}])
    st = c.get("/api/whatsapp", headers=ALICE).json()
    assert st["state"] == "open" and st["qr"] is None and st["pairing_code"] is None and st["me"] == "919000000000"
    c.post("/api/whatsapp/logout", headers=ALICE)
    assert sync(c, [{"user_id": "alice", "state": "open"}]).json()["commands"] == [{"user_id": "alice", "type": "logout"}]
    assert c.get("/api/whatsapp", headers=ALICE).json()["state"] == "not_linked"


def test_sync_returns_each_users_targets_only(env):
    c, _, _ = env
    target(c, "919876543210", ALICE)
    target(c, "918765432109", BOB)
    sync(c, [{"user_id": "alice", "state": "open"}, {"user_id": "bob", "state": "open"}])
    r = sync(c, [{"user_id": "alice", "state": "open"}, {"user_id": "bob", "state": "open"}]).json()
    assert r["targets"] == {"alice": ["919876543210"], "bob": ["918765432109"]}


def test_linked_account_limit_and_own_number_not_a_target(env):
    c, _, _ = env
    for u in ("u1", "u2"):
        h = {"Authorization": f"Bearer user:{u}"}
        consent(c, h)
        assert c.post("/api/whatsapp/link", headers=h).status_code == 200
    h3 = {"Authorization": "Bearer user:u3"}
    consent(c, h3)
    assert c.post("/api/whatsapp/link", headers=h3).status_code == 429               # MAX_LINKED_ACCOUNTS=2
    sync(c, [{"user_id": "u1", "state": "open", "me": "919000000000"}])
    assert c.post("/api/targets", headers={"Authorization": "Bearer user:u1"}, json={"number": "+91 90000 00000"}).status_code == 422


def test_sync_ignores_unknown_users_and_bad_states_and_needs_signature(env):
    c, _, _ = env
    assert c.post("/bridge/sync", json={"accounts": []}).status_code == 401
    assert signed(c, "POST", "/bridge/sync", {"accounts": []}, secret="x" * 48).status_code == 401
    consent(c)
    sync(c, [{"user_id": "ghost", "state": "open"}, {"user_id": "alice", "state": "hacked"}])
    assert c.get("/api/whatsapp", headers=ALICE).json()["state"] == "not_linked"


# ---------------- sessions / manual / proof / pdf ----------------
def test_manual_session_detail_proof_pdf_and_tamper_detection(env):
    c, f, _ = env
    sid = c.post("/api/sessions", headers=ALICE, json={}).json()["session_id"]
    r = c.post(f"/api/sessions/{sid}/messages", headers=ALICE, json={"text": SCAM}).json()
    assert r["action"] == "reply"
    d = c.get(f"/api/sessions/{sid}", headers=ALICE).json()
    kinds = {i["kind"] for i in d["iocs"]}
    assert {"upi", "url", "phone"} <= kinds and d["ledger"]["ok"] and d["turns"][-1]["draft"]
    proof = c.get(f"/api/sessions/{sid}/proof.json", headers=ALICE).json()
    assert ledger.verify_proof(proof)
    pdf = c.get(f"/api/sessions/{sid}/report.pdf", headers=ALICE)
    assert pdf.content[:4] == b"%PDF" and len(pdf.content) > 2000
    with session_scope(f) as db:
        ev = db.scalar(select(LedgerEvent).where(LedgerEvent.session_id == sid, LedgerEvent.type == "turn"))
        ev.payload = {**ev.payload, "text": "forged by an insider"}
    assert c.get(f"/api/sessions/{sid}", headers=ALICE).json()["ledger"]["ok"] is False


def test_simulation_endpoint_runs_pipeline_and_benign_halts(env):
    c, _, _ = env
    sid = c.post("/api/simulations", headers=ALICE, json={"scenario_id": "delivery", "turns": 3}).json()["session_id"]
    d = c.get(f"/api/sessions/{sid}", headers=ALICE).json()
    assert not [t for t in d["turns"] if t["role"] == "agent"] and d["session"]["status"] == "halted_benign"


# ---------------- canary routes ----------------
def _mint(c, f):
    sid = c.post("/api/sessions", headers=ALICE, json={}).json()["session_id"]
    from sentinel.canary import mint
    with session_scope(f) as db:
        info = mint(db, db.get(Session, sid), "receipt", "http://testserver")
    return sid, info["token"]


def test_canary_crawler_gets_opengraph_no_alert_human_gets_decoy_and_alert(env):
    c, f, _ = env
    sid, tok = _mint(c, f)
    for ua in ("WhatsApp/2.23.20.0 A", "facebookexternalhit/1.1", "TelegramBot (like TwitterBot)"):
        r = c.get(f"/r/{tok}", headers={"User-Agent": ua})
        assert r.status_code == 200 and "og:title" in r.text and "ERR_PDF_CORRUPT" not in r.text
    assert [h for h in c.get(f"/api/sessions/{sid}", headers=ALICE).json()["canaries"] if h["alert"]] == []
    r = c.get(f"/r/{tok}", headers=CHROME)
    assert "ERR_PDF_CORRUPT" in r.text and f"/r/{tok}/fp" in r.text
    fp = {"screen": "1080x2400", "platform": "Linux armv8l", "timezone": "Asia/Kolkata", "languages": "en-IN", "webgl": "Adreno 610", "cores": 8, "memory": 4, "touch": 5, "colorDepth": 24}
    assert c.post(f"/r/{tok}/fp", json=fp).status_code == 200
    hits = c.get(f"/api/sessions/{sid}", headers=ALICE).json()["canaries"]
    alerts = [h for h in hits if h["alert"]]
    assert len(alerts) == 1 and alerts[0]["fingerprint_hash"] and len([h for h in hits if not h["alert"]]) == 3


def test_unknown_canary_404_and_oversized_fingerprint_rejected(env):
    c, f, _ = env
    assert c.get("/r/doesnotexist", headers=CHROME).status_code == 404
    _, tok = _mint(c, f)
    assert c.post(f"/r/{tok}/fp", json={"x": "y" * 9000}).status_code == 413


# ---------------- takedown flow ----------------
def test_takedown_requires_approval_and_is_dry_run_only(env):
    c, f, _ = env
    sid = c.post("/api/sessions", headers=ALICE, json={}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/messages", headers=ALICE, json={"text": SCAM + " A/C No 50100123456789 IFSC HDFC0001234"})
    drafts = c.post(f"/api/sessions/{sid}/takedowns/draft", headers=ALICE).json()
    kinds = {d["kind"] for d in drafts}
    assert {"domain", "upi", "bank_account"} <= kinds
    d = next(x for x in drafts if x["kind"] == "domain")
    assert d["status"] == "drafted" and d["bundle"]["type"] == "bundle" and "Chain head" in d["report"]
    assert c.post(f"/api/takedowns/{d['id']}/dispatch", headers=ALICE).status_code == 409        # not approved yet
    assert c.post(f"/api/takedowns/{d['id']}/approve", headers=ALICE).json()["status"] == "approved"
    out = c.post(f"/api/takedowns/{d['id']}/dispatch", headers=ALICE).json()
    assert out["status"] == "dispatched" and out["mode"] == "dry_run"
    assert c.post(f"/api/sessions/{sid}/takedowns/draft", headers=ALICE).json() == []            # no duplicate drafts


def test_graph_endpoint_links_the_users_sessions_sharing_a_upi(env):
    c, _, _ = env
    for _ in range(2):
        sid = c.post("/api/sessions", headers=ALICE, json={}).json()["session_id"]
        c.post(f"/api/sessions/{sid}/messages", headers=ALICE, json={"text": SCAM})
    g = c.get("/api/graph", headers=ALICE).json()
    assert len(g["rings"]) == 1 and g["rings"][0]["confidence"] == "high" and g["rings"][0]["size"] == 2


# ---------------- MCP ----------------
async def test_mcp_server_exposes_same_tools_and_runs_select_ploy(env):
    from sentinel.mcp.server import build_server
    from sentinel.mcp.tools import REGISTRY
    c, f, settings = env
    sid = c.post("/api/sessions", headers=ALICE, json={}).json()["session_id"]
    server = build_server(f, settings, fetch=offline)
    names = {t.name for t in await server.list_tools()}
    assert names == set(REGISTRY)
    res = await server.call_tool("select_ploy", {"session_id": sid})
    payload = json.loads(res.content[0].text)
    assert payload["ploy_id"] == "ask_payment_rail" and payload["targets"] == ["upi"]

# ---------------- profile ----------------
def test_profile_roundtrip_validation_and_isolation(env):
    c, _, _ = env
    assert c.get("/api/profile", headers=ALICE).json() == {"data": {}, "share": {}, "complete": False, "collective_opt_in": False}
    r = c.put("/api/profile", headers=ALICE, json={"data": {"alias": "Anita", "age": 58, "occupation": "teacher", "full_name": "Anita Rao"},
                                                   "share": {"occupation": False}, "collective_opt_in": True})
    assert r.json() == {"complete": True}
    got = c.get("/api/profile", headers=ALICE).json()
    assert got["data"]["full_name"] == "Anita Rao" and got["share"] == {"occupation": False} and got["collective_opt_in"] is True
    assert c.get("/api/profile", headers=BOB).json()["data"] == {}                       # bob never sees alice's profile
    bad = c.put("/api/profile", headers=ALICE, json={"data": {"alias": "Anita", "extra": "my card number 4111 1111 1111 1111"}})
    assert bad.status_code == 422 and "bank" in bad.json()["detail"]
    assert c.get("/api/profile", headers=ALICE).json()["data"]["alias"] == "Anita"        # failed update changed nothing
    assert c.put("/api/profile", json={"data": {}}).status_code == 401


# ---------------- dev auth is opt-in and cannot be mistaken for Clerk ----------------
def test_dev_auth_is_off_by_default_and_accepts_only_dev_tokens_when_enabled():
    mk = lambda **kw: TestClient(create_app(Settings(bridge_shared_secret=SECRET, **kw), make_session_factory(make_engine("sqlite://")), FakeLLM()))
    off = mk(clerk_issuer="https://x.clerk.accounts.dev")
    assert off.get("/api/sessions", headers={"Authorization": "Bearer dev:alice"}).status_code == 401      # control: not enabled => rejected
    assert off.get("/api/health").json()["dev_auth"] is False
    on = mk(dev_auth=True)
    assert on.get("/api/sessions", headers={"Authorization": "Bearer dev:alice"}).status_code == 200
    assert on.get("/api/health").json()["dev_auth"] is True
    for bad in ("dev:", "dev:../x", "dev:a b", "alice", "dev:" + "x" * 41):
        assert on.get("/api/sessions", headers={"Authorization": f"Bearer {bad}"}).status_code == 401, bad
    assert on.get("/api/sessions").status_code == 401


def test_outbox_next_only_leases_jobs_for_users_the_bridge_says_are_connected(env):
    c, _, _ = env
    target(c)
    inbound(c)
    assert signed(c, "POST", "/bridge/outbox/next", {"users": ["bob"]}).json()["job"] is None
    assert signed(c, "POST", "/bridge/outbox/next", {"users": []}).json()["job"] is None
    assert signed(c, "POST", "/bridge/outbox/next", {"users": ["alice"]}).json()["job"]["user_id"] == "alice"

# ---------------- media shown in the chat ----------------
def test_forged_screenshot_is_listed_on_the_turn_and_served_only_to_its_owner(env):
    c, _, _ = env
    sid = c.post("/api/sessions", headers=ALICE, json={}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/messages", headers=ALICE, json={"text": SCAM})
    c.post(f"/api/sessions/{sid}/messages", headers=ALICE, json={"text": "Send screenshot of the Rs 500 payment now or police!"})
    agent = [t for t in c.get(f"/api/sessions/{sid}", headers=ALICE).json()["turns"] if t["role"] == "agent"][-1]
    media = agent["gate"]["media"]
    assert media and media[0]["kind"] == "image"
    sha = media[0]["sha256"]
    r = c.get(f"/api/media/{sha}", headers=ALICE)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    assert c.get(f"/api/media/{sha}", headers=BOB).status_code == 404          # another user cannot fetch it even with the hash
    assert c.get(f"/api/media/{sha}").status_code == 401
    assert c.get("/api/media/" + "0" * 64, headers=ALICE).status_code == 404
    assert c.get("/api/media/not-a-hash", headers=ALICE).status_code == 400