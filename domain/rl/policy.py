"""MaskablePPO loading and deterministic assignment inference."""

from __future__ import annotations

from pathlib import Path

from domain.rl.env import ICUEnv


def load_model(model_path: str | Path, env: ICUEnv | None = None):
    from sb3_contrib import MaskablePPO

    return MaskablePPO.load(str(model_path), env=env)


def predict_assignments(model, env: ICUEnv, *, seed: int | None = None) -> dict:
    observation, _ = env.reset(seed=seed)
    terminated = False
    total_reward = 0.0
    reward_totals: dict[str, float] = {}
    while not terminated:
        action, _ = model.predict(
            observation,
            action_masks=env.action_masks(),
            deterministic=True,
        )
        observation, reward, terminated, truncated, info = env.step(int(action))
        if truncated:
            break
        total_reward += float(reward)
        for name, value in info["reward_components"].items():
            reward_totals[name] = reward_totals.get(name, 0.0) + float(value)
    return {
        "policy": "ppo",
        "assignments": list(env.assignments),
        "assigned": len(env.assignments),
        "n_stays": len(env.patients),
        "total_reward": round(total_reward, 4),
        "reward_components": {key: round(value, 4) for key, value in reward_totals.items()},
        "status": "ok",
    }
