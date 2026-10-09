"""Unit tests for method bake-off pure helpers (no DB / no solver)."""

from domain.ops.method_bakeoff import (
    bakeoff_takeaways,
    epsilon_bounds_from_reference,
    flatten_bakeoff_row,
)


def test_epsilon_bounds_from_small_ws_pool():
    bounds = epsilon_bounds_from_reference(
        {"occupancy": 5, "high_risk": 5, "overload": 12, "balance": 0}
    )
    assert bounds["occupancy"] == 2  # 5 // 2
    assert bounds["high_risk"] == 2
    assert bounds["overload"] >= 12
    assert bounds["occupancy"] < 10  # not stuck on DEFAULT 10


def test_flatten_bakeoff_row():
    row = flatten_bakeoff_row(
        {
            "method": "weighted_sum",
            "status": "OPTIMAL",
            "assigned": 20,
            "values": {"occupancy": 20, "high_risk": 4, "wait": 100, "overload": 0},
            "wall_time_seconds": 1.2,
        }
    )
    assert row["method"] == "weighted_sum"
    assert row["high_risk"] == 4
    assert row["wait"] == 100


def test_takeaways_lex_serves_more_high_risk():
    rows = [
        {
            "method": "weighted_sum",
            "status": "OPTIMAL",
            "assigned": 20,
            "values": {"high_risk": 4, "occupancy": 20},
        },
        {
            "method": "lexicographic",
            "status": "OPTIMAL",
            "assigned": 20,
            "values": {"high_risk": 12, "occupancy": 20},
        },
        {
            "method": "epsilon_mid",
            "status": "OPTIMAL",
            "assigned": 18,
            "values": {"high_risk": 8, "occupancy": 18},
        },
        {
            "method": "greedy",
            "status": "ok",
            "assigned": 18,
            "values": {},
        },
    ]
    notes = bakeoff_takeaways(rows)
    assert any("词典序" in n and "高危" in n for n in notes)
    assert any("OR-Tools" in n or "online" in n for n in notes)


def test_takeaways_epsilon_infeasible():
    rows = [
        {"method": "weighted_sum", "status": "OPTIMAL", "assigned": 20, "values": {}},
        {
            "method": "epsilon_mid",
            "status": "ERROR:RuntimeError",
            "assigned": None,
            "values": {},
            "error": "CP-SAT failed: status=CpSolverStatus.INFEASIBLE",
        },
    ]
    notes = bakeoff_takeaways(rows)
    assert any("ε" in n and ("过紧" in n or "不可解" in n) for n in notes)
