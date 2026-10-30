"""Rolling-horizon ICU scheduling engine (PLAN §5.3)."""

from __future__ import annotations

import math
import random

from sqlalchemy import text

from domain.optimizer.constraint_rules import needs_isolation, needs_ventilator
from domain.optimizer.resources import layout_covers_beds, scale_bed_layout
from infra.config import load_yaml
from infra.db import get_engine


def _turnover_count(capacity: int, rate: float) -> int:
    """Keep a positive-rate demo moving, while respecting an explicit zero."""
    return min(capacity, max(1, int(capacity * rate))) if capacity and rate > 0 else 0


def _occupant(patient: dict, zone: str, steps: int = 0) -> dict:
    return {
        "stay_id": int(patient["stay_id"]),
        "weight": float(patient.get("w", 1.0)),
        "sofa": float(patient.get("sofa", 0)),
        "zone": zone,
        "needs_iso": needs_isolation(patient.get("first_careunit")),
        "needs_vent": needs_ventilator(int(patient["stay_id"]), float(patient.get("sofa", 0))),
        "steps_in_icu": steps,
    }


def _checked_occupancy(
    assignments: list[dict], patients: dict[int, dict], previous: dict[int, dict],
    bed_zones: dict[int, str], n_iso: int, n_vents: int,
) -> dict[int, dict]:
    """Independently check solver output before applying a new bed state."""
    occupied: dict[int, dict] = {}
    seen: set[int] = set()
    previous_steps = {p["stay_id"]: p["steps_in_icu"] for p in previous.values()}
    for assignment in assignments:
        sid, bed_id = int(assignment["stay_id"]), int(assignment["bed_id"])
        if sid not in patients or sid in seen or bed_id in occupied or bed_id not in bed_zones:
            raise RuntimeError("invalid rolling assignment: unknown/duplicate patient or bed")
        patient = _occupant(patients[sid], bed_zones[bed_id], previous_steps.get(sid, 0))
        if patient["needs_iso"] and bed_id > n_iso:
            raise RuntimeError("invalid rolling assignment: isolation constraint violated")
        occupied[bed_id] = patient
        seen.add(sid)
    if sum(p["needs_vent"] for p in occupied.values()) > n_vents:
        raise RuntimeError("invalid rolling assignment: ventilator capacity exceeded")
    return occupied


