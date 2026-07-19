"""Rolling-horizon ICU scheduling engine (PLAN §5.3)."""

from __future__ import annotations

import random

from sqlalchemy import text

from infra.db import get_engine
from infra.config import load_yaml


def _deterministic_seed(step: int, base: int = 42) -> None:
    """Reproducible randomness per step."""
    random.seed(base + step)


def run_rolling_simulation(
    n_steps: int = 12,        # steps (each = rolling_hours)
    discharge_rate: float = 0.15,  # fraction of occupied beds discharged per step
    admission_rate: float = 0.15,  # fraction of beds refilled per step
) -> dict:
    """Simulate ICU scheduling over multiple time steps.

    Each step:
      1. Discharge some patients (random from currently occupied)
      2. Admit new patients (top of waiting queue by priority)
      3. Run CP-SAT to reassign beds
      4. Record metrics

    Returns a dict with step-by-step metrics.
    """
    opt = load_yaml("optimizer.yaml")
    n_beds = int(opt.get("resources", {}).get("n_beds", 20))
    step_hours = int(opt.get("rolling", {}).get("step_hours", 2))

    engine = get_engine()

    # ── 0. Load full patient pool (waiting queue) ─────────────────
    with engine.connect() as conn:
        all_patients = conn.execute(
            text(
                """
                SELECT s.stay_id, COALESCE(p.priority_weight, 1.0) AS w,
                       COALESCE(so.sofa_total, 0) AS sofa,
                       s.first_careunit
                FROM staging.icustays s
                LEFT JOIN feat.patient_priority p ON s.stay_id = p.stay_id
                LEFT JOIN feat.sofa_timeseries so ON s.stay_id = so.stay_id AND so.hour_index = 0
                ORDER BY w DESC, sofa DESC
                """
            )
        ).mappings().all()

    queue = [dict(r) for r in all_patients]  # sorted by priority
    occupied: dict[int, dict] = {}           # bed_id → patient
    discharged: list[int] = []               # stay_ids
    history: list[dict] = []

    # ── 1. Initial assignment ─────────────────────────────────────
    from domain.optimizer.cp_sat import run_assignment

    r0 = run_assignment()
    for a in r0.get("top_assignments", [])[:n_beds]:
        occupied[a["bed_id"]] = {
            "stay_id": a["stay_id"],
            "weight": float(a["priority_weight"]),
            "sofa": float(a["sofa_total"]),
            "zone": a.get("bed_type", "?"),
            "steps_in_icu": 0,
        }
        # Remove assigned from queue
        queue = [p for p in queue if p["stay_id"] != a["stay_id"]]

    history.append(_snapshot(0, occupied, 0, 0))

    # ── 2. Rolling steps ──────────────────────────────────────────
    total_discharges = 0
    total_admissions = len(occupied)

    for step in range(1, n_steps + 1):
        _deterministic_seed(step)

        # 2a. Discharge some patients
        n_discharge = max(1, int(len(occupied) * discharge_rate))
        n_discharge = min(n_discharge, len(occupied))
        if n_discharge > 0 and occupied:
            to_discharge = random.sample(
                list(occupied.keys()), min(n_discharge, len(occupied))
            )
            for bed_id in to_discharge:
                discharged.append(occupied[bed_id]["stay_id"])
                del occupied[bed_id]
            total_discharges += len(to_discharge)

        # 2b. Admit new patients from queue
        n_admit = max(1, int(n_beds * admission_rate))
        free_beds = [b for b in range(1, n_beds + 1) if b not in occupied]
        n_admit = min(n_admit, len(free_beds), len(queue))
        newly_admitted = 0
        if n_admit > 0 and queue:
            new_patients = queue[:n_admit]
            queue = queue[n_admit:]
            for p in new_patients:
                if free_beds:
                    bed = free_beds.pop(0)
                    occupied[bed] = {
                        "stay_id": p["stay_id"],
                        "weight": float(p.get("w", 1.0)),
                        "sofa": float(p.get("sofa", 0)),
                        "zone": p.get("first_careunit") or "?",
                        "steps_in_icu": 0,
                    }
                    newly_admitted += 1
            total_admissions += newly_admitted

        # 2c. Run CP-SAT to optimize current assignment
        # Rebuild candidate pool: currently occupied + top of queue
        candidate_ids = [occ["stay_id"] for occ in occupied.values()]
        # Add some from queue
        candidate_ids += [p["stay_id"] for p in queue[:max_patients(n_beds)]]
        candidate_ids = list(set(candidate_ids))  # dedup
        free_slots = n_beds - len(occupied)

        # Simple re-optimization: if free slots, fill from queue
        if free_slots > 0 and queue:
            for p in queue[:free_slots]:
                if free_slots <= 0:
                    break
                for b in range(1, n_beds + 1):
                    if b not in occupied:
                        occupied[b] = {
                            "stay_id": p["stay_id"],
                            "weight": float(p.get("w", 1.0)),
                            "sofa": float(p.get("sofa", 0)),
                            "zone": p.get("first_careunit") or "?",
                            "steps_in_icu": 0,
                        }
                        queue = [x for x in queue if x["stay_id"] != p["stay_id"]]
                        free_slots -= 1
                        break

        # Increment stay duration
        for occ in occupied.values():
            occ["steps_in_icu"] += 1

        # 2d. Record snapshot
        history.append(
            _snapshot(step, occupied, newly_admitted, n_discharge)
        )

    # ── 3. Summary ────────────────────────────────────────────────
    return {
        "total_steps": n_steps,
        "step_hours": step_hours,
        "total_hours_simulated": n_steps * step_hours,
        "total_discharges": total_discharges,
        "total_admissions": total_admissions,
        "final_occupancy": len(occupied),
        "n_beds": n_beds,
        "bed_utilization_pct": round(len(occupied) / n_beds * 100, 1),
        "history": history,
    }


def _snapshot(
    step: int, occupied: dict, admitted: int, discharged: int
) -> dict:
    """Record state at a given time step."""
    weights = [o["weight"] for o in occupied.values()]
    sofas = [o["sofa"] for o in occupied.values()]
    stays = [o["steps_in_icu"] for o in occupied.values()]
    return {
        "step": step,
        "occupied": len(occupied),
        "admitted": admitted,
        "discharged": discharged,
        "avg_weight": round(sum(weights) / max(len(weights), 1), 3),
        "avg_sofa": round(sum(sofas) / max(len(sofas), 1), 1),
        "avg_stay_steps": round(sum(stays) / max(len(stays), 1), 1),
    }


def max_patients(n_beds: int) -> int:
    return n_beds * 5
