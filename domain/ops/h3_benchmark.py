"""Pure helpers for S3 multi-episode fair PPO / greedy / CP-SAT summaries."""

from __future__ import annotations

from typing import Any, Sequence


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / max(len(values), 1), 4)


def summarize_benchmark_episodes(
    episode_reports: Sequence[dict[str, Any]],
    *,
    episodes: int,
    seed: int,
    candidate_patients: int,
    pool_patients: int,
    model_path: str,
) -> dict[str, Any]:
    """Aggregate per-episode fair H3 metrics (DB/PPO free)."""

    def _policy_mean(policy: str, key: str) -> float:
        vals: list[float] = []
        for report in episode_reports:
            block = report.get(policy) or {}
            if key in block and block[key] is not None:
                vals.append(float(block[key]))
                continue
            if policy == "cp_sat":
                ev = block.get("evaluation") or {}
                if key in ev and ev[key] is not None:
                    vals.append(float(ev[key]))
        return _mean(vals) if vals else 0.0

    return {
        "episodes": episodes,
        "seed": seed,
        "candidate_patients": candidate_patients,
        "pool_patients": pool_patients,
        "model_path": model_path,
        "same_candidate_scale": True,
        "fair_pool": True,
        "ppo": {
            "mean_assigned": _policy_mean("ppo", "assigned"),
            "mean_total_reward": _policy_mean("ppo", "total_reward"),
            "mean_high_risk_wait": _policy_mean("ppo", "high_risk_wait"),
            "mean_constraint_violations": _policy_mean("ppo", "constraint_violations"),
        },
        "greedy": {
            "mean_assigned": _policy_mean("greedy", "assigned"),
            "mean_total_reward": _policy_mean("greedy", "total_reward"),
            "mean_high_risk_wait": _policy_mean("greedy", "high_risk_wait"),
            "mean_constraint_violations": _policy_mean(
                "greedy", "constraint_violations"
            ),
        },
        "cp_sat": {
            "mean_assigned": _policy_mean("cp_sat", "assigned"),
            "mean_high_risk_wait": _policy_mean("cp_sat", "high_risk_wait"),
            "mean_constraint_violations": _policy_mean(
                "cp_sat", "constraint_violations"
            ),
        },
        "note": (
            "S3 deepen: each episode shares the same candidate_stay_ids and "
            "resource layout (beds / isolation / ventilators / zones) across "
            "PPO / greedy / CP-SAT. Offline only — do not claim online MIMIC-PPO."
        ),
        "episodes_detail": list(episode_reports),
    }
