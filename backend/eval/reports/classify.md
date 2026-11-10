### C7 triage and scam-type rules (seed 1, generator v1, grounding v1)

Command: `python -m eval.eval_classify --seed 1`. Synthetic corpus unless marked as the public dataset. Rules only, no LLM.

#### Triage: hand-written openers (scam 74, benign 24)

| Gold \ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |
|---|---|---|---|
| scam | 43 | 31 | 0 |
| benign | 3 | 20 | 1 |

- Scams engaged: **58.1%** (95% CI 46.1%–68.9%); halted: 41.9%
- Benign messages engaged (the safety-critical error): **12.5%** (95% CI 0.0%–26.7%)

#### Triage: generated openers (scam 300, benign 100)

| Gold \ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |
|---|---|---|---|
| scam | 203 | 97 | 0 |
| benign | 31 | 47 | 22 |

- Scams engaged: **67.7%** (95% CI 62.4%–72.7%); halted: 32.3%
- Benign messages engaged (the safety-critical error): **31.0%** (95% CI 22.3%–40.9%)

#### Triage: held-out openers (written before grounding v2) (scam 36, benign 11)

| Gold \ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |
|---|---|---|---|
| scam | 15 | 21 | 0 |
| benign | 3 | 8 | 0 |

- Scams engaged: **41.7%** (95% CI 25.0%–56.8%); halted: 58.3%
- Benign messages engaged (the safety-critical error): **27.3%** (95% CI 0.0%–57.1%)

Why benign messages were engaged: 34 of 34 had an extracted `bank_account` among the triage reasons (a payment rail adds 2 to the score). See the C3 report: these are toll-free or reference numbers read as accounts.

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
| spam | 154 | 593 | 0 |

- Ham messages the rules would engage: **0.0%** (95% CI 0.0%–0.0%)
- Spam messages the rules would engage: 20.6% (95% CI 17.8%–23.6%)

