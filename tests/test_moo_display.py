from domain.optimizer.moo_display import (
    midpoint_epsilon_bounds,
    pivot_scenario_rows,
    three_mode_metrics,
)


def test_pivot_scenario_rows_wide():
    rows = [
        {
            "scenario_id": "S1",
            "scenario_name": "正常",
            "method": "weighted_sum",
            "status": "OPTIMAL",
            "assigned": 20,
            "obj_wait": 1,
            "obj_high_risk": 4,
        },
        {
            "scenario_id": "S1",
            "scenario_name": "正常",
            "method": "lexicographic",
            "status": "OPTIMAL",
            "assigned": 20,
            "obj_wait": 2,
            "obj_high_risk": 12,
        },
    ]
    wide = pivot_scenario_rows(rows)
    assert len(wide) == 1
    assert wide[0]["lexicographic_high_risk"] == 12
    assert wide[0]["weighted_sum_wait"] == 1


def test_three_mode_metrics_flatten():
    payload = {
        "objective_mode": "lexicographic",
        "solver_status": "OPTIMAL",
        "assigned": 20,
        "n_stays": 50,
        "multiobjective": {
            "values": {"wait": 58892, "high_risk": 12, "overload": 84, "occupancy": 20},
            "wall_time_seconds": 1.5,
            "exact_hierarchy": True,
        },
        "evaluation": {"solve_time_seconds": 1.5},
    }
    row = three_mode_metrics(payload)
    assert row["high_risk"] == 12
    assert row["exact_hierarchy"] is True


def test_midpoint_epsilon_bounds():
    bounds = midpoint_epsilon_bounds(
        {"occupancy": 20, "high_risk": 12, "overload": 0, "wait": 500},
        {"occupancy": 10, "high_risk": 0, "overload": 80, "wait": 100},
    )
    assert bounds["occupancy"] == 15
    assert bounds["high_risk"] == 6
    assert bounds["overload"] == 40
    assert "wait" not in bounds