def run_rolling_simulation(
    n_steps: int = 12,
    discharge_rate: float | None = None,
    admission_rate: float | None = None,
    *,
    reoptimize: bool = True,
    persist: bool = True,
    max_time_seconds: float | None = None,
    initial_assignments: list[dict] | None = None,
    retain_occupied: bool = True,
) -> dict:
    """Simulate ICU scheduling over multiple time steps.

    Each step:
      1. Discharge some patients (random from currently occupied)
      2. Admit up to the configured admission volume under hard constraints
      3. Re-run CP-SAT, or greedily fill legal free beds (H6 baseline)
      4. Record metrics

    When ``reoptimize=False`` (H6 static/greedy baseline): keep step-1
    CP-SAT initial fill, then only discharge + greedy admit into free beds
    — no per-step re-optimization. Same RNG seed schedule for fair contrast.

    Returns a dict with step-by-step metrics.

    ``initial_assignments`` reuses a validated starting allocation for paired
    experiments. In that case no initial solver call or sched write is made.
    Inpatients are retained until the discharge step. ``retain_occupied=False``
    is an explicit legacy research option that permits returning them to queue.
    """
    if isinstance(n_steps, bool) or not isinstance(n_steps, int) or n_steps < 0:
        raise ValueError("n_steps must be a non-negative integer")
    opt = load_yaml("optimizer.yaml")
    resources = dict(opt.get("resources") or {})
    n_beds = int(resources.get("n_beds", 20))
    if n_beds < 1:
        raise ValueError("n_beds must be positive")
    if not layout_covers_beds(resources.get("bed_zones") or [], n_beds):
        resources.update(scale_bed_layout(n_beds))
    n_iso = min(int(resources.get("n_isolation_beds", max(1, n_beds // 5))), n_beds)
    n_vents = int(resources.get("n_ventilators", max(1, round(n_beds * 8 / 20))))
    if n_iso < 0 or n_vents < 0:
        raise ValueError("isolation and ventilator capacities must be non-negative")
    rolling_cfg = opt.get("rolling", {}) or {}
    step_hours = int(rolling_cfg.get("step_hours", 2))
    if discharge_rate is None:
        discharge_rate = float(rolling_cfg.get("discharge_rate", 0.15))
    if admission_rate is None:
        admission_rate = float(rolling_cfg.get("admission_rate", 0.15))
    if step_hours < 1:
        raise ValueError("step_hours must be positive")
    for name, rate in (("discharge_rate", discharge_rate), ("admission_rate", admission_rate)):
        if not math.isfinite(rate) or not 0 <= rate <= 1:
            raise ValueError(f"{name} must be finite and between 0 and 1")

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
                ORDER BY w DESC, sofa DESC, s.stay_id
                """
            )
        ).mappings().all()

    queue = [dict(r) for r in all_patients]  # sorted by priority
    patients_by_id = {int(p["stay_id"]): p for p in queue}
    occupied: dict[int, dict] = {}           # bed_id → patient
    discharged: list[int] = []               # stay_ids
    history: list[dict] = []

    # ── 1. Initial assignment ─────────────────────────────────────
    from domain.optimizer.cp_sat import _resolve_bed_zones, run_assignment

    bed_zones, _, _ = _resolve_bed_zones(n_beds, resources.get("bed_zones"))
    r0 = (
        {"top_assignments": initial_assignments, "solver_status": "SHARED_INITIAL"}
        if initial_assignments is not None
        else run_assignment(
            persist=persist, resource_overrides=resources, max_time_seconds=max_time_seconds,
        )
    )
    occupied = _checked_occupancy(
        r0.get("top_assignments", []), patients_by_id, {}, bed_zones, n_iso, n_vents,
    )
    assigned_ids = {p["stay_id"] for p in occupied.values()}
    queue = [p for p in queue if p["stay_id"] not in assigned_ids]
    initial_occupancy = len(occupied)
    initial = _snapshot(0, occupied, initial_occupancy, 0)
    initial.update({"admitted_stay_ids": sorted(assigned_ids), "discharged_stay_ids": [],
                    "returned_to_queue_stay_ids": [], "waiting": len(queue),
                    "solver_status": r0.get("solver_status", r0.get("status"))})
    history.append(initial)

    # ── 2. Rolling steps ──────────────────────────────────────────
    total_discharges = 0
    total_admissions = len(occupied)
    total_returns = 0
    solver_failures = 0

    for step in range(1, n_steps + 1):
        rng = random.Random(42 + step)

        # 2a. Discharge some patients (fixed fraction per step)
        n_discharge = _turnover_count(len(occupied), discharge_rate)
        discharged_ids = []
        if n_discharge > 0 and occupied:
            to_discharge = rng.sample(sorted(occupied), n_discharge)
            for bed_id in to_discharge:
                discharged_ids.append(occupied[bed_id]["stay_id"])
                del occupied[bed_id]
            total_discharges += len(to_discharge)
            discharged.extend(discharged_ids)

        # 2b. Both policies see the same bounded priority shortlist and admission limit.
        n_admit = min(_turnover_count(n_beds, admission_rate), len(queue))
        shortlist = queue[:max_patients(n_beds)] if n_admit else []
        survivors = dict(occupied)
        survivor_ids = {p["stay_id"] for p in survivors.values()}
        solver_status = "GREEDY"
        if reoptimize:
            candidate_ids = sorted(survivor_ids) + [p["stay_id"] for p in shortlist]
            candidate_ids = list(dict.fromkeys(candidate_ids))  # dedup, keep order
            occupied_beds_map = {occ["stay_id"]: bed for bed, occ in occupied.items()}
            try:
                reopt = run_assignment(
                    stay_ids=candidate_ids, occupied_beds=occupied_beds_map,
                    max_new_admissions=n_admit, persist=False,
                    retain_occupied=retain_occupied,
                    resource_overrides=resources, max_time_seconds=max_time_seconds,
                )
            except RuntimeError as exc:
                if not str(exc).startswith("CP-SAT failed:"):
                    raise
                # No feasible solve was returned. Keep the last validated survivors.
                solver_status = "FALLBACK"
                solver_failures += 1
            else:
                occupied = _checked_occupancy(
                    reopt.get("top_assignments", []),
                    {sid: patients_by_id[sid] for sid in candidate_ids},
                    survivors, bed_zones, n_iso, n_vents,
                )
                if retain_occupied and not survivor_ids.issubset(
                    {p["stay_id"] for p in occupied.values()}
                ):
                    raise RuntimeError("invalid rolling assignment: current inpatient was removed")
                solver_status = reopt.get("solver_status", reopt.get("status"))
        else:
            free_beds = [bed for bed in bed_zones if bed not in occupied]
            vents_used = sum(p["needs_vent"] for p in occupied.values())
            admitted_count = 0
            for raw in shortlist:
                if admitted_count >= n_admit:
                    break
                patient = _occupant(raw, "")
                if patient["needs_vent"] and vents_used >= n_vents:
                    continue
                bed = next((b for b in free_beds if not patient["needs_iso"] or b <= n_iso), None)
                if bed is None:
                    continue
                patient["zone"] = bed_zones[bed]
                occupied[bed] = patient
                free_beds.remove(bed)
                vents_used += int(patient["needs_vent"])
                admitted_count += 1

        assigned_ids = {p["stay_id"] for p in occupied.values()}
        admitted_ids = sorted(assigned_ids - survivor_ids)
        returned_ids = sorted(survivor_ids - assigned_ids)
        if len(admitted_ids) > n_admit:
            raise RuntimeError("invalid rolling assignment: admission limit exceeded")
        # Put displaced patients back using their original clinical attributes.
        remaining = {p["stay_id"]: p for p in queue if p["stay_id"] not in assigned_ids}
        remaining.update({sid: patients_by_id[sid] for sid in returned_ids})
        queue = sorted(remaining.values(), key=lambda p: (-float(p["w"]), -float(p["sofa"]), int(p["stay_id"])))
        total_admissions += len(admitted_ids)
        total_returns += len(returned_ids)
        if len(queue) + len(occupied) + len(discharged) != len(patients_by_id):
            raise RuntimeError("rolling patient conservation failed")

        # Increment stay duration
        for occ in occupied.values():
            occ["steps_in_icu"] += 1

        # 2d. Record snapshot
        snapshot = _snapshot(step, occupied, len(admitted_ids), len(discharged_ids))
        snapshot.update({"admitted_stay_ids": admitted_ids, "discharged_stay_ids": discharged_ids,
                         "returned_to_queue_stay_ids": returned_ids, "waiting": len(queue),
                         "solver_status": solver_status})
        history.append(snapshot)

    # ── 3. Summary ────────────────────────────────────────────────
    return {
        "total_steps": n_steps,
        "step_hours": step_hours,
        "total_hours_simulated": n_steps * step_hours,
        "total_discharges": total_discharges,
        "total_admissions": total_admissions,
        "initial_occupancy": initial_occupancy,
        "total_returns_to_queue": total_returns,
        "solver_failures": solver_failures,
        "final_occupancy": len(occupied),
        "n_beds": n_beds,
        "bed_utilization_pct": round(len(occupied) / n_beds * 100, 1),
        "reoptimize": bool(reoptimize),
        "policy": "rolling_cp_sat" if reoptimize else "greedy_admit_only",
        "retain_occupied": retain_occupied,
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
        "assignments": [{"bed_id": bed, **p} for bed, p in sorted(occupied.items())],
        # Solver output and greedy admissions are checked before this snapshot.
        "constraint_violation": False,
    }


def max_patients(n_beds: int) -> int:
    return n_beds * 5
