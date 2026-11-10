"""C1 phase 2: the shadow tactic policy logs what it would pick and never changes the live choice."""
import dataclasses
import random

import pytest
from sqlalchemy import select

from sentinel.config import Settings
from sentinel.db import make_engine, make_session_factory, session_scope
from sentinel.db.models import Session, TacticStat, ToolTrace, User
from sentinel.mcp.tools import ToolContext, call_tool, t_select_tactic
from sentinel.orchestrator import bandit

TACTICS = ["ask_payment_rail", "ask_callback_number", "ask_beneficiary_name", "card_ready_stall", "official_verification_stall"]


def world():
    """One user with learned counters for several scam types (so Thompson sampling, not cold start, is exercised)."""
    f = make_session_factory(make_engine("sqlite://"))
    rng = random.Random(0)
    with session_scope(f) as db:
        db.add(User(id="alice", collective_opt_in=1))
        for scope in ("alice", "*"):
            for st in ("kyc_bank", "police_impersonation", "other"):
                for t in TACTICS:
                    n = rng.randint(1, 12)
                    db.add(TacticStat(scope=scope, scam_type=st, tactic=t, successes=rng.randint(0, n), trials=n))
        for i in range(40):
            db.add(Session(id=f"s{i:02d}", kind="live", user_id="alice", exchange_count=1 + i % 4))
    return f


def settings(policy: str) -> Settings:
    return dataclasses.replace(Settings(), bandit_shadow_policy=policy)


async def pick(f, policy, sid, scam_type="kyc_bank"):
    with session_scope(f) as db:
        return await t_select_tactic(ToolContext(db=db, settings=settings(policy)), sid, scam_type=scam_type)


def test_default_is_off(monkeypatch):
    monkeypatch.delenv("SENTINEL_BANDIT_SHADOW_POLICY", raising=False)
    assert Settings().bandit_shadow_policy == ""


@pytest.mark.parametrize("policy", ["pooled", "backoff"])
async def test_live_choice_is_identical_with_the_shadow_on(policy):
    f = world()
    agree = 0
    for i in range(40):
        for st in ("kyc_bank", "police_impersonation", "other"):
            off = await pick(f, "", f"s{i:02d}", st)
            on = await pick(f, policy, f"s{i:02d}", st)
            assert "shadow" not in off                                   # flag off: output exactly as before
            assert {k: v for k, v in on.items() if k != "shadow"} == off  # flag on: live part unchanged
            assert on["shadow"]["policy"] == policy and on["shadow"]["ploy_id"] in TACTICS + ["upi_daily_limit", "need_ifsc",
                                                                                              "need_upi_backup", "link_not_opening",
                                                                                              "family_consult", "partial_test_payment"]
            agree += on["shadow"]["agrees"]
    assert 0 < agree < 120          # the shadow is a genuinely different policy, not a copy of the live one


def test_positive_control_sharing_the_live_random_stream_would_change_live_choices():
    """Proves the 120 cases above are enough to notice interference: if a shadow drew from the live stream first,
    live choices would change in some of them."""
    stats = {t: (random.Random(t).randint(0, 5), 6) for t in TACTICS}
    other = {t: (3, 6) for t in TACTICS}
    changed = 0
    for i in range(120):
        clean = bandit.choose(TACTICS, stats, random.Random(f"s{i}"))[0]
        shared = random.Random(f"s{i}")
        bandit.choose(TACTICS, other, shared)                  # a careless shadow consumes the live stream
        changed += bandit.choose(TACTICS, stats, shared)[0] != clean
    assert changed > 0


def test_unknown_policy_value_is_treated_as_off():
    import asyncio
    f = world()
    assert "shadow" not in asyncio.run(pick(f, "bogus", "s01"))


async def test_shadow_is_logged_in_the_tool_trace():
    f = world()
    with session_scope(f) as db:
        await call_tool(ToolContext(db=db, settings=settings("backoff")), "select_tactic", {"session_id": "s03", "scam_type": "kyc_bank"}, session_id="s03")
    with session_scope(f) as db:
        tr = db.scalar(select(ToolTrace).where(ToolTrace.session_id == "s03"))
        assert tr.result["shadow"]["policy"] == "backoff" and isinstance(tr.result["shadow"]["agrees"], bool)


def test_backoff_and_pooled_stats():
    assert bandit.backoff_stats({"a": (1, 2)}, {"a": (10, 20), "b": (1, 2)}, ["a", "b", "c"]) == {"a": (3.0, 6.0), "b": (1.0, 2.0)}
    assert bandit.backoff_stats({}, {"a": (1, 1)}, ["a"], strength=4.0) == {"a": (1.0, 1.0)}   # never more pseudo-trials than real ones
    f = world()
    with session_scope(f) as db:
        mine = bandit.load_pooled_stats(db, "alice", False)
        both = bandit.load_pooled_stats(db, "alice", True)
        own = sum(r.trials for r in db.scalars(select(TacticStat).where(TacticStat.scope == "alice", TacticStat.tactic == "ask_payment_rail")))
        shared = sum(r.trials for r in db.scalars(select(TacticStat).where(TacticStat.scope == "*", TacticStat.tactic == "ask_payment_rail")))
        assert mine["ask_payment_rail"][1] == own                      # summed over every scam type
        assert both["ask_payment_rail"][1] == own + 0.5 * shared       # shared counters at half weight, as in load_stats
