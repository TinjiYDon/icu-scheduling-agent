"""S2-MOO phase-2 objective semantics (acuity overload + honest naming)."""

from __future__ import annotations

from domain.optimizer.objective_semantics import (
    HIGH_RISK_SOFA,
    OBJECTIVE_SEMANTICS,
    count_high_risk_on_regular,
    overload_sofa_from_assignment,
    sum_overload_from_assignments,
)


def test_wait_canonical_is_priority_served():
    assert OBJECTIVE_SEMANTICS["wait"]["canonical"] == "priority_served"
    assert "非真实等待" in OBJECTIVE_SEMANTICS["wait"]["meaning"]


def test_overload_canonical_is_high_risk_on_regular():
    assert OBJECTIVE_SEMANTICS["overload"]["canonical"] == "high_risk_on_regular_beds"


def test_low_risk_on_regular_not_counted():
    assert overload_sofa_from_assignment(sofa=4, bed_type="MICU") == 0
    assert overload_sofa_from_assignment(sofa=HIGH_RISK_SOFA - 1, bed_type="REG") == 0


def test_high_risk_on_regular_counted():
    assert overload_sofa_from_assignment(sofa=12, bed_type="MICU") == 12
    assert overload_sofa_from_assignment(sofa=10, bed_type="SICU") == 10


def test_high_risk_on_iso_not_counted():
    assert overload_sofa_from_assignment(sofa=15, bed_type="ISO") == 0
    assert overload_sofa_from_assignment(sofa=15, bed_type="iso") == 0


def test_sum_and_count_on_mixed_assignments():
    rows = [
        {"sofa_total": 4, "bed_type": "MICU"},
        {"sofa_total": 12, "bed_type": "SICU"},
        {"sofa_total": 14, "bed_type": "ISO"},
        {"sofa_total": 11, "bed_type": "CCU"},
    ]
    assert sum_overload_from_assignments(rows) == 12 + 11
    assert count_high_risk_on_regular(rows) == 2
