from __future__ import annotations

from domain.rl.env import Bed, ICUEnv, Patient
from domain.rl.policy import predict_assignments


class FirstValidModel:
    def predict(self, observation, *, action_masks, deterministic):
        action = next(index for index, valid in enumerate(action_masks) if valid)
        return action, None


def test_policy_inference_returns_common_assignment_shape():
    env = ICUEnv(
        patients=[Patient(1, 2.0)],
        beds=[Bed(1, has_ventilator=True)],
        ventilator_capacity=1,
    )

    result = predict_assignments(FirstValidModel(), env, seed=42)

    assert result["status"] == "ok"
    assert result["policy"] == "ppo"
    assert result["assigned"] == 1
    assert result["assignments"] == [{"stay_id": 1, "bed_id": 1, "zone": "REG"}]
