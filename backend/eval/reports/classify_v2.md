### C7 triage and scam-type rules (seed 1, generator v1, grounding v2)

Command: `python -m eval.eval_classify --seed 1 --grounding v2`. Synthetic corpus unless marked as the public dataset. Rules only, no LLM.

#### Triage: hand-written openers (scam 74, benign 24)

| Gold \ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |
|---|---|---|---|
| scam | 43 | 31 | 0 |
| benign | 0 | 21 | 3 |

- Scams engaged: **58.1%** (95% CI 46.8%–68.9%); halted: 41.9%
- Benign messages engaged (the safety-critical error): **0.0%** (95% CI 0.0%–0.0%)

#### Triage: generated openers (scam 300, benign 100)

| Gold \ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |
|---|---|---|---|
| scam | 225 | 75 | 0 |
| benign | 0 | 62 | 38 |

- Scams engaged: **75.0%** (95% CI 69.7%–79.6%); halted: 25.0%
- Benign messages engaged (the safety-critical error): **0.0%** (95% CI 0.0%–0.0%)

#### Triage: held-out openers (written before grounding v2) (scam 36, benign 11)

| Gold \ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |
|---|---|---|---|
| scam | 16 | 20 | 0 |
| benign | 1 | 9 | 1 |

- Scams engaged: **44.4%** (95% CI 28.2%–60.0%); halted: 55.6%
- Benign messages engaged (the safety-critical error): **9.1%** (95% CI 0.0%–28.6%)

Why benign messages were engaged: 0 of 0 had an extracted `bank_account` among the triage reasons (a payment rail adds 2 to the score). See the C3 report: these are toll-free or reference numbers read as accounts.

#### Scam type (`strategy.analyze`), scam messages only

| Subset | N | Accuracy (95% CI) | Lenient accuracy | Wrong labels that are `other` |
|---|---|---|---|---|
| hand-written openers | 74 | 81.1% (71.6%–89.2%) | 82.4% | 42.9% |
| hand-written follow-ups | 24 | 16.7% (4.2%–33.3%) | 16.7% | 90.0% |
| generated openers | 300 | 98.0% (96.3%–99.3%) | 98.0% | 0.0% |

Most common confusions (hand-written, openers and follow-ups):

- `kyc_bank -> other`: 6
- `police_impersonation -> other`: 3
- `electricity_bill -> other`: 3
- `job_task -> other`: 3
- `sextortion -> other`: 2
- `loan -> lottery_prize`: 2
- `investment_crypto -> other`: 2
- `lottery_prize -> other`: 2

#### Out-of-domain: UCI SMS Spam Collection (public dataset, 5574 messages: ham 4827, spam 747)

Gold labels are ham/spam. Spam includes marketing that is not fraud, so 'spam not engaged' is not a miss in Sentinel's sense.

| Gold \ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |
|---|---|---|---|
| ham | 0 | 4796 | 31 |
| spam | 14 | 733 | 0 |

- Ham messages the rules would engage: **0.0%** (95% CI 0.0%–0.0%)
- Spam messages the rules would engage: 1.9% (95% CI 1.0%–2.9%)

