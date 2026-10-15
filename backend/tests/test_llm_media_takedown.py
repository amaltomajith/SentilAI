import base64
import io
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from PIL import Image

from sentinel.config import Settings
from sentinel.llm import LLMClient, LLMUnavailable
from sentinel.media import NPCI_ERRORS, forge_screenshot, synthesize_voice, transcribe_voice

IST = timezone(timedelta(hours=5, minutes=30))


def ok(text):
    return {"choices": [{"message": {"content": text}}]}


def settings(**k):
    return Settings(groq_api_key=k.get("groq", ""), sambanova_api_key=k.get("samba", ""), openrouter_api_key=k.get("or_", ""),
                    ollama_base_url="http://ollama.invalid")


async def test_fallback_chain_groq_429_then_sambanova_ok():
    calls = []
    def handler(req):
        calls.append(req.url.host)
        return httpx.Response(429) if "groq" in req.url.host else httpx.Response(200, json=ok("from sambanova"))
    c = LLMClient(settings(groq="g", samba="s"), httpx.MockTransport(handler), backoff_s=0)
    assert await c.complete("sys", [{"role": "user", "content": "hi"}]) == "from sambanova"
    assert c.last.provider == "sambanova" and calls.count("api.groq.com") == 2


async def test_scammer_sim_prefers_sambanova():
    seen = []
    def handler(req):
        seen.append(req.url.host)
        return httpx.Response(200, json=ok("x"))
    c = LLMClient(settings(groq="g", samba="s"), httpx.MockTransport(handler))
    await c.complete("s", [], purpose="scammer_sim")
    assert seen[0] == "api.sambanova.ai"


async def test_no_keys_means_only_ollama_and_total_failure_raises():
    c = LLMClient(settings(), httpx.MockTransport(lambda r: httpx.Response(500)), backoff_s=0)
    assert [p.name for p in c.available()] == ["ollama"]
    with pytest.raises(LLMUnavailable):
        await c.complete("s", [])


async def test_keys_are_sent_only_as_bearer_to_their_own_provider():
    seen = {}
    def handler(req):
        seen[req.url.host] = req.headers.get("authorization")
        return httpx.Response(200, json=ok("x"))
    await LLMClient(settings(groq="GROQKEY"), httpx.MockTransport(handler)).complete("s", [])
    assert seen == {"api.groq.com": "Bearer GROQKEY"}


async def test_bad_key_provider_is_put_on_cooldown_and_skipped():
    hosts = []
    def handler(req):
        hosts.append(req.url.host)
        return httpx.Response(401) if "sambanova" in req.url.host else httpx.Response(200, json=ok("fine"))
    c = LLMClient(settings(groq="g", samba="bad"), httpx.MockTransport(handler), backoff_s=0)
    assert await c.complete("s", [], purpose="scammer_sim") == "fine"
    hosts.clear()
    await c.complete("s", [], purpose="scammer_sim")
    assert "api.sambanova.ai" not in hosts               # not retried during cooldown


async def test_empty_reply_falls_through_to_next_provider():
    def handler(req):
        return httpx.Response(200, json=ok("")) if "groq" in req.url.host else httpx.Response(200, json=ok("real text"))
    c = LLMClient(settings(groq="g", samba="s"), httpx.MockTransport(handler), backoff_s=0)
    assert await c.complete("s", []) == "real text"


def test_forged_screenshot_is_deterministic_and_marked():
    t = datetime(2026, 10, 15, 9, 30, tzinfo=IST)
    a, ma = forge_screenshot("refund.dept@ybl", "500", "U16", now=t)
    b, mb = forge_screenshot("refund.dept@ybl", "500", "U16", now=t)
    assert a == b and ma["sha256"] == mb["sha256"]
    img = Image.open(io.BytesIO(a))
    assert img.size == (720, 1500) and img.info.get("sentinel-forged") == "1"
    c, _ = forge_screenshot("other@ybl", "500", "U16", now=t)
    assert c != a
    with pytest.raises(ValueError):
        forge_screenshot("x@ybl", "1", "NOPE")
    assert "U16" in NPCI_ERRORS


async def test_whisper_original_and_english_translation_via_mock():
    def handler(req):
        if req.url.path.endswith("/transcriptions"):
            return httpx.Response(200, json={"text": "मुझे पैसे भेजो", "language": "hi"})
        return httpx.Response(200, json={"text": "Send me the money"})
    r = await transcribe_voice(b"audio", "v.ogg", "key", transport=httpx.MockTransport(handler))
    assert r == {"original": "मुझे पैसे भेजो", "language": "hi", "english": "Send me the money"}
    with pytest.raises(RuntimeError):
        await transcribe_voice(b"a", "v.ogg", "")


async def test_synthesize_voice_degrades_without_network_or_ffmpeg():
    try:
        out = await synthesize_voice("Kindly wait sir.")
    except Exception as e:  # edge-tts is an online free service; offline CI must not fail the suite
        pytest.skip(f"edge-tts unreachable here: {type(e).__name__}")
    assert out["audio"] and out["mime"] in ("audio/mpeg", "audio/ogg; codecs=opus")


def test_stix_bundle_is_valid_and_patterns_escape_quotes():
    import stix2
    from sentinel.takedown import build_bundle
    from sentinel.db.models import Session
    s = Session(id="abc-123")
    b = build_bundle(s, [("upi", "a'b@ybl"), ("url", "http://x.example/p"), ("domain", "x.example"), ("ipv4", "1.2.3.4"),
                         ("bank_account", "123456789012"), ("phone", "9876543210")], "f" * 64)
    assert b["type"] == "bundle"
    parsed = stix2.parse(b, allow_custom=True)
    inds = [o for o in parsed.objects if o.type == "indicator"]
    assert len(inds) == 6 and any("a\\'b@ybl" in i.pattern for i in inds)
    assert any(o.type == "report" and "f" * 64 in o.description for o in parsed.objects)