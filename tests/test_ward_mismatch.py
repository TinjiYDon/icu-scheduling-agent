"""Ward-pool extension: f2 is severe misplacement, not total SOFA."""

from __future__ import annotations

import pytest

from domain.optimizer.cp_sat import run_assignment


def row(sid: int, sofa: float, weight: float, zone: str = "MICU") -> dict:
    return {
        "stay_id": sid,
        "sofa_total": sofa,
        "priority_weight": weight,
        "first_careunit": zone,
    }


def solve(rows, *, n_beds=1, n_ward_beds=2, max_severe_ward=1, pivot="wait", **kwargs):
    resources = {
        "n_beds": n_beds,
        "n_isolation_beds": 0,
        "n_ventilators": 0,
        "bed_zones": [[1, n_beds, "MICU"]],
        "n_ward_beds": n_ward_beds,
        "severe_threshold": 8,
        "max_severe_ward": max_severe_ward,
        "ward_eligible_sofa_max": 24,
    }
    resources.update(kwargs.pop("resource_overrides", {}))
    return run_assignment(
        candidate_rows=rows,
        persist=False,
        solver_seed=0,
        max_time_seconds=3,
        pivot=pivot,
        resource_overrides=resources,
        **kwargs,
    )


def test_f2_counts_only_severe_ward_patients():
    result = solve(
        [row(1, 10, 3.0), row(2, 9, 2.0), row(3, 3, 1.0)],
        n_beds=1,
        n_ward_beds=2,
        max_severe_ward=1,
    )
    assert result["assigned"] == 1
    assert result["ward_patients"] == [2, 3]
    assert result["n_severe_ward"] == 1
    assert result["objective"]["f2_overload_penalty"] == 1
    assert result["objective"]["f1_priority_total"] == 6000
    assert result["evaluation"]["served_sofa_total"] == 22.0
    # The old identity cannot hold: severe ICU care contributes f1 but not f2.
    assert result["objective"]["f1_priority_total"] != (
        1000 * result["objective"]["f0_occupancy"]
        + 100 * result["objective"]["f2_overload_penalty"]
    )


def test_severe_ward_cap_zero_blocks_severe_overflow():
    result = solve(
        [row(1, 10, 3.0), row(2, 9, 2.0), row(3, 3, 1.0)],
        n_beds=1,
        n_ward_beds=2,
        max_severe_ward=0,
    )
    assert result["n_severe_ward"] == 0
    assert result["objective"]["f2_overload_penalty"] == 0
    assert result["ward_patients"] == [3]
    assert result["evaluation"]["severe_ward_count"] == 0


def test_ward_capacity_bounds_total_served_and_ward_occupancy():
    result = solve(
        [row(1, 10, 3.0), row(2, 9, 2.0), row(3, 3, 1.0)],
        n_beds=1,
        n_ward_beds=1,
        max_severe_ward=1,
    )
    assert result["n_ward_assigned"] == 1
    assert result["assigned"] + result["n_ward_assigned"] <= 2


def test_ward_disabled_keeps_legacy_f2():
    rows = [
        row(1, 10, 1.0 + 10 / 10),
        row(2, 9, 1.0 + 9 / 10),
        row(3, 3, 1.0 + 3 / 10),
    ]
    result = solve(rows, n_beds=1, n_ward_beds=0, max_severe_ward=0)
    assert result["ward_active"] is False
    assert result["ward_patients"] == []
    assert result["objective"]["f0_occupancy"] == 1
    assert result["objective"]["f2_overload_penalty"] == 10
    assert result["objective"]["f1_priority_total"] == 2000
    assert result["objective"]["f1_priority_total"] == (
        1000 * result["objective"]["f0_occupancy"]
        + 100 * result["objective"]["f2_overload_penalty"]
    )


def test_max_severe_ward_cannot_exceed_ward_capacity():
    with pytest.raises(ValueError, match="max_severe_ward"):
        solve([row(1, 10, 1.0)], n_beds=1, n_ward_beds=1, max_severe_ward=2)


def test_ward_ineligible_patients_cannot_be_placed_in_ward():
    result = solve(
        [row(1, 10, 3.0), row(2, 9, 2.0)],
        n_beds=1,
        n_ward_beds=2,
        max_severe_ward=2,
        resource_overrides={"ward_eligible_sofa_max": 8},
    )
    # Both are severe and therefore ineligible; the ward stays empty.
    assert result["ward_patients"] == []
    assert result["objective"]["f2_overload_penalty"] == 0


def test_existing_ward_census_consumes_capacity():
    result = solve(
        [row(1, 10, 3.0), row(2, 3, 1.0)],
        n_beds=1,
        n_ward_beds=2,
        max_severe_ward=1,
        ward_occupancy=2,
    )
    assert result["ward_patients"] == []
    assert result["ward_census"] == 2
    assert result["resources"]["ward_beds_used"] == "2/2"
