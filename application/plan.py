"""L4 API: fetch bed assignment plan from latest simulation run."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from application.simulate import run_simulate
from infra.db import get_engine


def get_plan(run_id: str | None = None) -> dict[str, Any]:
    """Return assignment rows and summary metrics for a simulation run."""
    engine = get_engine()
    with engine.connect() as conn:
        if run_id is None:
            run_id = conn.execute(
                text("SELECT run_id FROM sched.assignments ORDER BY created_at DESC NULLS LAST LIMIT 1")
            ).scalar()
        if not run_id:
            return {"run_id": None, "assignments": [], "metrics": {"assigned": 0}, "status": "empty"}

        rows = conn.execute(
            text(
                """
                SELECT a.stay_id, a.bed_id,
                       COALESCE(so.sofa_total, 0) AS sofa_total,
                       COALESCE(p.priority_weight, 1.0) AS priority_weight
                FROM sched.assignments a
                LEFT JOIN feat.sofa_timeseries so ON a.stay_id = so.stay_id AND so.hour_index = 0
                LEFT JOIN feat.patient_priority p ON a.stay_id = p.stay_id
                WHERE a.run_id = :run_id
                ORDER BY a.bed_id
                """
            ),
            {"run_id": run_id},
        ).mappings().all()

    assignments = [dict(r) for r in rows]
    return {
        "run_id": run_id,
        "assignments": assignments,
        "metrics": {
            "assigned": len(assignments),
            "beds_used": len({a["bed_id"] for a in assignments}),
        },
        "status": "ok",
    }


def run_simulation_with_plan() -> dict[str, Any]:
    """L4: SOFA + CP-SAT then return plan JSON for Streamlit."""
    sim = run_simulate()
    plan = get_plan(sim.get("run_id"))
    return {"simulate": sim, "plan": plan, "status": "ok"}
