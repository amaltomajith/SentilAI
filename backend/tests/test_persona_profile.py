import pytest
from sqlalchemy import select

from sentinel.config import Settings
from sentinel.db import make_engine, make_session_factory, session_scope
from sentinel.db.models import Profile, Turn
from sentinel.gate import detect, run_gate
from sentinel.llm import FakeLLM
from sentinel.orchestrator import persona as P
from sentinel.orchestrator.engine import Engine

PROFILE = {"alias": "Anita", "age": 58, "occupation": "school teacher", "city": "Pune", "languages": ["English", "Hindi"],
           "formality": "formal", "tech_comfort": "low", "full_name": "Anita Rao", "employer": "St Marys School", "own_phone": "+91 98765 43210"}
SCAM = "Dear user, your SBI KYC is expired. Pay Rs 500 to refund.dept@ybl immediately or account blocked. Call 9876543210"


def built(share=None, data=None):
    d, s = P.validate_profile(data or PROFILE, share or {})
    return P.build(d, s, "user_1")


# ---------------- validation ----------------
@pytest.mark.parametrize("bad", [
    {"alias": "A", "extra": "my account number is 50100123456789"},
    {"alias": "A", "extra": "send to me@okaxis"},
    {"alias": "A", "situation": "my OTP is usually sent by SMS"},
    {"alias": "A", "extra": "aadhaar 1234 5678 9012"},
    {"alias": "A", "age": 7},
    {"alias": "A", "age": "abc"},
    {"alias": "A" * 31},
    {"alias": "A", "languages": "English"},
])
def test_profile_rejects_sensitive_or_malformed_values(bad):
    with pytest.raises(P.ProfileError):
        P.validate_profile(bad)


def test_profile_completeness_and_cleaning():
    d, s = P.validate_profile({"alias": " Anita ", "age": "58", "occupation": "teacher", "junk": "x"}, {"city": 0, "junk": 1, "alias": 0})
    assert d == {"alias": "Anita", "age": 58, "occupation": "teacher"} and s == {"city": False} and P.is_complete(d)
    assert not P.is_complete({"alias": "A"})


# ---------------- the model never sees protected details ----------------
def test_prompt_contains_shared_facts_and_never_protected_ones():
    p = built(share={"city": False})
    prompt = p.system("Ask for the UPI id.")
    for secret in ("Anita Rao", "Rao", "St Marys", "98765", "Pune"):          # full name, surname, employer, own phone, unshared city
        assert secret not in prompt, secret
    for shown in ("Anita", "58 years old", "school teacher", "formal"):
        assert shown in prompt
    assert p.honey["upi"] in prompt and "@" in p.honey["upi"]


def test_alias_is_not_protected_even_though_it_is_the_first_name():
    p = built()
    assert "anita" not in p.protected and "anita rao" in p.protected and "rao" in p.protected
    assert p.protected >= {"st marys school", "76543210"}


def test_honey_identity_is_stable_per_user_and_differs_between_users():
    assert P.honey_upi("Anita", "u1") == P.honey_upi("Anita", "u1") != P.honey_upi("Anita", "u2")


# ---------------- the gate keeps real details out (positive control) ----------------
LEAKY = "I am Anita Rao and I teach at St Marys School in Pune. You can call me on 9876543210 sir. Please share the UPI again."


def test_gate_blocks_real_details_and_the_control_proves_the_test_can_fail():
    p = built(share={"city": False})
    approved = {"9876543210"}
    off = run_gate(LEAKY, approved, enabled=False, protected=p.protected)
    assert off.verdict == "bypassed" and "real_detail_leak" in {v.code for v in off.violations}
    assert "Anita Rao" in off.final                                   # control: without the gate the real name goes out
    on = run_gate(LEAKY, approved, protected=p.protected)
    assert on.verdict in ("repaired", "fallback")
    assert not detect(on.final, approved, p.protected)
    for secret in ("Anita Rao", "St Marys", "Pune"):
        assert secret not in on.final


def test_gate_normalises_phone_formatting_and_ignores_word_fragments():
    p = built()
    assert detect("my number is 98765-43210", {"98765-43210"}, p.protected)[0].code == "real_detail_leak"
    assert not [v for v in detect("The restaurant is raring to go sir", set(), p.protected) if v.code == "real_detail_leak"]   # 'rao' not inside 'raring'


# ---------------- engine end to end ----------------
def make(gate_enabled=True, llm_text=LEAKY):
    f = make_session_factory(make_engine("sqlite://"))
    with session_scope(f) as db:
        d, s = P.validate_profile(PROFILE, {"city": False})
        db.add(Profile(user_id="alice", data=d, share=s))

    async def offline(u):
        raise RuntimeError("offline")
    return f, Engine(f, Settings(), FakeLLM([llm_text]), fetch=offline, gate_enabled=gate_enabled)


async def test_engine_never_sends_the_users_real_details_but_does_when_the_gate_is_off():
    f, eng = make(gate_enabled=False)
    sid = eng.create_session("manual", user_id="alice")
    await eng.handle_inbound(sid, SCAM)
    with session_scope(f) as db:
        sent = next(t for t in db.scalars(select(Turn).where(Turn.session_id == sid, Turn.role == "agent"))).text
    assert "Anita Rao" in sent                                         # control

    f, eng = make(gate_enabled=True)
    sid = eng.create_session("manual", user_id="alice")
    r = await eng.handle_inbound(sid, SCAM)
    with session_scope(f) as db:
        sent = next(t for t in db.scalars(select(Turn).where(Turn.session_id == sid, Turn.role == "agent"))).text
    assert r.gate["verdict"] in ("repaired", "fallback")
    assert not any(x in sent for x in ("Anita Rao", "St Marys", "Pune"))
    assert "real_detail_leak" in {v["code"] for v in r.gate["violations"]}