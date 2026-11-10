"""C3: how well does Sentinel's IOC extractor find what the scammer actually sent? (synthetic data)

    python -m eval.eval_ioc --seed 1          # prints a markdown report and writes eval/reports/ioc.md

It runs the production code path exactly: `grounding.extract_candidates(text)`, then `grounding.ground(..., honey)`,
keeping accepted candidates. Gold labels come from the corpus (placeholder slots that are true IOCs).

Matching rules (stated in advance): a prediction matches a gold IOC if the kind is equal and the normalised values are equal.
  url:  lower-case, scheme removed, leading "www." removed, trailing "/" removed
  upi:  lower-case
  phone / bank_account: ASCII digits only (Indic digits mapped to ASCII); phone also drops a leading 91 / 0 country or trunk prefix
  ifsc: upper-case
Reports show templates (placeholders), never rendered values.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from eval import synth
from eval.stats import bootstrap_ci, fmt, ratio
from sentinel import grounding

KINDS = synth.IOC_KINDS
REPORT = Path(__file__).resolve().parent / "reports" / "ioc.md"


def _ascii_digits(s: str) -> str:
    return "".join(str(unicodedata.digit(c)) for c in s if unicodedata.digit(c, None) is not None)


def norm(kind: str, value: str) -> str:
    if kind == "url":
        v = re.sub(r"^[a-z]+://", "", value.lower())
        return (v[4:] if v.startswith("www.") else v).rstrip("/")
    if kind == "upi":
        return value.lower()
    if kind in ("phone", "bank_account"):
        d = _ascii_digits(value)
        if kind == "phone" and len(d) == 12 and d.startswith("91"):
            d = d[2:]
        if kind == "phone" and len(d) == 11 and d.startswith("0"):
            d = d[1:]
        return d
    if kind == "ifsc":
        return value.upper()
    return value


def predict(record: dict, extract=grounding.extract_candidates, ground=grounding.ground) -> tuple[list[tuple[str, str]], Counter]:
    """Accepted IOCs as (kind, value), plus counts of grounding rejections by reason."""
    res = ground(extract(record["text"]), record["text"], set(record.get("honey", [])))
    return [(g.candidate.kind, g.candidate.value) for g in res if g.accepted], Counter(g.reason for g in res if not g.accepted)


def score_record(gold: list[dict], pred: list[tuple[str, str]]) -> dict[str, Counter]:
    """Per-kind TP/FP/FN for one record (multiset matching on normalised values)."""
    g = Counter((x["kind"], norm(x["kind"], x["value"])) for x in gold)
    p = Counter((k, norm(k, v)) for k, v in pred)
    out: dict[str, Counter] = defaultdict(Counter)
    for key in g | p:
        tp = min(g[key], p[key])
        out[key[0]]["tp"] += tp
        out[key[0]]["fn"] += g[key] - tp
        out[key[0]]["fp"] += p[key] - tp
    return out


def evaluate(records: list[dict], extract=grounding.extract_candidates, ground=grounding.ground) -> dict:
    rows = []
    rejected: Counter = Counter()
    honey_accepted = 0
    for r in records:
        pred, rej = predict(r, extract, ground)
        rejected += rej
        honey = {h.lower() for h in r.get("honey", [])}
        honey_accepted += sum(v.lower() in honey for _, v in pred)
        rows.append({"rec": r, "pred": pred, "score": score_record(r["gold_iocs"], pred)})
    return {"rows": rows, "rejected": rejected, "honey_accepted": honey_accepted,
            "honey_records": sum(bool(r.get("honey")) for r in records)}


def totals(rows, kind: str | None = None) -> Counter:
    c: Counter = Counter()
    for row in rows:
        for k, v in row["score"].items():
            if kind is None or k == kind:
                c += v
    return c


def prf(c: Counter) -> tuple[float | None, float | None, float | None]:
    p, r = ratio(c["tp"], c["tp"] + c["fp"]), ratio(c["tp"], c["tp"] + c["fn"])
    f = (2 * p * r / (p + r)) if p and r else (0.0 if p is not None and r is not None else None)
    return p, r, f


def table(rows, title: str) -> list[str]:
    L = [f"#### {title} (records: {len(rows)})", "", "| Kind | Gold | TP | FP | FN | Precision (95% CI) | Recall (95% CI) | F1 |", "|---|---|---|---|---|---|---|---|"]
    for kind in list(KINDS) + [None]:
        c = totals(rows, kind)
        p, r, f = prf(c)
        pl, ph = bootstrap_ci(rows, lambda s: prf(totals(s, kind))[0])
        rl, rh = bootstrap_ci(rows, lambda s: prf(totals(s, kind))[1])
        L.append(f"| {kind or '**all**'} | {c['tp'] + c['fn']} | {c['tp']} | {c['fp']} | {c['fn']} | {fmt(p)} ({fmt(pl)}–{fmt(ph)}) | "
                 f"{fmt(r)} ({fmt(rl)}–{fmt(rh)}) | {fmt(f)} |")
    return L + [""]


def failures(rows) -> list[str]:
    by_tag: dict[str, Counter] = defaultdict(Counter)
    examples: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        rec = row["rec"]
        c = totals([row])
        if not (c["fp"] or c["fn"]):
            continue
        misses = [f"{k}: {v['fn']} missed" for k, v in row["score"].items() if v["fn"]] + \
                 [f"{k}: {v['fp']} wrong" for k, v in row["score"].items() if v["fp"]]
        for tag in rec.get("tags", []) or ["untagged"]:
            by_tag[tag]["records"] += 1
            by_tag[tag]["fn"] += c["fn"]
            by_tag[tag]["fp"] += c["fp"]
        if rec["source"] in ("handwritten", "heldout", "heldout3"):
            examples[rec["tags"][0]].append(f"- `{rec['id']}` {'; '.join(misses)}: `{rec['template']}`")
    L = ["#### Failures by tag (records with at least one miss or wrong value)", "", "| Tag | Records | Missed | Wrong |", "|---|---|---|---|"]
    L += [f"| {t} | {c['records']} | {c['fn']} | {c['fp']} |" for t, c in sorted(by_tag.items(), key=lambda x: (-x[1]["fn"] - x[1]["fp"], x[0]))]
    L += ["", "#### Hand-written failure cases (templates; values are filled in at run time)", ""]
    for group in sorted(examples):
        L += [f"**{group}**", ""] + examples[group] + [""]
    return L


def evaluate_version(records: list[dict], v2: bool) -> dict:
    """Same production code path, with the grounding version pinned (v1 = today's default, v2 = SENTINEL_GROUNDING_V2=1)."""
    return evaluate(records, extract=lambda text: grounding.extract_candidates(text, v2),
                    ground=lambda cands, text, honey=frozenset(): grounding.ground(cands, text, honey, v2))


def report(seed: int, corpus: str = "main", v2: bool = False) -> str:
    recs = synth.build_corpus(seed, corpus=corpus)
    res = evaluate_version(recs, v2)
    ver = "v2" if v2 else "v1"
    flags = (" --corpus %s" % corpus if corpus != "main" else "") + (" --grounding v2" if v2 else "")
    L = [f"### C3 IOC extraction (synthetic, seed {seed}, generator v{synth.GENERATOR_VERSION}, corpus {corpus}, grounding {ver})", "",
         f"Command: `python -m eval.eval_ioc --seed {seed}{flags}`. All records are synthetic; each source is reported separately.", ""]
    for source in ("handwritten", "generated", "heldout"):
        rows = [r for r in res["rows"] if r["rec"]["source"] == source]
        if rows:
            L += table(rows, {"handwritten": "Hand-written cases", "generated": "Generated messages", "heldout": "Held-out cases"}[source])
    if corpus == "main":
        L += table(res["rows"], "All")
    L += [f"Decoy (honey-token) values accepted as scammer IOCs: **{res['honey_accepted']}** in {res['honey_records']} records that echo a decoy (must be 0).",
          f"Candidates rejected by grounding: {dict(res['rejected']) or 'none'}.", ""]
    L += failures(res["rows"])
    return "\n".join(L)


def compare(seed: int) -> str:
    """v1 vs v2 on the corpus v2 was developed against (seen) and on the held-out set written before v2 (unseen)."""
    L = [f"### Grounding v1 vs v2 (synthetic, seed {seed})", "",
         f"Command: `python -m eval.eval_ioc --compare --seed {seed}`. v2 is OFF in production unless `SENTINEL_GROUNDING_V2=1`.",
         "", "*Main* = the corpus whose failure report v2 was written to fix, so its v2 numbers are optimistic. "
         "*Held-out* = 49 cases written before any v2 code and never used to tune it. "
         "*Held-out v3* = 32 cases for the obfuscation fixes (at / defanged links / IFSC case / dotted phones), written before "
         "that code. Its first run found 25 of 30 (three bugs in the new code); after fixing them it is no longer unseen.", "",
         "| Corpus | Kind | v1 precision | v2 precision | v1 recall | v2 recall | v1 FP | v2 FP | v1 FN | v2 FN |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for corpus, name, source in (("main: hand-written", "main", "handwritten"), ("main: generated", "main", "generated"),
                                 ("held-out", "heldout", "heldout"), ("held-out v3", "heldout3", "heldout3")):
        recs = [r for r in synth.build_corpus(seed, corpus=name) if r["source"] == source]
        a, b = evaluate_version(recs, False), evaluate_version(recs, True)
        for kind in list(KINDS) + [None]:
            ca, cb = totals(a["rows"], kind), totals(b["rows"], kind)
            (pa, ra, _), (pb, rb, _) = prf(ca), prf(cb)
            L.append(f"| {corpus} | {kind or '**all**'} | {fmt(pa)} | {fmt(pb)} | {fmt(ra)} | {fmt(rb)} | {ca['fp']} | {cb['fp']} | {ca['fn']} | {cb['fn']} |")
        L.append(f"| {corpus} | decoys accepted | {a['honey_accepted']} | {b['honey_accepted']} | | | | | | |")
    ho = synth.build_corpus(seed, corpus="heldout") + synth.build_corpus(seed, corpus="heldout3")
    L += ["", "#### Held-out failures left under v2", ""] + failures(evaluate_version(ho, True)["rows"])[2:]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None)
    ap.add_argument("--corpus", choices=("main", "heldout", "heldout3"), default="main")
    ap.add_argument("--grounding", choices=("v1", "v2"), default="v1", help="v1 = production default")
    ap.add_argument("--compare", action="store_true", help="v1 vs v2 on the main and held-out corpora")
    a = ap.parse_args(argv)
    if a.compare:
        text, out = compare(a.seed), a.out or str(REPORT.with_name("ioc_v2.md"))
    else:
        text = report(a.seed, a.corpus, a.grounding == "v2")
        out = a.out or str(REPORT if (a.corpus, a.grounding) == ("main", "v1") else REPORT.with_name(f"ioc_{a.corpus}_{a.grounding}.md"))
    a.out = out
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
