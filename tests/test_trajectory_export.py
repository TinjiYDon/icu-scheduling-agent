"""Constraint rules + trajectory export tests."""

from __future__ import annotations

from domain.optimizer.constraint_rules import needs_isolation, needs_ventilator
from domain.rl.env import DEFAULT_REWARD_WEIGHTS


def test_needs_isolation_keywords():
    assert needs_isolation("Medical Intensive Care Unit (MICU)") is True
    assert needs_isolation("Floor") is False


def test_needs_ventilator_deterministic():
    a = needs_ventilator(12345)
    b = needs_ventilator(12345)
    assert a is b


def test_reward_weights_include_occupancy():
    assert "occupancy" in DEFAULT_REWARD_WEIGHTS


def test_trajectory_from_history_unit():
    from domain.rl.trajectory import _transition_from_history

    hist = [
        {"step": 0, "occupied": 10, "admitted": 10, "discharged": 0, "avg_sofa": 5, "avg_weight": 1},
        {"step": 1, "occupied": 12, "admitted": 3, "discharged": 1, "avg_sofa": 6, "avg_weight": 1.2},
    ]
    tr = _transition_from_history(hist, step_hours=2, n_beds=20)
    assert len(tr) == 1
    assert tr[0]["state"]["free_beds"] == 8
    assert tr[0]["constraint_violation"] is False
