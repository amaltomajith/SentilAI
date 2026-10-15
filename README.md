# Sentinel

A scam-baiting assistant that lives on **your WhatsApp**. You sign up, tell it a bit about yourself, link your WhatsApp, and paste the number of someone who is scamming you. From then on Sentinel reads and answers **only that number**: it plays a believable version of *you* (no fixed character), keeps the scammer engaged, and collects the payment details they reveal as evidence (UPI IDs, accounts, IFSC codes, phone numbers, links) in a tamper-evident log.

> **The model only writes text. Deterministic code decides everything that matters.**
> **$0 stack:** Clerk (free tier) for sign-in, free LLM tiers (Groq / SambaNova / OpenRouter `:free` / Ollama), Groq Whisper, `edge-tts`, Pillow, RDAP, `ifsc.razorpay.com`, `ip-api.com`, SQLite locally or any free Postgres (e.g. Supabase) in production. Nothing needs a payment method.

## The flow

The public landing page is `/`; the signed-in app lives under `/app`, `/onboarding`, `/practice`, `/connect` and `/live`.

1. **Sign up** (Clerk). Accept the responsible-use terms.
2. **About you.** Name the agent uses, age, what you do, city, languages, how you write, your situation. Each field has a switch: *the agent may mention this*. Private details (real name, employer, address, your number) are never sent to the AI; they are only used to **block** them from ever appearing in a reply.
3. **Practice.** Rehearse against a sample scam (a simulated scammer, or you type as the scammer) using your real profile. A "why it replied that way" view shows the detected scam type, stage, language and the tactic chosen.
4. **Connect.** Link WhatsApp (QR code, or a pairing code if you only have that one phone) and paste the scammer's number.
5. **Live.** Their chat appears in real time. The agent answers only that number, never starts a conversation, never pays, never gives real bank details. Remove the number or unlink and it stops at once.

```
 your WhatsApp ⇄ whatsapp-bridge ──HMAC-signed──▶ FastAPI backend ◀── REST/SSE (Clerk JWT) ── React app
 (one socket per user, no AI)                      │
                                                   ▼
   analyze (scam type · stage · pressure · language) → tactic (playbook + learned outcomes) → draft (LLM, persona from YOUR profile)
        → outbound gate (self-disclosure, jailbreaks, unapproved numbers/links, YOUR protected details) → hash-chained ledger → one approved reply
```

## What makes it trustworthy

| Property | How |
|---|---|
| No persona, but adaptive | The persona is built per user from their profile. A rules-based analyzer reads each scammer message; a Thompson-sampling chooser picks the next tactic from a playbook using what worked before. Opt-in users also contribute **anonymous counters only** (scam type, tactic, successes, trials). This is not model training and not federated learning in the strict sense; see `docs/SAFETY.md`. |
| Your details stay private | Only fields you mark mentionable reach the model. Protected values never do; the gate blocks them (name, surname, employer, address, your number) even if a draft somehow contains them. Positive-control tested. |
| Only the scammer's number | The bridge drops every other chat before it leaves your device; the backend accepts inbound only for numbers *you* added; the send side refuses any other number. Per-user isolation is tested end to end. |
| Never initiates, never pays | Replies exist only as answers to inbound messages. The agent can offer only a generated decoy UPI id. |
| Grounded evidence | An IOC is stored only if its exact text appears in the scammer's message and is not our own decoy. |
| Tamper-evident log | SHA-256 chain over every turn, IOC, tool call and canary hit; `python -m sentinel.verify proof.json` re-checks it offline; forensic PDF prints the chain head. |
| Guardrailed replies | Deterministic gate: AI self-disclosure, jailbreak compliance, code, unapproved URLs/numbers, protected details, length, then repair, then a stall template. Benign messages are triaged safe and not engaged. |
| Extras | Forged "payment failed" screenshots (Pillow), voice notes (Groq Whisper in, `edge-tts` out), canary links that fingerprint scammers who open them (crawler previews never alert), OSINT enrichment behind an SSRF guard, a syndicate graph, STIX 2.1 takedown drafts (**dry-run only**), all exposed as MCP tools. |

