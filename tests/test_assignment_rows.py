"""Real CP-SAT checks for time-specific, database-free candidate snapshots."""

import pytest

from domain.optimizer import cp_sat


def solve(rows, **kwargs):
    return cp_sat.run_assignment(
        candidate_rows=rows,
        persist=False,
        solver_seed=0,
        constraint_modes={"isolation": "none", "ventilator": "none"},
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


def test_snapshot_does_not_open_database_and_is_reproducible(monkeypatch):
    monkeypatch.setattr(cp_sat, "get_engine", lambda: pytest.fail("DB opened"))
    a = solve([row(1), row(2, 12, 2.2)])
    b = solve([row(1), row(2, 12, 2.2)])
    assert a["top_assignments"] == b["top_assignments"]
    assert a["assigned"] == 2
    assert a["constraint_demand"] == {"n_isolation_demand": 0, "n_ventilator_demand": 0}


def test_f5_counts_forced_moves_but_not_new_admissions():
    result = solve(
        [row(1, zone="SICU"), row(2, zone="MICU")],
        occupied_beds={1: 1},
        retain_occupied=True,
        objective_mode="epsilon_constraint",
        epsilon_primary="wait",
        epsilon_bounds={"occupancy": 2, "zone_mismatch": 0},
    )
    assert {a["stay_id"]: a["bed_id"] for a in result["top_assignments"]} == {
        1: 2,
        2: 1,
    }
    assert result["multiobjective"]["values"]["move"] == 1


def test_retained_patient_cannot_be_dropped_for_higher_priority():
    result = solve(
        [row(1, weight=1), row(2, weight=2), row(3, weight=10)],
        occupied_beds={1: 1, 2: 2},
        retain_occupied=True,
    )
    assert {a["stay_id"] for a in result["top_assignments"]} == {1, 2}


def test_mismatch_is_exact_even_when_not_optimized():
    result = solve(
        [row(1, zone="MICU"), row(2, zone="MICU")],
        objective_mode="epsilon_constraint",
        epsilon_primary="occupancy",
    )
    assert result["multiobjective"]["values"]["zone_mismatch"] == 1


@pytest.mark.parametrize(
    "rows", [[row(1), row(1)], [row(1, sofa=25)], [row(1, weight=float("nan"))]]
)
def test_bad_snapshot_is_rejected(rows):
    with pytest.raises(ValueError):
        solve(rows)


def test_snapshot_requires_explicit_nonpersistent_mode():
    with pytest.raises(ValueError, match="persist"):
        cp_sat.run_assignment(candidate_rows=[row(1)])


def test_retention_rejects_missing_patients():
    with pytest.raises(ValueError, match="occupied"):
        solve([row(1)], occupied_beds={2: 1}, retain_occupied=True)


def test_infeasible_epsilon_retains_solver_status():
    with pytest.raises(cp_sat.AssignmentSolveError) as caught:
        solve(
            [row(1)],
            objective_mode="epsilon_constraint",
            epsilon_primary="wait",
            epsilon_bounds={"occupancy": 3},
        )
    assert caught.value.solver_status == "INFEASIBLE"
