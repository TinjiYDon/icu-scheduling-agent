from __future__ import annotations

import pytest

from domain.scoring.priority import build_priority, composite, sofa_rule


def test_sofa_rule_matches_legacy_formula():
    assert sofa_rule([0, 4, 10, 12]) == [1.0, 1.4, 2.0, 2.2]


def test_composite_without_wait_equals_normalized_sofa():
    weights = composite([0, 6, 12], [0, 0, 0], sofa_weight=0.6, wait_weight=0.4)
    assert weights == [1.0, 1.3, 1.6]


def test_composite_adds_wait_term():
    no_wait = composite([6], [0.0], sofa_weight=0.6, wait_weight=0.4)
    with_wait = composite([6], [0.5], sofa_weight=0.6, wait_weight=0.4)
    assert with_wait[0] > no_wait[0]
    assert with_wait[0] == pytest.approx(1.3 + 0.2)


def test_composite_clamps_wait_percentile():
    clamped = composite([0], [1.5], sofa_weight=0.0, wait_weight=1.0)
    assert clamped == [2.0]


def test_composite_rejects_length_mismatch():
    with pytest.raises(ValueError, match="length mismatch"):
        composite([1, 2], [1])


def test_composite_rejects_negative_weights():
    with pytest.raises(ValueError, match="non-negative"):
        composite([1], [1], sofa_weight=-0.1)


def test_build_priority_dispatch():
    assert build_priority("sofa_rule", [4], [0]) == [1.4]
    assert build_priority(
        "composite", [4], [0], {"sofa_weight": 0.6, "wait_weight": 0.4}
    ) == pytest.approx([1.2])
    with pytest.raises(ValueError, match="unknown priority.mode"):
        build_priority("bogus", [1], [0])
