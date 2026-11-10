# Sentinel: data and ML extension plan

_Status: proposal awaiting approval (2026-11-10). Nothing here is built. All numbers come from commands named in section 2._


## 1. Facts check

| Note | Status | Evidence |
|---|---|---|
| Python 3.11 | **CHANGED** | `pyproject.toml` needs >=3.11; production image is `python:3.12-slim` (`Dockerfile`), CI uses 3.12, local venv is 3.13.11 |
| FastAPI, SQLAlchemy 2, Alembic, SSE | VERIFIED | `pyproject.toml`; `alembic/versions/0001,0002`; `api/app.py:336` (`text/event-stream`) |
| PostgreSQL (Supabase) or SQLite | VERIFIED (code) / FROM DOCS (Supabase) | `config.py:19` (SQLite default), `db/__init__.py:15` (Postgres URL); Supabase is in `PROJECT_CONTEXT.md` §0 |
| Bridge: Node + TS + Baileys, HMAC to the API | VERIFIED | `whatsapp-bridge/package.json` (`@whiskeysockets/baileys`, typescript), `src/signer.ts:7` (HMAC-SHA256) |
| One socket per user | FROM DOCS | `docs/ARCHITECTURE.md` (LinkManager). I did not read `whatsapp.ts` |
| React, Vite, Clerk | VERIFIED | `package.json` (react 18, vite 5, @clerk/clerk-react) |
| Render backend, Cloudflare Pages frontend, $0 | VERIFIED (Render `plan: free` in `render.yaml`) / FROM DOCS (Pages, $0) | `PROJECT_CONTEXT.md` §0 |
| Message flow | VERIFIED, with detail | `orchestrator/engine.py:123-287`: lock, dedupe, record turn, triage (only until the session is engaged; benign or uncertain halts), ground IOCs and enrich, exchange cap, `strategy.analyze`, score the previous tactic, `select_tactic`, draft, gate, canary or screenshot added by code, voice, persist, outbox. Streaming goes through `EventBus` |
| IOCs kept only if literal | VERIFIED | `grounding/__init__.py:70-89`; honey tokens (decoys) are also rejected |
| Playbook cold start, then Thompson sampling | VERIFIED, **already contextual** | `bandit.py:29-39`, `mcp/tools.py:77-95`. Counters are keyed by `(scope, scam_type, tactic)` (`db/models.py:193`), so **per-scam-type posteriors already exist**. Candidates are the top 5 of `ploy_order(captured, turn, scam_type)`. Screenshot and wind-down overrides skip the bandit |
| Success = next message reveals a new IOC of the targeted kind | **CHANGED** (detail) | `engine.py:208-213`: for tactics with **no** target (`ask_beneficiary_name`, `card_ready_stall`, `screenshot_error`, `wind_down`), **any** new IOC counts as success. Override tactics are scored too. Scoring happens only for sessions with a `user_id` |
| Hash-chain ledger | VERIFIED | `ledger/__init__.py:25-30` (canonical JSON, SHA-256 chain), `tests/test_ledger_and_grounding.py` |
| Syndicate graph across sessions | **CHANGED** | `graph/__init__.py` exists (weighted session-artifact graph, connected components, confidence). But `/api/graph` calls `attribution(db, uid)` (`app.py:339-342`), so it links **only one user's own sessions**, never across users |
| STIX drafts, approval-gated dry-run takedowns, PDF, traced MCP tools | VERIFIED | `takedown/__init__.py` (stix2, `approve`, dry-run only), `report.py` (fpdf), `mcp/tools.py:164-183` (ToolTrace and ledger event on every call) |
| Tenant isolation, 404 for other users' data | VERIFIED | `tests/test_api.py:94-99` |
| "Federated" = opt-in anonymous counters | VERIFIED | `bandit.py:1-6, 42-50`: with `User.collective_opt_in`, the same `(scam_type, tactic, successes, trials)` row is added under scope `"*"`, with no user id and no text. It is read back at weight 0.5. **NOT FOUND:** any API or UI that shows these counters |
| Known limits | FROM DOCS + VERIFIED | `PROJECT_CONTEXT.md` §9. Small corpora confirmed: 4 scam and 3 benign triage fixtures, about one multi-IOC grounding message |
| Positive-control test philosophy | VERIFIED | `test_gate_triage_ploys.py:39`, `test_strategy_bandit.py:56-74`, `PROJECT_CONTEXT.md` §7 |

