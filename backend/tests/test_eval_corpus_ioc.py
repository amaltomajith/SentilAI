"""Synthetic corpus hygiene and the C3 IOC evaluation harness. Every 'must not' check has a positive control."""
import re

from eval import eval_ioc, synth
from sentinel import grounding

LONG_DIGITS = re.compile(r"\d[\d\s-]{5,}\d")          # 7+ digits in a run (Python \d also matches Indic digits)


def realistic_identifiers(text: str) -> list[str]:
    """Anything in COMMITTED text that could be a real person's number, account, UPI id, IFSC or domain."""
    t = re.sub(r"\bSYN[A-Z]0\d{6}\b", " ", synth.SLOT_RE.sub(" ", text))   # made-up bank code, allowed
    bad = [m.group(0) for m in LONG_DIGITS.finditer(t)
           if len(re.sub(r"\D", "", m.group(0))) >= 7 and not re.fullmatch(r"\d{1,2}-\d{1,2}-\d{4}", m.group(0))]   # dates are fine
    bad += [m.group(0) for m in grounding.UPI_RE.finditer(t) if not m.group(0).lower().startswith("synth")]
    bad += [m.group(0) for m in grounding.IFSC_RE.finditer(t) if not m.group(0).startswith("SYN")]
    bad += [u for u in re.findall(r"[a-z0-9-]+\.[a-z]{2,}(?:/\S*)?", t.lower()) if not re.search(r"\.(example|invalid)\b", u)
            and not re.fullmatch(r"[a-z0-9-]+\.(pdf|jpg|png|apk|docx?)", u)]   # file names are not domains
    return bad


def test_positive_control_the_scanner_flags_realistic_values():
    assert realistic_identifiers("Call 9123456780 or pay ramesh@oksbi, IFSC HDFC0001234, site sbi-kyc.com")
    assert realistic_identifiers("खाता ९८७६५४३२१० है")
    assert not realistic_identifiers("Call {PHONE_1|spaced} or pay {UPI_1}, IFSC SYNT0000001, mail support@kyc-helpdesk.example")


def test_committed_corpus_has_no_realistic_identifiers_and_valid_slots():
    recs = synth.load_handwritten() + synth.load_handwritten(synth.HELDOUT) + synth.load_handwritten(synth.HELDOUT_V3)
    assert len(recs) >= 180 and len({r["id"] for r in recs}) == len(recs)
    for r in recs:
        assert not realistic_identifiers(r["text"]), (r["id"], realistic_identifiers(r["text"]))
        slots = {f"{m.group(1)}_{m.group(2)}" for m in synth.SLOT_RE.finditer(r["text"])}
        assert set(r["iocs"]) <= slots, r["id"]
        assert r["triage"] in ("scam", "benign") and r["turn"] in ("opener", "followup")
        assert (r["scam_type"] == "") == (r["triage"] == "benign"), r["id"]


def test_rendering_is_seeded_synthetic_and_stays_in_the_synthetic_namespace():
    a, b = synth.build_corpus(1), synth.build_corpus(1)
    assert a == b and a != synth.build_corpus(2)
    assert all(r["synthetic"] is True and r["seed"] == 1 for r in a)
    for r in a:
        for g in r["gold_iocs"]:
            if g["kind"] == "upi":
                assert g["value"].startswith("synth")
            if g["kind"] == "ifsc":
                assert g["value"].startswith("SYN")
            if g["kind"] == "url":
                assert re.search(r"\.(example|invalid)(/|$)", g["value"].split("?")[0])


def test_scoring_counts_tp_fp_fn():
    gold = [{"kind": "upi", "value": "synthkyc@ybl"}, {"kind": "phone", "value": "7000000001"}]
    s = eval_ioc.score_record(gold, [("upi", "SynthKyc@ybl"), ("bank_account", "123456789012")])
    assert s["upi"]["tp"] == 1 and s["phone"]["fn"] == 1 and s["bank_account"]["fp"] == 1
    assert eval_ioc.norm("url", "HTTPS://www.Kyc-desk.example/pay/") == "kyc-desk.example/pay"
    assert eval_ioc.norm("phone", "+91 70000 00001") == "7000000001" and eval_ioc.norm("phone", "०७००००००००१") == "7000000001"


def test_positive_control_harness_detects_a_broken_extractor():
    recs = synth.build_corpus(1)
    good = eval_ioc.evaluate(recs)
    assert eval_ioc.totals(good["rows"], "url")["tp"] > 0

    def no_urls(text):
        return [c for c in grounding.extract_candidates(text) if c.kind != "url"]
    broken = eval_ioc.evaluate(recs, extract=no_urls)
    assert eval_ioc.prf(eval_ioc.totals(broken["rows"], "url"))[1] == 0.0


def test_positive_control_harness_detects_wrong_values():
    recs = synth.build_corpus(1)
    base_fp = eval_ioc.totals(eval_ioc.evaluate(recs)["rows"])["fp"]

    def otp_as_account(text):     # a literal 6-digit OTP is in the text, so grounding accepts it; it is still wrong
        return grounding.extract_candidates(text) + [grounding.Candidate("bank_account", m) for m in re.findall(r"\b\d{6}\b", text)]
    assert eval_ioc.totals(eval_ioc.evaluate(recs, extract=otp_as_account)["rows"])["fp"] > base_fp


def test_decoys_are_never_accepted_and_positive_control_without_the_honey_check():
    recs = synth.build_corpus(1)
    res = eval_ioc.evaluate(recs)
    assert res["honey_records"] >= 4 and res["honey_accepted"] == 0

    def ground_without_honey(cands, text, honey=frozenset()):
        return grounding.ground(cands, text, frozenset())
    assert eval_ioc.evaluate(recs, ground=ground_without_honey)["honey_accepted"] > 0


def test_report_shows_templates_not_rendered_values():
    text = eval_ioc.report(1)
    rendered = {g["value"] for r in synth.build_corpus(1) for g in r["gold_iocs"]}
    assert not [v for v in rendered if v in text]
    assert not re.search(r"(?<!\d)\d{10}(?!\d)", text)
