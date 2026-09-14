"""Unit tests for H3 policy comparison table."""

from domain.ops.policy_comparison import flatten_comparison


def test_flatten_comparison_rows():
    report = {
        "note": "unit",
        "ppo": {"assigned": 8, "n_stays": 10, "episode_reward": 1.2, "high_risk_wait": 3},
        "greedy": {"assigned": 7, "n": 10, "reward": 0.9},
        "cp_sat": {
            "assigned": 9,
            "n_stays": 10,
            "evaluation": {"mean_wait": 2.5, "constraint_violations": 0},
        },
    }
    table = flatten_comparison(report)
    assert table["status"] == "ok"
    assert len(table["rows"]) == 3
    by_policy = {r["policy"]: r for r in table["rows"]}
    assert abs(by_policy["ppo"]["assignment_rate"] - 0.8) < 1e-9
    assert by_policy["cp_sat"]["constraint_violations"] == 0
