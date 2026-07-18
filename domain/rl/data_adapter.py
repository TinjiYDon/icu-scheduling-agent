"""Convert repository/config state into PPO environment inputs."""

from __future__ import annotations

from sqlalchemy import text

from domain.optimizer.cp_sat import _careunit_zone, _needs_ventilator, _zone_label
from domain.rl.env import Bed, Patient
from infra.config import load_yaml
from infra.db import get_engine


def load_patients(limit: int | None = None) -> list[Patient]:
    config = load_yaml("optimizer.yaml")
    max_patients = limit or int(config.get("ppo", {}).get("candidate_patients", 20))
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT s.stay_id,
                       COALESCE(p.priority_weight, 1.0) AS priority_weight,
                       COALESCE(so.sofa_total, 0) AS sofa_total,
                       s.first_careunit
                FROM staging.icustays s
                LEFT JOIN feat.patient_priority p ON p.stay_id = s.stay_id
                LEFT JOIN feat.sofa_timeseries so
                  ON so.stay_id = s.stay_id AND so.hour_index = 0
                ORDER BY priority_weight DESC, sofa_total DESC, s.stay_id
                LIMIT :limit
                """
            ),
            {"limit": max_patients},
        ).mappings().all()
    return [patient_from_row(dict(row)) for row in rows]


def patient_from_row(row: dict) -> Patient:
    careunit = row.get("first_careunit") or ""
    lower_careunit = careunit.lower()
    return Patient(
        stay_id=int(row["stay_id"]),
        priority_weight=float(row.get("priority_weight", 1.0)),
        sofa_total=float(row.get("sofa_total", 0.0)),
        preferred_zone=_zone_label(_careunit_zone(careunit)),
        needs_isolation=any(
            keyword in lower_careunit for keyword in ("micu", "sicu", "cvicu", "nsicu")
        ),
        needs_ventilator=_needs_ventilator(int(row["stay_id"])),
    )


def load_beds() -> list[Bed]:
    config = load_yaml("optimizer.yaml")
    resources = config.get("resources", {})
    n_beds = int(resources.get("n_beds", 20))
    zones = resources.get("bed_zones", [[1, n_beds, "REG"]])
    zone_by_id = {
        bed_id: str(label)
        for start, count, label in zones
        for bed_id in range(int(start), int(start) + int(count))
    }
    return [
        Bed(
            bed_id=bed_id,
            zone=zone_by_id.get(bed_id, "REG"),
            is_isolation=zone_by_id.get(bed_id) == "ISO",
            # CP-SAT treats ventilators as a global portable resource.  Every
            # bed is compatible; ICUEnv separately enforces global capacity.
            has_ventilator=True,
        )
        for bed_id in range(1, n_beds + 1)
    ]
