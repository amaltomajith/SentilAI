# Sentinel data and ML extension: results

Branch `data-ml-extension` (off `main` at `8f7d82e`). Plan: [`plan-data-ml.md`](plan-data-ml.md). All dates are 2026-11-10.
Every number below comes from the command shown next to it. Commands run from `backend/` in a clean copy without `.env`, so no keys and no network. Python 3.13.11 locally; CI uses 3.12.
**Sentinel has no real catch statistics.** Nothing here is one. Each number is labelled *synthetic*, *simulation* or *public dataset*.

## Baseline

| What | Number | Command |
|---|---|---|
| Backend tests on `main` | 174 collected, 174 passed | `python -m pytest --collect-only -q`, `python -m pytest -q` |
| Offline benchmark on `main` | gate 15/15 leak bypassed, 0/15 enabled; triage 4/4 and 3/3; tactic chooser 67% vs 29% (toy simulation) | `python -m scripts.bench` (live part skipped: no keys) |
| Labelled data or evaluation scripts before this work | none, apart from `scripts/bench.py` and its 7 triage fixtures | (code reading) |

## What was built

| Item | Status | Where |
|---|---|---|
| **C8**: practice sessions no longer teach the tactic learner | DONE, **on** by default (bug fix; `SENTINEL_BANDIT_EXCLUDE_PRACTICE=0` restores the old behaviour) | `orchestrator/engine.py`, `config.py`, `tests/test_practice_learning.py` |
| C8: rebuild tool for existing counters | DONE (dry run by default; **not run on any real database**) | `scripts/rebuild_tactic_stats.py` |
| Shared synthetic generator and hand-written corpus | DONE | `eval/synth.py`, `eval/corpus/handwritten.jsonl` (placeholders only) |
| **C3**: IOC extraction evaluation | DONE | `eval/eval_ioc.py`, report `eval/reports/ioc.md`, `tests/test_eval_corpus_ioc.py` |
| **C7**: triage and scam-type rule evaluation, plus UCI out-of-domain check | DONE (rules only; LLM tie-breaker not measured) | `eval/eval_classify.py`, report `eval/reports/classify.md`, `tests/test_eval_classify.py` |
| **C1 phase 1**: tactic learner simulation | DONE | `eval/bandit_sim.py`, reports `eval/reports/bandit_sim*.md`, `tests/test_bandit_sim.py` |
| **C1 phase 2**: back-off policy in shadow mode | DONE, **off** by default (`SENTINEL_BANDIT_SHADOW_POLICY=backoff`); never switched on anywhere | `mcp/tools.py`, `orchestrator/bandit.py`, `tests/test_shadow_policy.py` |
| C4-lite (evaluate existing rings on planted campaigns) | NOT DONE | see below |

After this work there are 211 backend tests and all pass (`python -m pytest -q`). The offline benchmark is unchanged (same numbers as the baseline). Each new "must not happen" test has a positive control that first shows the failure can happen.

## Measurements