## Quick start (local)

Prereqs: Python 3.11+, Node 20.12+ (22 recommended), optional `ffmpeg` for aged voice notes. Free keys: Groq (console.groq.com), Clerk (clerk.com).

```powershell
# 1. backend            (Windows PowerShell 5.1 has no &&, so one command per line)
cd backend
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy ..\.env.example .env          # then fill GROQ_API_KEY, BRIDGE_SHARED_SECRET, CLERK_ISSUER
.venv\Scripts\python -m sentinel.api            # http://127.0.0.1:8000

# 2. app (new terminal, repo root)
npm install
copy .env.example .env.local       # fill VITE_CLERK_PUBLISHABLE_KEY
npm run dev                        # http://localhost:5173

# 3. WhatsApp connector (new terminal)
cd whatsapp-bridge
copy .env.example .env             # same BRIDGE_SHARED_SECRET as the backend
npm install
npm run dev
```

**Authentication.** Create a free application at clerk.com, enable Email (or Google), then:
`VITE_CLERK_PUBLISHABLE_KEY` goes in `.env.local`; `CLERK_ISSUER` (the "Frontend API URL", e.g. `https://xyz.clerk.accounts.dev`) goes in `backend/.env`. Add `http://localhost:5173` under authorized origins if you use `CLERK_AUTHORIZED_PARTIES`. The backend verifies Clerk session tokens against Clerk's public keys; no Clerk secret key is stored anywhere.
*No Clerk yet?* For local testing only, set `DEV_AUTH=1` (backend) and `VITE_DEV_AUTH=1` (frontend) to sign in with any test name. The backend prints a warning; never deploy that way.

**Database.** SQLite by default. For Postgres (e.g. a free Supabase project): set `DATABASE_URL=postgresql+psycopg://...`, `pip install psycopg[binary]`, run `alembic upgrade head` in `backend/`.

**Real canary links** need a public URL, e.g. `cloudflared tunnel --url http://localhost:8000` (free); set `PUBLIC_BASE_URL=<that url>` and `TRUSTED_PROXY=1`.

**Use the tools from Claude Desktop / Claude Code (MCP):** `{"command": "<repo>/backend/.venv/Scripts/python.exe", "args": ["-m", "sentinel.mcp"], "cwd": "<repo>/backend"}`.

## Tests and evals
```bash
cd backend && python -m pytest -q      # offline: fixtures, no keys, no network
npm test                               # frontend
cd whatsapp-bridge && npm test         # includes a cross-language HMAC vector against the Python signer
cd backend && python -m scripts.bench  # regenerates docs/BENCHMARKS.md (live parts need a Groq key)
```
**Every negative-property guard has a positive control**: the test first proves the failure happens with the guard off (a leaky draft reveals the real name; a naive verifier accepts a foreign-issuer token; another user's number is sent from the wrong account), then that the guard stops it. Isolation tests prove user B can never read, change or message through user A's data. Measured numbers: `docs/BENCHMARKS.md`. The corpora are small, so they are regression baselines, not proof of robustness.

## Honest limitations
- **Single machine, small scale.** Link state lives in memory and each linked WhatsApp costs a socket, so the number of linked accounts is capped (`MAX_LINKED_ACCOUNTS`, default 5). An always-on *free* host for the WhatsApp connector is the weak link (free tiers sleep or need a card), so run it on a machine that stays on.
- **WhatsApp does not allow unofficial clients (Baileys).** A linked account can be restricted; say so to users and prefer a secondary number.
- **The "learning" is a bandit over a hand-written playbook**, rewarded by whether the scammer revealed something new. It starts from a sensible default order and improves with data; it cannot invent new tactics.
- A hash chain proves consistency, not provenance. Canary telemetry only catches scammers who open links we send. Voice replies are unit-tested but not verified on a real account; `edge-tts` is an unofficial endpoint. Free-tier model names and limits change.
- Engaging real people has legal and ethical limits. Read `docs/SAFETY.md`.

Design system and rules: `docs/DESIGN.md`. History and design rationale: `PROJECT_CONTEXT.md`.