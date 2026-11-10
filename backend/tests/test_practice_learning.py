"""C8: practice sessions must not teach the tactic learner. Positive control first: with the fix switched off, they do."""
import dataclasses

import pytest
from sqlalchemy import select

from scripts import rebuild_tactic_stats as rebuild
from sentinel.config import Settings
from sentinel.db import make_engine, make_session_factory, session_scope
from sentinel.db.models import LedgerEvent, Profile, TacticStat, User
from sentinel.llm import FakeLLM
from sentinel.orchestrator.engine import PRACTICE_KINDS, Engine

# synthetic values only (public repo): made-up UPI handle, bank code and an all-zero account number
CONVERSATION = [
    "Dear user your SBI KYC expired. Pay now or account blocked, urgent",
    "Send Rs 500 to synth.refund@ybl or A/C 000000001234 IFSC SYNT0000001",
    "Why not paying? Send now!",
    "Open http://kyc-verify.example/pay and finish it, urgent",
]


async def offline(u):
    raise RuntimeError("offline")


def make(exclude_practice: bool, opt_in: bool = True, url: str = "sqlite://"):
    f = make_session_factory(make_engine(url))
    with session_scope(f) as db:
        db.add(User(id="alice", collective_opt_in=int(opt_in)))
        db.add(Profile(user_id="alice", data={"alias": "Anita", "age": 58, "occupation": "teacher", "languages": ["English"]}, share={}))
    s = dataclasses.replace(Settings(), bandit_exclude_practice=exclude_practice)
    return f, Engine(f, s, FakeLLM(["Kindly wait sir, my app shows error. Please share the details again."]), fetch=offline)


async def converse(eng, kind: str) -> str:
    sid = eng.create_session(kind, user_id="alice")
    for msg in CONVERSATION:
        await eng.handle_inbound(sid, msg)
    return sid


def trials(f) -> dict:
    with session_scope(f) as db:
        return {(r.scope, r.scam_type, r.tactic): (r.successes, r.trials) for r in db.scalars(select(TacticStat))}


def test_default_is_on(monkeypatch):
    monkeypatch.delenv("SENTINEL_BANDIT_EXCLUDE_PRACTICE", raising=False)
    assert Settings().bandit_exclude_practice is True
    monkeypatch.setenv("SENTINEL_BANDIT_EXCLUDE_PRACTICE", "0")
    assert Settings().bandit_exclude_practice is False


@pytest.mark.parametrize("kind", sorted(PRACTICE_KINDS))
async def test_positive_control_fix_off_practice_sessions_do_teach_the_learner(kind):
    f, eng = make(exclude_practice=False)
    await converse(eng, kind)
    rows = trials(f)
    assert sum(t for (scope, _, _), (_, t) in rows.items() if scope == "alice") == len(CONVERSATION) - 1
    assert any(scope == "*" for scope, _, _ in rows)          # and, with opt-in, the shared counters too


@pytest.mark.parametrize("kind", sorted(PRACTICE_KINDS))
async def test_fix_on_practice_sessions_are_not_learned_but_are_audited(kind):
    f, eng = make(exclude_practice=True)
    sid = await converse(eng, kind)
    assert trials(f) == {}
    with session_scope(f) as db:
        notes = [e.payload for e in db.scalars(select(LedgerEvent).where(LedgerEvent.session_id == sid, LedgerEvent.type == "note"))
                 if e.payload.get("event") == "tactic_outcome_not_learned"]
    assert len(notes) == len(CONVERSATION) - 1 and all(n["reason"] == "practice_session" for n in notes)


@pytest.mark.parametrize("exclude", [False, True])
async def test_live_sessions_are_learned_either_way(exclude):
    f, eng = make(exclude_practice=exclude)
    await converse(eng, "live")
    assert sum(t for (scope, _, _), (_, t) in trials(f).items() if scope == "alice") == len(CONVERSATION) - 1


# ---------------- rebuild tool (dry run by default) ----------------
async def _history_with_old_behaviour(url: str = "sqlite://"):
    """Live sessions first (snapshot = what the fixed learner would hold), then practice sessions recorded the old way."""
    f, eng = make(exclude_practice=False, url=url)
    for _ in range(3):
        await converse(eng, "live")
    snapshot = trials(f)
    for kind in ("simulation", "manual", "simulation"):
        await converse(eng, kind)
    return f, snapshot


async def test_replay_of_full_history_reproduces_the_live_counters():
    f, _ = await _history_with_old_behaviour()
    with session_scope(f) as db:
        r = rebuild.report(db)
    assert r["fidelity_ok"] and r["fidelity_mismatched_rows"] == 0
    assert r["scored_outcomes_by_kind"] == {"live": 9, "simulation": 6, "manual": 3}


async def test_positive_control_apply_refuses_counters_history_cannot_explain(tmp_path, capsys):
    url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    f, _ = await _history_with_old_behaviour(url)
    with session_scope(f) as db:
        db.add(TacticStat(scope="alice", scam_type="kyc_bank", tactic="wind_down", successes=5, trials=5))   # not in any history
    before = trials(f)
    assert rebuild.main(["--database-url", url, "--apply"]) == 2
    assert "REFUSING" in capsys.readouterr().out and trials(f) == before


async def test_dry_run_changes_nothing_and_rebuild_equals_live_only_history():
    f, snapshot = await _history_with_old_behaviour()
    before = trials(f)
    assert before != snapshot                                  # the practice sessions really did change the counters
    with session_scope(f) as db:
        r = rebuild.report(db)
    assert trials(f) == before                                 # dry run is read-only
    assert r["rows_that_would_change"] > 0
    with session_scope(f) as db:
        rebuild.apply(db)
    assert trials(f) == snapshot                               # rebuilt counters == what the fixed engine would have learned


async def test_report_contains_no_identifiers():
    f, _ = await _history_with_old_behaviour()
    with session_scope(f) as db:
        text = repr(rebuild.report(db))
    assert "alice" not in text and "synth.refund" not in text and "SYNT0000001" not in text
