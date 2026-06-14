"""P0 ETL：Layer0 icustays → staging + feat.patient_priority 占位."""

from __future__ import annotations

from sqlalchemy import text

from data_access.mimic_repo import fetch_icustays
from infra.db import get_engine


def run_pipeline() -> dict:
    rows = fetch_icustays()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE staging.icustays"))
        conn.execute(text("TRUNCATE feat.patient_priority"))
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO staging.icustays (
                        stay_id, subject_id, hadm_id, first_careunit, last_careunit,
                        intime, outtime, los_hours
                    ) VALUES (
                        :stay_id, :subject_id, :hadm_id, :first_careunit, :last_careunit,
                        :intime, :outtime, :los_hours
                    )
                    """
                ),
                row,
            )
            los = row["los_hours"] or 1.0
            weight = round(1.0 / max(los, 0.5), 4)
            conn.execute(
                text(
                    """
                    INSERT INTO feat.patient_priority (stay_id, priority_weight)
                    VALUES (:stay_id, :priority_weight)
                    """
                ),
                {"stay_id": row["stay_id"], "priority_weight": weight},
            )
    return {
        "staging_icustays": len(rows),
        "feat_priority_rows": len(rows),
        "message": "staging + feat.patient_priority loaded from Layer0",
    }
