### C3 IOC extraction (synthetic, seed 1, generator v1)

Command: `python -m eval.eval_ioc --seed 1`. All records are synthetic; hand-written and generated results are separate.

#### Hand-written cases (records: 122)

| Kind | Gold | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | F1 |
|---|---|---|---|---|---|---|---|
| upi | 31 | 26 | 0 | 5 | 100.0% (100.0%–100.0%) | 83.9% (69.4%–96.7%) | 91.2% |
| phone | 26 | 23 | 0 | 3 | 100.0% (100.0%–100.0%) | 88.5% (75.0%–100.0%) | 93.9% |
| url | 21 | 15 | 1 | 6 | 93.8% (80.0%–100.0%) | 71.4% (50.0%–90.0%) | 81.1% |
| bank_account | 13 | 13 | 12 | 0 | 52.0% (31.6%–73.7%) | 100.0% (100.0%–100.0%) | 68.4% |
| ifsc | 12 | 10 | 0 | 2 | 100.0% (100.0%–100.0%) | 83.3% (57.1%–100.0%) | 90.9% |
| **all** | 103 | 87 | 13 | 16 | 87.0% (79.6%–93.4%) | 84.5% (76.9%–91.4%) | 85.7% |

#### Generated messages (records: 400)

| Kind | Gold | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | F1 |
|---|---|---|---|---|---|---|---|
| upi | 109 | 90 | 0 | 19 | 100.0% (100.0%–100.0%) | 82.6% (75.0%–89.2%) | 90.5% |
| phone | 103 | 103 | 0 | 0 | 100.0% (100.0%–100.0%) | 100.0% (100.0%–100.0%) | 100.0% |
| url | 95 | 71 | 0 | 24 | 100.0% (100.0%–100.0%) | 74.7% (65.3%–83.7%) | 85.5% |
| bank_account | 51 | 51 | 40 | 0 | 56.0% (44.9%–65.9%) | 100.0% (100.0%–100.0%) | 71.8% |
| ifsc | 51 | 51 | 0 | 0 | 100.0% (100.0%–100.0%) | 100.0% (100.0%–100.0%) | 100.0% |
| **all** | 409 | 366 | 40 | 43 | 90.1% (86.8%–93.0%) | 89.5% (86.5%–92.3%) | 89.8% |

#### All (records: 522)

| Kind | Gold | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | F1 |
|---|---|---|---|---|---|---|---|
| upi | 140 | 116 | 0 | 24 | 100.0% (100.0%–100.0%) | 82.9% (75.9%–89.3%) | 90.6% |
| phone | 129 | 126 | 0 | 3 | 100.0% (100.0%–100.0%) | 97.7% (94.7%–100.0%) | 98.8% |
| url | 116 | 86 | 1 | 30 | 98.9% (96.1%–100.0%) | 74.1% (65.8%–82.0%) | 84.7% |
| bank_account | 64 | 64 | 52 | 0 | 55.2% (46.0%–64.1%) | 100.0% (100.0%–100.0%) | 71.1% |
| ifsc | 63 | 61 | 0 | 2 | 100.0% (100.0%–100.0%) | 96.8% (91.7%–100.0%) | 98.4% |
| **all** | 512 | 453 | 53 | 59 | 89.5% (86.6%–92.1%) | 88.5% (85.6%–91.2%) | 89.0% |

Decoy (honey-token) values accepted as scammer IOCs: **0** in 4 records that echo a decoy (must be 0).
Candidates rejected by grounding: {'honey_token': 4}.

#### Failures by tag (records with at least one miss or wrong value)

| Tag | Records | Missed | Wrong |
|---|---|---|---|
| generated | 83 | 43 | 40 |
| format | 10 | 10 | 2 |
| trap | 5 | 0 | 6 |
| benign | 5 | 0 | 5 |
| trap_ref | 4 | 0 | 5 |
| trap_tollfree | 3 | 0 | 4 |
| upi_spaced | 3 | 3 | 0 |
| followup | 2 | 2 | 0 |
| lang | 2 | 2 | 0 |
| phone_zero | 1 | 1 | 1 |
| trap_order | 2 | 0 | 2 |
| url_noscheme | 2 | 2 | 0 |
| url_spaced_dot | 1 | 1 | 1 |
| url_www | 2 | 2 | 0 |
| acct_grouped | 1 | 1 | 0 |
| clean | 1 | 1 | 0 |
| hard_benign | 1 | 0 | 1 |
| honey | 1 | 1 | 0 |
| honey_echo | 1 | 1 | 0 |
| ifsc_lower | 1 | 1 | 0 |
| ifsc_spaced | 1 | 1 | 0 |
| indic_digits | 1 | 1 | 0 |
| phone_dotted | 1 | 1 | 0 |
| trap_aadhaar | 1 | 0 | 1 |
| trap_card | 1 | 0 | 1 |
| upi_atword | 1 | 1 | 0 |
| upi_paren | 1 | 1 | 0 |
| url_defanged | 1 | 1 | 0 |

