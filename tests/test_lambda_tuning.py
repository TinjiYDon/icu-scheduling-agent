from __future__ import annotations

import pytest

from domain.optimizer.tuning import iter_lambda_grid, pareto_front, recommend_row


def test_lambda_grid_is_complete_and_ordered():
    rows = list(
        iter_lambda_grid(
            {
                "wait": [1, 2],
                "overload": [1],
                "balance": [0.1],
                "zone_mismatch": [0.5, 1],
            }
        )
    )
    assert len(rows) == 4
    assert rows[0] == {
        "wait": 1.0,
        "overload": 1.0,
        "balance": 0.1,
        "zone_mismatch": 0.5,
    }


def test_lambda_grid_rejects_missing_dimension():
    with pytest.raises(ValueError, match="missing"):
        list(iter_lambda_grid({"wait": [1]}))


def _row(run_id, risk, priority, match, overload, balance, seconds):
    return {
        "run_id": run_id,
        "high_risk_assigned_rate": risk,
        "priority_total": priority,
        "zone_match_rate": match,
        "overload_penalty": overload,
        "balance_deviation": balance,
        "solve_time_seconds": seconds,
    }


def test_pareto_front_removes_dominated_result():
    strong = _row("strong", 1.0, 20, 0.9, 1, 1, 0.5)
    weak = _row("weak", 0.8, 10, 0.7, 2, 2, 1.0)

    assert [row["run_id"] for row in pareto_front([strong, weak])] == ["strong"]
    assert recommend_row([strong, weak])["run_id"] == "strong"
