"""Evaluate trained PPO against greedy and CP-SAT baselines."""

from __future__ import annotations

import json
from pathlib import Path

from domain.optimizer.cp_sat import run_assignment
from domain.ops.flywheel_archive import archive_flywheel
from domain.ops.policy_comparison import flatten_comparison
from domain.rl.evaluation import evaluate_greedy
from domain.rl.factory import build_icu_env
from domain.rl.policy import load_model, predict_assignments
from infra.config import load_yaml

# SOFA threshold used across the repo to flag "high-risk" stays.
HIGH_RISK_SOFA = 10.0


def _enrich_policy_metrics(env, result: dict) -> dict:
    """Add canonical H3 fields to a PPO/greedy rollout result.

    ``flatten_comparison`` expects ``episode_reward`` / ``high_risk_wait`` /
    ``constraint_violations``; the rollout producer used to emit only
    ``total_reward``, so the comparison table showed ``null`` for real data.
    """
    enriched = dict(result)
    enriched["episode_reward"] = result.get("total_reward")

    patients = list(env.patients)
    assigned_ids = {int(a["stay_id"]) for a in env.assignments}
    high_risk_total = sum(1 for p in patients if float(p.sofa_total) >= HIGH_RISK_SOFA)
    high_risk_assigned = sum(
        1
        for p in patients
        if float(p.sofa_total) >= HIGH_RISK_SOFA and int(p.stay_id) in assigned_ids
    )
    enriched["high_risk_wait"] = max(high_risk_total - high_risk_assigned, 0)

    bed_by_id = {int(b.bed_id): b for b in env.beds}
    patient_by_id = {int(p.stay_id): p for p in patients}
    violations = 0
    for assignment in env.assignments:
        patient = patient_by_id.get(int(assignment["stay_id"]))
        bed = bed_by_id.get(int(assignment["bed_id"]))
        if patient is None or bed is None:
            continue
        if patient.needs_isolation and not bed.is_isolation:
            violations += 1
        if patient.needs_ventilator and not bed.has_ventilator:
            violations += 1
    enriched["constraint_violations"] = violations
    return enriched


def _cp_sat_canonical(evaluation: dict) -> dict:
    """Expose canonical H3 metric names on the CP-SAT evaluation block."""
    canonical = dict(evaluation)
    canonical.setdefault("high_risk_wait", canonical.get("high_risk_waiting"))
    # Isolation/ventilator needs are hard constraints in CP-SAT, so any
    # feasible assignment satisfies them by construction.
    canonical.setdefault("constraint_violations", 0)
    return canonical


def evaluate_ppo(model_path: str | None = None) -> dict:
    config = load_yaml("optimizer.yaml")
    ppo = config.get("ppo", {})
    seed = int(ppo.get("seed", 42))
    path = model_path or ppo.get("model_path", "artifacts/ppo_icu")

    ppo_env = build_icu_env()
    model = load_model(path, env=ppo_env)
    ppo_result = _enrich_policy_metrics(
        ppo_env, predict_assignments(model, ppo_env, seed=seed)
    )
    greedy_env = build_icu_env()
    greedy_result = _enrich_policy_metrics(
        greedy_env, evaluate_greedy(greedy_env, seed=seed)
    )
    cp_sat_result = run_assignment(run_id="evaluation_cp_sat")

    report = {
        "status": "ok",
        "note": "PPO/greedy share one episode; CP-SAT uses its configured candidate limit.",
        "ppo": ppo_result,
        "greedy": greedy_result,
        "cp_sat": {
            "assigned": cp_sat_result.get("assigned", 0),
            "n_stays": cp_sat_result.get("n_stays", 0),
            "evaluation": _cp_sat_canonical(cp_sat_result.get("evaluation", {})),
        },
    }
    report["comparison_table"] = flatten_comparison(report)
    output = Path("reports/ppo_evaluation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        report["flywheel_archive"] = archive_flywheel("ppo_eval", report)
    except OSError as exc:
        report["flywheel_archive_error"] = str(exc)
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate_ppo(), indent=2, ensure_ascii=False))