#### Hand-written failure cases (templates; values are filled in at run time)

**benign**

- `hw-100` bank_account: 1 wrong: `Rs 2,000 debited from A/c XX1234 on 03-Nov. Not you? Call {TOLLFREE_1}.`
- `hw-101` bank_account: 1 wrong: `Your order {ORDER_1} has been shipped and will arrive by Thursday.`
- `hw-107` bank_account: 1 wrong: `Rs 500 received from Suresh via UPI. Ref {REF_1}.`
- `hw-115` bank_account: 1 wrong: `Your Aadhaar update request has been received. URN {REF_1}.`
- `hw-116` bank_account: 1 wrong: `Your card ending 4821 is blocked as you requested. Call {TOLLFREE_1|spaced} for a new card.`

**clean**

- `hw-018` url: 1 missed: `Winner notification: claim your new phone at {URL_1|noscheme} before midnight.`

**followup**

- `hw-040` upi: 1 missed: `If you disconnect, a warrant will be issued. Pay {UPI_1|spaced} now.`
- `hw-045` url: 1 missed: `Did you update the address? Use this link {URL_1|www}`

**format**

- `hw-067` upi: 1 missed: `Pay to {UPI_1|atword} immediately or account blocked.`
- `hw-068` upi: 1 missed: `UPI: {UPI_1|paren} urgent payment needed for KYC`
- `hw-069` phone: 1 missed; bank_account: 1 wrong: `Call {PHONE_1|zero} for refund processing`
- `hw-070` phone: 1 missed: `Contact {PHONE_1|dotted} now, police case pending`
- `hw-072` url: 1 missed: `Update KYC: {URL_1|defanged}`
- `hw-073` url: 1 missed; url: 1 wrong: `Open {URL_1|spaced_dot} and enter details, account blocked`
- `hw-074` ifsc: 1 missed: `IFSC {IFSC_1|lower} account {ACCT_1} send now for KYC`
- `hw-075` ifsc: 1 missed: `Bank: {ACCT_1|grouped}, IFSC: {IFSC_1|spaced}. Pay fee for the lottery prize.`
- `hw-079` url: 1 missed: `Pay at {URL_1|www} to avoid arrest`
- `hw-080` upi: 1 missed: `Visit {URL_1|https}, then pay {UPI_1|spaced} and call {PHONE_1|spaced}, all three needed for KYC.`

**honey**

- `hw-096` upi: 1 missed: `I checked {DECOY_1}, payment failed. Use {UPI_1|spaced} now.`

**lang**

- `hw-062` phone: 1 missed: `आपका बिजली कनेक्शन आज रात काट दिया जाएगा। अधिकारी से {PHONE_1|dev} पर संपर्क करें।`
- `hw-066` url: 1 missed: `Aapka parcel atak gaya hai, address update karo {URL_1|noscheme}`

**trap**

- `hw-088` bank_account: 1 wrong: `Case number {REF_1} registered against you by CBI. Pay to {UPI_1} to close it.`
- `hw-089` bank_account: 1 wrong: `Your Aadhaar {AADHAAR_1|grouped} is linked to illegal SIM cards. Police will arrest you. Call {PHONE_1}`
- `hw-090` bank_account: 1 wrong: `Enter card number {CARD_1|grouped} at {URL_1} to receive the refund.`
- `hw-091` bank_account: 1 wrong: `Order {ORDER_1} delivery failed. Pay Rs 25 at {URL_1}`
- `hw-093` bank_account: 2 wrong: `Complaint ID {REF_1}. For refund call our helpline {TOLLFREE_1|dashed} or WhatsApp {PHONE_1}`

