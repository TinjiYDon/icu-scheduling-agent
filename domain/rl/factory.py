"""Configured construction of the PPO ICU environment."""

from __future__ import annotations

from domain.rl.data_adapter import load_beds, load_patients
from domain.rl.env import ICUEnv
from infra.config import load_yaml


def build_icu_env(*, training: bool = False, n_beds: int | None = None) -> ICUEnv:
    config = load_yaml("optimizer.yaml")
    ppo = config.get("ppo", {})
    resources = config.get("resources", {})
    episode_size = int(ppo.get("candidate_patients", 20))
    pool_size = int(ppo.get("training_pool_patients", 200)) if training else episode_size
    # PPO checkpoint is tied to observation dim = 7+4*n_beds+2 (trained at 20).
    beds_n = int(n_beds if n_beds is not None else ppo.get("inference_n_beds", 20))
    # Prefer rl.reward_weights (decoupled); fall back to lambda.* for compatibility.
    reward_weights = config.get("rl", {}).get("reward_weights") or config.get("lambda", {})
    return ICUEnv(
        patients=load_patients(pool_size),
        beds=load_beds(beds_n),
        reward_weights=reward_weights,
        invalid_action_penalty=float(ppo.get("invalid_action_penalty", 10.0)),
        wait_action_penalty=float(ppo.get("wait_action_penalty", 1.0)),
        ventilator_capacity=int(resources.get("n_ventilators", 8)),
        episode_size=episode_size,
        shuffle_on_reset=training,
    )
