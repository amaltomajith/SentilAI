"""C1 simulator acceptance tests. Positive controls show the harness can detect both a gain and a harm from
splitting by scam type, so a 'no difference' result is not just an insensitive harness."""
import statistics

from eval import bandit_sim as bs
from sentinel.orchestrator import bandit

PERFECT = dict(label_acc_opener=1.0, label_acc_followup=1.0)


def mean_gain(policy, world_fn, seeds, n, p):
    return statistics.fmean(bs.cumulative(bs.run(policy, world_fn(s), s, n, p)["gains"], n) for s in range(seeds))


def test_same_seed_same_result_and_every_policy_runs():
    p = bs.Params()
    w = bs.make_world(3, 1.0)
    assert bs.run("current", w, 3, 40, p) == bs.run("current", w, 3, 40, p)
    for pol in bs.POLICIES:
        r = bs.run(pol, w, 3, 20, p)
        assert len(r["gains"]) == 20 and all(0 <= g <= 5 for g in r["gains"])


def test_reward_rules():
    assert bs._reward("ask_payment_rail", ["upi"], "engine") and not bs._reward("ask_payment_rail", ["phone"], "engine")
    assert bs._reward("card_ready_stall", ["phone"], "engine") and not bs._reward("card_ready_stall", ["phone"], "targeted_only")
    assert bs._reward("ask_payment_rail", ["phone"], "any_new")
    assert bandit.tactic_hit(("upi",), ["upi"]) and bandit.tactic_hit((), ["url"]) and not bandit.tactic_hit((), [])


def test_positive_control_oracle_beats_random():
    p = bs.Params(sigma=1.0)
    assert mean_gain("oracle", lambda s: bs.make_world(s, 1.0), 6, 100, p) > mean_gain("random", lambda s: bs.make_world(s, 1.0), 6, 100, p) + 0.1


def planted_world(_seed):
    """Two equally common scam types with OPPOSITE best tactics. Pooling them must hurt."""
    q = {(t, s, a): 0.02 for t in bs.TYPES for s in bs.STAGES for a in bs.TACTICS}
    for s in bs.STAGES:
        q[("kyc_bank", s, "ask_callback_number")] = 0.9
        q[("lottery_prize", s, "ask_beneficiary_name")] = 0.9
    weights = [0.5 if t in ("kyc_bank", "lottery_prize") else 0.0 for t in bs.TYPES]
    return bs.World(q, weights)


def test_positive_control_splitting_by_type_wins_when_types_really_differ():
    p = bs.Params(**PERFECT, convs_per_user=1000, opt_in=1.0)
    assert mean_gain("current", planted_world, 8, 300, p) > mean_gain("pooled", planted_world, 8, 300, p) + 0.02


def test_positive_control_pooling_wins_when_types_are_identical():
    p = bs.Params(sigma=0.0, **PERFECT)
    assert mean_gain("pooled", lambda s: bs.make_world(s, 0.0), 10, 100, p) > mean_gain("current", lambda s: bs.make_world(s, 0.0), 10, 100, p)


def test_grid_and_verdicts_shape():
    res = bs.grid((0.0,), 2, (10, 30), bs.Params(), policies=("current", "pooled"))
    assert set(res[0.0]) == {"current", "pooled"} and res[0.0]["current"][30]["diff_vs_current"] == 0.0
    assert bs.verdicts({0.0: {"pooled": {100: {"ci": [0.1, 0.2]}, 300: {"ci": [0.0, 0.3]}}}}, (100, 300)) == {"pooled@sigma=0.0": "helps"}
    assert bs.verdicts({0.0: {"pooled": {100: {"ci": [-0.3, -0.1]}, 300: {"ci": [-0.2, 0.1]}}}}, (100, 300)) == {"pooled@sigma=0.0": "harms"}
