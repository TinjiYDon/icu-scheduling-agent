"""Unit tests for S2-MOO phase-3 helpers (no database)."""

from __future__ import annotations

from domain.optimizer.moo_phase3 import (
    ObjectivePoint,
    build_epsilon_levels,
    dominates,
    filter_nondominated,
    generate_epsilon_grid,
    hypervolume_maximization,
    normalize_for_maximization,
    payoff_ranges_from_matrix,
    run_epsilon_grid_scan,
    run_payoff_table,
    single_objective_weights,
)


def test_payoff_ranges_max_min():
    matrix = [
        {"a": 10, "b": 5},
        {"a": 4, "b": 1},
        {"a": 7, "b": 9},
    ]
    senses = {"a": "max", "b": "min"}
    ideal, nadir = payoff_ranges_from_matrix(
        matrix, objectives=["a", "b"], senses=senses
    )
    assert ideal == {"a": 10, "b": 1}
    assert nadir == {"a": 4, "b": 9}


def test_epsilon_levels_loose_to_tight():
    max_levels = build_epsilon_levels(ideal=20, nadir=5, levels=3, sense="max")
    assert max_levels == [5, 12, 20] or max_levels == [5, 13, 20]
    min_levels = build_epsilon_levels(ideal=10, nadir=100, levels=3, sense="min")
    assert min_levels == [10, 55, 100]


def test_grid_size_a2_shape():
    ideal = {"occupancy": 20, "high_risk": 15, "overload": 0, "balance": 0}
    nadir = {"occupancy": 10, "high_risk": 5, "overload": 80, "balance": 12}
    grid = generate_epsilon_grid(
        ideal=ideal,
        nadir=nadir,
        grid_objectives=["occupancy", "high_risk", "overload", "balance"],
        levels=3,
    )
    # unique ints may collapse some axes; product should be <= 81 and >= 16
    assert 16 <= len(grid) <= 81
    assert all(set(g) == {"occupancy", "high_risk", "overload", "balance"} for g in grid)


def test_dominates_and_nondominated():
    senses = {"wait": "max", "overload": "min"}
    a = ObjectivePoint({"wait": 10, "overload": 2}, "a", "OPTIMAL")
    b = ObjectivePoint({"wait": 8, "overload": 5}, "b", "OPTIMAL")
    c = ObjectivePoint({"wait": 9, "overload": 1}, "c", "OPTIMAL")
    assert dominates(a.values, b.values, senses=senses)
    front = filter_nondominated([a, b, c], senses=senses)
    assert {p.source for p in front} == {"a", "c"}


def test_hypervolume_2d_known():
    points = [{"x": 1.0, "y": 0.2}, {"x": 0.2, "y": 1.0}]
    ref = {"x": 0.0, "y": 0.0}
    hv = hypervolume_maximization(points, reference=ref, objectives=["x", "y"])
    # union of [0,1]x[0,0.2] and [0,0.2]x[0,1] = 0.2 + 0.2 - 0.04 = 0.36
    assert abs(hv - 0.36) < 1e-9


def test_hypervolume_monotone_when_adding_point():
    ref = {"x": 0.0, "y": 0.0}
    hv1 = hypervolume_maximization(
        [{"x": 1.0, "y": 0.2}], reference=ref, objectives=["x", "y"]
    )
    hv2 = hypervolume_maximization(
        [{"x": 1.0, "y": 0.2}, {"x": 0.2, "y": 1.0}],
        reference=ref,
        objectives=["x", "y"],
    )
    assert hv2 >= hv1


def test_normalize_flips_min_objectives():
    senses = {"wait": "max", "overload": "min"}
    ideal = {"wait": 100.0, "overload": 0.0}
    nadir = {"wait": 0.0, "overload": 50.0}
    norm = normalize_for_maximization(
        {"wait": 50, "overload": 0},
        ideal=ideal,
        nadir=nadir,
        senses=senses,
    )
    assert abs(norm["wait"] - 0.5) < 1e-9
    assert abs(norm["overload"] - 1.0) < 1e-9


def test_orchestration_with_fake_solve():
    objectives = ["wait", "occupancy", "overload"]

    def fake_solve(**kwargs):
        mode = kwargs.get("objective_mode")
        if mode == "weighted_sum":
            weights = kwargs.get("lambda_weights") or {}
            opt = max(weights, key=weights.get)
            values = {
                "wait": 100 if opt == "wait" else 40,
                "occupancy": 20 if opt == "occupancy" else 10,
                "overload": 0 if opt == "overload" else 30,
            }
            # when optimizing wait, still fill others reasonably
            if opt == "wait":
                values = {"wait": 100, "occupancy": 15, "overload": 20}
            elif opt == "occupancy":
                values = {"wait": 60, "occupancy": 20, "overload": 25}
            else:
                values = {"wait": 50, "occupancy": 12, "overload": 0}
            return {
                "solver_status": "OPTIMAL",
                "assigned": 20,
                "multiobjective": {"values": values, "wall_time_seconds": 0.01},
            }
        bounds = kwargs.get("epsilon_bounds") or {}
        return {
            "solver_status": "OPTIMAL",
            "assigned": 20,
            "multiobjective": {
                "values": {
                    "wait": 80,
                    "occupancy": int(bounds.get("occupancy", 10)),
                    "overload": int(bounds.get("overload", 10)),
                },
                "wall_time_seconds": 0.01,
            },
        }

    payoff = run_payoff_table(fake_solve, objectives=objectives, split="calib")
    assert "ideal" in payoff and "nadir" in payoff
    scan = run_epsilon_grid_scan(
        fake_solve,
        payoff=payoff,
        primary="wait",
        grid_objectives=["occupancy", "overload"],
        levels=3,
        max_points=4,
    )
    assert scan["n_grid"] == 4
    assert scan["n_feasible"] == 4
    assert scan["hypervolume"] >= 0


def test_single_objective_weights():
    w = single_objective_weights("wait", ["wait", "overload"])
    assert w == {"wait": 1.0, "overload": 0.0}