**New findings from the code (not in your notes):**
- **F1. Practice runs train the real learner.** `/api/simulations` creates a session with the user's id (`app.py:308`). The engine scores tactics without checking `Session.kind` (`engine.py:208`). So outcomes against Sentinel's own LLM scammer go into the user's counters, and into the shared `"*"` counters if the user opted in. Found by reading; no test covers it.
- **F2.** There are no labelled datasets and no evaluation scripts apart from `scripts/bench.py`. Its bandit check is one toy setup: one context, one tactic planted to win at 70% against 10%, 600 episodes, seed 7.
- **F3. Quick probes, not measurements** (8 made-up strings): `extract_candidates` missed scheme-less URLs (`sbi-update.com/kyc`, `www.fake-kyc.in`), a spaced UPI (`name @ ybl`) and Devanagari digits.
- **F4.** All semi-structured columns use the generic `JSON` type (`models.py:7`), which is `json` on Postgres, not `jsonb`. No code queries inside them (grep for JSON operators found nothing).
- **F5.** The LLM is called for triage only when the rules say "uncertain", and only until the session is engaged (`engine.py:156`, `triage.py:57`). Users name the scammer's number themselves, so these calls are rare.

## 2. Baseline (run 2026-11-10, offline copy of `backend/`, Python 3.13.11)

| Command | Result |
|---|---|
| `python -m pytest --collect-only -q` | 174 collected (api 26, auth 12, auth_store 7, canary_graph 12, engine 17, gate_triage_ploys 18, ledger_grounding 13, llm_media_takedown 10, migrations 1, persona_profile 15, security_enrich 28, strategy_bandit 15) |
| `python -m pytest -q` | 174 passed, 1 warning (Alembic deprecation), 19.5 s |
| `python -m scripts.bench` (offline part) | Matches `docs/BENCHMARKS.md`: gate 15/15 leak bypassed, 0/15 enabled; triage 4/4 and 3/3; real-detail guard True/False; bandit 67% vs 29% (toy simulation). Live part skipped (no keys) |

The bridge and frontend tests were not run; they are outside this brief.

**Code paths:**
- **Triage.** `triage.py:rule_triage(text)` returns a `TriageResult(verdict, confidence, reasons, source)` from regex categories plus IOC kinds. `triage(text, llm)` asks the LLM only on "uncertain"; with no LLM the result stays "uncertain", which halts. The caller is `engine.py:157`. Labelled data: the fixtures `SCAMS` and `BENIGN` in `test_gate_triage_ploys.py:81-91`.
- **Tactic choice.** `strategy.analyze` (regex) gives scam_type, stage, pressure and language. `ploy_order` gives the candidates, `tools.t_select_tactic` picks one with `bandit.choose` (seeded by `session:exchange`), and `Session.pending_tactic="type|tactic"` holds the choice until `bandit.record` scores it on the next message.

## 3. Candidates

### C1. Contextual tactic selection: **BUILD, reframed, simulation first**
- **Why reframed:** per-scam-type posteriors **already exist**. The real question is: *with as little data as Sentinel will ever have, does splitting by scam type help, would splitting further (by stage) help, or would pooling help more?* At current volumes (a user has at most 3 targets and 12 exchanges each), splitting may **hurt**. That would be a valid result to report.
- **Sub-question C1b (reward bias):** tactics with no target get credit for *any* new IOC, while targeted tactics get credit only for their own kind. When scammers volunteer details anyway, this may unfairly favour the target-less tactics. The simulation measures it.
- **Plugs in:** an offline harness in `backend/eval/bandit_sim.py`. It reuses the real `ploy_order`, `PLOYS` and `bandit.choose`. Pure-function policies go in `orchestrator/bandit.py` (`choose_pooled`, `choose_backoff`). **Optional phase 2** (only if phase 1 shows a gain): a shadow hook in `mcp/tools.py:t_select_tactic` under flag `SENTINEL_BANDIT_SHADOW_POLICY` (default empty = off). It uses a **separate** RNG, adds a `shadow` key to the tool result (so it is logged in ToolTrace and the ledger), never changes the live choice, and uses only the existing `TacticStat` table (no migration).
- **Data:** seeded synthetic conversations (§4). Hidden reveal rates are drawn per (scam_type, stage, tactic) from a hierarchical model with a knob σ (how different scam types really are). The simulation also includes a base rate of volunteered IOCs and a scam-type mislabel rate (taken from C7 if available).
- **Evaluation:** policies compared are playbook-only, uniform random, **current** (per-type plus 0.5 × global), pooled, back-off (per-type shrunk toward pooled) and an oracle. Volumes: 10, 30, 100, 300 and 1000 conversations. σ ∈ {0, 0.5, 1, 2}, with 30 seeds each. Metrics: mean reward per decision and regret against the oracle, with a 95% bootstrap interval over seeds. **"Does not help"** = the alternative does not beat *current* by more than the interval at ≤300 conversations. That result is reported as a negative. Everything is labelled "simulation".
- **Risks:** none to behaviour (offline). Phase 2 only logs. No LLM, $0, synthetic data only.
- **Acceptance tests:** the same seed gives identical output. Positive controls: the oracle beats random; with a tactic planted to win only in type A, per-type beats pooled in A; with σ = 0, pooled ≥ per-type (so the harness can show both gain and harm). Phase 2: with the flag off, `select_tactic` output is identical to today over seeded sessions. With the flag on, the live choice is unchanged. **Positive control:** a deliberately broken shadow that shares the RNG *does* change the choice, and the test catches it.
- **Effort (estimate):** 10-14 h for phase 1, plus 4-6 h for phase 2.

