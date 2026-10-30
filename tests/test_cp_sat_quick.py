"""Read-only integration smoke for the actual constrained assignment model."""

import pytest

pytestmark = pytest.mark.integration


def test_cp_sat_assignment_is_feasible():
    from domain.optimizer.cp_sat import run_assignment

    result = run_assignment(persist=False, max_time_seconds=30)
    assert result["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assignments = result["top_assignments"]
    assert 0 < len(assignments) <= result["n_beds"]
    assert len({a["stay_id"] for a in assignments}) == len(assignments)
    assert len({a["bed_id"] for a in assignments}) == len(assignments)
