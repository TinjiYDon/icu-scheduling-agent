from __future__ import annotations

from sb3_contrib import MaskablePPO

from domain.rl.env import Bed, ICUEnv, Patient
from domain.rl.policy import predict_assignments

# ts
def test_maskable_ppo_short_training_and_inference():
    env = ICUEnv(
        patients=[Patient(index, 1.0 + index / 10) for index in range(1, 5)],
        beds=[Bed(1), Bed(2)],
        episode_size=4,
        shuffle_on_reset=True,
    )
    model = MaskablePPO(
        "MlpPolicy",
        env,
        n_steps=8,
        batch_size=4,
        seed=42,
        verbose=0,
    )

    model.learn(total_timesteps=16)
    result = predict_assignments(model, env, seed=42)

    assert result["status"] == "ok"
    assert 0 <= result["assigned"] <= 2
