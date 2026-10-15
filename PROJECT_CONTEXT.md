# Sentinel (repo `SentilAI`): project context for agents

> Read this first. It lets an agent work on the repo without outside context. History: v1 was a browser-orchestrated Lovable prototype (replaced; see §10). v2 was a single-operator honeypot with a fixed "Ramesh Uncle" persona. **The current product is a multi-user WhatsApp scam-baiting service** with no fixed persona.

## 1. What it is
A person signs up (Clerk), describes themselves (profile), rehearses on a sample scam, links their own WhatsApp, and pastes **one scammer number**. Sentinel then reads and answers **only that number**, adaptively, playing a believable version of the user, to make the scammer reveal **IOCs** (UPI IDs, accounts, IFSC, phones, URLs). Around that: MCP tools (forged payment-failure screenshots, voice, OSINT enrichment, canary links), a tamper-evident ledger, a syndicate graph and an approval-gated (dry-run) takedown queue.

**Principle: the model only writes text; deterministic code decides everything that matters.**
**HARD CONSTRAINT: $0 stack.** Clerk free tier, free LLM tiers (Groq, SambaNova, OpenRouter `:free`, Ollama), Groq Whisper, `edge-tts`, Pillow, RDAP, `ifsc.razorpay.com`, `ip-api.com`, SQLite (prod: free Postgres via `DATABASE_URL`). Never add a paid API, a service needing a card, or paid image generation.

## 2. Layout
```
backend/                Python 3.11+ FastAPI (package `sentinel`), venv in backend/.venv, Alembic in backend/alembic
  sentinel/auth.py          Clerk JWT verification (JWKS, RS256, issuer/exp/azp); fail-closed
  sentinel/config.py        env settings (no secrets in code)
  sentinel/db/              SQLAlchemy 2 models (User, Profile, TargetNumber, Session.user_id, TacticStat, ...); SQLite auto-create, Postgres via alembic
  sentinel/ledger/          SHA-256 hash chain per session; export_proof/verify_proof; `python -m sentinel.verify`
  sentinel/grounding/       THE ONLY IOC extractor + literal-substring verifier (+ decoy exclusion)
  sentinel/gate/            outbound policy gate (+ inbound injection detector, stall fallbacks); `protected` terms = user's real details
  sentinel/llm/             provider chain Groq→SambaNova→OpenRouter→Ollama, cooldown on 401/403/404, FakeLLM for tests
  sentinel/orchestrator/    engine.py (pipeline), persona.py (profile → persona, validation, decoy UPI), strategy.py (analysis, language),
                            ploys.py (playbook), bandit.py (Thompson sampling + stats), triage.py, prompts.py (scammer-sim prompt only), scenarios.py
  sentinel/mcp/             tools.py (registry + call_tool tracing), server.py (MCPServer), `python -m sentinel.mcp`
  sentinel/media|enrich|canary|graph|takedown|security|report.py   screenshots/voice, OSINT, canary links, rings, STIX drafts, SSRF guard + HMAC, PDF
  sentinel/api/app.py       REST + SSE (per-user) + public canary routes + HMAC bridge routes
  scripts/bench.py          writes docs/BENCHMARKS.md        tests/   pytest, offline
whatsapp-bridge/        TypeScript Baileys transport, ONE process, one socket PER USER (LinkManager). No AI, no HTTP listener.
src/                    React 18 + Vite + Tailwind + shadcn/ui: lib/auth.tsx (Clerk or dev auth), pages Landing (public, /), Onboarding/Practice/Connect/Live (app, /app routes), design rules in docs/DESIGN.md
docs/                   ARCHITECTURE.md, SAFETY.md, DESIGN.md, BENCHMARKS.md
```

## 3. Request pipeline (`orchestrator/engine.py: Engine.handle_inbound`)
Per-session lock + dedupe by `inbound_id` → record scammer turn and **commit** (never hold a DB write lock across an `await`) → triage until engaged (benign/uncertain ⇒ halted, no reply) → ground IOCs (literal in the inbound text, not a decoy) + enrich → exchange limit → `strategy.analyze` → settle the previous tactic (`Session.pending_tactic`, `bandit.record`: success = a new IOC of a kind the tactic targeted) → MCP tool `select_tactic` (playbook order = cold-start default, Thompson sampling once data exists) → `persona.build(profile)` → draft (injection ⇒ model not consulted; LLM down ⇒ stall template) → `run_gate(draft, approved, protected=...)` → canary link and forged screenshot appended **by code** → persist + ledger + SSE → one `BridgeOutbox` job (WhatsApp channel).

