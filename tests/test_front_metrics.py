"""Unit tests for front quality metrics (no DB, no solver)."""

from __future__ import annotations

import pytest

from domain.optimizer.front_metrics import (
    KNEE_MIN_PROMINENCE,
    dominates,
    hypervolume,
    knee_analysis,
    knee_point,
    nondominated,
    normalize_to_max,
    summarize_front,
)


def test_dominates_strict_and_tie():
    assert dominates([1.0, 1.0], [0.5, 0.5])
    assert dominates([1.0, 0.5], [0.5, 0.5])
    # Identical points do not dominate each other.
    assert not dominates([1.0, 1.0], [1.0, 1.0])
    # Worse in one coordinate is not domination.
    assert not dominates([1.0, 0.1], [0.5, 0.5])


def test_nondominated_keeps_front_and_dedups():
    pts = [[1.0, 0.2], [0.2, 1.0], [0.1, 0.1], [1.0, 0.2]]
    kept = nondominated(pts)
    assert [list(p) for p in kept] == [[1.0, 0.2], [0.2, 1.0]]


def test_normalize_flips_min_objectives():
    norm = normalize_to_max(
        {"wait": 50.0, "overload": 0.0},
        ideal={"wait": 100.0, "overload": 0.0},
        nadir={"wait": 0.0, "overload": 50.0},
        senses={"wait": "max", "overload": "min"},
    )
    assert norm["wait"] == pytest.approx(0.5)
    assert norm["overload"] == pytest.approx(1.0)  # best possible for a min goal


def test_normalize_constant_axis_is_one():
    norm = normalize_to_max(
        {"balance": 3.0},
        ideal={"balance": 3.0},
        nadir={"balance": 3.0},
        senses={"balance": "min"},
    )
    assert norm["balance"] == 1.0


def test_hypervolume_2d_known_value():
    # Union of [0,1]x[0,0.2] and [0,0.2]x[0,1] = 0.2 + 0.2 - 0.04 = 0.36
    hv = hypervolume([[1.0, 0.2], [0.2, 1.0]], reference=0.0)
    assert hv == pytest.approx(0.36)


def test_hypervolume_drops_dominated_points():
    hv_clean = hypervolume([[1.0, 0.2], [0.2, 1.0]], reference=0.0)
    hv_with_dominated = hypervolume(
        [[1.0, 0.2], [0.2, 1.0], [0.1, 0.1]], reference=0.0
    )
    assert hv_with_dominated == pytest.approx(hv_clean)


def test_hypervolume_monotone_when_adding_point():
    hv1 = hypervolume([[1.0, 0.2]], reference=0.0)
    hv2 = hypervolume([[1.0, 0.2], [0.2, 1.0]], reference=0.0)
    assert hv2 >= hv1


def test_hypervolume_ignores_points_at_or_below_reference():
    assert hypervolume([[0.0, 0.0]], reference=0.0) == 0.0
    assert hypervolume([[-1.0, 0.5]], reference=0.0) == 0.0


def test_hypervolume_mapping_form_matches_sequence_form():
    pts = [{"a": 1.0, "b": 0.2}, {"a": 0.2, "b": 1.0}]
    hv = hypervolume(pts, objectives=["a", "b"], reference=0.0)
    assert hv == pytest.approx(0.36)


def test_hypervolume_mapping_requires_objectives():
    with pytest.raises(ValueError):
        hypervolume([{"a": 1.0}])


def test_knee_point_picks_the_bulge():
    front = [
        {"x": 1.0, "y": 0.0},
        {"x": 0.85, "y": 0.85},  # clearly the balanced compromise
        {"x": 0.0, "y": 1.0},
    ]
    assert knee_point(front, objectives=["x", "y"]) == 1


def test_knee_point_needs_three_points():
    assert knee_point([[1.0, 0.0], [0.0, 1.0]]) is None
    assert knee_point([]) is None


def test_knee_point_flat_front_returns_interior_point():
    front = [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]]
    # The middle point lies exactly on the chord, so it is still the returned one
    # (distance 0 beats the excluded extremes by construction).
    assert knee_point(front) == 1


def test_summarize_front_reports_size_hv_and_knee():
    senses = {"x": "max", "y": "max"}
    ideal = {"x": 1.0, "y": 1.0}
    nadir = {"x": 0.0, "y": 0.0}
    points = [
        {"x": 1.0, "y": 0.0},
        {"x": 0.85, "y": 0.85},
        {"x": 0.0, "y": 1.0},
    ]
    summary = summarize_front(points, ideal=ideal, nadir=nadir, senses=senses)
    assert summary["n_front"] == 3
    assert summary["hypervolume"] > 0.0
    assert summary["knee_index"] == 1


