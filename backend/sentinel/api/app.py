"""FastAPI app: REST for the dashboard, SSE stream, public canary routes, HMAC-signed bridge routes."""
from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from sentinel.auth import TokenError, Verifier
from sentinel.security.vault import CryptoError, load_key, open_, seal
from sentinel import canary as canary_mod
from sentinel import graph as graph_mod
from sentinel import ledger, takedown
from sentinel.config import Settings, get_settings
from sentinel.db import make_engine, make_session_factory, session_scope
from sentinel.db.models import (BridgeOutbox, BridgeSeen, Canary, CanaryHit, Ioc, Session, TargetNumber, Takedown,
                                Profile, ToolTrace, Turn, User, WaAuthBlob)
from sentinel.enrich import enrich_ip
from sentinel.llm import LLMClient
from sentinel.mcp.tools import MEDIA_DIR, ToolContext, call_tool
from sentinel.orchestrator import persona as persona_mod
from sentinel.orchestrator.engine import Engine, EventBus
from sentinel.orchestrator.scenarios import BY_ID, SCENARIOS, pick
from sentinel.report import build_pdf
from sentinel.security import verify_signature

DIGITS = re.compile(r"\D")


class MessageIn(BaseModel):
    text: str


class SessionIn(BaseModel):
    kind: str = "manual"


class SimIn(BaseModel):
    scenario_id: str | None = None
    turns: int = 4


class TargetIn(BaseModel):
    number: str


class ConsentIn(BaseModel):
    accept: bool


class ProfileIn(BaseModel):
    data: dict
    share: dict = {}
    collective_opt_in: bool | None = None


class PairCodeIn(BaseModel):
    phone: str


class AccountSync(BaseModel):
    user_id: str
    state: str                      # connecting | qr | open | logged_out
    qr: str | None = None
    pairing_code: str | None = None
    me: str | None = None


class SyncIn(BaseModel):
    accounts: list[AccountSync] = []


def normalize_number(raw: str) -> tuple[str, bool]:
    """Digits only. A bare 10-digit Indian mobile (6-9...) gets the 91 prefix; returns (number, country_code_assumed)."""
    n = DIGITS.sub("", raw).lstrip("0") if raw.strip().startswith("00") else DIGITS.sub("", raw)
    if len(n) == 10 and n[0] in "6789":
        return "91" + n, True
    return n, False


class AckIn(BaseModel):
    ok: bool = True
    error: str = ""


WA_STATES = {"connecting", "qr", "open", "logged_out"}
WA_FRESH_S = 20


