"""Constraint rules + trajectory export tests (S2-TRAJ protocol)."""

from __future__ import annotations

from domain.optimizer.constraint_rules import needs_isolation, needs_ventilator
from domain.rl.env import DEFAULT_REWARD_WEIGHTS

REQUIRED_PACK_KEYS = {
    "protocol_version",
    "created_at",
    "source",
    "n_beds",
    "step_hours",
    "n_steps",
    "summary",
    "transitions",
    "notes",
}
REQUIRED_TRANSITION_KEYS = {
    "t",
    "dt_hours",
    "state",
    "action",
    "reward_components",
    "constraint_violation",
}
REQUIRED_STATE_KEYS = {"occupied", "free_beds", "avg_sofa", "avg_weight"}
REQUIRED_ACTION_KEYS = {"admitted", "discharged", "policy"}
REQUIRED_REWARD_KEYS = {"occupancy", "wait"}


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
    assert tr[0]["reward_components"]["wait"] == 8.0


def test_protocol_schema_on_synthetic_pack():
    """S2-TRAJ 验收：合成包满足 protocol_version=1.0 字段契约。"""
    from domain.rl.trajectory import _transition_from_history

    hist = [
        {"step": 0, "occupied": 10, "admitted": 10, "discharged": 0, "avg_sofa": 5.0, "avg_weight": 1.0},
        {"step": 1, "occupied": 12, "admitted": 3, "discharged": 1, "avg_sofa": 6.0, "avg_weight": 1.2},
        {"step": 2, "occupied": 11, "admitted": 1, "discharged": 2, "avg_sofa": 5.5, "avg_weight": 1.1},
    ]
    transitions = _transition_from_history(hist, step_hours=2, n_beds=20)
    pack = {
        "protocol_version": "1.0",
        "created_at": "2026-09-24T00:00:00+00:00",
        "source": "unit",
        "n_beds": 20,
        "step_hours": 2,
        "n_steps": 2,
        "summary": {"final_occupancy": 11},
        "transitions": transitions,
        "notes": ["offline demo"],
    }
    assert REQUIRED_PACK_KEYS <= set(pack)
    assert pack["protocol_version"] == "1.0"
    assert len(transitions) == 2
    for tr in transitions:
        assert REQUIRED_TRANSITION_KEYS <= set(tr)
        assert REQUIRED_STATE_KEYS <= set(tr["state"])
        assert REQUIRED_ACTION_KEYS <= set(tr["action"])
        assert REQUIRED_REWARD_KEYS <= set(tr["reward_components"])
        assert tr["action"]["policy"]
        assert isinstance(tr["constraint_violation"], bool)
