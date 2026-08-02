"""L4 API: fetch bed assignment plan from latest simulation run."""

from __future__ import annotations

from typing import Any

from application.simulate import run_simulate
from data_access.assignments_repo import fetch_assignments, latest_run_id, run_exists
from domain.optimizer.cp_sat import run_assignment
from domain.optimizer.explain import explain_assignment


def get_plan(run_id: str | None = None, sim_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return assignment rows and summary metrics for a simulation run."""
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
    """L4: CP-SAT assignment + rolling occupancy, for Streamlit / MCP."""
    assign = run_assignment()
    rolling = run_simulate(n_steps=int(n_steps))
    plan = get_plan(assign.get("run_id"), sim_metrics=assign)
    # Prefer rich solver rows for demo table (zone_match / bed_type).
    if assign.get("top_assignments"):
        plan["assignments"] = list(assign["top_assignments"])
    plan["explain"] = explain_assignment(assign)
    ev = assign.get("evaluation") or {}
    simulate = {
        **rolling,
        "run_id": assign.get("run_id"),
        "solver_status": assign.get("solver_status"),
        "assigned": assign.get("assigned"),
        "n_stays": assign.get("n_stays"),
        "n_beds": assign.get("n_beds"),
        "n_candidates": assign.get("n_stays"),
        "evaluation": ev,
        "objective": assign.get("objective"),
        "resources": assign.get("resources"),
        "high_risk_assigned_rate": ev.get("high_risk_assigned_rate"),
        "zone_match_rate": ev.get("zone_match_rate"),
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
                "assigned": float(assign.get("assigned") or 0),
                "high_risk_assigned_rate": float(ev.get("high_risk_assigned_rate") or 0),
                "zone_match_rate": float(ev.get("zone_match_rate") or 0),
            },
        )
        if rid:
            simulate["mlflow_run_id"] = rid
    except Exception as exc:  # noqa: BLE001
        simulate["mlflow_error"] = str(exc)
    return {"simulate": simulate, "plan": plan, "assign": assign, "status": "ok"}
