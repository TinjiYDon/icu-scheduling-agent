"""Unit tests for H5/H6 pure helpers (no DB)."""

from domain.ops.pto_decision_ablation import (
    assignment_set,
    build_priority_maps,
    decision_delta,
    pto_takeaways,
)
from domain.ops.rolling_contrast import (
    rolling_contrast_takeaways,
    summarize_rolling_run,
)


def test_build_priority_maps_and_delta():
    rows = [
        {"stay_id": 1, "sofa_total": 10, "los_hours": 24},
        {"stay_id": 2, "sofa_total": 2, "los_hours": 100},
    ]
    maps = build_priority_maps(rows, gbdt_preds={1: 4.0, 2: 1.5})
    assert maps["sofa_only"][1] > maps["sofa_only"][2]
    assert maps["gbdt"][1] == 4.0
    deltas = decision_delta(
        {
            "formula": frozenset([1]),
            "sofa_only": frozenset([1, 2]),
            "gbdt": frozenset([1]),
        }
    )
    assert deltas["sofa_only"]["only_in_alt"] == 1
    notes = pto_takeaways(
        [{"method": "sofa_only", "high_risk": 1}, {"method": "formula", "high_risk": 2}],
        deltas,
    )
    assert any("H5" in n for n in notes)


def test_assignment_set():
    s = assignment_set({"top_assignments": [{"stay_id": 3}, {"stay_id": 5}]})
    assert s == frozenset([3, 5])


def test_rolling_contrast_summary():
    fake = {
        "reoptimize": True,
        "final_occupancy": 18,
        "bed_utilization_pct": 90.0,
        "total_admissions": 40,
        "total_discharges": 22,
        "history": [
            {"avg_sofa": 8.0, "avg_weight": 2.0, "occupied": 16},
            {"avg_sofa": 10.0, "avg_weight": 2.2, "occupied": 18},
        ],
    }
    s = summarize_rolling_run(fake)
    assert s["mean_avg_sofa"] == 9.0
    notes = rolling_contrast_takeaways(
        s,
        {
            "mean_avg_sofa": 7.0,
            "mean_avg_weight": 1.8,
            "final_occupancy": 18,
        },
    )
    assert any("H6" in n for n in notes)
