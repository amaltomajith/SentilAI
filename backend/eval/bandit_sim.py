"""C1 phase 1: does splitting the tactic learner by scam type help at Sentinel's data volumes? (SIMULATION)

    python -m eval.bandit_sim                    # full grid -> eval/reports/bandit_sim.md and .json
    python -m eval.bandit_sim --quick            # small grid for a smoke run

Everything here is a simulation with hidden, known truth. It shows how the policies behave under the stated assumptions,
not how real scammers behave. What is REAL code: the candidate list (`ploys.ploy_order`, top 5, last tactic excluded, as
in `mcp/tools.t_select_tactic`), the sampler (`bandit.choose`, with its playbook prior and cold start), the reward rule
(`bandit.tactic_hit`), the private + half-weighted shared counters (`bandit.load_stats`/`record`). What is ASSUMED:

  * the scammer: each (true scam type, stage, tactic) has a hidden chance q of making the scammer reveal one of the
    tactic's missing target kinds (a tactic with no target reveals a random missing kind when it works);
    q = sigmoid(mu[tactic] + sigma * (z[type, tactic] + w[stage, tactic])). sigma = how much scam types and stages differ.
  * independent of the tactic, the scammer volunteers a random missing payment kind with probability `volunteer` per turn,
    quits with probability `quit` per turn, and the opening message carries some IOCs already.
  * the scam-type label the learner sees is noisy, with rates taken from the C7 measurement (eval/reports/classify.json):
    openers and follow-up turns separately; a wrong label is `other` with the measured share, else a random other type.
  * users have 3 conversations each (MAX_TARGETS_PER_USER) and half of them opt in to the shared counters.

Outcome (what Sentinel wants): new IOC kinds captured after the opening message, per conversation (0..5), averaged over
the first N conversations. Policies are compared on the same simulated scammers (common random numbers) and the
difference to the CURRENT policy is reported with a 95% bootstrap interval over seeds.
Pre-stated rule: an alternative "helps" only if its interval is above 0 at N = 100 or N = 300 conversations.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from eval.stats import bootstrap_ci
from sentinel.orchestrator import bandit
from sentinel.orchestrator.ploys import PLOYS, ploy_order
from sentinel.orchestrator.strategy import SCAM_TYPES

HERE = Path(__file__).resolve().parent
TYPES = sorted(SCAM_TYPES)
STAGES = ("opening", "hook", "payment_pushed", "threat")
TACTICS = sorted(p for p in PLOYS if p not in ("screenshot_error", "wind_down"))   # overrides never go through the bandit
KINDS = ("upi", "bank_account", "ifsc", "phone", "url")
VOLUNTEER_KINDS = ("upi", "bank_account", "phone")
OPENER_REVEAL = {"upi": 0.4, "phone": 0.3, "url": 0.2, "bank_account": 0.1, "ifsc": 0.05}
POLICIES = ("playbook", "random", "current", "sticky", "pooled", "backoff", "type_stage", "oracle")


@dataclass
class Params:
    sigma: float = 1.0
    volunteer: float = 0.15
    quit: float = 0.15
    max_decisions: int = 6
    convs_per_user: int = 3
    opt_in: float = 0.5
    label_acc_opener: float = 0.81
    label_acc_followup: float = 0.17
    wrong_is_other_opener: float = 0.43
    wrong_is_other_followup: float = 0.90
    reward: str = "engine"            # engine | any_new | targeted_only
    backoff_strength: float = 4.0


@dataclass
class World:
    q: dict
    type_weights: list[float]


def make_world(seed: int, sigma: float) -> World:
    rng = random.Random(f"world:{seed}")
    mu = {a: rng.gauss(-1.2, 0.7) for a in TACTICS}
    z = {(t, a): rng.gauss(0, 1) for t in TYPES for a in TACTICS}
    w = {(s, a): rng.gauss(0, 1) for s in STAGES for a in TACTICS}
    q = {(t, s, a): 1 / (1 + math.exp(-(mu[a] + sigma * (z[(t, a)] + w[(s, a)])))) for t in TYPES for s in STAGES for a in TACTICS}
    weights = [rng.gammavariate(2.0, 1.0) for _ in TYPES]
    return World(q, [x / sum(weights) for x in weights])


@dataclass
class Ctx:
    user: int
    opted_in: bool
    true_type: str
    seen_type: str
    stage: str


@dataclass
class Learner:
    """Counter tables keyed like TacticStat. `key` maps a context to the counter key the policy learns under."""
    name: str
    strength: float = 4.0          # back-off only: pseudo-observations borrowed from the all-types estimate
    per_user: dict = field(default_factory=dict)
    shared: dict = field(default_factory=dict)

    def key(self, ctx: Ctx):
        return {"current": ctx.seen_type, "sticky": ctx.seen_type, "pooled": "*", "type_stage": (ctx.seen_type, ctx.stage), "backoff": ctx.seen_type}[self.name]

    def _stats(self, ctx: Ctx, key) -> dict[str, tuple[float, float]]:
        out: dict[str, tuple[float, float]] = {}
        for table, scope, wgt in ((self.per_user, ctx.user, 1.0), (self.shared, None, bandit.GLOBAL_WEIGHT)):
            if table is self.shared and not ctx.opted_in:
                continue
            for a, (s, t) in table.get((scope, key), {}).items():
                s0, t0 = out.get(a, (0.0, 0.0))
                out[a] = (s0 + wgt * s, t0 + wgt * t)
        return out

    def stats(self, ctx: Ctx, options: list[str]) -> dict[str, tuple[float, float]]:
        st = self._stats(ctx, self.key(ctx))
        if self.name != "backoff":
            return st
        return bandit.backoff_stats(st, self._stats(ctx, ("pool",)), options, self.strength)   # the production function

    def update(self, ctx: Ctx, tactic: str, hit: bool) -> None:
        keys = [self.key(ctx)] + ([("pool",)] if self.name == "backoff" else [])
        for key in keys:
            for table, scope in ((self.per_user, ctx.user), (self.shared, None)):
                if table is self.shared and not ctx.opted_in:
                    continue
                cell = table.setdefault((scope, key), {})
                s, t = cell.get(tactic, (0, 0))
                cell[tactic] = (s + int(hit), t + 1)


def _noisy_label(true_type: str, opener: bool, u1: float, u2: float, u3: float, p: Params) -> str:
    acc, other = (p.label_acc_opener, p.wrong_is_other_opener) if opener else (p.label_acc_followup, p.wrong_is_other_followup)
    if u1 < acc:
        return true_type
    if u2 < other:
        return "other"
    rest = [t for t in TYPES if t != true_type]
    return rest[int(u3 * len(rest)) % len(rest)]


def _reward(tactic: str, new_kinds: list[str], rule: str) -> bool:
    targets = PLOYS[tactic].targets
    if rule == "engine":
        return bandit.tactic_hit(targets, new_kinds)
    if rule == "any_new":
        return bool(new_kinds)
    return any(k in targets for k in new_kinds)          # targeted_only: a tactic with no target is never credited


def run(policy: str, world: World, seed: int, n_conv: int, p: Params) -> dict:
    """Simulate n_conv conversations with one policy. Exogenous randomness is keyed by (seed, conversation, turn), so all
    policies face the same scammers (common random numbers)."""
    learner = Learner(policy, p.backoff_strength) if policy in ("current", "sticky", "pooled", "backoff", "type_stage") else None
    gains, target_less_choices, decisions = [], 0, 0
    for i in range(n_conv):
        cr = random.Random(f"conv:{seed}:{i}")
        user = i // p.convs_per_user
        opted_in = random.Random(f"user:{seed}:{user}").random() < p.opt_in
        true_type = cr.choices(TYPES, weights=world.type_weights)[0]
        captured = {k for k, pr in OPENER_REVEAL.items() if cr.random() < pr}
        start = len(captured)
        u = [[cr.random() for _ in range(8)] for _ in range(p.max_decisions)]   # per-turn exogenous draws
        prng = random.Random(f"policy:{policy}:{seed}:{i}")
        last, first_label = "", ""
        for turn in range(p.max_decisions):
            d = u[turn]
            seen = _noisy_label(true_type, turn == 0, d[0], d[1], d[2], p)
            if policy == "sticky":           # keep the opening message's label for the whole conversation
                first_label = first_label or seen
                seen = first_label
            stage = "opening" if turn == 0 else "payment_pushed" if captured & {"upi", "bank_account"} else "threat" if d[3] < 0.25 else "hook"
            ctx = Ctx(user, opted_in, true_type, seen, stage)
            full = ploy_order(captured, turn, seen)
            options = ([x for x in full if x != last] or full)[:5]
            if policy == "playbook":
                tactic = options[0]
            elif policy == "random":
                tactic = prng.choice(options)
            elif policy == "oracle":
                tactic = max(options, key=lambda a: world.q[(true_type, stage, a)])
            else:
                tactic = bandit.choose(options, learner.stats(ctx, options), prng)[0]
            decisions += 1
            target_less_choices += not PLOYS[tactic].targets
            last = tactic
            if d[4] < p.quit:                     # the scammer stops replying: this tactic is never scored (as in the engine)
                break
            new: list[str] = []
            missing = [k for k in KINDS if k not in captured]
            if missing and d[5] < world.q[(true_type, stage, tactic)]:
                aim = [k for k in PLOYS[tactic].targets if k in missing] or missing
                new.append(aim[int(d[6] * len(aim)) % len(aim)])
            vol = [k for k in VOLUNTEER_KINDS if k not in captured and k not in new]
            if vol and d[7] < p.volunteer:
                new.append(vol[int(d[7] / p.volunteer * len(vol)) % len(vol)])
            captured |= set(new)
            if learner:
                learner.update(ctx, tactic, _reward(tactic, new, p.reward))
        gains.append(len(captured) - start)
    return {"gains": gains, "target_less_share": target_less_choices / max(decisions, 1)}


def cumulative(gains: list[int], n: int) -> float:
    return sum(gains[:n]) / n


def grid(sigmas, seeds: int, volumes, base: Params, policies=POLICIES) -> dict:
    n_max = max(volumes)
    out: dict = {}
    for sigma in sigmas:
        p = Params(**{**base.__dict__, "sigma": sigma})
        per_seed = {pol: [] for pol in policies}
        for seed in range(seeds):
            world = make_world(seed, sigma)
            for pol in policies:
                per_seed[pol].append(run(pol, world, seed, n_max, p)["gains"])
        cell = {}
        for pol in policies:
            cell[pol] = {}
            for n in volumes:
                vals = [cumulative(g, n) for g in per_seed[pol]]
                diffs = [cumulative(g, n) - cumulative(c, n) for g, c in zip(per_seed[pol], per_seed["current"])] if "current" in per_seed else []
                lo, hi = bootstrap_ci(diffs, statistics.fmean) if diffs else (None, None)
                cell[pol][n] = {"mean": statistics.fmean(vals), "diff_vs_current": statistics.fmean(diffs) if diffs else None, "ci": [lo, hi]}
        out[sigma] = cell
    return out


def verdicts(res: dict, volumes) -> dict:
    """Pre-stated rule: helps if the 95% interval of (policy - current) is above 0 at N=100 or N=300; harms if below 0."""
    out = {}
    for sigma, cell in res.items():
        for pol in ("sticky", "pooled", "backoff", "type_stage"):
            if pol not in cell:
                continue
            checks = [cell[pol][n]["ci"] for n in (100, 300) if n in volumes]
            out[f"{pol}@sigma={sigma}"] = "helps" if any(c[0] is not None and c[0] > 0 for c in checks) else \
                "harms" if any(c[1] is not None and c[1] < 0 for c in checks) else "no clear difference"
    return out


def reward_study(seeds: int, n: int, base: Params, volunteers=(0.0, 0.15, 0.3)) -> dict:
    """C1b: does crediting target-less tactics for ANY new IOC (the engine rule) mislead the learner?"""
    out = {}
    for v in volunteers:
        row = {}
        for rule in ("engine", "any_new", "targeted_only"):
            p = Params(**{**base.__dict__, "volunteer": v, "reward": rule})
            gains, shares = [], []
            for seed in range(seeds):
                r = run("current", make_world(seed, p.sigma), seed, n, p)
                gains.append(cumulative(r["gains"], n))
                shares.append(r["target_less_share"])
            row[rule] = {"mean_gain": statistics.fmean(gains), "target_less_share": statistics.fmean(shares), "per_seed": gains}
        for rule in ("any_new", "targeted_only"):
            d = [a - b for a, b in zip(row[rule]["per_seed"], row["engine"]["per_seed"])]
            row[rule]["diff_vs_engine"], row[rule]["ci"] = statistics.fmean(d), list(bootstrap_ci(d, statistics.fmean))
        oracle = [run("oracle", make_world(seed, base.sigma), seed, n, Params(**{**base.__dict__, "volunteer": v}))["target_less_share"] for seed in range(seeds)]
        row["oracle_target_less_share"] = statistics.fmean(oracle)
        for rule in ("engine", "any_new", "targeted_only"):
            row[rule].pop("per_seed")
        out[v] = row
    return out


def label_noise_from_c7(path: Path = HERE / "reports" / "classify.json") -> dict:
    try:
        st = json.loads(path.read_text(encoding="utf-8"))["scam_type"]
        o, f = st["hand-written openers"], st["hand-written follow-ups"]
        return {"label_acc_opener": round(o["accuracy"], 3), "label_acc_followup": round(f["accuracy"], 3),
                "wrong_is_other_opener": round(o["wrong_as_other"], 3), "wrong_is_other_followup": round(f["wrong_as_other"], 3)}
    except (OSError, KeyError, TypeError, ValueError):
        return {}


def _f(x, signed=False):
    return "n/a" if x is None else (f"{x:+.3f}" if signed else f"{x:.3f}")


def report(res: dict, rs: dict, rs_n: int, volumes, seeds: int, base: Params, secs: float, label_src: str, cmd: str) -> str:
    L = ["### C1 phase 1: tactic learner simulation (SIMULATION, synthetic)", "",
         f"Command: `{cmd}` ({seeds} seeds per cell, {secs:.0f} s). Outcome: new IOC kinds captured per conversation after the "
         "opening message (0 to 5), averaged over the first N conversations. Δ = policy minus CURRENT on the same simulated "
         "scammers, with a 95% bootstrap interval over seeds.", "",
         f"Assumptions: volunteer rate {base.volunteer}, quit rate {base.quit}, up to {base.max_decisions} decisions per conversation, "
         f"{base.convs_per_user} conversations per user, opt-in {base.opt_in}. Scam-type label noise ({label_src}): openers correct "
         f"{base.label_acc_opener:.0%} (wrong → `other` {base.wrong_is_other_opener:.0%}), follow-ups correct {base.label_acc_followup:.0%} "
         f"(wrong → `other` {base.wrong_is_other_followup:.0%}).", "",
         "Policies: **playbook** = always the first playbook candidate; **random**; **current** = what Sentinel does (counters per "
         "observed scam type, own + 0.5 × shared); **sticky** = current, but the scam type seen in the opening message is kept for "
         "the whole conversation; **pooled** = the same, ignoring scam type; **backoff** = per-type counters "
         "shrunk toward the pooled estimate; **type_stage** = split further by stage; **oracle** = knows the hidden rates (upper reference).", "",
         "Caveat: the simulated scammer ignores the playbook's order, so the playbook prior carries no information here; compare the "
         "learners that share it (current, sticky, pooled, backoff, type_stage). playbook, random and oracle are reference points only.", ""]
    for sigma, cell in res.items():
        L += [f"#### σ = {sigma} ({'scam types and stages behave the same' if sigma == 0 else 'how much they differ'})", "",
              "| Policy | " + " | ".join(f"N={n}" for n in volumes) + " |", "|---|" + "---|" * len(volumes)]
        for pol, by_n in cell.items():
            cells = []
            for n in volumes:
                c = by_n[n]
                if pol == "current":
                    cells.append(f"{c['mean']:.3f}")
                else:
                    cells.append(f"{c['mean']:.3f} (Δ {_f(c['diff_vs_current'], True)} [{_f(c['ci'][0], True)}, {_f(c['ci'][1], True)}])")
            L.append(f"| {pol} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["#### Verdicts (pre-stated rule: helps only if the interval is above 0 at N = 100 or 300)", ""]
    L += [f"- {k}: **{v}**" for k, v in verdicts(res, volumes).items()] + [""]
    L += [f"#### C1b reward rule (current policy, σ = {base.sigma}, N = {rs_n})", "",
          "| Volunteer rate | Rule | Mean gain | Δ vs engine rule [95% CI] | Share of choices that are target-less tactics |", "|---|---|---|---|---|"]
    for v, row in rs.items():
        for rule in ("engine", "any_new", "targeted_only"):
            r = row[rule]
            d = "—" if rule == "engine" else f"{_f(r['diff_vs_engine'], True)} [{_f(r['ci'][0], True)}, {_f(r['ci'][1], True)}]"
            L.append(f"| {v} | {rule} | {r['mean_gain']:.3f} | {d} | {r['target_less_share']:.1%} |")
        L.append(f"| {v} | (oracle) | | | {row['oracle_target_less_share']:.1%} |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=None)
    ap.add_argument("--out", default=str(HERE / "reports" / "bandit_sim"))
    ap.add_argument("--perfect-labels", action="store_true", help="sensitivity check: the learner sees the true scam type")
    ap.add_argument("--sigmas", default=None, help="comma-separated, e.g. 1,2")
    a = ap.parse_args(argv)
    seeds = a.seeds or (4 if a.quick else 30)
    volumes = (10, 30, 100) if a.quick else (10, 30, 100, 300, 1000)
    sigmas = tuple(float(x) for x in a.sigmas.split(",")) if a.sigmas else (0.0, 1.0) if a.quick else (0.0, 0.5, 1.0, 2.0)
    noise = {"label_acc_opener": 1.0, "label_acc_followup": 1.0} if a.perfect_labels else label_noise_from_c7()
    base = Params(**noise)
    t0 = time.perf_counter()
    res = grid(sigmas, seeds, volumes, base)
    rs_n = 100 if a.quick else 300
    rs = reward_study(seeds, rs_n, base)
    secs = time.perf_counter() - t0
    cmd = "python -m eval.bandit_sim" + (" --quick" if a.quick else "") + (f" --seeds {a.seeds}" if a.seeds else "")
    cmd += " --perfect-labels" if a.perfect_labels else ""
    cmd += f" --sigmas {a.sigmas}" if a.sigmas else ""
    src = "PERFECT LABELS (sensitivity check)" if a.perfect_labels else "measured in C7" if noise else "defaults"
    text = report(res, rs, rs_n, volumes, seeds, base, secs, src, cmd)
    Path(a.out + ".md").parent.mkdir(parents=True, exist_ok=True)
    Path(a.out + ".md").write_text(text, encoding="utf-8")
    Path(a.out + ".json").write_text(json.dumps({"simulation": True, "params": base.__dict__, "seeds": seeds, "grid": {str(k): v for k, v in res.items()},
                                                 "verdicts": verdicts(res, volumes), "reward_study": {str(k): v for k, v in rs.items()}}, indent=1, default=str) + "\n",
                                     encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
