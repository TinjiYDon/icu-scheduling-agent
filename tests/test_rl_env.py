from __future__ import annotations

import numpy as np
import pytest

from domain.rl.env import Bed, ICUEnv, Patient


def _environment() -> ICUEnv:
    return ICUEnv(
        patients=[
            Patient(1, 2.0, 12, preferred_zone="MICU", needs_isolation=True),
            Patient(2, 1.0, 4, preferred_zone="SICU"),
        ],
        beds=[
            Bed(1, "ISO", is_isolation=True, has_ventilator=True),
            Bed(2, "MICU"),
            Bed(3, "SICU"),
        ],
    )


def test_reset_returns_fixed_observation_and_action_mask():
    env = _environment()
    observation, info = env.reset(seed=42)

    assert env.observation_space.contains(observation)
    assert info["action_mask"].tolist() == [True, False, False, True]


def test_valid_assignments_occupy_beds_and_finish_episode():
    env = _environment()
    env.reset(seed=42)

    _, first_reward, terminated, truncated, first_info = env.step(0)
    assert first_reward > 0
    assert not terminated
    assert not truncated
    assert first_info["action_mask"].tolist() == [False, True, True, True]

    observation, _, terminated, truncated, info = env.step(2)
    assert terminated
    assert not truncated
    assert env.observation_space.contains(observation)
    assert info["assigned"] == 2


def test_invalid_action_is_penalized_without_assignment():
    env = _environment()
    env.reset(seed=42)

    _, reward, _, _, info = env.step(1)

    assert reward == -10.0
    assert info["reward_components"]["invalid"] == -10.0
    assert env.assignments == []


def test_reset_is_reproducible_and_clears_episode_state():
    env = _environment()
    first, _ = env.reset(seed=7)
    env.step(0)
    second, _ = env.reset(seed=7)

    assert np.array_equal(first, second)
    assert env.assignments == []


@pytest.mark.parametrize("penalty", [-1, np.inf, np.nan])
def test_invalid_penalty_configuration_is_rejected(penalty):
    with pytest.raises(ValueError, match="action penalties"):
        ICUEnv(
            patients=[],
            beds=[Bed(1)],
            invalid_action_penalty=penalty,
        )


def test_global_ventilator_capacity_masks_later_patients():
    env = ICUEnv(
        patients=[
            Patient(1, 2.0, needs_ventilator=True),
            Patient(2, 1.0, needs_ventilator=True),
        ],
        beds=[Bed(1, has_ventilator=True), Bed(2, has_ventilator=True)],
        ventilator_capacity=1,
    )
    env.reset()
    _, _, terminated, _, info = env.step(0)

    assert not terminated
    assert info["action_mask"].tolist() == [False, False, True]


def test_non_isolation_patient_can_use_free_isolation_bed_like_cp_sat():
    env = ICUEnv(patients=[Patient(1, 1)], beds=[Bed(1, "ISO", is_isolation=True)])
    _, info = env.reset()
    assert info["action_mask"].tolist() == [True, True]
    env.step(0)
    assert len(env.assignments) == 1


def test_portable_ventilator_does_not_remove_regular_bed_acuity_mismatch():
    env = ICUEnv(
        patients=[Patient(1, 1, sofa_total=12)],
        beds=[Bed(1, has_ventilator=True)],
        reward_weights={"overload": 2},
    )
    env.reset()
    _, _, _, _, info = env.step(0)
    assert info["reward_components"]["overload"] == -1.0


def test_isolation_patient_in_isolation_bed_has_no_zone_mismatch():
    env = _environment()
    env.reset()
    _, _, _, _, info = env.step(0)
    assert info["reward_components"]["zone_mismatch"] == 0


def test_training_episode_sampling_is_seeded_and_fixed_size():
    pool = [Patient(stay_id=index, priority_weight=1.0) for index in range(10)]
    env = ICUEnv(
        patients=pool,
        beds=[Bed(1)],
        episode_size=3,
        shuffle_on_reset=True,
    )

    env.reset(seed=42)
    first = [patient.stay_id for patient in env.patients]
    env.reset(seed=42)
    second = [patient.stay_id for patient in env.patients]

    assert len(first) == 3
    assert first == second
    assert first != [0, 1, 2]
