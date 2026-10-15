"""Provider-agnostic free-tier LLM client with fallback chain: Groq -> SambaNova -> OpenRouter(free) -> Ollama.
All providers speak the OpenAI chat-completions dialect, so one code path serves all of them."""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field

import httpx

from sentinel.config import Settings, get_settings


class LLMUnavailable(Exception):
    pass


@dataclass
class Provider:
    name: str
    url: str
    model: str
    key: str
    needs_key: bool = True


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int


def build_providers(s: Settings) -> dict[str, Provider]:
    return {
        "groq": Provider("groq", "https://api.groq.com/openai/v1/chat/completions", os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"), s.groq_api_key),
        "sambanova": Provider("sambanova", "https://api.sambanova.ai/v1/chat/completions", os.getenv("SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct"), s.sambanova_api_key),
        "openrouter": Provider("openrouter", "https://openrouter.ai/api/v1/chat/completions", os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"), s.openrouter_api_key),
        "ollama": Provider("ollama", s.ollama_base_url.rstrip("/") + "/v1/chat/completions", os.getenv("OLLAMA_MODEL", "llama3.2"), "", needs_key=False),
    }


ORDER_DEFAULT = ["groq", "sambanova", "openrouter", "ollama"]
ORDER_BY_PURPOSE = {"scammer_sim": ["sambanova", "groq", "openrouter", "ollama"]}


class LLMClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None,
                 backoff_s: float = 0.5, timeout: float = 25.0):
        self.providers = build_providers(settings or get_settings())
        self.transport, self.backoff_s, self.timeout = transport, backoff_s, timeout
        self.last: LLMResult | None = None
        self.disabled_until: dict[str, float] = {}   # provider -> monotonic time; set after 401/403/404 (bad key / retired model)

    def available(self, purpose: str = "") -> list[Provider]:
        order = ORDER_BY_PURPOSE.get(purpose, ORDER_DEFAULT)
        now = time.monotonic()
        return [self.providers[n] for n in order if (self.providers[n].key or not self.providers[n].needs_key)
                and self.disabled_until.get(n, 0) <= now]

    async def complete(self, system: str, messages: list[dict], *, purpose: str = "", max_tokens: int = 150,
                       temperature: float = 0.8) -> str:
        provs = self.available(purpose)
        if not provs:
            raise LLMUnavailable("no LLM provider configured (set GROQ_API_KEY / SAMBANOVA_API_KEY / OPENROUTER_API_KEY or run Ollama)")
        body_msgs = [{"role": "system", "content": system}, *messages]
        errors = []
        for p in provs:
            for attempt in range(2):
                t0 = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as c:
                        r = await c.post(p.url, headers={"Authorization": f"Bearer {p.key}"} if p.key else {},
                                         json={"model": p.model, "messages": body_msgs, "max_tokens": max_tokens, "temperature": temperature})
                    if r.status_code == 429 or r.status_code >= 500:
                        errors.append(f"{p.name}:{r.status_code}")
                        await asyncio.sleep(self.backoff_s * (attempt + 1))
                        continue
                    if r.status_code in (401, 403, 404):
                        self.disabled_until[p.name] = time.monotonic() + 600
                        errors.append(f"{p.name}:{r.status_code}(disabled 10m)")
                        break
                    r.raise_for_status()
                    text = (r.json()["choices"][0]["message"]["content"] or "").strip()
                    if not text:
                        errors.append(f"{p.name}:empty")
                        break
                    self.last = LLMResult(text, p.name, p.model, int((time.perf_counter() - t0) * 1000))
                    return text
                except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                    errors.append(f"{p.name}:{type(e).__name__}")
                    break
        raise LLMUnavailable("all providers failed: " + ", ".join(errors))


@dataclass
class FakeLLM:
    """Scripted LLM for tests/offline demos. `replies` is consumed in order; the last one repeats."""
    replies: list[str] = field(default_factory=lambda: ["Kindly share the UPI ID sir, my app is showing error."])
    calls: list[dict] = field(default_factory=list)
    last: LLMResult | None = None

    async def complete(self, system: str, messages: list[dict], *, purpose: str = "", max_tokens: int = 150, temperature: float = 0.8) -> str:
        self.calls.append({"system": system, "messages": messages, "purpose": purpose})
        text = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        self.last = LLMResult(text, "fake", "fake", 1)
        return text