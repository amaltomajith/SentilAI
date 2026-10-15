"""The tool surface. Every capability the orchestrator uses lives here and is exposed verbatim by the MCP server.
`call_tool` is the single entry point: it times the call, persists a ToolTrace and a ledger event."""
from __future__ import annotations

import base64
import hashlib
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select

from sentinel import canary as canary_mod
from sentinel import enrich, ledger, media
from sentinel.config import Settings
from sentinel.db.models import HoneyToken, Ioc, Session, ToolTrace, Turn, User
from sentinel.gate import run_gate
from sentinel.orchestrator import bandit
from sentinel.orchestrator.ploys import PLOYS, missing_targets, ploy_order, select_ploy
from sentinel.security import safe_get_json

MEDIA_DIR = Path(__file__).resolve().parents[2] / "data" / "media"


@dataclass
class ToolContext:
    db: Any                       # sqlalchemy Session
    settings: Settings
    fetch: Callable = safe_get_json
    http_transport: Any = None
    allow_network: bool = True
    extras: dict = field(default_factory=dict)


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, schema: dict):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, schema, fn)
        return fn
    return deco


def _sess(ctx: ToolContext, sid: str) -> Session:
    s = ctx.db.get(Session, sid)
    if s is None:
        raise KeyError(f"unknown session {sid}")
    return s


def session_iocs(ctx: ToolContext, sid: str) -> list[Ioc]:
    return list(ctx.db.scalars(select(Ioc).where(Ioc.session_id == sid).order_by(Ioc.created_at)))


@tool("select_ploy", "Pick the agent's next stalling tactic deterministically from captured vs missing IOCs.",
      {"type": "object", "properties": {"session_id": {"type": "string"}, "scammer_asked_screenshot": {"type": "boolean"}}, "required": ["session_id"]})
async def t_select_ploy(ctx: ToolContext, session_id: str, scammer_asked_screenshot: bool = False, last_ploy: str = "") -> dict:
    s = _sess(ctx, session_id)
    captured = {i.kind for i in session_iocs(ctx, session_id)}
    p = select_ploy(captured, s.exchange_count, last_ploy, scammer_asked_screenshot)
    return {"ploy_id": p.id, "targets": list(p.targets), "instruction": p.instruction,
            "captured": sorted(captured), "missing": missing_targets(captured)}


@tool("select_tactic", "Pick the agent's next tactic: playbook candidates for the scam type, chosen by Thompson sampling over learned outcomes.",
      {"type": "object", "properties": {"session_id": {"type": "string"}, "scam_type": {"type": "string"}, "scammer_asked_screenshot": {"type": "boolean"}}, "required": ["session_id"]})
async def t_select_tactic(ctx: ToolContext, session_id: str, scam_type: str = "other", scammer_asked_screenshot: bool = False, last_ploy: str = "") -> dict:
    s = _sess(ctx, session_id)
    captured = {i.kind for i in session_iocs(ctx, session_id)}
    scores: dict[str, float] = {}
    if s.exchange_count >= 10:
        p = PLOYS["wind_down"]
    elif scammer_asked_screenshot:
        p = PLOYS["screenshot_error"]
    else:
        full = ploy_order(captured, s.exchange_count, scam_type)
        order = [x for x in full if x != last_ploy] or full
        u = ctx.db.get(User, s.user_id) if s.user_id else None
        stats = bandit.load_stats(ctx.db, scam_type, s.user_id, bool(u and u.collective_opt_in)) if s.user_id else {}
        choice, scores = bandit.choose(order[:5], stats, random.Random(f"{session_id}:{s.exchange_count}"))
        p = PLOYS[choice]
    return {"ploy_id": p.id, "targets": list(p.targets), "instruction": p.instruction, "scam_type": scam_type,
            "captured": sorted(captured), "missing": missing_targets(captured), "candidates": scores}


@tool("get_session_iocs", "List verified (literal-grounded) IOCs captured in a session.",
      {"type": "object", "properties": {"session_id": {"type": "string"}}, "required": ["session_id"]})
async def t_get_iocs(ctx: ToolContext, session_id: str) -> dict:
    return {"iocs": [{"kind": i.kind, "value": i.value, "enrichment": i.enrichment} for i in session_iocs(ctx, session_id)]}


@tool("enrich_upi", "Map a UPI VPA's PSP handle to the app and issuing bank (offline table).",
      {"type": "object", "properties": {"vpa": {"type": "string"}}, "required": ["vpa"]})
async def t_enrich_upi(ctx: ToolContext, vpa: str) -> dict:
    return enrich.enrich_upi(vpa)


@tool("enrich_ifsc", "Resolve an IFSC to bank/branch/city (offline prefix table, ifsc.razorpay.com when reachable).",
      {"type": "object", "properties": {"ifsc": {"type": "string"}}, "required": ["ifsc"]})
