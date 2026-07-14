"""L4 API: fetch bed assignment plan from latest simulation run."""

from __future__ import annotations

from typing import Any

from application.simulate import run_simulate
from data_access.assignments_repo import fetch_assignments, latest_run_id, run_exists


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
        metrics.update(
            {
                "n_stays": sim_metrics.get("n_stays"),
                "n_beds": sim_metrics.get("n_beds"),
                "solver_status": sim_metrics.get("solver_status"),
                "unassigned": max(
                    int(sim_metrics.get("n_stays", 0)) - int(sim_metrics.get("assigned", 0)),
                    0,
                ),
            }
        )
    return {
        "run_id": run_id,
        "assignments": assignments,
        "metrics": metrics,
        "status": "ok",
    }


def run_simulation_with_plan() -> dict[str, Any]:
    """L4: SOFA + CP-SAT then return plan JSON for Streamlit."""
    sim = run_simulate()
    plan = get_plan(sim.get("run_id"), sim_metrics=sim)
    return {"simulate": sim, "plan": plan, "status": "ok"}
