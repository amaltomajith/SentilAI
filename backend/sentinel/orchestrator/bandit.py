"""Thompson-sampling over tactics, learning from outcomes ("did the scammer reveal a new detail after this tactic?").

This is NOT model training and NOT federated learning in the strict sense. It is:
  - per-user learning from that user's own conversations, and
  - opt-in collective learning through anonymised counters only: (scam_type, tactic, successes, trials). No text, no numbers, no profile data.
"""
from __future__ import annotations

import random

from sqlalchemy import select

from sentinel.db.models import TacticStat

GLOBAL = "*"
GLOBAL_WEIGHT = 0.5      # a stranger's experience counts half as much as your own


def load_stats(db, scam_type: str, user_id: str, use_global: bool) -> dict[str, tuple[float, float]]:
    out: dict[str, tuple[float, float]] = {}
    scopes = [(user_id, 1.0)] + ([(GLOBAL, GLOBAL_WEIGHT)] if use_global else [])
    for scope, w in scopes:
        for r in db.scalars(select(TacticStat).where(TacticStat.scope == scope, TacticStat.scam_type == scam_type)):
            s, t = out.get(r.tactic, (0.0, 0.0))
            out[r.tactic] = (s + w * r.successes, t + w * r.trials)
    return out


def choose(options: list[str], stats: dict[str, tuple[float, float]], rng: random.Random) -> tuple[str, dict[str, float]]:
    """options are ordered best-first by the deterministic playbook; that order is the prior (a small head start)."""
    if not any(stats.get(o, (0.0, 0.0))[1] > 0 for o in options):      # cold start: nothing learned yet, follow the playbook order
        return options[0], {o: round((1.6 if i == 0 else 1.3 if i == 1 else 1.0) / ((1.6 if i == 0 else 1.3 if i == 1 else 1.0) + 1.0), 3) for i, o in enumerate(options)}
    scores: dict[str, float] = {}
    for i, o in enumerate(options):
        s, t = stats.get(o, (0.0, 0.0))
        prior = 1.6 if i == 0 else 1.3 if i == 1 else 1.0
        scores[o] = rng.betavariate(prior + s, 1.0 + max(t - s, 0.0))
    best = max(scores, key=scores.get)
    return best, {k: round(v, 3) for k, v in scores.items()}


def record(db, user_id: str, scam_type: str, tactic: str, success: bool, contribute: bool) -> None:
    for scope in ([user_id] + ([GLOBAL] if contribute else [])):
        row = db.get(TacticStat, (scope, scam_type, tactic))
        if not row:
            row = TacticStat(scope=scope, scam_type=scam_type, tactic=tactic, successes=0, trials=0)
            db.add(row)
        row.trials += 1
        row.successes += int(success)
    db.flush()