def create_app(settings: Settings | None = None, factory=None, llm=None, fetch=None, ip_fetch=None, sim_pace_s: float = 2.0,
               verify_token=None) -> FastAPI:
    settings = settings or get_settings()
    factory = factory or make_session_factory(make_engine(settings.database_url))
    bus = EventBus()
    llm = llm if llm is not None else LLMClient(settings)
    engine = Engine(factory, settings, llm, bus, fetch=fetch)
    app = FastAPI(title="Sentinel v2", version="2.0.0")
    app.state.engine, app.state.factory, app.state.bus, app.state.settings = engine, factory, bus, settings
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    def _owner_of(sid: str) -> str:
        with session_scope(factory) as db:
            s = db.get(Session, sid)
            return s.user_id if s else ""
    bus.resolver = _owner_of

    # ---------------- auth ----------------
    def dev_verify(token: str) -> str:
        m = re.fullmatch(r"dev:([A-Za-z0-9_-]{1,40})", token)
        if not m:
            raise TokenError("invalid dev token")
        return "dev_" + m.group(1)

    verifier = verify_token or (dev_verify if settings.dev_auth else Verifier(settings).verify)
    auth_ready = verify_token is not None or settings.dev_auth or bool(settings.clerk_issuer)

    def current_user(request: Request) -> str:
        """Clerk-verified user id. Every /api route depends on this; every query is filtered by it."""
        if not auth_ready:
            raise HTTPException(503, "auth is not configured on the server (set CLERK_ISSUER)")
        tok = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not tok:
            raise HTTPException(401, "sign in required")
        try:
            uid = verifier(tok)
        except TokenError as e:
            raise HTTPException(401, str(e))
        try:
            with session_scope(factory) as db:
                if not db.get(User, uid):
                    db.add(User(id=uid))
        except IntegrityError:        # two first requests raced; the row exists now
            pass
        return uid

    def owned(db, sid: str, uid: str) -> Session:
        s = db.get(Session, sid)
        if not s or s.user_id != uid:      # 404, not 403: never confirm another user's ids exist
            raise HTTPException(404)
        return s

    seen_nonces: dict[str, float] = {}      # single-process replay cache (no database write per bridge request)

    async def bridge(request: Request) -> bytes:
        body = await request.body()
        ok, why = verify_signature(settings.bridge_shared_secret, request.method, request.url.path,
                                   int(request.headers.get("x-bridge-timestamp", "0") or 0),
                                   request.headers.get("x-bridge-nonce", ""), body, request.headers.get("x-bridge-signature", ""))
        if not ok:
            raise HTTPException(401, why)
        nonce = request.headers["x-bridge-nonce"]
        now = time.time()
        if len(seen_nonces) > 4096:                      # signatures expire after 60 s, so older nonces can never be replayed
            for k in [k for k, t in seen_nonces.items() if now - t > 120]:
                seen_nonces.pop(k, None)
        if nonce in seen_nonces:
            raise HTTPException(401, "nonce replay")
        seen_nonces[nonce] = now
        return body

    def client_ip(request: Request) -> str:
        if settings.trusted_proxy:
            for h in ("cf-connecting-ip", "x-forwarded-for"):
                v = request.headers.get(h)
                if v:
                    return v.split(",")[0].strip()
        return request.client.host if request.client else ""

    # ---------------- health / identity ----------------
    @app.get("/api/health")
    def health():
        return {"ok": True, "auth_configured": auth_ready, "dev_auth": settings.dev_auth and verify_token is None, "takedown_mode": settings.takedown_mode,
                "llm_providers": [p.name for p in getattr(llm, "available", lambda *_: [])()],
                "bridge_auth_configured": len(settings.bridge_shared_secret) >= 16}

    @app.get("/api/me")
    def me(uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            u = db.get(User, uid)
            return {"id": uid, "consented": bool(u and u.consent_at), "collective_opt_in": bool(u and u.collective_opt_in)}

    @app.post("/api/consent")
    def consent(body: ConsentIn, uid: str = Depends(current_user)):
        """Responsible-use terms. Required before the agent may engage anyone on WhatsApp."""
        with session_scope(factory) as db:
            u = db.get(User, uid)
            u.consent_at = datetime.now(timezone.utc) if body.accept else None
        return {"consented": body.accept}

    @app.get("/api/profile")
    def get_profile(uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            pr, u = db.get(Profile, uid), db.get(User, uid)
            data = pr.data if pr else {}
            return {"data": data, "share": pr.share if pr else {}, "complete": persona_mod.is_complete(data),
                    "collective_opt_in": bool(u and u.collective_opt_in)}

    @app.put("/api/profile")
    def put_profile(body: ProfileIn, uid: str = Depends(current_user)):
        try:
            data, share = persona_mod.validate_profile(body.data, body.share)
        except persona_mod.ProfileError as e:
            raise HTTPException(422, str(e))
        with session_scope(factory) as db:
            pr = db.get(Profile, uid)
            if pr:
                pr.data, pr.share, pr.updated_at = data, share, datetime.now(timezone.utc)
            else:
                db.add(Profile(user_id=uid, data=data, share=share))
            if body.collective_opt_in is not None:
                db.get(User, uid).collective_opt_in = int(body.collective_opt_in)
        return {"complete": persona_mod.is_complete(data)}

    @app.get("/api/scenarios")
    def scenarios(uid: str = Depends(current_user)):
        return [s.__dict__ for s in SCENARIOS]

    # ---------------- sessions ----------------
    def _ser_session(db, s: Session) -> dict:
        n_iocs = db.scalar(select(func.count(Ioc.id)).where(Ioc.session_id == s.id))
        return {"id": s.id, "kind": s.kind, "channel": s.channel, "peer": s.peer, "status": s.status, "scenario": s.scenario_id,
                "exchanges": s.exchange_count, "iocs": n_iocs, "head_hash": s.head_hash, "created_at": s.created_at.isoformat()}

    @app.get("/api/sessions")
    def list_sessions(uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            return [_ser_session(db, s) for s in db.scalars(select(Session).where(Session.user_id == uid).order_by(Session.created_at.desc()).limit(100))]

    @app.post("/api/sessions")
    def new_session(body: SessionIn, uid: str = Depends(current_user)):
        return {"session_id": engine.create_session(kind="manual" if body.kind != "simulation" else "simulation", user_id=uid)}

    @app.get("/api/sessions/{sid}")
    def session_detail(sid: str, uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            s = owned(db, sid, uid)
            v = ledger.verify(db, sid)
            hits = db.execute(select(CanaryHit, Canary).join(Canary, Canary.token == CanaryHit.token).where(Canary.session_id == sid)).all()
            return {
                "session": _ser_session(db, s),
                "turns": [{"seq": t.seq, "role": t.role, "text": t.text, "original_text": t.original_text, "media_kind": t.media_kind,
                           "draft": t.draft_text, "gate": t.gate, "latency_ms": t.latency_ms, "hash": t.event_hash,
                           "at": t.created_at.isoformat()} for t in db.scalars(select(Turn).where(Turn.session_id == sid).order_by(Turn.seq))],
                "iocs": [{"kind": i.kind, "value": i.value, "enrichment": i.enrichment} for i in db.scalars(select(Ioc).where(Ioc.session_id == sid))],
                "traces": [{"tool": t.tool, "args": t.args, "result": t.result, "ok": bool(t.ok), "latency_ms": t.latency_ms, "turn_seq": t.turn_seq,
                            "at": t.created_at.isoformat()} for t in db.scalars(select(ToolTrace).where(ToolTrace.session_id == sid).order_by(ToolTrace.created_at))],
                "canaries": [{"token": c.token, "kind": c.kind, "classification": h.classification, "ip": h.ip, "subnet": h.subnet, "asn": h.asn,
                              "isp": h.isp, "fingerprint": h.fingerprint, "fingerprint_hash": h.fingerprint_hash, "at": h.created_at.isoformat(),
                              "alert": canary_mod.is_alert(h)} for h, c in hits],
                "takedowns": [{"id": t.id, "kind": t.target_kind, "target": t.target, "recipient": t.recipient, "status": t.status, "mode": t.dispatch_mode}
                              for t in db.scalars(select(Takedown).where(Takedown.session_id == sid))],
                "ledger": {"ok": v.ok, "events": v.checked, "head_hash": v.head_hash, "reason": v.reason, "bad_seq": v.bad_seq},
            }

    @app.post("/api/sessions/{sid}/messages")
    async def manual_message(sid: str, body: MessageIn, uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            owned(db, sid, uid)
        try:
            return (await engine.handle_inbound(sid, body.text)).to_dict()
        except KeyError:
            raise HTTPException(404)

    @app.get("/api/sessions/{sid}/proof.json")
    def proof(sid: str, uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            owned(db, sid, uid)
            return ledger.export_proof(db, sid)

    @app.get("/api/sessions/{sid}/report.pdf")
    def report(sid: str, uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            owned(db, sid, uid)
            return Response(build_pdf(db, sid), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="sentinel-{sid[:8]}.pdf"'})

    @app.get("/api/media/{sha}")
    def media_for_user(sha: str, uid: str = Depends(current_user)):
        """Images/voice the agent sent in this user's own sessions (so the chat can show what the scammer received)."""
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise HTTPException(400)
        with session_scope(factory) as db:
            q = select(ToolTrace).join(Session, Session.id == ToolTrace.session_id).where(
                Session.user_id == uid, ToolTrace.tool.in_(("forge_screenshot", "synthesize_voice")))
            if not any((t.result or {}).get("sha256") == sha for t in db.scalars(q)):
                raise HTTPException(404)
        for ext, mime in (("png", "image/png"), ("ogg", "audio/ogg"), ("mp3", "audio/mpeg")):
            p = MEDIA_DIR / f"{sha}.{ext}"
            if p.exists():
                return Response(p.read_bytes(), media_type=mime, headers={"Cache-Control": "private, max-age=3600"})
        raise HTTPException(404)

    @app.post("/api/simulations")
    async def start_sim(body: SimIn, uid: str = Depends(current_user)):
        sc = BY_ID.get(body.scenario_id) if body.scenario_id else pick()
        if sc is None:
            raise HTTPException(404, "unknown scenario")
        sid = engine.create_session(kind="simulation", scenario_id=sc.id, user_id=uid)
        task = asyncio.create_task(engine.run_simulation(sc, turns=max(1, min(body.turns, 8)), pace_s=sim_pace_s, sid=sid))
        app.state.last_sim_task = task
        return {"session_id": sid, "scenario": sc.__dict__}

    # ---------------- SSE (each user receives only their own events) ----------------
    @app.get("/api/stream")
    async def stream(request: Request, session_id: str | None = None, uid: str = Depends(current_user)):
        q = bus.subscribe()

        async def gen():
            try:
                yield ": connected\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev = await asyncio.wait_for(q.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    if ev.get("user_id") != uid:
                        continue
                    if session_id and ev["session_id"] != session_id:
                        continue
                    yield f"event: {ev['type']}\ndata: {json.dumps(ev)}\n\n"
            finally:
                bus.unsubscribe(q)
        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---------------- graph ----------------
    @app.get("/api/graph")
    def graph(uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            return graph_mod.attribution(db, uid)

    # ---------------- takedowns ----------------
    def _ser_td(t: Takedown):
        return {"id": t.id, "session_id": t.session_id, "kind": t.target_kind, "target": t.target, "recipient": t.recipient, "status": t.status,
                "mode": t.dispatch_mode, "report": t.report, "bundle": t.bundle, "created_at": t.created_at.isoformat()}

    @app.get("/api/takedowns")
    def list_td(uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            q = select(Takedown).join(Session, Session.id == Takedown.session_id).where(Session.user_id == uid).order_by(Takedown.created_at.desc())
            return [_ser_td(t) for t in db.scalars(q)]

    @app.post("/api/sessions/{sid}/takedowns/draft")
    async def draft_td(sid: str, uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            s = owned(db, sid, uid)
            ds = await takedown.create_drafts(db, s, domain_fetch=fetch, fetch=fetch)
            return [_ser_td(t) for t in ds]

    @app.post("/api/takedowns/{tid}/{action}")
    def td_action(tid: str, action: str, uid: str = Depends(current_user)):
        if action not in ("approve", "reject", "dispatch"):
            raise HTTPException(404)
        with session_scope(factory) as db:
            t0 = db.get(Takedown, tid)
            if not t0:
                raise HTTPException(404)
            owned(db, t0.session_id, uid)
            try:
                if action == "dispatch":
                    if settings.takedown_mode != "dry_run":
                        raise HTTPException(400, "only TAKEDOWN_MODE=dry_run is supported")
                    t = takedown.dispatch(db, tid, "dry_run")
                else:
                    t = takedown.approve(db, tid, action == "approve")
            except KeyError:
                raise HTTPException(404)
            except (ValueError, PermissionError) as e:
                raise HTTPException(409, str(e))
            return _ser_td(t)

    # ---------------- WhatsApp link: per-user state pushed by the bridge, per-user commands pulled by it ----------------
    wa_state: dict[str, dict] = {}          # user_id -> {state, qr, pairing_code, me, seen}
    wa_cmds: dict[str, list[dict]] = {}     # user_id -> queued commands for the bridge
    bridge_seen = {"at": 0.0}

    def _fresh(st: dict | None) -> bool:
        return bool(st) and time.time() - st["seen"] < WA_FRESH_S

    def _slots_used() -> int:
        live = {u for u, st in wa_state.items() if _fresh(st) and st["state"] in ("connecting", "qr", "open")}
        return len(live | {u for u, c in wa_cmds.items() if any(x["type"] == "link" for x in c)})

    @app.get("/api/whatsapp")
    def whatsapp_state(uid: str = Depends(current_user)):
        online = time.time() - bridge_seen["at"] < WA_FRESH_S
        st = wa_state.get(uid)
        state = st["state"] if online and _fresh(st) else ("linking" if any(c["type"] == "link" for c in wa_cmds.get(uid, [])) else "not_linked")
        return {"bridge_online": online, "state": state,
                "qr": st["qr"] if st and state == "qr" else None, "pairing_code": st["pairing_code"] if st and state == "qr" else None,
                "me": st["me"] if st and state == "open" else None,
                "scope": "Only the numbers you add are read or answered. Every other chat is ignored on your device and never sent to the backend."}

    def _require_consent(uid: str):
        with session_scope(factory) as db:
            u = db.get(User, uid)
            if not (u and u.consent_at):
                raise HTTPException(403, "accept the responsible-use terms first")

    @app.post("/api/whatsapp/link")
    def whatsapp_link(uid: str = Depends(current_user)):
        _require_consent(uid)
        st = wa_state.get(uid)
        already = _fresh(st) and st["state"] in ("connecting", "qr", "open")
        if not already and _slots_used() >= settings.max_linked_accounts:
            raise HTTPException(429, "this server is at its linked-account limit; try again later")
        if not any(c["type"] == "link" for c in wa_cmds.get(uid, [])):
            wa_cmds.setdefault(uid, []).append({"type": "link"})
        return {"queued": True}

    @app.post("/api/whatsapp/pairing-code")
    def whatsapp_pair_code(body: PairCodeIn, uid: str = Depends(current_user)):
        n, _ = normalize_number(body.phone)
        if not 8 <= len(n) <= 15:
            raise HTTPException(422, "enter your own WhatsApp number with country code")
        if uid in wa_state:
            wa_state[uid]["pairing_code"] = None
        wa_cmds.setdefault(uid, []).append({"type": "pairing_code", "phone": n})
        return {"queued": True}

    @app.post("/api/whatsapp/logout")
    def whatsapp_logout(uid: str = Depends(current_user)):
        wa_cmds.setdefault(uid, []).append({"type": "logout"})
        return {"queued": True}

    # ---------------- engagement targets (the ONLY numbers the agent reads or answers) ----------------
    @app.get("/api/targets")
    def list_targets(uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            return [t.number for t in db.scalars(select(TargetNumber).where(TargetNumber.user_id == uid).order_by(TargetNumber.created_at))]

    @app.post("/api/targets")
    def add_target(body: TargetIn, uid: str = Depends(current_user)):
        _require_consent(uid)
        n, assumed = normalize_number(body.number)
        if not 8 <= len(n) <= 15:
            raise HTTPException(422, "number must include the country code, e.g. +91 98765 43210")
        own = (wa_state.get(uid) or {}).get("me")
        if own and own == n:
            raise HTTPException(422, "that is your own number")
        with session_scope(factory) as db:
            if not db.get(TargetNumber, (uid, n)):
                if db.scalar(select(func.count()).select_from(TargetNumber).where(TargetNumber.user_id == uid)) >= settings.max_targets_per_user:
                    raise HTTPException(429, f"you can engage at most {settings.max_targets_per_user} numbers at a time; remove one first")
                db.add(TargetNumber(user_id=uid, number=n))
        return {"number": n, "assumed_country_code_91": assumed}

    @app.delete("/api/targets/{number}")
    def del_target(number: str, uid: str = Depends(current_user)):
        with session_scope(factory) as db:
            t = db.get(TargetNumber, (uid, DIGITS.sub("", number)))
            if t:
                db.delete(t)
        return {"ok": True}
    # ---------------- public canary routes ----------------
    @app.get("/r/{token}", response_class=HTMLResponse)
    async def canary_open(token: str, request: Request):
        with session_scope(factory) as db:
            can = db.get(Canary, token)
            if not can:
                return HTMLResponse("<h1>404</h1>", status_code=404)
            headers = dict(request.headers)
            ip = client_ip(request)
            if canary_mod.classify(headers) == "crawler":
                canary_mod.record_hit(db, token, ip=ip, headers=headers)
                return HTMLResponse(canary_mod.og_html(can.kind, f"{settings.public_base_url.rstrip('/')}/r/{token}"))
            intel = await enrich_ip(ip, fetch=ip_fetch) if ip_fetch or (ip and ip not in ("127.0.0.1", "::1", "testclient")) else {}
            hit = canary_mod.record_hit(db, token, ip=ip, headers=headers, ip_intel=intel)
            bus.publish("canary_hit", can.session_id, {"token": token, "ip": ip, "isp": hit.isp, "asn": hit.asn, "alert": True})
            return HTMLResponse(canary_mod.decoy_html(token))

    @app.post("/r/{token}/fp")
    async def canary_fp(token: str, request: Request):
        try:
            fp = await request.json()
        except Exception:
            raise HTTPException(400)
        if not isinstance(fp, dict) or len(json.dumps(fp)) > 4000:
            raise HTTPException(413)
        with session_scope(factory) as db:
            hit = canary_mod.attach_fingerprint(db, token, client_ip(request), fp)
            if hit:
                can = db.get(Canary, token)
                bus.publish("canary_fingerprint", can.session_id, {"token": token, "fingerprint_hash": hit.fingerprint_hash})
        return JSONResponse({"ok": True})

    # ---------------- bridge (HMAC-signed transport; one bridge process serves many users' WhatsApp accounts) ----------------
    @app.post("/bridge/sync")
    async def bridge_sync(request: Request, body: bytes = Depends(bridge)):
        """Bridge reports every linked account's state; gets back queued per-user commands and each user's target numbers."""
        data = SyncIn(**json.loads(body or b"{}"))
        bridge_seen["at"] = time.time()
        known: set[str] = set()
        with session_scope(factory) as db:
            for a in data.accounts:
                if a.state not in WA_STATES or not db.get(User, a.user_id):
                    continue
                known.add(a.user_id)
                prev = wa_state.get(a.user_id)
                changed = not prev or (prev["state"], prev["pairing_code"], prev["qr"]) != (a.state, a.pairing_code, a.qr if a.state == "qr" else None)
                wa_state[a.user_id] = {"state": a.state, "qr": a.qr if a.state == "qr" else None,
                                       "pairing_code": a.pairing_code if a.state == "qr" else None,
                                       "me": a.me if a.state == "open" else None, "seen": time.time()}
                if changed:
                    bus.publish("wa_status", "", {"state": a.state}, user_id=a.user_id)
            commands = [{"user_id": u, **c} for u, cs in list(wa_cmds.items()) for c in cs]
            wa_cmds.clear()
            wanted = known | {c["user_id"] for c in commands}
            targets: dict[str, list[str]] = {u: [] for u in wanted}
            for t in db.scalars(select(TargetNumber).where(TargetNumber.user_id.in_(wanted))) if wanted else []:
                targets[t.user_id].append(t.number)
        for c in commands:        # a command for a user the bridge dropped is re-queued by the user's next click, not retried silently
            if c["type"] == "logout":
                wa_state.pop(c["user_id"], None)
        return {"commands": commands, "targets": targets}

    @app.post("/bridge/inbound")
    async def bridge_inbound(request: Request, body: bytes = Depends(bridge)):
        data = json.loads(body or b"{}")
        uid = str(data.get("user_id", ""))[:64]
        peer = DIGITS.sub("", str(data.get("peer", "")))
        inbound_id = str(data.get("inbound_id", ""))[:120]
        if not uid or not peer or not inbound_id:
            raise HTTPException(422, "user_id, peer and inbound_id required")
        with session_scope(factory) as db:
            if not db.get(TargetNumber, (uid, peer)):
                return {"accepted": False, "reason": "peer is not a target number of this user"}
            s = db.scalar(select(Session).where(Session.user_id == uid, Session.channel == "whatsapp", Session.peer == peer, Session.status != "closed").order_by(Session.created_at.desc()).limit(1))
            sid = s.id if s else None
        sid = sid or engine.create_session(kind="live", channel="whatsapp", peer=peer, user_id=uid)
        kind = data.get("kind", "text")
        text, original = str(data.get("text", "")), ""
        if kind == "voice":
            try:
                with session_scope(factory) as db:
                    tr = await call_tool(ToolContext(db=db, settings=settings), "transcribe_voice",
                                         {"audio_b64": data.get("audio_b64", ""), "filename": data.get("filename", "voice.ogg")}, session_id=sid)
                text, original = tr["english"] or tr["original"], tr["original"]
            except Exception as e:
                text = f"[voice note received; transcription unavailable: {type(e).__name__}]"
        res = await engine.handle_inbound(sid, text, media_kind=kind, original_text=original, inbound_id=inbound_id, audio_reply_ok=True)
        return {"accepted": True, "session_id": sid, "action": res.action}

    @app.post("/bridge/outbox/next")
    async def bridge_next(request: Request, body: bytes = Depends(bridge)):
        """Leases the oldest pending job for a user whose WhatsApp is connected right now (the bridge lists them in the body)."""
        users = [str(u)[:64] for u in (json.loads(body or b"{}").get("users") or [])]
        if not users:
            return {"job": None}
        with session_scope(factory) as db:
            j = db.scalar(select(BridgeOutbox).where(BridgeOutbox.status == "pending", BridgeOutbox.user_id.in_(users)).order_by(BridgeOutbox.created_at).limit(1))
            if not j:
                return {"job": None}
            j.status = "leased"          # at-most-once: a leased job is never re-offered automatically
            payload = {k: v for k, v in j.payload.items() if k != "path"}
            return {"job": {"id": j.id, "user_id": j.user_id, "peer": j.peer, "kind": j.kind, "payload": payload}}

    @app.post("/bridge/outbox/{jid}/ack")
    async def bridge_ack(jid: str, request: Request, body: bytes = Depends(bridge)):
        ack = AckIn(**json.loads(body or b"{}"))
        with session_scope(factory) as db:
            j = db.get(BridgeOutbox, jid)
            if not j or j.status != "leased":
                raise HTTPException(409, "job not leased")
            j.status = "sent" if ack.ok else "failed"
        return {"ok": True}

    # ---------------- encrypted WhatsApp credential store (for hosts without a persistent disk) ----------------
    try:
        enc_key = load_key(settings.session_enc_key)
    except CryptoError:
        enc_key = None

    def _need_key() -> bytes:
        if enc_key is None:
            raise HTTPException(503, "SESSION_ENC_KEY is not configured; the database auth store is disabled")
        return enc_key

    def _uid(d: dict) -> str:
        uid = str(d.get("user_id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", uid):
            raise HTTPException(422, "bad user_id")
        return uid

    @app.post("/bridge/auth/get")
    async def auth_get(request: Request, body: bytes = Depends(bridge)):
        key, data = _need_key(), json.loads(body or b"{}")
        uid, names = _uid(data), [str(n)[:200] for n in (data.get("names") or [])][:500]
        out: dict[str, str | None] = {n: None for n in names}
        with session_scope(factory) as db:
            for r in db.scalars(select(WaAuthBlob).where(WaAuthBlob.user_id == uid, WaAuthBlob.name.in_(names))):
                try:
                    out[r.name] = open_(key, uid, r.name, r.data)
                except CryptoError:
                    out[r.name] = None
        return {"items": out}

    @app.post("/bridge/auth/set")
    async def auth_set(request: Request, body: bytes = Depends(bridge)):
        key, data = _need_key(), json.loads(body or b"{}")
        uid, items = _uid(data), data.get("items") or {}
        if not isinstance(items, dict) or len(items) > 500:
            raise HTTPException(422, "items must be an object of at most 500 entries")
        with session_scope(factory) as db:
            for name, val in items.items():
                name = str(name)[:200]
                row = db.get(WaAuthBlob, (uid, name))
                if val is None:
                    if row:
                        db.delete(row)
                    continue
                sealed = seal(key, uid, name, str(val))
                if row:
                    row.data, row.updated_at = sealed, datetime.now(timezone.utc)
                else:
                    db.add(WaAuthBlob(user_id=uid, name=name, data=sealed))
        return {"ok": True}

    @app.post("/bridge/auth/users")
    async def auth_users(request: Request, _: bytes = Depends(bridge)):
        _need_key()
        with session_scope(factory) as db:
            return {"users": list(db.scalars(select(WaAuthBlob.user_id).where(WaAuthBlob.name == "creds").distinct()))}

    @app.post("/bridge/auth/wipe")
    async def auth_wipe(request: Request, body: bytes = Depends(bridge)):
        _need_key()
        uid = _uid(json.loads(body or b"{}"))
        with session_scope(factory) as db:
            db.execute(delete(WaAuthBlob).where(WaAuthBlob.user_id == uid))
        return {"ok": True}

    @app.get("/bridge/media/{sha}")
    async def bridge_media(sha: str, request: Request, _: bytes = Depends(bridge)):
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise HTTPException(400)
        for ext, mime in (("png", "image/png"), ("ogg", "audio/ogg"), ("mp3", "audio/mpeg")):
            p = MEDIA_DIR / f"{sha}.{ext}"
            if p.exists():
                return Response(p.read_bytes(), media_type=mime)
        raise HTTPException(404)

    return app