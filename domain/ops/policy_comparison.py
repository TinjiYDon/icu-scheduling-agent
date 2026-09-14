"""Flatten multi-policy evaluation payloads into an H3 comparison table."""

from __future__ import annotations

from typing import Any


def _rate(assigned: Any, n: Any) -> float | None:
    try:
        a = float(assigned)
        total = float(n)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return a / total


def flatten_comparison(report: dict[str, Any]) -> dict[str, Any]:
    """Build a policy × metric table for答辩对照 (H3)."""
    ppo = report.get("ppo") or {}
    greedy = report.get("greedy") or {}
    cp = report.get("cp_sat") or {}
    cp_eval = cp.get("evaluation") or {}

    rows = [
        {
            "policy": "ppo",
            "assigned": ppo.get("assigned"),
            "n_stays": ppo.get("n_stays") or ppo.get("n"),
            "assignment_rate": _rate(ppo.get("assigned"), ppo.get("n_stays") or ppo.get("n")),
            "episode_reward": ppo.get("episode_reward") or ppo.get("reward"),
            "high_risk_wait": ppo.get("high_risk_wait") or ppo.get("high_urgency_wait"),
            "constraint_violations": ppo.get("constraint_violations"),
        },
        {
            "policy": "greedy",
            "assigned": greedy.get("assigned"),
            "n_stays": greedy.get("n_stays") or greedy.get("n"),
            "assignment_rate": _rate(
                greedy.get("assigned"), greedy.get("n_stays") or greedy.get("n")
            ),
            "episode_reward": greedy.get("episode_reward") or greedy.get("reward"),
            "high_risk_wait": greedy.get("high_risk_wait") or greedy.get("high_urgency_wait"),
            "constraint_violations": greedy.get("constraint_violations"),
        },
        {
            "policy": "cp_sat",
            "assigned": cp.get("assigned"),
            "n_stays": cp.get("n_stays"),
            "assignment_rate": _rate(cp.get("assigned"), cp.get("n_stays")),
            "episode_reward": None,
            "high_risk_wait": cp_eval.get("high_risk_wait") or cp_eval.get("mean_wait"),
            "constraint_violations": cp_eval.get("constraint_violations"),
            "evaluation": {k: cp_eval.get(k) for k in sorted(cp_eval)[:12]} if cp_eval else {},
        },
    ]
    return {
        "status": "ok",
        "primary_metrics": ["assignment_rate", "high_risk_wait", "constraint_violations"],
        "h3_note": (
            "Same candidate pool where possible; no trajectory protocol ⇒ "
            "do not claim online MIMIC-PPO."
        ),
        "note": report.get("note"),
        "rows": rows,
    }