async def t_enrich_ifsc(ctx: ToolContext, ifsc: str) -> dict:
    return await enrich.enrich_ifsc(ifsc, fetch=ctx.fetch)


@tool("enrich_domain", "RDAP lookup (registrar, registration date, abuse contact) behind an SSRF guard.",
      {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]})
async def t_enrich_domain(ctx: ToolContext, domain: str) -> dict:
    return await enrich.enrich_domain(domain, fetch=ctx.fetch)


@tool("mint_canary", "Mint a disguised receipt/KYC canary URL that fingerprints whoever opens it (bots get OpenGraph only).",
      {"type": "object", "properties": {"session_id": {"type": "string"}, "kind": {"type": "string", "enum": ["receipt", "kyc"]}}, "required": ["session_id"]})
async def t_mint_canary(ctx: ToolContext, session_id: str, kind: str = "receipt") -> dict:
    return canary_mod.mint(ctx.db, _sess(ctx, session_id), kind, ctx.settings.public_base_url)


@tool("forge_screenshot", "Render a realistic UPI 'payment failed' screen for a VPA/amount the scammer supplied (Pillow, zero tokens).",
      {"type": "object", "properties": {"session_id": {"type": "string"}, "vpa": {"type": "string"}, "amount": {"type": "string"},
                                       "error_code": {"type": "string"}}, "required": ["session_id", "vpa", "amount"]})
async def t_forge(ctx: ToolContext, session_id: str, vpa: str, amount: str, error_code: str = "U16") -> dict:
    grounded = {i.value for i in session_iocs(ctx, session_id) if i.kind in ("upi", "bank_account")}
    if vpa not in grounded:
        raise ValueError("refusing to forge a screen for a payee that is not a verified scammer IOC of this session")
    if not re.fullmatch(r"\d{1,7}", amount):
        raise ValueError("amount must be 1-7 digits")
    data, meta = media.forge_screenshot(vpa, amount, error_code)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    path = MEDIA_DIR / f"{meta['sha256']}.png"
    path.write_bytes(data)
    return {**meta, "path": str(path), "mime": "image/png"}


@tool("transcribe_voice", "Transcribe a scammer voice note with Groq Whisper (free tier): original-language text + English.",
      {"type": "object", "properties": {"audio_b64": {"type": "string"}, "filename": {"type": "string"}}, "required": ["audio_b64"]})
async def t_transcribe(ctx: ToolContext, audio_b64: str, filename: str = "voice.ogg") -> dict:
    return await media.transcribe_voice(base64.b64decode(audio_b64), filename, ctx.settings.groq_api_key, transport=ctx.http_transport)


@tool("synthesize_voice", "Speak a (gate-approved) reply in an elderly Indian-English voice via edge-tts, aged with ffmpeg if present.",
      {"type": "object", "properties": {"session_id": {"type": "string"}, "text": {"type": "string"}}, "required": ["session_id", "text"]})
async def t_synth(ctx: ToolContext, session_id: str, text: str) -> dict:
    approved = {i.value for i in session_iocs(ctx, session_id)} | {h.value for h in ctx.db.scalars(select(HoneyToken))}
    g = run_gate(text, approved, seed=session_id)  # the voice channel gets the same gate as text
    out = await media.synthesize_voice(g.final)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(out["audio"]).hexdigest()
    ext = "ogg" if out["ptt"] else "mp3"
    path = MEDIA_DIR / f"{sha}.{ext}"
    path.write_bytes(out["audio"])
    return {"sha256": sha, "path": str(path), "mime": out["mime"], "ptt": out["ptt"], "aged": out["aged"], "note": out["note"], "text": g.final}


async def call_tool(ctx: ToolContext, name: str, args: dict, *, session_id: str | None = None, trace: bool = True) -> dict:
    t = REGISTRY[name]
    t0 = time.perf_counter()
    ok, result = 1, {}
    try:
        result = await t.fn(ctx, **args)
        return result
    except Exception as e:
        ok, result = 0, {"error": f"{type(e).__name__}: {e}"[:300]}
        raise
    finally:
        if trace and session_id:
            sess = ctx.db.get(Session, session_id)
            if sess is not None:
                safe_args = {k: (v if k != "audio_b64" else f"<{len(v)} b64 chars>") for k, v in args.items()}
                ms = int((time.perf_counter() - t0) * 1000)
                ev = ledger.append(ctx.db, sess, "tool_trace", {"tool": name, "args": safe_args, "ok": ok, "result_keys": sorted(result.keys())})
                ctx.db.add(ToolTrace(session_id=session_id, turn_seq=sess.exchange_count, tool=name, args=safe_args,
                                     result={k: v for k, v in result.items() if k != "audio"}, ok=ok, latency_ms=ms, event_hash=ev.hash))
                ctx.db.flush()