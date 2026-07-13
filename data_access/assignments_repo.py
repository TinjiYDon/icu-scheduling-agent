"""Read sched.assignments for L4 plan API."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from infra.db import get_engine


def latest_run_id() -> str | None:
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT run_id FROM sched.assignments ORDER BY created_at DESC NULLS LAST LIMIT 1")
        ).scalar()


def run_exists(run_id: str) -> bool:
    engine = get_engine()
    with engine.connect() as conn:
        n = conn.execute(
            text("SELECT COUNT(*) FROM sched.assignments WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).scalar_one()
    return int(n) > 0


def fetch_assignments(run_id: str) -> list[dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as conn:
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
    return [dict(r) for r in rows]
