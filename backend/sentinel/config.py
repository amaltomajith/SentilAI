"""Central settings. Everything comes from env vars (see /.env.example). No secret is ever hardcoded."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///./data/sentinel.db"))
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    sambanova_api_key: str = field(default_factory=lambda: _env("SAMBANOVA_API_KEY"))
    openrouter_api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY"))
    ollama_base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))
    bridge_shared_secret: str = field(default_factory=lambda: _env("BRIDGE_SHARED_SECRET"))
    clerk_issuer: str = field(default_factory=lambda: _env("CLERK_ISSUER").rstrip("/"))               # e.g. https://xxx.clerk.accounts.dev
    clerk_jwks_url: str = field(default_factory=lambda: _env("CLERK_JWKS_URL"))                       # default: <issuer>/.well-known/jwks.json
    clerk_authorized_parties: str = field(default_factory=lambda: _env("CLERK_AUTHORIZED_PARTIES", "http://localhost:5173"))
    dev_auth: bool = field(default_factory=lambda: _env("DEV_AUTH", "0") == "1")                # local testing only: accepts 'Bearer dev:<name>' instead of Clerk
    session_enc_key: str = field(default_factory=lambda: _env("SESSION_ENC_KEY"))                    # enables the encrypted WhatsApp auth store (AUTH_STORE=db on the bridge)
    max_linked_accounts: int = field(default_factory=lambda: int(_env("MAX_LINKED_ACCOUNTS", "5")))
    max_targets_per_user: int = field(default_factory=lambda: int(_env("MAX_TARGETS_PER_USER", "3")))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://localhost:8000"))
    takedown_mode: str = field(default_factory=lambda: _env("TAKEDOWN_MODE", "dry_run"))
    trusted_proxy: bool = field(default_factory=lambda: _env("TRUSTED_PROXY", "0") == "1")
    cors_origins: str = field(default_factory=lambda: _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    max_exchanges: int = field(default_factory=lambda: int(_env("MAX_EXCHANGES", "12")))
    # Practice sessions (AI scammer simulations and "I'll type as the scammer") must not teach the tactic learner.
    # Bug fix, ON by default; set SENTINEL_BANDIT_EXCLUDE_PRACTICE=0 to restore the old behaviour (learn from every session).
    bandit_exclude_practice: bool = field(default_factory=lambda: _env("SENTINEL_BANDIT_EXCLUDE_PRACTICE", "1") == "1")
    # Shadow tactic policy: "" (off, default) | "pooled" | "backoff". Computes and logs what that policy WOULD pick next to the
    # live choice (ToolTrace + ledger); it never changes the live choice. See eval/reports/bandit_sim.md.
    bandit_shadow_policy: str = field(default_factory=lambda: _env("SENTINEL_BANDIT_SHADOW_POLICY", "").strip().lower())
    # IOC extractor v2 (toll-free / reference-number traps, scheme-less links, spaced UPI, Indic digits). OFF by default;
    # judged in eval/reports/ioc_v2.md. Read once at start-up.
    grounding_v2: bool = field(default_factory=lambda: _env("SENTINEL_GROUNDING_V2", "0") == "1")


def get_settings() -> Settings:
    return Settings()
