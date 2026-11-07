"""Check time-specific candidate snapshots against the archive CP-SAT model."""

import pytest
from ortools.sat.python import cp_model

from domain.optimizer import cp_sat
from domain.optimizer.objectives import ModelContext, build_objectives
from domain.optimizer.pareto import objective_vector


def solve(rows, **kwargs):
    return cp_sat.run_assignment(
        candidate_rows=rows,
        persist=False,
        solver_seed=0,
        resource_overrides={
            "n_beds": 2,
            "n_isolation_beds": 0,
            "bed_zones": [[1, 1, "MICU"], [2, 1, "SICU"]],
        },
        max_time_seconds=3,
        **kwargs,
    )


def row(sid, sofa=5, weight=1.5, zone="MICU"):
    return {
        "stay_id": sid,
        "sofa_total": sofa,
        "priority_weight": weight,
        "first_careunit": zone,
    }


def test_snapshot_uses_provided_weights_and_archive_objective_units(monkeypatch):
    monkeypatch.setattr(cp_sat, "get_engine", lambda: pytest.fail("DB opened"))
    rows = [row(1, 2, 2.5), row(2, 14, 1.5)]
    first = solve(rows, pivot="wait")
    second = solve(list(reversed(rows)), pivot="wait")
    assert first["top_assignments"] == second["top_assignments"]
    assert first["priority_mode"] == "provided"
    assert first["wait_source"] == "unavailable"
    assert first["evaluation"]["avg_wait_hours"] is None
    assert objective_vector(first) == {
        "occupancy": 2,
        "wait": 4000,
        "overload": 16,
        "balance": 0,
        "zone_mismatch": 1,
        "move": 0,
    }


def test_retained_patient_can_move_but_is_not_displaced():
    result = solve(
        [
            row(1, weight=1, zone="SICU"),
            row(2, weight=2),
            row(3, weight=10, zone="SICU"),
        ],
        previous_beds={1: 1},
        retain_occupied=True,
        pivot="wait",
        epsilon={"occupancy": 2, "zone_mismatch": 0},
    )
    assert {a["stay_id"]: a["bed_id"] for a in result["top_assignments"]} == {
        1: 2,
        2: 1,
    }
    assert objective_vector(result)["move"] == 1


def test_infeasible_epsilon_preserves_status():
    with pytest.raises(cp_sat.AssignmentSolveError) as exc:
        solve([row(1)], pivot="wait", epsilon={"occupancy": 2})
    assert exc.value.solver_status == "INFEASIBLE"


def test_snapshot_rejects_retention_of_missing_candidate():
    with pytest.raises(ValueError, match="retained patients"):
        solve([], previous_beds={1: 1}, retain_occupied=True)


@pytest.mark.parametrize(
    "rows", [[row(1), row(1)], [row(1, sofa=25)], [row(1, weight=float("nan"))]]
)
def test_invalid_snapshot_rejected(rows):
    with pytest.raises(ValueError, match="candidate_rows"):
        solve(rows)


def test_snapshot_rejects_persistence():
    with pytest.raises(ValueError, match="persist=False"):
        cp_sat.run_assignment(candidate_rows=[row(1)])


def test_balance_is_exact_even_when_not_minimized():
    model = cp_model.CpModel()
    x = {(0, 0): model.NewBoolVar("bed_1"), (0, 1): model.NewBoolVar("bed_2")}
    model.Add(x[0, 0] == 1)
    model.Add(x[0, 1] == 0)
    ctx = ModelContext(
        n=1,
        n_beds=2,
        n_iso_beds=0,
        weights=[1_000],
        sofa_vals=[5],
        regular_beds=[0, 1],
        iso_flags=[False],
        iso_active=False,
        patient_zones=[0],
        bed_zone_start={},
        bed_zone_count={},
        zone_specs=[("MICU", [0]), ("SICU", [1])],
        prev_bed={},
        stay_ids=[1],
    )
    balance = build_objectives(model, x, ctx)["balance"]
    model.Maximize(balance)
    solver = cp_model.CpSolver()
    assert solver.Solve(model) == cp_model.OPTIMAL
    assert solver.Value(balance) == 1