def test_summarize_front_empty():
    summary = summarize_front(
        [], ideal={"x": 1.0}, nadir={"x": 0.0}, senses={"x": "max"}
    )
    assert summary == {
        "n_front": 0,
        "hypervolume": 0.0,
        "knee_index": None,
        "knee_prominence": 0.0,
        "knee_axes": None,
        "n_knee_ties": 0,
    }


def test_knee_pivot_is_always_one_of_the_axes():
    # Even when a non-pivot axis has the widest spread, the pivot must stay in
    # the knee plane: the whole point of the sweep is "what does the pivot cost".
    points = [
        {"wait": 0.6, "overload": 1.0, "zone_mismatch": 1.0},
        {"wait": 0.7, "overload": 0.7, "zone_mismatch": 0.8},
        {"wait": 0.8, "overload": 0.5, "zone_mismatch": 1.0},
        {"wait": 1.0, "overload": 0.0, "zone_mismatch": 0.3},
    ]
    info = knee_analysis(
        points, objectives=["wait", "overload", "zone_mismatch"], pivot="wait"
    )
    assert info["axes"][0] == "wait"
    # Without the pivot hint the widest-spread pair is chosen instead, which for
    # this front does not contain "wait" -- that is exactly what the hint avoids.
    hintless = knee_analysis(
        points, objectives=["wait", "overload", "zone_mismatch"]
    )
    assert hintless["axes"][0] == "overload"


def test_knee_prominence_stays_bounded_on_a_staircase_front():
    # Regression: endpoints chosen by a lexicographic argmax could collapse to a
    # near-zero chord and inflate prominence to >1.  Sorted-by-first-axis
    # endpoints keep it meaningful.
    points = [
        {"wait": 0.5882, "overload": 1.0, "zone_mismatch": 1.0},
        {"wait": 0.6471, "overload": 0.8571, "zone_mismatch": 1.0},
        {"wait": 0.7059, "overload": 0.7143, "zone_mismatch": 1.0},
        {"wait": 0.7647, "overload": 0.5714, "zone_mismatch": 1.0},
        {"wait": 0.9412, "overload": 0.1429, "zone_mismatch": 1.0},
        {"wait": 1.0, "overload": 0.0, "zone_mismatch": 1.0},
        {"wait": 1.0, "overload": 0.0, "zone_mismatch": 0.3333},
    ]
    info = knee_analysis(
        points,
        objectives=["wait", "overload", "zone_mismatch"],
        pivot="wait",
    )
    assert info["axes"] == ("wait", "overload")
    assert info["prominence"] <= 1.0


def test_knee_analysis_reports_prominence_for_a_bulge():
    front = [
        {"x": 1.0, "y": 0.0},
        {"x": 0.85, "y": 0.85},
        {"x": 0.0, "y": 1.0},
    ]
    info = knee_analysis(front, objectives=["x", "y"])
    assert info["index"] == 1
    assert info["distinct"] is True
    assert info["prominence"] > KNEE_MIN_PROMINENCE


def test_collinear_front_has_no_knee():
    # A straight trade-off line: every point is equally far (0) from the chord,
    # so no point can be singled out as the compromise.
    collinear = [[1.0, 0.0], [0.75, 0.25], [0.5, 0.5], [0.25, 0.75], [0.0, 1.0]]
    info = knee_analysis(collinear)
    assert info["index"] is None
    assert info["distinct"] is False
    assert info["prominence"] == 0.0

    summary = summarize_front(
        [{"x": p[0], "y": p[1]} for p in collinear],
        ideal={"x": 1.0, "y": 1.0},
        nadir={"x": 0.0, "y": 0.0},
        senses={"x": "max", "y": "max"},
    )
    # Still report the front size and HV; only the knee is withheld.
    assert summary["n_front"] == 5
    assert summary["hypervolume"] > 0.0
    assert summary["knee_index"] is None
    assert summary["n_knee_ties"] == 0


def test_near_collinear_front_below_threshold_is_withheld():
    # A tiny bulge (well under the 2% prominence gate) must not be reported.
    nearly = [[1.0, 0.0], [0.5, 0.5005], [0.0, 1.0]]
    assert knee_analysis(nearly)["index"] is None
    # Lowering the gate surfaces it again, which proves the gate is what filtered it.
    assert knee_analysis(nearly, min_prominence=0.0)["index"] == 1