| # | Item | Number | Unit | Command | Label |
|---|---|---|---|---|---|
| 1 | Tests after the work | 211 passed (174 before) | tests | `python -m pytest -q` | — |
| 2 | C3 hand-written cases, all kinds | precision 87.0% (87 / 100), recall 84.5% (87 / 103) | IOCs | `python -m eval.eval_ioc --seed 1` | synthetic |
| 3 | C3 URL recall, hand-written | 71.4% (15 / 21); misses: no `http://`, `www.`, defanged, spaced dot | IOCs | same | synthetic |
| 4 | C3 UPI recall, hand-written | 83.9% (26 / 31); misses: `name @ psp`, `name at psp`, `name(at)psp` | IOCs | same | synthetic |
| 5 | C3 bank-account precision, all 522 records | 55.2% (64 / 116); wrong values come from 11-digit toll-free, UPI reference, order, card and Aadhaar-style numbers | IOCs | same | synthetic |
| 6 | C3 decoy values accepted as scammer IOCs | 0 in 4 records that echo a decoy | values | same | synthetic |
| 7 | C7 scam openers engaged by rules alone (hand-written) | 58.1% (43 / 74); the other 31 are "uncertain", which halts if the LLM is unavailable | messages | `python -m eval.eval_classify --seed 1` | synthetic |
| 8 | C7 benign openers engaged by rules | hand-written 12.5% (3 / 24); generated 31.0% (31 / 100) | messages | same | synthetic |
| 9 | C7 benign messages engaged because an extracted `bank_account` was among the triage reasons | 34 of 34 | messages | same | synthetic |
| 10 | C7 scam-type accuracy (`strategy.analyze`) | openers 81.1% (60 / 74); follow-up turns 16.7% (4 / 24, 90% of the wrong labels are `other`); generated openers 98.0% (optimistic, see limits) | messages | same | synthetic |
| 11 | C7 UCI SMS Spam: ham the rules would engage | 0 / 4,827 (0.0%) | messages | same, with the local UCI file | public dataset, out-of-domain |
| 12 | C7 UCI SMS Spam: spam the rules would engage | 154 / 747 (20.6%) | messages | same | public dataset, out-of-domain |
| 13 | C1 back-off minus current, N = 300 conversations, C7 label noise | σ 0: +0.029 [+0.012, +0.046]; σ 0.5: +0.043 [+0.026, +0.061]; σ 1: +0.045 [+0.020, +0.066]; σ 2: +0.053 [+0.029, +0.077] | IOC kinds per conversation (current ≈ 1.34–1.66) | `python -m eval.bandit_sim` (30 seeds, 95% bootstrap CI) | simulation |
| 14 | C1 back-off minus current with perfect labels, σ 2, N = 300 | +0.047 [+0.022, +0.073] | IOC kinds per conversation | `python -m eval.bandit_sim --perfect-labels --sigmas 0,1,2` | simulation |
| 15 | C1 pooled minus current with perfect labels, σ 2, N = 300 | +0.021 [−0.003, +0.048] (no clear difference) | IOC kinds per conversation | same | simulation |
| 16 | C1 splitting further by stage, σ 1, N = 300 | −0.014 [−0.025, −0.001] (harms) | IOC kinds per conversation | `python -m eval.bandit_sim` | simulation |
| 17 | C1 sticky scam type, σ 1, N = 300 | −0.024 [−0.036, −0.012] (harms) | IOC kinds per conversation | same | simulation |
| 18 | C1b reward rule, volunteer rate 0.15, N = 300 | "any new IOC" vs engine rule +0.000 [−0.006, +0.006]; "targeted only" −0.056 [−0.085, −0.031] | IOC kinds per conversation | same | simulation |
| 19 | Shadow policy: live choice changed | 0 of 120 seeded cases for each shadow policy (pooled, back-off) | cases | `python -m pytest tests/test_shadow_policy.py` | synthetic |

## Datasets used

- **Synthetic**, generated by `eval/synth.py` (generator v1, seeds 1–3). It produces 122 hand-written templates and 400 generated messages. Values are filled in at run time and never committed. IFSC codes use a made-up `SYN?0` bank code, UPI ids start with `synth`, and domains end in `.example` or `.invalid`.
- **Simulation**, generated by `eval/bandit_sim.py`. Worlds are seeded per run, with 30 seeds per cell.
- **UCI SMS Spam Collection.** https://archive.ics.uci.edu/dataset/228/sms+spam+collection, DOI 10.24432/C5CC84.
  - Licence: **CC BY 4.0**, as stated on that page (checked 2026-11-10).
  - Citation: Almeida, T. & Hidalgo, J. (2011). *SMS Spam Collection* [Dataset]. UCI Machine Learning Repository. Paper: T. A. Almeida, J. M. Gómez Hidalgo, A. Yamakami, "Contributions to the study of SMS spam filtering: new collection and results", ACM DocEng 2011.
  - The file was downloaded locally to `backend/eval/data/external/`. It is git-ignored and was never committed. Zip sha256 `1587ea43e58e82b14ff1f5425c88e17f8496bfcdb67a583dbff9eefaf9963ce3`.
  - No message text from it appears in any report.

