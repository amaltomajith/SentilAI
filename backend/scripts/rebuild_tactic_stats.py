"""Rebuild the tactic learner's counters (tactic_stats) from stored history, optionally leaving out practice sessions.

    python -m scripts.rebuild_tactic_stats                 # DRY RUN (default): reads only, prints aggregate counts
    python -m scripts.rebuild_tactic_stats --apply         # rewrites tactic_stats (only with the owner's explicit OK)

How the replay works: for each session (in creation order), the `select_tactic` tool traces give the tactic chosen at each
turn and the scam type it was chosen for; the IOC rows created between one choice and the next are what the scammer revealed
in reply. A choice is scored exactly as `Engine._handle_locked` does (a new IOC of a targeted kind, or any new IOC for a tactic
with no target). The last choice of a session is never scored, as in the engine.

Before trusting a rebuild, the dry run REPLAYS EVERYTHING (practice included) and compares the result with the live table.
If that "fidelity" check does not match, the history does not explain the current counters and --apply refuses to run.
Known gap: the shared "*" counters depend on each user's opt-in at the time; history does not record when it changed, so the
replay uses today's opt-in. The fidelity check shows whether that matters for this database.

Output is aggregate only: no user ids, no IOC values, no message text.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from sentinel.db.models import Ioc, Session, TacticStat, ToolTrace, User  # noqa: E402
from sentinel.orchestrator.bandit import GLOBAL, tactic_hit  # noqa: E402
from sentinel.orchestrator.engine import PRACTICE_KINDS  # noqa: E402
from sentinel.orchestrator.ploys import PLOYS  # noqa: E402

Key = tuple[str, str, str]   # (scope, scam_type, tactic)


def replay(db, exclude_kinds: frozenset[str] = frozenset()) -> tuple[dict[Key, list[int]], Counter]:
    """Returns ({(scope, scam_type, tactic): [successes, trials]}, scored outcomes per session kind)."""
    opt_in = {u.id: bool(u.collective_opt_in) for u in db.scalars(select(User))}
    out: dict[Key, list[int]] = defaultdict(lambda: [0, 0])
    scored_by_kind: Counter = Counter()
    for s in db.scalars(select(Session).where(Session.user_id != "").order_by(Session.created_at)):
        timeline = [(t.created_at, 1, "tactic", t.result or {}) for t in
                    db.scalars(select(ToolTrace).where(ToolTrace.session_id == s.id, ToolTrace.tool == "select_tactic", ToolTrace.ok == 1))]
        timeline += [(i.created_at, 0, "ioc", i.kind) for i in db.scalars(select(Ioc).where(Ioc.session_id == s.id))]
        timeline.sort(key=lambda e: (e[0], e[1]))   # within one request the IOCs are written before the tactic is chosen
        pending, revealed = None, []
        for _, _, what, data in timeline:
            if what == "ioc":
                revealed.append(data)
                continue
            if pending is not None:
                scam_type, tactic = pending
                targets = PLOYS[tactic].targets if tactic in PLOYS else ()
                hit = tactic_hit(targets, revealed)
                scored_by_kind[s.kind] += 1
                if s.kind not in exclude_kinds:
                    for scope in [s.user_id] + ([GLOBAL] if opt_in.get(s.user_id) else []):
                        row = out[(scope, scam_type, tactic)]
                        row[0] += int(hit)
                        row[1] += 1
            pending, revealed = (data.get("scam_type", "other"), data.get("ploy_id", "")), []
    return dict(out), scored_by_kind


def current(db) -> dict[Key, list[int]]:
    return {(r.scope, r.scam_type, r.tactic): [r.successes, r.trials] for r in db.scalars(select(TacticStat))}


def _norm(d: dict[Key, list[int]]) -> dict[Key, tuple[int, int]]:
    return {k: (v[0], v[1]) for k, v in d.items() if v[1] > 0}


def report(db) -> dict:
    live = _norm(current(db))
    everything, by_kind = replay(db)
    everything = _norm(everything)
    rebuilt = _norm(replay(db, PRACTICE_KINDS)[0])
    mismatch = sorted(set(live) ^ set(everything) | {k for k in live.keys() & everything.keys() if live[k] != everything[k]})

    def trials(d, glob: bool):
        return sum(v[1] for k, v in d.items() if (k[0] == GLOBAL) == glob)
    return {
        "sessions_by_kind": dict(Counter(s.kind for s in db.scalars(select(Session).where(Session.user_id != "")))),
        "scored_outcomes_by_kind": dict(by_kind),
        "fidelity_ok": not mismatch,
        "fidelity_mismatched_rows": len(mismatch),
        "fidelity_mismatched_global_rows": sum(k[0] == GLOBAL for k in mismatch),
        "live_trials": {"private": trials(live, False), "global": trials(live, True)},
        "rebuilt_trials": {"private": trials(rebuilt, False), "global": trials(rebuilt, True)},
        "rows_live": len(live), "rows_rebuilt": len(rebuilt),
        "rows_that_would_change": len(set(live) ^ set(rebuilt) | {k for k in live.keys() & rebuilt.keys() if live[k] != rebuilt[k]}),
    }


def apply(db) -> None:
    rebuilt = _norm(replay(db, PRACTICE_KINDS)[0])
    for r in db.scalars(select(TacticStat)):
        db.delete(r)
    db.flush()
    for (scope, scam_type, tactic), (s, t) in rebuilt.items():
        db.add(TacticStat(scope=scope, scam_type=scam_type, tactic=tactic, successes=s, trials=t))
    db.flush()


def main(argv=None) -> int:
    from sentinel.config import get_settings
    from sentinel.db import make_engine, make_session_factory, session_scope
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--database-url", default=None, help="defaults to DATABASE_URL / the local SQLite file")
    ap.add_argument("--apply", action="store_true", help="rewrite tactic_stats (needs the owner's explicit OK)")
    a = ap.parse_args(argv)
    f = make_session_factory(make_engine(a.database_url or get_settings().database_url))
    with session_scope(f) as db:
        r = report(db)
        for k, v in r.items():
            print(f"{k}: {v}")
        if not a.apply:
            print("DRY RUN: nothing was changed.")
            return 0
        if not r["fidelity_ok"]:
            print("REFUSING to apply: replaying the full history does not reproduce the current counters.")
            return 2
        apply(db)
        print("tactic_stats rebuilt without practice sessions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
