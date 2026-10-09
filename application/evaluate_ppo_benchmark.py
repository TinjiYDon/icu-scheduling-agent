"""Multi-episode PPO / greedy / CP-SAT benchmark on matched fair pools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from domain.ops.h3_benchmark import summarize_benchmark_episodes
from infra.config import load_yaml


def evaluate_ppo_benchmark(
    episodes: int | None = None,
    candidate_patients: int | None = None,
    pool_patients: int | None = None,
    seed: int | None = None,
    model_path: str | None = None,
    output_path: str | None = None,
) -> dict:
    from application.evaluate_ppo import _cp_sat_canonical, _enrich_policy_metrics
    from domain.ops.h3_fair import annotate_fair_report, resource_overrides_from_env
    from domain.optimizer.cp_sat import run_assignment
    from domain.rl.data_adapter import load_patients
    from domain.rl.evaluation import evaluate_greedy
    from domain.rl.factory import build_icu_env
    from domain.rl.policy import load_model, predict_assignments

    config = load_yaml("optimizer.yaml")
    ppo = config.get("ppo", {})
    default_seed = int(ppo.get("seed", 42))
    default_candidate_patients = int(ppo.get("candidate_patients", 20))
    default_pool_patients = int(ppo.get("training_pool_patients", 200))
    default_episodes = int(ppo.get("benchmark_episodes", 5))
    seed = int(seed if seed is not None else default_seed)
    episodes = int(episodes if episodes is not None else default_episodes)
    candidate_patients = int(
        candidate_patients
        if candidate_patients is not None
        else default_candidate_patients
    )
    pool_patients = int(
        pool_patients if pool_patients is not None else default_pool_patients
    )
    path = model_path or ppo.get("model_path", "artifacts/ppo_icu")
    output = Path(output_path or "reports/ppo_benchmark.json")

    pool = load_patients(pool_patients)
    if len(pool) < candidate_patients:
        raise ValueError(
            f"candidate_patients={candidate_patients} exceeds pool size {len(pool)}"
        )

    rng = np.random.default_rng(seed)
    pool_ids = [patient.stay_id for patient in pool]
    episode_reports: list[dict] = []
    shared_resources: dict[str, Any] | None = None

    for episode_index in range(episodes):
        episode_seed = seed + episode_index
        sampled_ids = [
            int(x)
            for x in rng.choice(pool_ids, size=candidate_patients, replace=False).tolist()
        ]
        ppo_env = build_icu_env(candidate_stay_ids=sampled_ids)
        resources = resource_overrides_from_env(ppo_env)
        n_beds = int(resources["n_beds"])
        if shared_resources is None:
            shared_resources = dict(resources)

        model = load_model(path, env=ppo_env)
        ppo_result = _enrich_policy_metrics(
            ppo_env,
            predict_assignments(model, ppo_env, seed=episode_seed, policy_name="ppo"),
        )
        greedy_env = build_icu_env(candidate_stay_ids=sampled_ids, n_beds=n_beds)
        greedy_result = _enrich_policy_metrics(
            greedy_env, evaluate_greedy(greedy_env, seed=episode_seed)
        )
        cp_sat_result = run_assignment(
            run_id=f"ppo_benchmark_{episode_index}",
            stay_ids=sampled_ids,
            persist=False,
            resource_overrides=resources,
        )

        episode_reports.append(
            {
                "episode": episode_index + 1,
                "seed": episode_seed,
                "candidate_stay_ids": sampled_ids,
                "shared_n_beds": n_beds,
                "shared_resources": resources,
                "ppo": ppo_result,
                "greedy": greedy_result,
                "cp_sat": {
                    "assigned": cp_sat_result.get("assigned", 0),
                    "n_stays": cp_sat_result.get("n_stays", 0),
                    "evaluation": _cp_sat_canonical(
                        cp_sat_result.get("evaluation", {})
                    ),
                },
            }
        )

    summary = summarize_benchmark_episodes(
        episode_reports,
        episodes=episodes,
        seed=seed,
        candidate_patients=candidate_patients,
        pool_patients=len(pool),
        model_path=path,
    )
    report: dict[str, Any] = {
        "status": "ok",
        "summary": summary,
    }
    report = annotate_fair_report(
        report,
        stay_ids=pool_ids[:candidate_patients],
        n_beds=int((shared_resources or {}).get("n_beds", 20)),
        resources=shared_resources,
    )
    report["note"] = summary["note"]
    report["fair_pool"] = True

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="多 episode PPO / Greedy / CP-SAT 同候选+同资源 benchmark"
    )
    parser.add_argument(
        "--episodes", type=int, default=None, help="episode 数，默认读取 optimizer.yaml"
    )
    parser.add_argument(
        "--candidate-patients",
        type=int,
        default=None,
        help="每个 episode 的候选患者数，默认读取 optimizer.yaml",
    )
    parser.add_argument(
        "--pool-patients",
        type=int,
        default=None,
        help="候选池大小，默认读取 optimizer.yaml 的 training_pool_patients",
    )
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--model-path", default=None, help="PPO 模型路径")
    parser.add_argument(
        "--output-path",
        default=None,
        help="报告输出路径（默认 reports/ppo_benchmark.json）",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate_ppo_benchmark(
                episodes=args.episodes,
                candidate_patients=args.candidate_patients,
                pool_patients=args.pool_patients,
                seed=args.seed,
                model_path=args.model_path,
                output_path=args.output_path,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )
