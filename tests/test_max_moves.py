"""Hard cap on f5 (bed moves): stability as a constraint, not only a penalty.

Layout used here is 4 beds in two zones (MICU = beds 1-2, SICU = beds 3-4).

Two incumbents start inside MICU:
  * stay 11 prefers SICU, currently bed 1  -> must move to satisfy f4 = 0
  * stay 22 prefers MICU, currently bed 2  -> already in its preferred zone
So ``zone_mismatch == 0`` forces exactly one bed change, which lets us pin down
the interaction between the move cap and the epsilon constraints.
"""

from __future__ import annotations

import pytest

from domain.optimizer.cp_sat import AssignmentSolveError, run_assignment

RESOURCES = {
    "n_beds": 4,
    "n_isolation_beds": 0,
    "n_ventilators": 8,
    "bed_zones": [[1, 2, "MICU"], [3, 2, "SICU"]],
}

# stay 11 wants SICU, stay 22 wants MICU; both currently sit in MICU.
CANDIDATES = [
    {"stay_id": 11, "sofa_total": 4, "priority_weight": 1.4, "first_careunit": "SICU"},
    {"stay_id": 22, "sofa_total": 2, "priority_weight": 1.2, "first_careunit": "MICU"},
]
PREVIOUS = {11: 1, 22: 2}


def _solve(**kwargs) -> dict:
    return run_assignment(
        persist=False,
        candidate_rows=CANDIDATES,
        resource_overrides=RESOURCES,
        previous_beds=PREVIOUS,
        solver_seed=0,
        retain_occupied=True,
        **kwargs,
    )


def _assignments(result: dict) -> dict[int, int]:
    return {
        int(row["stay_id"]): int(row["bed_id"])
        for row in result["top_assignments"]
    }


def _moves(result: dict) -> int:
    """Recompute f5 from the bed map instead of trusting the objective value."""
    amap = _assignments(result)
    return sum(bed != PREVIOUS[sid] for sid, bed in amap.items() if sid in PREVIOUS)


def test_cap_zero_forces_no_bed_change():
    result = _solve(max_moves=0)
    assert _moves(result) == 0
    assert result["objective"]["f5_move"] == 0
    # Staying put means stay 11 remains in the wrong zone.
    assert result["objective"]["f4_zone_mismatch"] == 1
    assert result["max_moves"] == 0


def test_uncapped_weighted_sum_keeps_the_bed_despite_the_mismatch():
    """lambda_move (0.5) dwarfs lambda_zone (0.1), so stability wins.

    Coefficients are weight * 1e6 / upper_bound, i.e. 125000 per move versus
    25000 per zone mismatch on this 4-bed layout.  This is exactly why the
    executed rolling reference shows f5 == 0 even when a move would fit better.
    """
    result = _solve()
    assert result["max_moves"] is None
    assert result["objective"]["f4_zone_mismatch"] == 1
    assert _moves(result) == 0


def test_pivot_on_zone_mismatch_relocates_the_patient():
    result = _solve(pivot="zone_mismatch")
    assert result["objective"]["f4_zone_mismatch"] == 0
    assert _moves(result) == 1
    assert result["objective"]["f5_move"] == 1


def test_cap_one_is_binding_but_satisfiable():
    result = _solve(max_moves=1)
    assert _moves(result) <= 1
    assert result["objective"]["f5_move"] == _moves(result)
    assert result["max_moves"] == 1


def test_ratio_zero_behaves_like_a_zero_cap():
    result = _solve(max_moves_ratio=0.0)
    assert _moves(result) == 0
    assert result["max_moves"] == 0
    assert result["max_moves_ratio"] == 0.0


def test_ratio_is_floored_over_common_patients():
    # Both incumbents are candidates, so floor(0.5 * 2) == 1.
    result = _solve(max_moves_ratio=0.5)
    assert result["max_moves"] == 1
    assert _moves(result) <= 1


def test_absolute_cap_wins_over_ratio():
    result = _solve(max_moves=0, max_moves_ratio=1.0)
    assert result["max_moves"] == 0
    assert _moves(result) == 0


def test_cap_conflicting_with_epsilon_is_reported_infeasible():
    # f4 = 0 requires exactly one bed change, which a zero cap forbids.
    with pytest.raises(AssignmentSolveError) as excinfo:
        _solve(max_moves=0, pivot="occupancy", epsilon={"zone_mismatch": 0})
    assert excinfo.value.solver_status == "INFEASIBLE"


def test_same_epsilon_is_feasible_once_the_cap_is_relaxed():
    result = _solve(max_moves=1, pivot="occupancy", epsilon={"zone_mismatch": 0})
    assert result["objective"]["f4_zone_mismatch"] == 0
    assert result["objective"]["f5_move"] == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_moves": -1},
        {"max_moves_ratio": -0.1},
        {"max_moves_ratio": 1.5},
    ],
)
def test_invalid_cap_values_are_rejected(kwargs):
    with pytest.raises(ValueError):
        _solve(**kwargs)
