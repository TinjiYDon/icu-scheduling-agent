"""Simplified SOFA from first-24h labs (P0 Demo)."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from infra.config import get_data_source, get_layer0_dsn
from infra.db import get_engine


def _score_creatinine(v: float | None) -> int:
    if v is None:
        return 0
    if v >= 5.0:
        return 4
    if v >= 3.5:
        return 3
    if v >= 2.0:
        return 2
    if v >= 1.2:
        return 1
    return 0


def _score_bilirubin(v: float | None) -> int:
    if v is None:
        return 0
    if v >= 12.0:
        return 4
    if v >= 6.0:
        return 3
    if v >= 2.0:
        return 2
    if v >= 1.2:
        return 1
    return 0


def _score_platelet(v: float | None) -> int:
    if v is None:
        return 0
    if v < 20:
        return 4
    if v < 50:
        return 3
    if v < 100:
        return 2
    if v < 150:
        return 1
    return 0


def _fetch_lab_scores() -> list[dict]:
    source = get_data_source()
    if source == "mock":
        return [
            {"stay_id": 1, "creatinine": 2.5, "bilirubin": 1.0, "platelet": 120.0},
            {"stay_id": 2, "creatinine": 0.9, "bilirubin": 0.8, "platelet": 200.0},
        ]
    dsn = get_layer0_dsn()
    if not dsn:
        raise RuntimeError("layer0 DSN not configured")
    engine = create_engine(dsn, pool_pre_ping=True)
    sql = """
        SELECT i.stay_id,
               MAX(CASE WHEN l.itemid IN (50912, 52546) THEN l.valuenum END) AS creatinine,
               MAX(CASE WHEN l.itemid = 50885 THEN l.valuenum END) AS bilirubin,
               MIN(CASE WHEN l.itemid IN (51265, 51277, 53157) THEN l.valuenum END) AS platelet
        FROM mimiciv_icu.icustays i
        LEFT JOIN mimiciv_hosp.labevents l
          ON l.subject_id = i.subject_id AND l.hadm_id = i.hadm_id
         AND l.charttime >= i.intime
         AND l.charttime <= i.intime + interval '24 hours'
         AND l.valuenum IS NOT NULL
        GROUP BY i.stay_id
        ORDER BY i.stay_id
    """
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql)).mappings().all()]


def compute_sofa_timeseries() -> dict:
    rows = _fetch_lab_scores()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE feat.sofa_timeseries"))
        for row in rows:
            renal = _score_creatinine(row.get("creatinine"))
            liver = _score_bilirubin(row.get("bilirubin"))
            coag = _score_platelet(row.get("platelet"))
            total = float(renal + liver + coag)
            conn.execute(
                text(
                    """
                    INSERT INTO feat.sofa_timeseries (stay_id, hour_index, sofa_total)
                    VALUES (:stay_id, 0, :sofa_total)
                    """
                ),
                {"stay_id": row["stay_id"], "sofa_total": total},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO feat.patient_priority (stay_id, priority_weight)
                    VALUES (:stay_id, :w)
                    ON CONFLICT (stay_id) DO UPDATE SET priority_weight = EXCLUDED.priority_weight
                    """
                ),
                {"stay_id": row["stay_id"], "w": round(1.0 + total / 10.0, 4)},
            )
    return {"sofa_rows": len(rows)}
