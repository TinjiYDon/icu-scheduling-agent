"""In-repo predict-then-optimize: GBDT priority (+ optional LOS) → feat.patient_priority.

Does NOT read icu-decision-agent risk scores.
Uses staging/feat SOFA and careunit features available in this repo.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sqlalchemy import text

from infra.db import get_engine

ARTIFACT = Path("artifacts/models/priority_gbdt.json")


def _load_training_frame(conn) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT s.stay_id,
                   COALESCE(so.sofa_total, 0) AS sofa_total,
                   COALESCE(s.first_careunit, '') AS first_careunit,
                   COALESCE(s.los_hours, 0) AS los_hours
            FROM staging.icustays s
            LEFT JOIN feat.sofa_timeseries so
              ON s.stay_id = so.stay_id AND so.hour_index = 0
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def _careunit_code(name: str, vocab: dict[str, int]) -> int:
    if name not in vocab:
        vocab[name] = len(vocab)
    return vocab[name]


def _fit_gbdt(X: np.ndarray, y: np.ndarray):
    try:
        import lightgbm as lgb

        model = lgb.LGBMRegressor(
            n_estimators=80,
            learning_rate=0.08,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
        )
        model.fit(X, y)
        return ("lightgbm", model)
    except Exception:
        from sklearn.ensemble import GradientBoostingRegressor

        model = GradientBoostingRegressor(random_state=42)
        model.fit(X, y)
        return ("sklearn_gbr", model)


def build_priority_from_gbdt(*, use_los_feature: bool = True) -> dict:
    """Train GBDT to map in-repo severity features → priority_weight and upsert.

    Target construction (predict-then-optimize friendly, no external risk):
      urgency = 1 + sofa/10 + 2 / (1 + max(los_hours, 1))
    so shorter expected stay + higher SOFA → higher priority.
    The model learns a smoothed mapping; inference writes feat.patient_priority.
    """
    engine = get_engine()
    with engine.connect() as conn:
        rows = _load_training_frame(conn)
    if not rows:
        return {"status": "empty", "n": 0}

    vocab: dict[str, int] = {}
    X_list = []
    y_list = []
    stay_ids = []
    for r in rows:
        sofa = float(r["sofa_total"] or 0.0)
        los = float(r["los_hours"] or 0.0)
        cu = _careunit_code(str(r["first_careunit"] or ""), vocab)
        feats = [sofa, float(cu)]
        if use_los_feature:
            feats.append(los)
        X_list.append(feats)
        # Constructed supervision signal (in-repo only)
        y_list.append(1.0 + sofa / 10.0 + 2.0 / (1.0 + max(los, 1.0)))
        stay_ids.append(int(r["stay_id"]))

    X = np.asarray(X_list, dtype=np.float64)
    y = np.asarray(y_list, dtype=np.float64)
    backend, model = _fit_gbdt(X, y)
    pred = np.asarray(model.predict(X), dtype=np.float64)
    pred = np.clip(pred, 1.0, 5.0)

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "backend": backend,
        "n": len(stay_ids),
        "feature_names": ["sofa_total", "careunit_code"]
        + (["los_hours"] if use_los_feature else []),
        "careunit_vocab": vocab,
        "y_mean": float(y.mean()),
        "pred_mean": float(pred.mean()),
    }
    ARTIFACT.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    with engine.begin() as conn:
        for sid, w in zip(stay_ids, pred, strict=True):
            conn.execute(
                text(
                    """
                    INSERT INTO feat.patient_priority (stay_id, priority_weight)
                    VALUES (:stay_id, :w)
                    ON CONFLICT (stay_id) DO UPDATE
                    SET priority_weight = EXCLUDED.priority_weight
                    """
                ),
                {"stay_id": int(sid), "w": float(round(w, 4))},
            )

    return {
        "status": "ok",
        "backend": backend,
        "n": len(stay_ids),
        "pred_mean": float(pred.mean()),
        "artifact": str(ARTIFACT).replace("\\", "/"),
    }


def estimate_arrival_intensity() -> dict:
    """Empirical admission/discharge-ish rates from staging LOS distribution.

    Maps mean LOS to a soft refill rate for rolling simulation defaults.
    """
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS n,
                       AVG(NULLIF(los_hours, 0)) AS mean_los,
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY los_hours)
                         FILTER (WHERE los_hours > 0) AS median_los
                FROM staging.icustays
                """
            )
        ).mappings().one()
    mean_los = float(row["mean_los"] or 72.0)
    # Expected fraction of beds turning over per 2h step ≈ step / mean_los
    step_hours = 2.0
    rate = float(np.clip(step_hours / max(mean_los, 1.0), 0.05, 0.35))
    return {
        "n_stays": int(row["n"] or 0),
        "mean_los_hours": mean_los,
        "median_los_hours": float(row["median_los"] or mean_los),
        "suggested_admission_rate": round(rate, 4),
        "suggested_discharge_rate": round(rate, 4),
        "step_hours": step_hours,
    }
