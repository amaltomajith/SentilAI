"""C7: how often does Sentinel's rule triage halt a scam or engage a benign chat, and how often is the scam type wrong?

    python -m eval.eval_classify --seed 1 [--uci eval/data/external/uci_sms_spam/SMSSpamCollection]

Synthetic corpus (in-domain, written for Sentinel) and, optionally, the public UCI SMS Spam Collection (out-of-domain:
SMS spam is not WhatsApp scam chat; reported separately; message text is never printed).
Triage is evaluated on opening messages only, because the engine runs triage only until a session is engaged.
Scam type is evaluated on openers AND follow-up turns, because the engine recomputes it on every inbound message and
uses it as the tactic learner's context key.
No LLM is called: this measures the deterministic rules (`rule_triage`, `strategy.analyze`).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Callable

from eval import synth
from sentinel import grounding
from eval.stats import bootstrap_ci, fmt, ratio
from sentinel.orchestrator.strategy import analyze
from sentinel.orchestrator.triage import rule_triage

HERE = Path(__file__).resolve().parent
REPORT_MD = HERE / "reports" / "classify.md"
REPORT_JSON = HERE / "reports" / "classify.json"
UCI_DEFAULT = HERE / "data" / "external" / "uci_sms_spam" / "SMSSpamCollection"
VERDICTS = ("scam", "uncertain", "benign")


def triage_rows(records, verdict: Callable[[str], str] = lambda t: rule_triage(t).verdict) -> list[tuple[str, str]]:
    return [(r["triage"], verdict(r["text"])) for r in records]


def triage_metrics(rows: list[tuple[str, str]]) -> dict:
    c = Counter(rows)
    n_s, n_b = sum(v for (g, _), v in c.items() if g == "scam"), sum(v for (g, _), v in c.items() if g == "benign")
    return {"n_scam": n_s, "n_benign": n_b, "confusion": {f"{g}->{p}": c[(g, p)] for g in ("scam", "benign") for p in VERDICTS},
            "scam_engaged": ratio(c[("scam", "scam")], n_s), "scam_halted": ratio(n_s - c[("scam", "scam")], n_s),
            "benign_engaged": ratio(c[("benign", "scam")], n_b), "benign_halted": ratio(n_b - c[("benign", "scam")], n_b)}


def _rate(gold: str, pred: str):
    return lambda s: ratio(sum(1 for g, p in s if g == gold and p == pred), sum(1 for g, _ in s if g == gold))


def triage_table(rows, title: str) -> list[str]:
    m = triage_metrics(rows)
    se, be = bootstrap_ci(rows, _rate("scam", "scam")), bootstrap_ci(rows, _rate("benign", "scam"))
    L = [f"#### Triage: {title} (scam {m['n_scam']}, benign {m['n_benign']})", "",
         "| Gold \\ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |", "|---|---|---|---|"]
    for g in ("scam", "benign"):
        L.append(f"| {g} | " + " | ".join(str(m["confusion"][f"{g}->{p}"]) for p in VERDICTS) + " |")
    L += ["", f"- Scams engaged: **{fmt(m['scam_engaged'])}** (95% CI {fmt(se[0])}–{fmt(se[1])}); halted: {fmt(m['scam_halted'])}",
          f"- Benign messages engaged (the safety-critical error): **{fmt(m['benign_engaged'])}** (95% CI {fmt(be[0])}–{fmt(be[1])})", ""]
    return L


def scam_type_rows(records) -> list[dict]:
    out = []
    for r in records:
        if r["triage"] != "scam":
            continue
        pred = analyze(r["text"], 0 if r["turn"] == "opener" else 2, set()).scam_type
        out.append({"gold": r["scam_type"], "alt": r.get("scam_type_alt", []), "pred": pred, "turn": r["turn"], "source": r["source"]})
    return out


def scam_type_metrics(rows) -> dict:
    n = len(rows)
    strict = sum(x["pred"] == x["gold"] for x in rows)
    lenient = sum(x["pred"] == x["gold"] or x["pred"] in x["alt"] for x in rows)
    wrong = [x for x in rows if x["pred"] != x["gold"]]
    return {"n": n, "accuracy": ratio(strict, n), "accuracy_lenient": ratio(lenient, n),
            "wrong_as_other": ratio(sum(x["pred"] == "other" for x in wrong), len(wrong)),
            "top_confusions": Counter(f"{x['gold']} -> {x['pred']}" for x in wrong).most_common(8)}


def scam_type_section(rows) -> tuple[list[str], dict]:
    L = ["#### Scam type (`strategy.analyze`), scam messages only", "", "| Subset | N | Accuracy (95% CI) | Lenient accuracy | Wrong labels that are `other` |", "|---|---|---|---|---|"]
    out = {}
    for name, sub in [("hand-written openers", [x for x in rows if x["source"] == "handwritten" and x["turn"] == "opener"]),
                      ("hand-written follow-ups", [x for x in rows if x["source"] == "handwritten" and x["turn"] == "followup"]),
                      ("generated openers", [x for x in rows if x["source"] == "generated"])]:
        m = scam_type_metrics(sub)
        lo, hi = bootstrap_ci(sub, lambda s: ratio(sum(x["pred"] == x["gold"] for x in s), len(s)))
        L.append(f"| {name} | {m['n']} | {fmt(m['accuracy'])} ({fmt(lo)}–{fmt(hi)}) | {fmt(m['accuracy_lenient'])} | {fmt(m['wrong_as_other'])} |")
        out[name] = m
    L += ["", "Most common confusions (hand-written, openers and follow-ups):", ""]
    L += [f"- `{k}`: {v}" for k, v in scam_type_metrics([x for x in rows if x["source"] == "handwritten"])["top_confusions"]] + [""]
    return L, out


def load_uci(path: Path) -> list[dict]:
    recs = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        label, _, text = line.partition("\t")
        if label in ("ham", "spam") and text:
            recs.append({"triage": "benign" if label == "ham" else "scam", "text": text})
    return recs


def uci_section(path: Path) -> tuple[list[str], dict | None]:
    if not path.exists():
        return ["#### Public dataset: skipped (file not downloaded)", ""], None
    recs = load_uci(path)
    rows = triage_rows(recs)
    m = triage_metrics(rows)
    se, be = bootstrap_ci(rows, _rate("scam", "scam")), bootstrap_ci(rows, _rate("benign", "scam"))
    L = [f"#### Out-of-domain: UCI SMS Spam Collection (public dataset, {len(recs)} messages: ham {m['n_benign']}, spam {m['n_scam']})", "",
         "Gold labels are ham/spam. Spam includes marketing that is not fraud, so 'spam not engaged' is not a miss in Sentinel's sense.", "",
         "| Gold \\ rule verdict | scam (engage) | uncertain (halt) | benign (halt) |", "|---|---|---|---|"]
    for g, name in (("benign", "ham"), ("scam", "spam")):
        L.append(f"| {name} | " + " | ".join(str(m["confusion"][f"{g}->{p}"]) for p in VERDICTS) + " |")
    L += ["", f"- Ham messages the rules would engage: **{fmt(m['benign_engaged'])}** (95% CI {fmt(be[0])}–{fmt(be[1])})",
          f"- Spam messages the rules would engage: {fmt(m['scam_engaged'])} (95% CI {fmt(se[0])}–{fmt(se[1])})", ""]
    return L, m


def report(seed: int, uci: Path, v2: bool = False) -> tuple[str, dict]:
    prev = grounding.v2_enabled()
    grounding.use_v2(v2)        # triage reads the extractor through the module default, as in production
    recs = synth.build_corpus(seed)
    openers = [r for r in recs if r["turn"] == "opener"]
    ver = "v2" if v2 else "v1"
    L = [f"### C7 triage and scam-type rules (seed {seed}, generator v{synth.GENERATOR_VERSION}, grounding {ver})", "",
         f"Command: `python -m eval.eval_classify --seed {seed}{' --grounding v2' if v2 else ''}`. "
         "Synthetic corpus unless marked as the public dataset. Rules only, no LLM.", ""]
    hw, gen = [r for r in openers if r["source"] == "handwritten"], [r for r in openers if r["source"] == "generated"]
    ho = [r for r in synth.build_corpus(seed, corpus="heldout") if r["turn"] == "opener"]
    L += triage_table(triage_rows(hw), "hand-written openers") + triage_table(triage_rows(gen), "generated openers")
    L += triage_table(triage_rows(ho), "held-out openers (written before grounding v2)")
    engaged = [rule_triage(r["text"]) for r in openers if r["triage"] == "benign"]
    engaged = [t for t in engaged if t.verdict == "scam"]
    via_acct = sum("bank_account" in t.reasons for t in engaged)
    L += [f"Why benign messages were engaged: {via_acct} of {len(engaged)} had an extracted `bank_account` among the triage reasons "
          "(a payment rail adds 2 to the score). See the C3 report: these are toll-free or reference numbers read as accounts.", ""]
    st_lines, st = scam_type_section(scam_type_rows(recs))
    L += st_lines
    u_lines, u = uci_section(uci)
    L += u_lines
    summary = {"seed": seed, "synthetic": True, "triage_handwritten": triage_metrics(triage_rows(hw)), "triage_generated": triage_metrics(triage_rows(gen)),
               "triage_heldout": triage_metrics(triage_rows(ho)), "grounding": ver,
               "scam_type": {k: {kk: vv for kk, vv in v.items() if kk != "top_confusions"} for k, v in st.items()},
               "uci_sms_spam": u}
    grounding.use_v2(prev)
    return "\n".join(L), summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--uci", default=str(UCI_DEFAULT))
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--grounding", choices=("v1", "v2"), default="v1", help="v1 = production default")
    a = ap.parse_args(argv)
    v2 = a.grounding == "v2"
    a.out_md = a.out_md or str(REPORT_MD.with_name("classify_v2.md") if v2 else REPORT_MD)
    a.out_json = a.out_json or str(REPORT_JSON.with_name("classify_v2.json") if v2 else REPORT_JSON)
    text, summary = report(a.seed, Path(a.uci), v2)
    Path(a.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out_md).write_text(text + "\n", encoding="utf-8")
    Path(a.out_json).write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