## Not done and why

- **The rebuild dry run on real data was not run.** It needs your OK and access to a real database: Supabase through `DATABASE_URL`, or the local `backend/data/sentinel.db`. I opened neither. What I checked instead: on synthetic history, replaying everything reproduces the live counters exactly, and a rebuild equals what the fixed engine would have learned (tests). When you allow it, run `python -m scripts.rebuild_tactic_stats` (dry run, aggregate output only, no ids, values or text). `--apply` refuses to run if the replay does not reproduce the live table.
- **The LLM triage tie-breaker was not measured.** Measuring it would send synthetic text to a free-tier LLM using the production keys. Row 7 shows how often it matters: 42% of hand-written scam openers depend on it.
- **The extractor was not fixed.** The failures are listed in `eval/reports/ioc.md`. A fix would change behaviour, so it belongs behind its own flag (`SENTINEL_GROUNDING_V2`) and should be judged on the same corpus.
- **The shadow policy was never switched on.** No real outcomes were collected, so there is no real-world evidence for or against back-off.
- **C4-lite was not done** (optional; time went to C1). C2, C5 and C6 were skipped as decided in the plan.
- **Bridge and frontend tests were not run.** Those parts were not changed.

## Honest limits

- **The corpus is not independent of the code.** I wrote it after reading the regexes. The generated openers reuse words the rules look for, so 98% generated scam-type accuracy is optimistic. The hand-written follow-ups (16.7%) are the realistic stress test.
- **Precision depends on the trap mix.** It reflects how many traps (OTPs, reference numbers, toll-free numbers) the corpus contains, not how often they occur in real chats. The same applies to the generated benign rate (31%): 3 of the 10 benign templates contain such numbers.
- **Indic digits are matched leniently.** Account numbers written in Devanagari digits count as correct in C3, but Sentinel stores them in Devanagari script.
- **Benign messages are rarer in production.** Users name the scammer's number themselves, so the C7 benign rates describe the rules, not real exposure.
- **UCI SMS spam is not WhatsApp scam chat.** It is 2011-era, includes marketing, and is reported only as an out-of-domain check.
- **The C1 scammer is assumed, not observed.** In particular, it ignores the playbook's order, so the playbook prior carries no information there. The simulation shows how learners behave under stated assumptions.
- **The C1 effects are small.** Back-off gained about 2–4% relative. It was not reliably better at N ≤ 30, and pooled was worse at N = 30 when σ = 0.
- **Counters from earlier practice sessions remain.** C8 changes default behaviour (practice is no longer learned), but counters already written stay until a rebuild is approved and run.

## Resume-safe sentences

1. Built a seeded synthetic evaluation set (122 hand-written cases and 400 generated messages, no real data) and measured per-type precision and recall of a scam-intelligence system's indicator extractor. It showed that toll-free and reference numbers were recorded as bank accounts (bank-account precision 55%, synthetic). *(rows 2–5)*
2. Traced a triage false-positive chain: every benign message the rules would engage in the synthetic corpus (34 of 34) was engaged because an extractor false positive created a fake payment detail (synthetic). *(rows 8–9)*
3. Evaluated the rule-based triage on the public UCI SMS Spam Collection: it would engage 0 of 4,827 legitimate messages (public dataset, out-of-domain). *(row 11)*
4. Found and fixed, behind a flag, a data-provenance bug where rehearsal conversations trained a Thompson-sampling tactic learner. Added a replay tool that verifies it reproduces the live counters before rebuilding them. *(row 1, C8 tests)*
5. Built a common-random-numbers simulator around the production bandit code (30 seeds, bootstrap intervals). Shrinking per-scam-type estimates toward a pooled estimate gained 0.03–0.05 IOC kinds per conversation over the current learner at 300 conversations in every tested setting, while finer splitting hurt (simulation). *(rows 13–17)*
6. Shipped the winning policy in shadow mode, logging its choice next to the live one, with tests showing the live choice is unchanged. *(row 19)*
