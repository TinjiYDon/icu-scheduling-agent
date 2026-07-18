"""Run deterministic PPO inference against the configured ICU snapshot."""

from __future__ import annotations

import json

from domain.rl.factory import build_icu_env
from domain.rl.policy import load_model, predict_assignments
from infra.config import load_yaml


def run_ppo(model_path: str | None = None) -> dict:
    config = load_yaml("optimizer.yaml")
    ppo = config.get("ppo", {})
    env = build_icu_env()
    path = model_path or ppo.get("model_path", "artifacts/ppo_icu")
    model = load_model(path, env=env)
    return predict_assignments(model, env, seed=int(ppo.get("seed", 42)))


if __name__ == "__main__":
    print(json.dumps(run_ppo(), indent=2, ensure_ascii=False))