### C2. Triage pre-filter classifier: **SKIP** (the evaluation part moves into C7)
- The cost argument does not hold. LLM triage runs only on "uncertain" messages and only before engagement (F5), so there are a few calls per session.
- There is no in-domain labelled data, and SMS spam is not WhatsApp scam chat.
- A model that can turn "halt" into "engage" touches a core safety rule: benign chats must never be drawn into roleplay.
- Measure the existing triage instead (C7). Revisit only if C7 shows many scam messages halted as "uncertain" when the LLM is unavailable.

### C3. IOC extraction evaluation: **BUILD, first**
- **Plain question:** how often does Sentinel record a wrong payment detail, or miss one the scammer actually sent? Every downstream piece (rewards, graph, STIX) depends on this. F3 suggests real gaps exist.
- **Plugs in:** `backend/eval/ioc_gold/test.jsonl` (frozen) and `dev.jsonl`, plus `backend/eval/eval_ioc.py`, which calls `grounding.extract_candidates` and `ground` with a honey set. No production change and no flag. Any later extractor fix would be a separate item behind `SENTINEL_GROUNDING_V2` (default off), judged on the same frozen set.
- **Data:** about 300-500 records (estimate).
  - Generated messages with planted IOCs, so the truth is known by construction.
  - About 100 hand-written hard cases: spacing and "at" obfuscation, scheme-less URLs, +91 and toll-free formats, email vs UPI, account vs phone hints, Indic digits, look-alike Unicode, echoed honey tokens, and traps (OTP, amounts, dates, order numbers) that must **not** be extracted.
  - Every record has `synthetic: true` and `source`. Values use a synthetic namespace: `.example`/`.invalid` domains and `synth*` UPI handles.
  - **Limit:** I have read the regexes, so the hand-written set is not independent. The test split is written before the first run and never tuned against.
- **Evaluation:** precision, recall and F1 for each kind with TP/FP/FN counts, using exact value match, with bootstrap intervals. The honey-token acceptance rate must be 0. A failure report is grouped by tag. Generated and hand-written results are reported separately.
- **Acceptance tests:** the eval is deterministic. **Positive controls:** an extractor with the URL regex removed scores URL recall 0, and an extractor that invents a value produces a false positive. A schema test checks that every record is synthetic and every value sits in the synthetic namespace.
- **Effort:** 8-12 h.

### C4. Campaign clustering: **SKIP** the new clustering; **DEFER** a small evaluation
- IOC-based rings already exist (`graph.rings`).
- The graph is per-user, with very few sessions. Clustering across users would break tenant isolation.
- TF-IDF script similarity on generated data is circular: it would just recover my own templates.
- **C4-lite (DEFER, about 4-6 h):** score the existing `rings()` on planted campaigns plus coincidence traps (shared IFSC or subnet only), using pairwise precision/recall and the adjusted Rand index. Labelled "simulation".

### C5. Privacy-preserving analytics layer: **SKIP**
- Anonymous opt-in counters already exist and carry **no** id. Keyed-hash ids would *add* linkability.
- A minimum-users threshold needs a record of who contributed to each cell, which is new linkable data.
- No screen or person reads these counters today.
- BigQuery needs a GCP project and moving data out of Supabase. It fails the $0, privacy and "not Axiom" tests.
- If a view is ever needed, a PostgreSQL view over `tactic_stats` is enough.

### C6. Document store vs JSONB: **SKIP**
- JSON columns are written once and read whole per session. Nothing queries inside them (F4).
- JSONB is not needed either, so no MongoDB or Firestore claim.
- The ledger hashes canonical sorted-key JSON (`ledger/__init__.py:25`), so even a JSONB change is unnecessary risk for no gain.

### C7 (new). Labelled corpus to evaluate triage and scam-type rules: **BUILD**
- **Plain question:** how often are scams halted, or benign chats engaged? How often is the scam type (the key the learner groups by) wrong?
- **Plugs in:** `backend/eval/eval_classify.py` over the same corpus. It calls `rule_triage` and `strategy.analyze`. Optionally rules plus LLM triage (a few free-tier calls, run by hand, rate-limited). No flag needed.
- **Data:** the generated plus hand-written corpus (scam types, benign, Hinglish). Optionally the **UCI SMS Spam Collection** (licence stated as CC BY 4.0 on UCI; to be confirmed before use; downloaded locally, not committed), used for triage only and reported separately as out-of-domain.
- **Evaluation:**
  - Triage: a confusion matrix over scam/benign/uncertain, the scam-halted rate, and the benign-engaged rate. Benign-engaged is the safety-critical number.
  - Scam type: accuracy and confusion. This feeds C1's mislabel rate.
  - Rules are never tuned on the frozen split.
