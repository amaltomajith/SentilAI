import random

import pytest
from sqlalchemy import select

from sentinel.config import Settings
from sentinel.db import make_engine, make_session_factory, session_scope
from sentinel.db.models import Profile, Session, TacticStat, User
from sentinel.llm import FakeLLM
from sentinel.orchestrator import bandit, strategy
from sentinel.orchestrator.engine import Engine
from sentinel.orchestrator.ploys import PLOYS, ploy_order


# ---------------- analysis ----------------
@pytest.mark.parametrize("msg,expected", [
    ("This is CBI. Your Aadhaar is linked to a money laundering case. You will be arrested.", "police_impersonation"),
    ("Dear user your SBI KYC is expired, account will be blocked", "kyc_bank"),
    ("Congratulations you won the KBC lucky draw prize, pay processing fee", "lottery_prize"),
    ("Work from home part time job, earn Rs 5000 per day, registration fee 999", "job_task"),
    ("Invest in bitcoin, guaranteed returns", "investment_crypto"),
    ("Hi, are we meeting for tea at five?", "other"),
])
def test_scam_type_detection(msg, expected):
    assert strategy.analyze(msg, 0, set()).scam_type == expected


def test_stage_and_pressure():
    a = strategy.analyze("URGENT last warning pay immediately or arrest within 2 hours", 3, set())
    assert a.pressure == "high" and a.stage == "threat"
    assert strategy.analyze("hello", 0, set()).stage == "opening"
    assert strategy.analyze("ok", 2, {"upi"}).stage == "payment_pushed"
    assert strategy.analyze("please pay when free", 2, set()).pressure == "low"


def test_language_detection_and_mirroring_only_when_the_user_speaks_it():
    assert strategy.detect_language("aap abhi paisa bhejo turant") == "Hinglish"
    assert strategy.detect_language("\u0906\u092a\u0915\u093e \u0916\u093e\u0924\u093e \u092c\u0902\u0926 \u0939\u094b \u091c\u093e\u090f\u0917\u093e") == "Hindi"
    assert strategy.detect_language("\u0d28\u0d3f\u0d19\u0d4d\u0d19\u0d33\u0d41\u0d1f\u0d46 \u0d05\u0d15\u0d4d\u0d15\u0d57\u0d23\u0d4d\u0d1f\u0d4d") == "Malayalam"
    assert strategy.detect_language("send the money now") == "English"
    assert "Hinglish" in strategy.lang_instruction("Hinglish", ["English", "Hindi"])
    assert "English" in strategy.lang_instruction("Hinglish", ["English"])          # user does not speak it: do not fake fluency
    assert "Malayalam" in strategy.lang_instruction("Malayalam", ["Malayalam"])
    assert "English" in strategy.lang_instruction("Tamil", ["Malayalam"])


# ---------------- playbook ----------------
def test_playbook_adds_scam_specific_tactics_and_keeps_default_first():
    assert ploy_order(set(), 0)[0] == "ask_payment_rail"
    assert ploy_order(set(), 1, "police_impersonation")[0] == "official_verification_stall"
    assert ploy_order({"phone"}, 1, "police_impersonation")[0] != "official_verification_stall"
    assert all(p in PLOYS for p in ploy_order(set(), 5, "kyc_bank"))


# ---------------- bandit (positive control: it must beat blind choice) ----------------
def simulate(policy, episodes=600, seed=7):
    """A scammer who reveals a phone number only after 'family_consult' (70%) and almost never after other tactics (10%)."""
    rng = random.Random(seed)
    stats: dict[str, tuple[float, float]] = {}
    wins = 0
    options = ["ask_callback_number", "family_consult", "ask_beneficiary_name", "card_ready_stall"]
    for _ in range(episodes):
        choice = policy(options, stats, rng)
        ok = rng.random() < (0.7 if choice == "family_consult" else 0.1)
        s, t = stats.get(choice, (0.0, 0.0))
        stats[choice] = (s + ok, t + 1)
        wins += ok
    return wins / episodes


def test_bandit_learns_the_better_tactic_and_beats_random():
    thompson = simulate(lambda o, st, r: bandit.choose(o, st, r)[0])
    blind = simulate(lambda o, st, r: r.choice(o))
    assert thompson > 0.55 and blind < 0.3 and thompson > blind + 0.25


