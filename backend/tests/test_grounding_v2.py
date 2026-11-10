"""Grounding v2 (SENTINEL_GROUNDING_V2): off by default, v1 unchanged, each fix shown failing under v1 first (positive control).
All identifiers are synthetic: synth* UPI ids, .example domains, SYNT IFSC, numbers made of zeros."""
import asyncio

import pytest

from eval import eval_ioc, synth
from sentinel import gate, grounding
from sentinel.config import Settings
from sentinel.grounding import Candidate, extract_candidates, extract_grounded, ground


def kv(cands):
    return {(c.kind, c.value) for c in cands}


@pytest.fixture
def v2_on():
    prev = grounding.v2_enabled()
    grounding.use_v2(True)
    yield
    grounding.use_v2(prev)


def test_flag_is_off_by_default_and_read_from_env(monkeypatch):
    monkeypatch.delenv("SENTINEL_GROUNDING_V2", raising=False)
    assert Settings().grounding_v2 is False
    assert grounding.v2_enabled() is False                          # the test process runs with production defaults
    monkeypatch.setenv("SENTINEL_GROUNDING_V2", "1")
    assert Settings().grounding_v2 is True


def test_v1_is_unchanged_on_the_whole_corpus():
    """Regression lock: v1 numbers equal those reported before v2 existed (docs/RESULTS.md rows 2 and 5, seed 1)."""
    recs = synth.build_corpus(1)
    res = eval_ioc.evaluate(recs)                                    # module default = v1
    hw = [r for r in res["rows"] if r["rec"]["source"] == "handwritten"]
    t = eval_ioc.totals(hw)
    assert (t["tp"], t["fp"], t["fn"]) == (87, 13, 16)
    b = eval_ioc.totals(res["rows"], "bank_account")
    assert (b["tp"], b["tp"] + b["fp"]) == (64, 116)
    for r in recs + synth.build_corpus(1, corpus="heldout"):
        assert extract_candidates(r["text"]) == extract_candidates(r["text"], v2=False)


@pytest.mark.parametrize("text,v1_wrong,v2_expected", [
    ("Helpline 1800 000 0001 is busy", {("bank_account", "18000000001")}, set()),                       # toll-free
    ("Your UTR 000000001234 failed", {("bank_account", "000000001234")}, set()),                        # reference
    ("Card 0000 0000 0000 1234 is blocked", {("bank_account", "0000000000001234")}, set()),             # card
    ("Call 0 70000 00001 now", {("bank_account", "07000000001")}, {("phone", "7000000001")}),           # trunk prefix
    ("Update at synth-kyc.example/pay today", set(), {("url", "synth-kyc.example/pay")}),               # no scheme
    ("Open www.synth-kyc.example now", set(), {("url", "www.synth-kyc.example")}),
    ("Pay on synthkyc @ ybl quickly", set(), {("upi", "synthkyc@ybl")}),                               # spaced @
    ("कॉल करें ७००००००००१", set(), {("phone", "7000000001")}),                                     # Devanagari digits
])
def test_each_v2_fix_with_v1_as_positive_control(text, v1_wrong, v2_expected):
    v1, v2 = kv(extract_grounded(text, v2=False)), kv(extract_grounded(text, v2=True))
    assert v1_wrong <= v1 and not (v2_expected <= v1 and v2_expected)      # the failure is real under v1
    assert v2 == v2_expected


def test_v2_keeps_hinted_accounts_phones_after_weak_labels_and_ignores_non_links():
    assert kv(extract_grounded("A/c no 000000001234 IFSC SYNT0000001", v2=True)) == {("bank_account", "000000001234"), ("ifsc", "SYNT0000001")}
    assert kv(extract_grounded("Complaint ID 000000001234. Call 7000000001", v2=True)) == {("phone", "7000000001")}
    assert kv(extract_grounded("Case id 7000000001", v2=True)) == {("phone", "7000000001")}
    for text in ("Meet at 5.in the evening", "Version 2.1.4 needed", "Rs.500 only", "Meet me @ 5 pm", "hello @ home",
                 "Mail refunds@desk-help.example", "File report.pdf attached"):
        assert extract_grounded(text, v2=True) == [], text


def test_literal_rule_still_holds_under_v2():
    real = "Pay synthkyc@ybl"
    lookalike = "Pay synthkус@ybl"                                     # Cyrillic у and с
    c = Candidate("upi", "synthkyc@ybl")
    assert ground([c], real, v2=True)[0].accepted                      # positive control
    assert ground([c], lookalike, v2=True)[0].reason == "not_in_message"
    assert ground([Candidate("url", "synth-kyc.example/pay")], "nothing here", v2=True)[0].reason == "not_in_message"


def test_scheme_less_decoy_is_rejected_by_host():
    text = "Your synthdecoy.example/claim link failed, pay synthkyc@ybl"
    assert ("url", "synthdecoy.example/claim") in kv(extract_grounded(text, v2=True))              # positive control: no honey set
    got = kv(extract_grounded(text, {"synthdecoy.example"}, v2=True))
    assert got == {("upi", "synthkyc@ybl")}


def test_gate_leak_check_is_never_looser_under_v2(v2_on):
    draft = "ok my card 0000 0000 0000 1234"
    assert not extract_candidates(draft)                              # v2 alone would not see it ...
    assert any(v.code == "leak" for v in gate.detect(draft))          # ... but the gate still flags it
    assert any(v.code == "leak" for v in gate.detect("try synthme @ ybl"))   # and v2 adds the spaced UPI id


def test_gate_is_unchanged_with_the_flag_off():
    for text in ("my card 0000 0000 0000 1234", "try synthme @ ybl", "see synth-kyc.example/pay", "call 7000000001"):
        assert grounding.extract_for_leak_check(text) == extract_candidates(text, v2=False)


def test_scheme_less_links_get_the_right_host_downstream():
    from sentinel.enrich import enrich_domain
    from sentinel.graph import _domain
    assert grounding.url_host("www.Synth-Kyc.example/pay?x=1") == "www.synth-kyc.example"
    assert grounding.url_host("https://synth-kyc.example/a") == "synth-kyc.example"
    assert _domain("synth-kyc.example/pay") == "synth-kyc.example"
    seen = []

    async def fetch(url):
        seen.append(url)
        return {}
    out = asyncio.run(enrich_domain("synth-kyc.example/pay", fetch=fetch))
    assert out["domain"] == "synth-kyc.example" and seen == ["https://rdap.org/domain/synth-kyc.example"]


def test_v2_on_heldout_accepts_no_decoys_and_compare_report_has_no_values():
    ho = synth.build_corpus(1, corpus="heldout")
    assert eval_ioc.evaluate_version(ho, True)["honey_accepted"] == 0
    text = eval_ioc.compare(1)
    rendered = {g["value"] for r in synth.build_corpus(1) + ho for g in r["gold_iocs"]}
    assert not [v for v in rendered if v in text]
