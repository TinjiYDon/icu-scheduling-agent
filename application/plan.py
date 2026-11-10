"""L4 API: fetch an assignment plan from the rolling decision history."""

from __future__ import annotations

from typing import Any

from application.simulate import run_simulate
from data_access.assignments_repo import fetch_assignments, latest_run_id, run_exists
from domain.optimizer.explain import explain_assignment


def get_plan(run_id: str | None = None, sim_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return assignment rows and summary metrics for a persisted run."""
    if run_id is None:
        run_id = latest_run_id()
    if not run_id:
        return {"run_id": None, "assignments": [], "metrics": {"assigned": 0}, "status": "empty"}

    if not run_exists(run_id):
        return {
            "run_id": run_id,
            "assignments": [],
            "metrics": {"assigned": 0},
            "status": "not_found",
        }

    assignments = fetch_assignments(run_id)
    metrics = {
        "assigned": len(assignments),
        "beds_used": len({a["bed_id"] for a in assignments}),
    }
    if sim_metrics:
        ev = sim_metrics.get("evaluation") or {}
        metrics.update(
            {
                "n_stays": sim_metrics.get("n_stays"),
                "n_beds": sim_metrics.get("n_beds"),
                "solver_status": sim_metrics.get("solver_status"),
                "n_candidates": sim_metrics.get("n_candidates") or sim_metrics.get("n_stays"),
                "unassigned": max(
                    int(sim_metrics.get("n_stays", 0)) - int(sim_metrics.get("assigned", 0)),
                    0,
                ),
                "high_risk_assigned_rate": ev.get("high_risk_assigned_rate"),
                "zone_match_rate": ev.get("zone_match_rate"),
                "assignment_rate": ev.get("assignment_rate"),
                "solve_time_seconds": ev.get("solve_time_seconds"),
                "objective": sim_metrics.get("objective"),
                "resources": sim_metrics.get("resources"),
            }
        )
    return {
        "run_id": run_id,
        "assignments": assignments,
        "metrics": metrics,
        "status": "ok",
    }


def run_simulation_with_plan(n_steps: int = 12) -> dict[str, Any]:
    """Run the H=1 rolling scheduler and return the last committed plan."""
    rolling = run_simulate(n_steps=int(n_steps))
    history = rolling.get("history") or []
    last = history[-1] if history else {}
    decision = last.get("decision") or {}
    evaluation = decision.get("evaluation") or {}
    assignments = list(decision.get("top_assignments") or [])
    plan = {
        "run_id": rolling.get("run_id"),
        "step": last.get("step"),
        "hour": last.get("hour"),
        "assignments": assignments,
        "metrics": {
            "assigned": decision.get("assigned", 0),
            "beds_used": len({a["bed_id"] for a in assignments}),
            "n_stays": decision.get("n_stays"),
            "n_beds": decision.get("n_beds"),
            "solver_status": decision.get("solver_status"),
            "unassigned": max(
                int(decision.get("n_stays", 0)) - int(decision.get("assigned", 0)),
                0,
            ),
            "assignment_rate": evaluation.get("assignment_rate"),
            "zone_match_rate": evaluation.get("zone_match_rate"),
            "objective": decision.get("objective"),
            "resources": decision.get("resources"),
        },
        "status": "ok" if decision else "empty",
    }
    plan["explain"] = explain_assignment(decision) if decision else ""
    simulate = {
        **rolling,
        "run_id": rolling.get("run_id"),
        "solver_status": decision.get("solver_status"),
        "assigned": decision.get("assigned"),
        "n_stays": decision.get("n_stays"),
        "n_beds": decision.get("n_beds"),
        "n_candidates": decision.get("n_stays"),
        "evaluation": evaluation,
        "objective": decision.get("objective"),
        "resources": decision.get("resources"),
    }
    try:
        from infra.mlflow_util import log_run

        rid = log_run(
            "icu-scheduling",
            "simulate_with_plan",
            {
                "n_steps": n_steps,
                "solver_status": simulate.get("solver_status"),
                "n_beds": simulate.get("n_beds"),
            },
            {
                "final_occupancy": float(rolling.get("final_occupancy") or 0),
                "bed_utilization_pct": float(rolling.get("bed_utilization_pct") or 0),
                "total_admissions": float(rolling.get("total_admissions") or 0),
                "total_discharges": float(rolling.get("total_discharges") or 0),
                "assigned": float(decision.get("assigned") or 0),
                "high_risk_assigned_rate": float(
                    evaluation.get("high_risk_assigned_rate") or 0
                ),
                "zone_match_rate": float(evaluation.get("zone_match_rate") or 0),
            },
        )
        if rid:
            simulate["mlflow_run_id"] = rid
    except Exception as exc:  # noqa: BLE001
        simulate["mlflow_error"] = str(exc)
    return {"simulate": simulate, "plan": plan, "assign": decision, "status": "ok"}
