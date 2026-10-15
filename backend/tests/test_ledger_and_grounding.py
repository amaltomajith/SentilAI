from sqlalchemy import select

from sentinel import ledger
from sentinel.db.models import LedgerEvent
from sentinel.grounding import Candidate, extract_candidates, extract_grounded, ground


def _fill(db, sess, n=5):
    for i in range(n):
        ledger.append(db, sess, "turn", {"role": "scammer" if i % 2 == 0 else "agent", "text": f"msg {i}"})
    db.flush()


def test_valid_chain_verifies(db, sess):
    _fill(db, sess)
    r = ledger.verify(db, sess.id)
    assert r.ok and r.checked == 5 and r.head_hash == sess.head_hash


def test_mutated_payload_detected(db, sess):
    _fill(db, sess)
    ev = db.scalar(select(LedgerEvent).where(LedgerEvent.seq == 3))
    ev.payload = {**ev.payload, "text": "tampered"}
    db.flush()
    r = ledger.verify(db, sess.id)
    assert not r.ok and r.bad_seq == 3


def test_deleted_event_detected(db, sess):
    _fill(db, sess)
    db.delete(db.scalar(select(LedgerEvent).where(LedgerEvent.seq == 2)))
    db.flush()
    assert not ledger.verify(db, sess.id).ok


def test_truncation_detected(db, sess):
    _fill(db, sess)
    db.delete(db.scalar(select(LedgerEvent).where(LedgerEvent.seq == 5)))
    db.flush()
    r = ledger.verify(db, sess.id)
    assert not r.ok and "truncation" in r.reason


def test_reorder_detected(db, sess):
    _fill(db, sess)
    a = db.scalar(select(LedgerEvent).where(LedgerEvent.seq == 2))
    b = db.scalar(select(LedgerEvent).where(LedgerEvent.seq == 3))
    a.payload, b.payload = b.payload, a.payload
    db.flush()
    assert not ledger.verify(db, sess.id).ok


def test_exported_proof_verifies_offline_and_tamper_fails(db, sess):
    _fill(db, sess)
    proof = ledger.export_proof(db, sess.id)
    assert ledger.verify_proof(proof)
    proof["events"][1]["payload"]["text"] = "x"
    assert not ledger.verify_proof(proof)


MSG = ("Pay Rs 500 to refund.dept@ybl now! Or transfer to A/C No 50100123456789 IFSC HDFC0001234. "
       "Call 98765 43210 or open http://sbi-update.com/kyc. Mail help@sbi.co.in")


def test_extracts_all_kinds_literally():
    c = {(x.kind, x.value) for x in extract_candidates(MSG)}
    assert ("upi", "refund.dept@ybl") in c
    assert ("bank_account", "50100123456789") in c
    assert ("ifsc", "HDFC0001234") in c
    assert ("phone", "9876543210") in c
    assert ("url", "http://sbi-update.com/kyc") in c
    assert not any(k == "upi" and "sbi.co.in" in v for k, v in c)


def test_bank_account_extracted_unlike_v1():
    assert Candidate("bank_account", "50100123456789") in extract_grounded(MSG)


def test_hallucinated_ioc_rejected():
    res = ground([Candidate("upi", "scammer.real@okaxis")], "Pay me quickly please")
    assert not res[0].accepted and res[0].reason == "not_in_message"


def test_honey_token_excluded_even_if_scammer_echoes_it():
    honey = {"ramesh.pension@oksbi"}
    got = {c.value for c in extract_grounded("ok send to ramesh.pension@oksbi no wait use thief@ybl", honey)}
    assert "ramesh.pension@oksbi" not in got and "thief@ybl" in got


def test_honey_url_domain_excluded():
    assert extract_grounded("see http://canary.example.net/r/abc", {"canary.example.net"}) == []


def test_unicode_lookalike_does_not_match():
    assert not ground([Candidate("upi", "pay\u0430@ybl")], "send to paya@ybl")[0].accepted


def test_phone_vs_account_disambiguation():
    kinds = {(c.kind, c.value) for c in extract_candidates("Account number 9876543210 at SBI")}
    assert ("bank_account", "9876543210") in kinds
    assert ("phone", "9876543210") not in kinds