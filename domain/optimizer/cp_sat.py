"""CP-SAT bed assignment (P0 snapshot)."""

from __future__ import annotations

import uuid

from ortools.sat.python import cp_model
from sqlalchemy import text

from infra.config import load_yaml
from infra.db import get_engine


def run_assignment(run_id: str | None = None) -> dict:
    opt = load_yaml("optimizer.yaml")
    n_beds = int(opt.get("resources", {}).get("n_beds", 20))
    run_id = run_id or f"p0_{uuid.uuid4().hex[:8]}"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT s.stay_id, COALESCE(p.priority_weight, 1.0) AS priority_weight,
                       COALESCE(so.sofa_total, 0) AS sofa_total
                FROM staging.icustays s
                LEFT JOIN feat.patient_priority p ON s.stay_id = p.stay_id
                LEFT JOIN feat.sofa_timeseries so ON s.stay_id = so.stay_id AND so.hour_index = 0
                ORDER BY priority_weight DESC, sofa_total DESC
                """
            )
        ).mappings().all()
    stays = [dict(r) for r in rows]
    n_stays = len(stays)
    if n_stays == 0:
        return {"run_id": run_id, "assigned": 0, "n_beds": n_beds}

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for si in range(n_stays):
        for bi in range(n_beds):
            x[si, bi] = model.NewBoolVar(f"x_{si}_{bi}")

    for bi in range(n_beds):
        model.Add(sum(x[si, bi] for si in range(n_stays)) <= 1)
    for si in range(n_stays):
        model.Add(sum(x[si, bi] for bi in range(n_beds)) <= 1)

    weights = [int(float(s["priority_weight"]) * 1000) for s in stays]
    model.Maximize(sum(weights[si] * x[si, bi] for si in range(n_stays) for bi in range(n_beds)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT failed: status={status}")

    assigned = 0
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sched.assignments WHERE run_id = :run_id"), {"run_id": run_id})
        for si, stay in enumerate(stays):
            for bi in range(n_beds):
                if solver.Value(x[si, bi]) == 1:
                    assigned += 1
                    conn.execute(
                        text(
                            """
                            INSERT INTO sched.assignments (run_id, stay_id, bed_id)
                            VALUES (:run_id, :stay_id, :bed_id)
                            """
                        ),
                        {"run_id": run_id, "stay_id": stay["stay_id"], "bed_id": bi + 1},
                    )
    return {
        "run_id": run_id,
        "assigned": assigned,
        "n_beds": n_beds,
        "n_stays": n_stays,
        "solver_status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
    }