- **Acceptance tests:** **positive control:** a triage stub that always says "scam" is reported with benign-engaged = 100%, so the metric can fire.
- **Effort:** 5-8 h (after C3's corpus exists).

### C8 (new). Keep practice runs out of the learner: **BUILD, small**
- **Plain problem:** rehearsals against Sentinel's own AI scammer count as real evidence of which tactic works (F1).
- **Plugs in:** `engine.py:208` skips `bandit.record` for `sess.kind == "simulation"` when `SENTINEL_BANDIT_EXCLUDE_SIMULATIONS=1` (default 0 = today's behaviour). With the flag off, a ledger note records what would have been skipped (shadow).
- **Acceptance tests:** **positive control:** with the flag off, a simulation session's outcome *is* written to `tactic_stats`, which proves the leak. With the flag on, it is not. Live sessions are scored in both cases.
- **Effort:** 2-3 h.

## 4. Shared building block: synthetic generator
`backend/eval/synth.py` is seeded and stdlib-only (no new dependencies). It stamps every record with `synthetic: true`, `seed` and `generator_version`. It simulates:
- the 11 `strategy.SCAM_TYPES` plus "other" and benign kinds, in English and Hinglish;
- planted IOCs with known spans and formats, plus obfuscation variants at set rates;
- hidden reveal rates per (scam_type, stage, tactic), with the σ knob, a base volunteer rate and a mislabel rate;
- shared IOCs and planted campaigns with coincidence traps.

Generated files are written to `backend/eval/data/`, which is git-ignored and added to `.dockerignore` (the Docker image copies all of `backend/`). Only the small frozen gold test set is committed.

## 5. Recommended order
1. Generator.
2. **C3**: lowest risk, and it tests Sentinel's central claim.
3. **C7**: reuses the corpus and produces the mislabel rate C1 needs.
4. **C8**: cleans the learner's data before any shadow work.
5. **C1 phase 1**: needs the generator and C7.
6. C1 phase 2: only if phase 1 shows a gain.
7. C4-lite: optional.

C2, C5 and C6 are not built.

## 6. Claims possible after each item (to be filled with measured numbers only)
- **C3:** "Built a synthetic labelled gold set of N messages and measured per-kind precision and recall of Sentinel's IOC extractor, with a failure report (synthetic)." Evidence: a RESULTS row and its command.
- **C7:** "Measured Sentinel's rule triage and scam-type classifier on a labelled synthetic corpus (and triage on a public SMS dataset), including the rate of benign chats it would engage."
- **C8:** "Found a data-provenance flaw where rehearsal conversations trained the tactic learner, and fixed it behind a flag, with a test that first reproduces the flaw."
- **C1:** "Built a seeded simulator over Sentinel's real tactic playbook and compared per-type, pooled and back-off Thompson sampling across data volumes (simulation)." The result sentence is written only from the measured result.

## 7. Open questions
1. Time budget? C3, C7, C8 and C1 phase 1 together are about 25-37 h (estimate).
2. C8: keep the default OFF as your rule requires, or turn it ON, since today's behaviour looks like a bug?
3. Synthetic identifiers: do `.example`/`.invalid` domains and `synth*` UPI handles work for you? Generated 10-digit phone and account numbers cannot be guaranteed fictional (they are never dialled or sent anywhere). Is that acceptable, or should I use only invalid formats, at some cost to realism?
4. May I download the UCI SMS Spam Collection locally (not committed) for the out-of-domain triage check?
5. Under this plan no GCP project or analytics store is needed. Do you agree with skipping C5?
6. Should I commit the plan doc on `data-ml-plan`, and push?


## 8. Decisions (owner, 2026-11-10)
- Build order: C8, then the generator, C3, C7 and C1 phase 1. Do C1 phase 2 only if phase 1 shows a gain, and C4-lite only if time is left. C2, C5 and C6 are not built.
- C8 ships **ON** by default because it is a bug fix. The flag stays so it can be switched back. A dry-run tool reports whether existing tactic counts can be rebuilt without practice runs. No live data is changed without the owner's OK.
- No realistic phone or account numbers in git. Committed corpora use placeholders (`{PHONE_1}`), and the seeded generator fills values at run time. IFSC codes use a made-up bank code (`SYNT0000001`). `synth*` UPI handles and `.example`/`.invalid` domains are allowed.
- UCI SMS Spam Collection: local download only, after confirming the licence. It is cited, and its results are reported separately as out-of-domain.
- No BigQuery or NoSQL work in Sentinel.
