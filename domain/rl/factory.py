"""Configured construction of the PPO ICU environment."""

from __future__ import annotations

from domain.rl.data_adapter import load_beds, load_patients
from domain.rl.env import ICUEnv
from infra.config import load_yaml


def build_icu_env(*, training: bool = False) -> ICUEnv:
    config = load_yaml("optimizer.yaml")
    ppo = config.get("ppo", {})
    resources = config.get("resources", {})
    episode_size = int(ppo.get("candidate_patients", 20))
    pool_size = int(ppo.get("training_pool_patients", 200)) if training else episode_size
    return ICUEnv(
        patients=load_patients(pool_size),
        beds=load_beds(),
        reward_weights=config.get("lambda", {}),
        invalid_action_penalty=float(ppo.get("invalid_action_penalty", 10.0)),
        wait_action_penalty=float(ppo.get("wait_action_penalty", 1.0)),
        ventilator_capacity=int(resources.get("n_ventilators", 8)),
        episode_size=episode_size,
        shuffle_on_reset=training,
    )
