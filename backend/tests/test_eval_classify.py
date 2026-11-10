"""C7 harness. Positive controls: a stub that engages everything must show 100% benign-engaged; a stub that never
engages must show 0% scams engaged; a deliberately wrong scam-type labeller must score 0%."""
from pathlib import Path

from eval import eval_classify as ec
from eval import synth


def test_positive_control_engage_everything_shows_benign_engaged_100():
    recs = [r for r in synth.build_corpus(1) if r["turn"] == "opener"]
    m = ec.triage_metrics(ec.triage_rows(recs, verdict=lambda t: "scam"))
    assert m["benign_engaged"] == 1.0 and m["scam_engaged"] == 1.0


def test_positive_control_engage_nothing_shows_zero_scams_engaged():
    recs = [r for r in synth.build_corpus(1) if r["turn"] == "opener"]
    m = ec.triage_metrics(ec.triage_rows(recs, verdict=lambda t: "uncertain"))
    assert m["scam_engaged"] == 0.0 and m["benign_engaged"] == 0.0 and m["scam_halted"] == 1.0


def test_scam_type_metrics_detect_a_wrong_labeller():
    rows = [{"gold": "kyc_bank", "alt": [], "pred": "other", "turn": "opener", "source": "handwritten"}] * 3
    m = ec.scam_type_metrics(rows)
    assert m["accuracy"] == 0.0 and m["wrong_as_other"] == 1.0
    assert ec.scam_type_metrics([dict(rows[0], pred="kyc_bank")])["accuracy"] == 1.0


def test_uci_loader_and_missing_file(tmp_path: Path):
    p = tmp_path / "s.tsv"
    p.write_text("ham\tsee you at 5\nspam\tWIN a prize now, claim today\nbad line\n", encoding="utf-8")
    assert [r["triage"] for r in ec.load_uci(p)] == ["benign", "scam"]
    lines, m = ec.uci_section(tmp_path / "missing")
    assert m is None and "skipped" in lines[0]


def test_report_never_prints_public_dataset_text(tmp_path: Path):
    p = tmp_path / "s.tsv"
    p.write_text("ham\tunique-ham-sentence-xyz\nspam\tunique-spam-sentence-abc call now urgent\n", encoding="utf-8")
    text, summary = ec.report(1, p)
    assert "unique-ham-sentence-xyz" not in text and "unique-spam-sentence-abc" not in text
    assert summary["uci_sms_spam"]["n_benign"] == 1
