"""Evaluate trained PPO against greedy and CP-SAT baselines."""

from __future__ import annotations

import json
from pathlib import Path

from domain.optimizer.cp_sat import run_assignment
from domain.rl.evaluation import evaluate_greedy
from domain.rl.factory import build_icu_env
from domain.rl.policy import load_model, predict_assignments
from infra.config import load_yaml


def evaluate_ppo(model_path: str | None = None) -> dict:
    config = load_yaml("optimizer.yaml")
    ppo = config.get("ppo", {})
    seed = int(ppo.get("seed", 42))
    path = model_path or ppo.get("model_path", "artifacts/ppo_icu")

    ppo_env = build_icu_env()
    model = load_model(path, env=ppo_env)
    ppo_result = predict_assignments(model, ppo_env, seed=seed)
    greedy_result = evaluate_greedy(build_icu_env(), seed=seed)
    cp_sat_result = run_assignment(run_id="evaluation_cp_sat")

    report = {
        "status": "ok",
        "note": "PPO/greedy share one episode; CP-SAT uses its configured candidate limit.",
        "ppo": ppo_result,
        "greedy": greedy_result,
        "cp_sat": {
            "assigned": cp_sat_result.get("assigned", 0),
            "n_stays": cp_sat_result.get("n_stays", 0),
            "evaluation": cp_sat_result.get("evaluation", {}),
        },
    }
    output = Path("reports/ppo_evaluation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate_ppo(), indent=2, ensure_ascii=False))