## 4. Multi-user model
- Identity = Clerk `sub`. `current_user` dependency on every `/api` route; every query filters by `user_id`; other users' resources answer **404**. `Session.user_id == ""` rows are never served.
- Per user: `Profile` (data + `share` flags), `User.consent_at`, `TargetNumber(user_id, number)`, WhatsApp link state (in memory, `wa_state[user]`), queued bridge commands (`wa_cmds`).
- SSE: `EventBus.owner[session_id]` and `ev["user_id"]`; the stream yields only the caller's events.
- Bridge protocol (HMAC): `POST /bridge/sync` (accounts → commands + targets), `POST /bridge/inbound` (`user_id` required; accepted only for that user's targets), `POST /bridge/outbox/next` (body lists connected users; only their jobs are leased), `POST /bridge/outbox/{id}/ack`, `GET /bridge/media/{sha}`.
- Limits: `MAX_LINKED_ACCOUNTS`, `MAX_TARGETS_PER_USER`, `MAX_EXCHANGES`. Consent required for linking/targets (403 otherwise).
- Dev auth (`DEV_AUTH=1` backend, `VITE_DEV_AUTH=1` frontend) accepts `Bearer dev:<name>`; local testing only.

## 5. Privacy rules (do not weaken; see docs/SAFETY.md)
Protected profile values (full name, employer, address, own phone, anything the user switched off) are **never put in a prompt**; the gate blocks them in drafts. The profile validator refuses bank/card/UPI/OTP/password/ID-looking values. The agent only ever offers a generated decoy UPI. The agent never initiates. Takedown dispatch is dry-run only. Secrets only in untracked `.env` files; `wa_session*/` holds credentials.

## 6. Running
See README "Quick start". Tests: `cd backend && python -m pytest -q`; `npm test`; `cd whatsapp-bridge && npm test && npm run typecheck`; benchmarks `python -m scripts.bench`. Windows PowerShell 5.1 has no `&&`. Port 8080 is often held by Oracle; the dashboard uses 5173 with `strictPort`. `git` needs `-c safe.directory=*` on this drive.

## 7. Test philosophy (do not weaken)
Every negative-property guard has a **positive control** that first proves the failure occurs with the guard off: outbound gate (`test_gate_triage_ploys.py`, `test_engine.py`), protected-details leak (`test_persona_profile.py`), Clerk verifier vs foreign issuer (`test_auth.py`), tenant isolation (`test_api.py`), bridge send-side guard and multi-user routing (`whatsapp-bridge/test`), canary classifier, SSRF guard. Add a positive control with any new guard.

## 8. Conventions
Typed Python, small modules; async DB code must `commit()` before awaiting slow I/O. Prompts live in `persona.py` (victim side) and `prompts.py` (scammer simulator). IOC extraction lives only in `grounding/`. LLM calls only via `LLMClient` (`FakeLLM` in tests). New free APIs get an injectable `fetch` and an offline fixture. TS strict; UI monospace terminal aesthetic.

## 9. Known limitations
In-memory WhatsApp link state (single backend process); capped linked accounts; no free always-on host for the bridge; Baileys is unofficial (ban risk); the bandit learns only over a hand-written playbook; "federated" = opt-in anonymous counters, not training; voice replies not verified on a real account; canary links need a public URL; small test corpora; SambaNova/Groq model names and limits change.

## 10. v1 mistakes that must not return
Browser-side orchestration; fabricated analysis JSON; triplicated backend/regexes; stateful `/g` regexes with `.test()`; hardcoded keys / tracked `.env` / committed WhatsApp sessions; a bridge that calls the LLM itself while the UI calls it too; unauthenticated bridge port; benign messages forced into scammer roleplay; DB write transactions held across network awaits; a fixed persona; trusting any non-empty token on the login screen.