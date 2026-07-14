"""Generate synthetic SOFA scores for all stays (no MIMIC required).

Python computes hashes (fast), then bulk-inserts via psycopg.
Later replace with real MIMIC-based computation when Layer0 data is available.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import text

from infra.db import get_engine


def _sofa_sub(stay_id: int, seed: str, mod: int = 5) -> int:
    h = hashlib.md5(f"{stay_id}:{seed}".encode()).hexdigest()
    return int(h[:8], 16) % mod


def gen_synthetic_sofa() -> dict:
    engine = get_engine()

    # Read stay_ids
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT stay_id FROM staging.icustays ORDER BY stay_id")
        ).mappings().all()

    stays = [r["stay_id"] for r in rows]
    n = len(stays)
    print(f"Computing SOFA for {n} patients...")

    # Compute in Python (fast)
    sofa_rows = []
    priority_updates = []
    for sid in stays:
        total = (
            _sofa_sub(sid, "resp", 5)
            + _sofa_sub(sid, "coag", 5)
            + _sofa_sub(sid, "liver", 5)
            + _sofa_sub(sid, "cv", 4)
            + _sofa_sub(sid, "neuro", 5)
            + _sofa_sub(sid, "renal", 5)
        )
        sofa_rows.append({"stay_id": sid, "hour_index": 0, "sofa_total": float(total)})
        priority_updates.append(
            {"stay_id": sid, "priority_weight": round(1.0 + total / 10.0, 4)}
        )

    print(f"Writing {n} rows to DB...")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM feat.sofa_timeseries"))

        # Bulk insert SOFA
        conn.execute(
            text(
                "INSERT INTO feat.sofa_timeseries (stay_id, hour_index, sofa_total) "
                "VALUES (:stay_id, :hour_index, :sofa_total)"
            ),
            sofa_rows,
        )

        # Bulk upsert priority weights
        conn.execute(
            text(
                "INSERT INTO feat.patient_priority (stay_id, priority_weight) "
                "VALUES (:stay_id, :priority_weight) "
                "ON CONFLICT (stay_id) DO UPDATE SET priority_weight = EXCLUDED.priority_weight"
            ),
            priority_updates,
        )

    # Summary
    with engine.connect() as conn:
        dist = conn.execute(
            text(
                "SELECT FLOOR(sofa_total)::int as score, COUNT(*) as cnt "
                "FROM feat.sofa_timeseries GROUP BY 1 ORDER BY 1"
            )
        ).mappings().all()

    for d in dist:
        bar = "█" * min(d["cnt"] // 500, 60)
        print(f"  SOFA={d['score']:>2}: {d['cnt']:>6} {bar}")

    return {"sofa_rows": n, "distribution": [dict(d) for d in dist]}


