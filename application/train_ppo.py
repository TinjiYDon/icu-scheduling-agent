"""Train and persist a MaskablePPO ICU scheduling policy."""

from __future__ import annotations

from pathlib import Path

from domain.rl.factory import build_icu_env
from infra.config import load_yaml


def train_ppo(total_timesteps: int | None = None, model_path: str | None = None) -> dict:
    from sb3_contrib import MaskablePPO

    config = load_yaml("optimizer.yaml").get("ppo", {})
    env = build_icu_env(training=True)
    target = Path(model_path or config.get("model_path", "artifacts/ppo_icu"))
    target.parent.mkdir(parents=True, exist_ok=True)
    model = MaskablePPO(
        "MlpPolicy",
        env,
        learning_rate=float(config.get("learning_rate", 3e-4)),
        gamma=float(config.get("gamma", 0.99)),
        gae_lambda=float(config.get("gae_lambda", 0.95)),
        clip_range=float(config.get("clip_range", 0.2)),
        batch_size=int(config.get("batch_size", 64)),
        n_steps=int(config.get("n_steps", 256)),
        seed=int(config.get("seed", 42)),
        verbose=1,
    )
    steps = int(total_timesteps or config.get("total_timesteps", 200_000))
    model.learn(total_timesteps=steps)
    model.save(str(target))
    return {"status": "ok", "model_path": str(target), "total_timesteps": steps}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="训练 MaskablePPO ICU 调度策略")
    parser.add_argument(
        "--timesteps",
        type=int,
        default=None,
        help="覆盖 optimizer.yaml 的 total_timesteps（如小规模试训 20000）",
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help="模型保存路径（默认 artifacts/ppo_icu）",
    )
    args = parser.parse_args()
    print(train_ppo(total_timesteps=args.timesteps, model_path=args.model_path))
