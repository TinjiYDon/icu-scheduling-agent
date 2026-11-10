"""Persistence for the H=1 rolling scheduler.

The scheduler only needs three operations: start a run, append/replace one
step, and finalize the run.  JSONB keeps the decision snapshot auditable
without forcing every objective to a new relational column.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import text

from infra.db import get_engine


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


class PostgresRollingStore:
    """Store rolling runs/decisions in ``sched.rolling_runs``/``rolling_decisions``."""

    def start_run(self, run_id: str, config: Mapping[str, Any]) -> None:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO sched.rolling_runs (run_id, status, config)
                    VALUES (:run_id, 'running', CAST(:config AS JSONB))
                    ON CONFLICT (run_id) DO UPDATE
                    SET status = 'running',
                        config = EXCLUDED.config
                    """
                ),
                {"run_id": run_id, "config": _json(dict(config))},
            )

    def save_step(self, run_id: str, record: Mapping[str, Any]) -> None:
        engine = get_engine()
        payload = {
            "run_id": run_id,
            "step": int(record["step"]),
            "hour": int(record["hour"]),
            "status": str(record["status"]),
            "assignments": _json(record.get("assignments") or {}),
            "top_assignments": _json(record.get("top_assignments") or []),
            "waiting": _json(record.get("waiting") or []),
            "pending": _json(record.get("pending") or []),
            "discharged": _json(record.get("discharged") or []),
            "transferred": _json(record.get("transferred") or []),
            "warded": _json(record.get("warded") or []),
            "ward_census": int(record.get("ward_census") or 0),
            "arrivals": _json(record.get("arrivals") or []),
            "departed": _json(record.get("departed") or []),
            "patient_conservation": bool(record.get("patient_conservation")),
            "objective": _json(record.get("objective") or {}),
            "evaluation": _json(record.get("evaluation") or {}),
            "decision": _json(record.get("decision") or {}),
        }
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO sched.rolling_decisions (
                        run_id, step, hour, status, assignments, top_assignments,
                        waiting, pending, discharged, transferred, warded,
                        ward_census, arrivals, departed, patient_conservation,
                        objective, evaluation, decision
                    ) VALUES (
                        :run_id, :step, :hour, :status,
                        CAST(:assignments AS JSONB),
                        CAST(:top_assignments AS JSONB),
                        CAST(:waiting AS JSONB),
                        CAST(:pending AS JSONB),
                        CAST(:discharged AS JSONB),
                        CAST(:transferred AS JSONB),
                        CAST(:warded AS JSONB),
                        :ward_census,
                        CAST(:arrivals AS JSONB),
                        CAST(:departed AS JSONB),
                        :patient_conservation,
                        CAST(:objective AS JSONB),
                        CAST(:evaluation AS JSONB),
                        CAST(:decision AS JSONB)
                    )
                    ON CONFLICT (run_id, step) DO UPDATE SET
                        hour = EXCLUDED.hour,
                        status = EXCLUDED.status,
                        assignments = EXCLUDED.assignments,
                        top_assignments = EXCLUDED.top_assignments,
                        waiting = EXCLUDED.waiting,
                        pending = EXCLUDED.pending,
                        discharged = EXCLUDED.discharged,
                        transferred = EXCLUDED.transferred,
                        warded = EXCLUDED.warded,
                        ward_census = EXCLUDED.ward_census,
                        arrivals = EXCLUDED.arrivals,
                        departed = EXCLUDED.departed,
                        patient_conservation = EXCLUDED.patient_conservation,
                        objective = EXCLUDED.objective,
                        evaluation = EXCLUDED.evaluation,
                        decision = EXCLUDED.decision
                    """
                ),
                payload,
            )

    def finish_run(self, run_id: str, summary: Mapping[str, Any]) -> None:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE sched.rolling_runs
                    SET status = 'finished',
                        summary = CAST(:summary AS JSONB)
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id, "summary": _json(dict(summary))},
            )

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT run_id, status, config, summary, created_at
                    FROM sched.rolling_runs WHERE run_id = :run_id
                    """
                ),
                {"run_id": run_id},
            ).mappings().first()
        return dict(row) if row else None

    def load_steps(self, run_id: str) -> list[dict[str, Any]]:
        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT * FROM sched.rolling_decisions
                    WHERE run_id = :run_id ORDER BY step
                    """
                ),
                {"run_id": run_id},
            ).mappings().all()
        return [dict(row) for row in rows]
