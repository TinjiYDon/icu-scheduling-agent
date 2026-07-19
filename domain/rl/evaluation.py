"""Deterministic PPO and greedy rollout metrics on a shared ICU environment."""

from __future__ import annotations

from domain.rl.env import ICUEnv
from domain.rl.policy import predict_assignments


class GreedyPolicy:
    """Prefer a legal matching-zone bed, then the first legal bed, then wait."""

    def __init__(self, env: ICUEnv):
        self.env = env

    def predict(self, observation, *, action_masks, deterministic):
        patient = self.env.current_patient
        legal_beds = [
            index for index, allowed in enumerate(action_masks[:-1]) if allowed
        ]
        if patient:
            for index in legal_beds:
                if self.env.beds[index].zone == patient.preferred_zone:
                    return index, None
        return (legal_beds[0] if legal_beds else self.env.wait_action), None


def evaluate_greedy(env: ICUEnv, seed: int = 42) -> dict:
    return predict_assignments(GreedyPolicy(env), env, seed=seed)
