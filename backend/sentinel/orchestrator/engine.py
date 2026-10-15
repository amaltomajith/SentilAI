"""The orchestrator: triage -> ground IOCs -> ploy -> draft(LLM) -> outbound gate -> persist -> dispatch.
The model writes text only. Every decision that matters is made by deterministic code in this file or its imports."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

from sqlalchemy import func, select

from sentinel import ledger
from sentinel.config import Settings
from sentinel.db import session_scope
from sentinel.db.models import BridgeOutbox, BridgeSeen, HoneyToken, Ioc, Profile, Session, Takedown, ToolTrace, Turn, User
from sentinel.gate import fallback_for, looks_like_injection, run_gate
from sentinel.grounding import extract_candidates, ground
from sentinel.llm import LLMUnavailable
from sentinel.mcp.tools import ToolContext, call_tool, session_iocs
from sentinel.orchestrator import bandit, strategy
from sentinel.orchestrator import persona as persona_mod
from sentinel.orchestrator import prompts
from sentinel.orchestrator.ploys import PLOYS
from sentinel.orchestrator.scenarios import Scenario
from sentinel.orchestrator.triage import triage

SCREENSHOT_ASK = re.compile(r"screen ?shot|proof of payment|payment proof|send (me )?(the )?(receipt|image|photo|pic)|show (me )?(the )?(payment|receipt)", re.I)
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)\s?([\d,]{2,9})|\b([\d,]{2,9})\s?(?:rs\b|rupees)", re.I)


class EventBus:
    """In-process pub/sub feeding the SSE stream."""
    def __init__(self):
        self.subs: set[asyncio.Queue] = set()
        self.owner: dict[str, str] = {}      # session_id -> user_id, so the SSE stream can serve each user only their own events
        self.resolver = None                  # optional callable(session_id) -> user_id for sessions created before this process started

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.subs.add(q)
        return q

    def unsubscribe(self, q):
        self.subs.discard(q)

    def publish(self, type_: str, session_id: str, data: dict, user_id: str | None = None):
        if user_id is None and session_id:
            if session_id not in self.owner and self.resolver:
                self.owner[session_id] = self.resolver(session_id) or ""
            user_id = self.owner.get(session_id, "")
        ev = {"type": type_, "session_id": session_id, "user_id": user_id or "", "data": data, "ts": time.time()}
        for q in list(self.subs):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass


@dataclass
class Result:
    action: str  # reply | halted | duplicate | closed
    session_id: str
    reply_text: str = ""
    media: dict | None = None
    triage: dict = field(default_factory=dict)
    gate: dict = field(default_factory=dict)
    ploy: dict = field(default_factory=dict)
    new_iocs: list = field(default_factory=list)
    reason: str = ""

    def to_dict(self):
        return self.__dict__


def load_persona(db, user_id: str) -> persona_mod.Persona:
    prof = db.get(Profile, user_id) if user_id else None
    return persona_mod.build(prof.data if prof else {}, prof.share if prof else {}, user_id or "anon")


def ensure_honey(db, p: persona_mod.Persona) -> None:
    """The decoy identity we may offer. Registered so the grounding step never mistakes it for scammer intel."""
    for kind, val in p.honey.items():
        if not db.scalar(select(HoneyToken).where(HoneyToken.value == val)):
            db.add(HoneyToken(session_id="", kind=kind, value=val))
    db.flush()


class Engine:
    def __init__(self, factory, settings: Settings, llm=None, bus: EventBus | None = None, *, fetch=None,
                 gate_enabled: bool = True, voice_replies: bool = True):
        self.factory, self.settings, self.llm = factory, settings, llm
        self.bus = bus or EventBus()
        self.fetch, self.gate_enabled, self.voice_replies = fetch, gate_enabled, voice_replies
        self._locks: dict[str, asyncio.Lock] = {}

    # ---------- helpers ----------
    def _ctx(self, db) -> ToolContext:
        kw = {"fetch": self.fetch} if self.fetch else {}
        return ToolContext(db=db, settings=self.settings, **kw)

    def create_session(self, kind="manual", channel="web", peer="", scenario_id="", user_id="") -> str:
        with session_scope(self.factory) as db:
            s = Session(kind=kind, channel=channel, peer=peer, scenario_id=scenario_id, user_id=user_id)
            db.add(s)
            db.flush()
            ensure_honey(db, load_persona(db, user_id))
            ledger.append(db, s, "note", {"event": "session_created", "kind": kind, "channel": channel, "scenario": scenario_id})
            sid = s.id
        self.bus.owner[sid] = user_id
        self.bus.publish("session_created", sid, {"kind": kind, "channel": channel, "scenario": scenario_id})
        return sid

    @staticmethod
    def _next_seq(db, sid) -> int:
        return (db.scalar(select(func.max(Turn.seq)).where(Turn.session_id == sid)) or 0) + 1

    def _history(self, db, sid, limit=8):
        turns = db.scalars(select(Turn).where(Turn.session_id == sid).order_by(Turn.seq.desc()).limit(limit)).all()[::-1]
        return [{"role": "user" if t.role == "scammer" else "assistant", "content": t.text} for t in turns]

    # ---------- main entry ----------
    async def handle_inbound(self, session_id: str, text: str, *, media_kind: str = "text", original_text: str = "",
                             inbound_id: str = "", audio_reply_ok: bool = False) -> Result:
        text = (text or "").strip()
        if not text:
            return Result("halted", session_id, reason="empty message")
        # one message at a time per session (ledger sequence + turn order stay consistent)
        async with self._locks.setdefault(session_id, asyncio.Lock()):
            return await self._handle_locked(session_id, text, media_kind, original_text, inbound_id, audio_reply_ok)

    async def _handle_locked(self, session_id, text, media_kind, original_text, inbound_id, audio_reply_ok) -> Result:
        t_start = time.perf_counter()
        events: list[tuple[str, dict]] = []
        with session_scope(self.factory) as db:
            sess = db.get(Session, session_id)
            if sess is None:
                raise KeyError(session_id)
            ctx = self._ctx(db)
            if inbound_id and db.get(BridgeSeen, f"in:{session_id}:{inbound_id}"):
                return Result("duplicate", session_id, reason="inbound message already processed")
            if sess.status == "closed":
                return Result("closed", session_id, reason="session closed")

            # 1. record the scammer's turn (always: evidence is kept even when we do not engage)
            seq = self._next_seq(db, sid := session_id)
            ev = ledger.append(db, sess, "turn", {"role": "scammer", "seq": seq, "text": text, "media_kind": media_kind, "original_text": original_text})
            sturn = Turn(session_id=sid, seq=seq, role="scammer", text=text, original_text=original_text, media_kind=media_kind, event_hash=ev.hash)
            db.add(sturn)
            db.flush()
            events.append(("turn", {"role": "scammer", "text": text, "seq": seq, "media_kind": media_kind, "original_text": original_text}))
            db.commit()   # evidence is durable before any slow I/O; never hold the SQLite write lock across an await

            # 2. triage (until the session has been judged a scam)
            tri = None
            if sess.status in ("active", "halted_benign", "halted_uncertain") and not self._engaged(db, sid):
                tri = await triage(text, self.llm)
                db.commit()
                ledger.append(db, sess, "note", {"event": "triage", "verdict": tri.verdict, "confidence": tri.confidence, "reasons": tri.reasons, "source": tri.source})
                events.append(("triage", {"verdict": tri.verdict, "confidence": tri.confidence, "reasons": tri.reasons, "source": tri.source}))
                if tri.verdict == "benign":
                    sess.status = "halted_benign"
                elif tri.verdict == "uncertain":
                    sess.status = "halted_uncertain"
                else:
                    sess.status = "active"
                if sess.status != "active":
                    ledger.append(db, sess, "note", {"event": "engagement_halted", "status": sess.status})
                    res = Result("halted", sid, triage=tri.__dict__, reason=f"triage verdict: {tri.verdict}")
                    self._flush_events(sid, events)
                    return res

            # 3. literal-grounded IOC capture
            pers = load_persona(db, sess.user_id)
            ensure_honey(db, pers)
            honey = {h.value for h in db.scalars(select(HoneyToken))}
            grounded = [g for g in ground(extract_candidates(text), text, honey)]
            new_iocs = []
            have = {(i.kind, i.value) for i in session_iocs(ctx, sid)}
            for g in grounded:
                if not g.accepted:
                    ledger.append(db, sess, "note", {"event": "ioc_rejected", "kind": g.candidate.kind, "value": g.candidate.value, "reason": g.reason})
                    continue
                key = (g.candidate.kind, g.candidate.value)
                if key in have:
                    continue
                have.add(key)
                db.commit()
                enr = await self._enrich(ctx, sid, g.candidate.kind, g.candidate.value)
                iev = ledger.append(db, sess, "ioc", {"kind": g.candidate.kind, "value": g.candidate.value, "turn_seq": seq})
                db.add(Ioc(session_id=sid, turn_id=sturn.id, kind=g.candidate.kind, value=g.candidate.value, enrichment=enr, event_hash=iev.hash))
                new_iocs.append({"kind": g.candidate.kind, "value": g.candidate.value, "enrichment": enr})
            db.flush()
            for n in new_iocs:
                events.append(("ioc", n))

            # 4. exchange limit
            if sess.exchange_count >= self.settings.max_exchanges:
                sess.status = "closed"
                ledger.append(db, sess, "note", {"event": "session_closed", "reason": "max_exchanges"})
                self._flush_events(sid, events)
                return Result("closed", sid, reason="max exchanges reached", new_iocs=new_iocs)

            # 5. tactic
            asked_shot = bool(SCREENSHOT_ASK.search(text))
            last_ploy = self._last_ploy(db, sid)
            analysis = strategy.analyze(text, sess.exchange_count, {i.kind for i in session_iocs(ctx, sid)})
            if sess.pending_tactic and sess.user_id:          # learn from the previous tactic: did it make the scammer reveal something new?
                prev_type, _, prev_tac = sess.pending_tactic.partition("|")
                targets = PLOYS[prev_tac].targets if prev_tac in PLOYS else ()
                hit = any((n["kind"] in targets) if targets else True for n in new_iocs)
                owner = db.get(User, sess.user_id)
                bandit.record(db, sess.user_id, prev_type, prev_tac, hit, bool(owner and owner.collective_opt_in))
            sess.pending_tactic = ""
            ploy = await call_tool(ctx, "select_tactic", {"session_id": sid, "scam_type": analysis.scam_type, "scammer_asked_screenshot": asked_shot, "last_ploy": last_ploy}, session_id=sid)
            sess.pending_tactic = f"{analysis.scam_type}|{ploy['ploy_id']}"
            lang_hint = strategy.lang_instruction(analysis.language, pers.languages)

            # 6. draft (the only model call that matters)
            approved = honey | {i.value for i in session_iocs(ctx, sid)}
            db.commit()
            tdraft = time.perf_counter()
            injected = looks_like_injection(text)
            llm_note = ""
            if injected:
                draft, llm_note = fallback_for(text + sid), "inbound prompt-injection detected: model not consulted"
            else:
                try:
                    system = pers.system(ploy["instruction"], lang_hint)
                    draft = await self.llm.complete(system, self._history(db, sid), purpose="agent", max_tokens=150, temperature=0.9) if self.llm else ""
                    if not draft:
                        raise LLMUnavailable("no llm configured")
                except LLMUnavailable as e:
                    draft, llm_note = fallback_for(text + sid), f"llm unavailable ({e}); stall template used"
            draft_ms = int((time.perf_counter() - tdraft) * 1000)

            # 7. deterministic gate (+ canary link and forged screenshot are added by CODE, never by the model)
            can_info = None
            if asked_shot and not self._has_canary(db, sid) and sess.exchange_count >= 1:
                can_info = await call_tool(ctx, "mint_canary", {"session_id": sid, "kind": "receipt"}, session_id=sid)
                approved = approved | {can_info["url"]}
            gate = run_gate(draft, approved, enabled=self.gate_enabled, seed=text + sid, protected=pers.protected)
            final = gate.final
            if can_info:
                final = f"{final} I have also uploaded the payment receipt here sir: {can_info['url']}"
            media_out = None
            if asked_shot:
                media_out = await self._maybe_forge(ctx, sid, text)

            db.commit()
            # 8. voice reply if the scammer sent a voice note
            voice = None
            if audio_reply_ok and self.voice_replies and media_kind == "voice":
                try:
                    voice = await call_tool(ctx, "synthesize_voice", {"session_id": sid, "text": final}, session_id=sid)
                except Exception as e:
                    llm_note += f" voice synthesis failed: {type(e).__name__}"

            # 9. persist the agent turn
            aseq = self._next_seq(db, sid)
            total_ms = int((time.perf_counter() - t_start) * 1000)
            media_list = ([{"kind": "image", "sha256": media_out["sha256"]}] if media_out else []) + ([{"kind": "voice", "sha256": voice["sha256"]}] if voice else [])
            gate_d = gate.to_dict() | {"media": media_list, "strategy": {"scam_type": analysis.scam_type, "stage": analysis.stage, "pressure": analysis.pressure, "language": analysis.language,
                                                                    "tactic": ploy["ploy_id"], "candidates": ploy.get("candidates", {})}, "llm_note": llm_note, "provider": getattr(self.llm, "last", None) and self.llm.last.provider, "draft_ms": draft_ms}
            aev = ledger.append(db, sess, "turn", {"role": "agent", "seq": aseq, "text": final, "draft": draft, "gate": gate.to_dict()})
            db.add(Turn(session_id=sid, seq=aseq, role="agent", text=final, draft_text=draft, gate=gate_d, latency_ms=total_ms,
                        media_kind="voice" if voice else "text", event_hash=aev.hash))
            sess.exchange_count += 1
            events.append(("turn", {"role": "agent", "text": final, "draft": draft, "seq": aseq, "gate": gate_d, "latency_ms": total_ms, "ploy": ploy["ploy_id"]}))

            if inbound_id:
                db.add(BridgeSeen(key=f"in:{session_id}:{inbound_id}"))   # marked only once the reply is durably recorded
            # 10. outbound jobs (single approved reply; the bridge only ever sends what is in the outbox)
            if sess.channel == "whatsapp":
                job_media = voice if voice else None
                if job_media:
                    db.add(BridgeOutbox(session_id=sid, user_id=sess.user_id, peer=sess.peer, kind="voice", payload={"sha256": job_media["sha256"], "mime": job_media["mime"], "ptt": job_media["ptt"], "path": job_media["path"], "text": final}, inbound_id=inbound_id))
                else:
                    db.add(BridgeOutbox(session_id=sid, user_id=sess.user_id, peer=sess.peer, kind="text", payload={"text": final}, inbound_id=inbound_id))
                if media_out:
                    db.add(BridgeOutbox(session_id=sid, user_id=sess.user_id, peer=sess.peer, kind="image", payload={"sha256": media_out["sha256"], "path": media_out["path"], "mime": "image/png", "caption": "Payment screenshot"}, inbound_id=inbound_id))
            if media_out:
                events.append(("media", {"kind": "image", "sha256": media_out["sha256"]}))
            db.flush()
            self._flush_events(sid, events)
            return Result("reply", sid, reply_text=final, media=media_out or (voice and {"voice": voice["sha256"]}), triage=(tri.__dict__ if tri else {}),
                          gate=gate_d, ploy=ploy, new_iocs=new_iocs)

    # ---------- internals ----------
    def _flush_events(self, sid, events):
        for t, d in events:
            self.bus.publish(t, sid, d)

    @staticmethod
    def _engaged(db, sid) -> bool:
        return db.scalar(select(func.count(Turn.id)).where(Turn.session_id == sid, Turn.role == "agent")) > 0

    @staticmethod
    def _has_canary(db, sid) -> bool:
        from sentinel.db.models import Canary
        return db.scalar(select(func.count(Canary.token)).where(Canary.session_id == sid)) > 0

    @staticmethod
    def _last_ploy(db, sid) -> str:
        t = db.scalar(select(ToolTrace).where(ToolTrace.session_id == sid, ToolTrace.tool == "select_tactic").order_by(ToolTrace.created_at.desc()).limit(1))
        return (t.result or {}).get("ploy_id", "") if t else ""

    async def _enrich(self, ctx, sid, kind, value) -> dict:
        try:
            if kind == "upi":
                return await call_tool(ctx, "enrich_upi", {"vpa": value}, session_id=sid)
            if kind == "ifsc":
                return await call_tool(ctx, "enrich_ifsc", {"ifsc": value}, session_id=sid)
            if kind == "url":
                return await call_tool(ctx, "enrich_domain", {"domain": value}, session_id=sid)
        except Exception as e:
            return {"error": f"{type(e).__name__}"}
        return {}

    async def _maybe_forge(self, ctx, sid, text) -> dict | None:
        iocs = session_iocs(ctx, sid)
        payee = next((i.value for i in iocs if i.kind == "upi"), None) or next((i.value for i in iocs if i.kind == "bank_account"), None)
        if not payee:
            return None
        amt = "500"
        for t in ctx.db.scalars(select(Turn).where(Turn.session_id == sid, Turn.role == "scammer").order_by(Turn.seq)):
            m = AMOUNT_RE.search(t.text)
            if m:
                amt = re.sub(r"\D", "", m.group(1) or m.group(2)) or amt
                break
        try:
            return await call_tool(ctx, "forge_screenshot", {"session_id": sid, "vpa": payee, "amount": amt[:7], "error_code": "U53"}, session_id=sid)
        except Exception:
            logging.getLogger(__name__).warning("forge_screenshot failed; replying without an image", exc_info=True)
            return None

    # ---------- simulation (AI scammer vs the user's agent) ----------
    async def scammer_next(self, session_id: str, scenario: Scenario) -> str:
        with session_scope(self.factory) as db:
            hist = db.scalars(select(Turn).where(Turn.session_id == session_id).order_by(Turn.seq.desc()).limit(8)).all()[::-1]
            msgs = [{"role": "assistant" if t.role == "scammer" else "user", "content": t.text} for t in hist]
        msgs.append({"role": "user", "content": "Write the scammer's next message."})
        system = prompts.SCAMMER_SIM_SYSTEM.format(scenario=scenario.type, opening=scenario.message)
        return (await self.llm.complete(system, msgs, purpose="scammer_sim", max_tokens=150, temperature=0.8)).strip()

    async def run_simulation(self, scenario: Scenario, turns: int = 4, pace_s: float = 0.0, sid: str | None = None) -> str:
        sid = sid or self.create_session(kind="simulation", channel="web", scenario_id=scenario.id)
        text = scenario.message
        for i in range(turns):
            res = await self.handle_inbound(sid, text)
            if res.action != "reply":
                break
            if pace_s:
                await asyncio.sleep(pace_s)
            try:
                text = await self.scammer_next(sid, scenario)
            except LLMUnavailable:
                break
        with session_scope(self.factory) as db:
            s = db.get(Session, sid)
            if s.status == "active":
                s.status = "closed"
                ledger.append(db, s, "note", {"event": "simulation_complete", "turns": turns})
        self.bus.publish("session_closed", sid, {})
        return sid