### Grounding v1 vs v2 (synthetic, seed 1)

Command: `python -m eval.eval_ioc --compare --seed 1`. v2 is OFF in production unless `SENTINEL_GROUNDING_V2=1`.

*Main* = the corpus whose failure report v2 was written to fix, so its v2 numbers are optimistic. *Held-out* = 49 cases written before any v2 code and never used to tune it.

| Corpus | Kind | v1 precision | v2 precision | v1 recall | v2 recall | v1 FP | v2 FP | v1 FN | v2 FN |
|---|---|---|---|---|---|---|---|---|---|
| main: hand-written | upi | 100.0% | 100.0% | 83.9% | 93.5% | 0 | 0 | 5 | 2 |
| main: hand-written | phone | 100.0% | 100.0% | 88.5% | 96.2% | 0 | 0 | 3 | 1 |
| main: hand-written | url | 93.8% | 95.0% | 71.4% | 90.5% | 1 | 1 | 6 | 2 |
| main: hand-written | bank_account | 52.0% | 100.0% | 100.0% | 100.0% | 12 | 0 | 0 | 0 |
| main: hand-written | ifsc | 100.0% | 100.0% | 83.3% | 83.3% | 0 | 0 | 2 | 2 |
| main: hand-written | **all** | 87.0% | 99.0% | 84.5% | 93.2% | 13 | 1 | 16 | 7 |
| main: hand-written | decoys accepted | 0 | 0 | | | | | | |
| main: generated | upi | 100.0% | 100.0% | 82.6% | 100.0% | 0 | 0 | 19 | 0 |
| main: generated | phone | 100.0% | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 0 |
| main: generated | url | 100.0% | 100.0% | 74.7% | 100.0% | 0 | 0 | 24 | 0 |
| main: generated | bank_account | 56.0% | 100.0% | 100.0% | 100.0% | 40 | 0 | 0 | 0 |
| main: generated | ifsc | 100.0% | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 0 |
| main: generated | **all** | 90.1% | 100.0% | 89.5% | 100.0% | 40 | 0 | 43 | 0 |
| main: generated | decoys accepted | 0 | 0 | | | | | | |
| held-out | upi | 100.0% | 100.0% | 77.8% | 100.0% | 0 | 0 | 4 | 0 |
| held-out | phone | 100.0% | 100.0% | 80.0% | 100.0% | 0 | 0 | 2 | 0 |
| held-out | url | 100.0% | 100.0% | 40.0% | 100.0% | 0 | 0 | 6 | 0 |
| held-out | bank_account | 23.8% | 100.0% | 100.0% | 100.0% | 16 | 0 | 0 | 0 |
| held-out | ifsc | 100.0% | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 0 |
| held-out | **all** | 68.6% | 100.0% | 74.5% | 100.0% | 16 | 0 | 12 | 0 |
| held-out | decoys accepted | 0 | 0 | | | | | | |

#### Held-out failures left under v2

| Tag | Records | Missed | Wrong |
|---|---|---|---|

#### Hand-written failure cases (templates; values are filled in at run time)

