# Architecture

```
React app (Clerk sign-in) ──REST + SSE, Bearer Clerk JWT──▶ FastAPI (backend/sentinel)
                                                              │  verifies JWT (JWKS) → user id; every query filtered by user id
WhatsApp ⇄ whatsapp-bridge (one Baileys socket per user) ─HMAC─┘  POST /bridge/sync · /bridge/inbound · /bridge/outbox/next|ack · /bridge/media
```

**Per inbound message** (`orchestrator/engine.py`): per-session lock and dedupe → record scammer turn (commit) → triage until engaged (rules, LLM only for ties; benign/uncertain halts, no reply) → ground IOCs (literal substring, not a decoy) + enrich → exchange limit → `strategy.analyze` (scam type, stage, pressure, language) → settle the previous tactic's outcome (`bandit.record`) → `select_tactic` (playbook candidates, Thompson sampling, cold-start = playbook order) → persona from the user's profile (`persona.build`) → draft (LLM) → gate (`gate.run_gate` with approved values and the user's protected terms) → canary link / forged screenshot added by code → persist + ledger → one outbox job.

| Module | Role |
|---|---|
| `auth.py` | Clerk JWT verification (RS256, issuer, expiry, authorised origin); fails closed |
| `db/` | SQLAlchemy 2 models; SQLite for dev/tests, Postgres via `DATABASE_URL` + Alembic (`backend/alembic`) |
| `orchestrator/persona.py` | Profile validation and persona prompt; protected terms; decoy UPI |
| `orchestrator/strategy.py`, `ploys.py`, `bandit.py` | Analysis, playbook, outcome learning |
| `gate/` | Outbound policy gate (+ inbound injection detector, stall fallbacks) |
| `grounding/` | The only IOC extractor and literal-substring verifier |
| `ledger/` | SHA-256 chain per session, proof export/verify |
| `mcp/` | Tool registry (`select_tactic`, `select_ploy`, enrichment, screenshot, voice, canary) served over stdio/HTTP |
| `media/`, `enrich/`, `canary/`, `graph/`, `takedown/`, `security/`, `report.py` | Screenshots/voice, OSINT, canary links, attribution rings, STIX drafts (dry-run), SSRF guard + HMAC, forensic PDF |

**Tenancy.** `Session.user_id`, `TargetNumber(user_id, number)`, `BridgeOutbox.user_id`, `Profile`, `User`. Routes take `Depends(current_user)`; foreign resources answer 404. SSE events carry the owner (`EventBus.owner`) and are filtered per connection. WhatsApp link state and queued commands are in memory per user (single process; move to the database before running more than one backend instance).

**Bridge.** `LinkManager` holds one `WhatsAppLink` per user (credentials in `wa_session/<user id>/`, ids validated against path traversal). It syncs states every ~3 s, receives per-user commands (`link`, `pairing_code`, `logout`) and target lists, forwards inbound only for that user's targets, and asks the backend only for jobs of currently connected users.