def test_cold_start_follows_the_playbook_order_deterministically():
    opts = ["upi_daily_limit", "ask_beneficiary_name", "card_ready_stall"]
    assert all(bandit.choose(opts, {}, random.Random(i))[0] == "upi_daily_limit" for i in range(20))


# ---------------- engine: outcomes are recorded, collective counters are opt-in and contain no content ----------------
SCAM = "Dear user, your SBI KYC is expired. Pay Rs 500 to refund.dept@ybl immediately or account blocked. Call 9876543210"


async def offline(u):
    raise RuntimeError("offline")


def setup(opt_in: bool):
    f = make_session_factory(make_engine("sqlite://"))
    with session_scope(f) as db:
        db.add(User(id="alice", collective_opt_in=int(opt_in)))
        db.add(Profile(user_id="alice", data={"alias": "Anita", "age": 58, "occupation": "teacher", "languages": ["English", "Hindi"]}, share={}))
    return f, Engine(f, Settings(), FakeLLM(["Kindly wait sir, my app shows error. Please share the UPI again."]), fetch=offline)


@pytest.mark.parametrize("opt_in", [False, True])
async def test_outcome_updates_private_stats_and_global_counters_only_when_opted_in(opt_in):
    f, eng = setup(opt_in)
    sid = eng.create_session("manual", user_id="alice")
    r1 = await eng.handle_inbound(sid, SCAM)
    assert r1.gate["strategy"]["scam_type"] == "kyc_bank"
    with session_scope(f) as db:
        assert db.get(Session, sid).pending_tactic.startswith("kyc_bank|")
        assert db.scalars(select(TacticStat)).all() == []              # nothing is scored before the next message
    await eng.handle_inbound(sid, "Why not paying? Send now!")           # no new detail revealed -> failure for the previous tactic
    with session_scope(f) as db:
        rows = {(r.scope, r.scam_type): (r.successes, r.trials) for r in db.scalars(select(TacticStat))}
    assert rows[("alice", "kyc_bank")] == (0, 1)
    assert (("*", "kyc_bank") in rows) is opt_in
    if opt_in:                                                          # counters only: no text, no user id, no numbers
        g = next(r for r in rows if r[0] == "*")
        assert set(TacticStat.__table__.columns.keys()) == {"scope", "scam_type", "tactic", "successes", "trials"}


async def test_successful_tactic_is_rewarded_when_the_scammer_reveals_what_it_targeted():
    f, eng = setup(False)
    sid = eng.create_session("manual", user_id="alice")
    await eng.handle_inbound(sid, "Dear user your SBI KYC expired. Pay now or account blocked, urgent")        # no IOC in the first message
    with session_scope(f) as db:
        tactic = db.get(Session, sid).pending_tactic.split("|")[1]
    await eng.handle_inbound(sid, "Send Rs 500 to refund.dept@ybl or A/C 50100123456789 IFSC HDFC0001234")      # reveals payment details
    with session_scope(f) as db:
        row = db.get(TacticStat, ("alice", "kyc_bank", tactic))
    assert row.trials == 1 and row.successes == 1


async def test_agent_mirrors_hinglish_only_for_a_user_who_speaks_it():
    f, eng = setup(False)
    captured: dict = {}

    class Spy(FakeLLM):
        async def complete(self, system, messages, **kw):
            captured["system"] = system
            return "Kindly wait sir, please share the UPI again."
    eng.llm = Spy()
    sid = eng.create_session("manual", user_id="alice")
    await eng.handle_inbound(sid, "aap abhi paisa bhejo turant warna khata band ho jayega, refund.dept@ybl")
    assert "Hinglish" in captured["system"]
    with session_scope(f) as db:
        db.get(Profile, "alice").data = {"alias": "Anita", "age": 58, "occupation": "teacher", "languages": ["English"]}
    sid2 = eng.create_session("manual", user_id="alice")
    await eng.handle_inbound(sid2, "aap abhi paisa bhejo turant warna khata band ho jayega, refund.dept@ybl")
    assert "Hinglish" not in captured["system"] and "simple English" in captured["system"]