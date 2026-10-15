"""MCP server: the exclusive tool surface for active defense. Usable by Sentinel's orchestrator (same registry,
same code path) and by external MCP clients such as Claude Desktop / Claude Code.

  stdio:  python -m sentinel.mcp
  http:   python -m sentinel.mcp --http   (streamable HTTP)
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from sentinel.config import Settings, get_settings
from sentinel.db import make_engine, make_session_factory, session_scope
from sentinel.mcp.tools import REGISTRY, ToolContext, call_tool


def build_server(factory=None, settings: Settings | None = None, fetch=None) -> MCPServer:
    settings = settings or get_settings()
    factory = factory or make_session_factory(make_engine(settings.database_url))
    mcp = MCPServer("sentinel")

    async def run(name: str, args: dict, sid: str | None = None) -> dict:
        with session_scope(factory) as db:
            kw = {"fetch": fetch} if fetch else {}
            return await call_tool(ToolContext(db=db, settings=settings, **kw), name, args, session_id=sid)

    @mcp.tool(description=REGISTRY["select_ploy"].description)
    async def select_ploy(session_id: str, scammer_asked_screenshot: bool = False) -> dict:
        return await run("select_ploy", {"session_id": session_id, "scammer_asked_screenshot": scammer_asked_screenshot}, session_id)

    @mcp.tool(description=REGISTRY["select_tactic"].description)
    async def select_tactic(session_id: str, scam_type: str = "other", scammer_asked_screenshot: bool = False) -> dict:
        return await run("select_tactic", {"session_id": session_id, "scam_type": scam_type, "scammer_asked_screenshot": scammer_asked_screenshot}, session_id)

    @mcp.tool(description=REGISTRY["get_session_iocs"].description)
    async def get_session_iocs(session_id: str) -> dict:
        return await run("get_session_iocs", {"session_id": session_id}, session_id)

    @mcp.tool(description=REGISTRY["enrich_upi"].description)
    async def enrich_upi(vpa: str) -> dict:
        return await run("enrich_upi", {"vpa": vpa})

    @mcp.tool(description=REGISTRY["enrich_ifsc"].description)
    async def enrich_ifsc(ifsc: str) -> dict:
        return await run("enrich_ifsc", {"ifsc": ifsc})

    @mcp.tool(description=REGISTRY["enrich_domain"].description)
    async def enrich_domain(domain: str) -> dict:
        return await run("enrich_domain", {"domain": domain})

    @mcp.tool(description=REGISTRY["mint_canary"].description)
    async def mint_canary(session_id: str, kind: str = "receipt") -> dict:
        return await run("mint_canary", {"session_id": session_id, "kind": kind}, session_id)

    @mcp.tool(description=REGISTRY["forge_screenshot"].description)
    async def forge_screenshot(session_id: str, vpa: str, amount: str, error_code: str = "U16") -> dict:
        return await run("forge_screenshot", {"session_id": session_id, "vpa": vpa, "amount": amount, "error_code": error_code}, session_id)

    @mcp.tool(description=REGISTRY["transcribe_voice"].description)
    async def transcribe_voice(audio_b64: str, filename: str = "voice.ogg") -> dict:
        return await run("transcribe_voice", {"audio_b64": audio_b64, "filename": filename})

    @mcp.tool(description=REGISTRY["synthesize_voice"].description)
    async def synthesize_voice(session_id: str, text: str) -> dict:
        return await run("synthesize_voice", {"session_id": session_id, "text": text}, session_id)

    return mcp