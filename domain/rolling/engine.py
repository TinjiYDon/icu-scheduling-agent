"""H=1 online rolling scheduler.

The scheduler is intentionally a thin state machine around the existing CP-SAT
assignment model:

1. apply discharges/arrivals;
2. build a time-specific candidate snapshot from the current state;
3. solve one assignment with ``previous_beds`` and ``retain_occupied``;
4. commit only the current step's decisions;
5. persist the decision when a store is supplied.

It does not use random bed filling: every admission in the ICU bed pool is the
output of the solver.  The loop can be run without a database by passing a
patient list and a ``solve`` callable (used by the tests).
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sqlalchemy import text

from domain.optimizer.cp_sat import AssignmentSolveError, run_assignment
from infra.config import load_yaml
from infra.db import get_engine

FEASIBLE = {"OPTIMAL", "FEASIBLE"}


def _load_patients() -> list[dict]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT s.stay_id,
                       COALESCE(p.priority_weight, 1.0) AS priority_weight,
                       COALESCE(so.sofa_total, 0) AS sofa_total,
                       s.first_careunit
                FROM staging.icustays s
                LEFT JOIN feat.patient_priority p ON s.stay_id = p.stay_id
                LEFT JOIN feat.sofa_timeseries so
                       ON s.stay_id = so.stay_id AND so.hour_index = 0
                ORDER BY priority_weight DESC, sofa_total DESC, s.stay_id
                """
            )
        ).mappings().all()
    return [_normalise_row(dict(row)) for row in rows]


def _normalise_row(row: Mapping[str, Any]) -> dict:
    raw_sid = row.get("stay_id")
    try:
        sid = int(raw_sid)
        priority = float(row.get("priority_weight", row.get("w", 1.0)))
        sofa = float(row.get("sofa_total", row.get("sofa", 0.0)))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("patients need numeric stay_id, priority and sofa") from exc
    if sid <= 0:
        raise ValueError("patients need positive stay_id")
    careunit = row.get("first_careunit") or ""
    if not isinstance(careunit, str):
        raise ValueError("patients first_careunit must be a string or None")
    return {
        "stay_id": sid,
        "priority_weight": priority,
        "sofa_total": sofa,
        "first_careunit": careunit,
    }


def _normalise_patients(patients: Sequence[Mapping[str, Any]]) -> list[dict]:
    rows = [_normalise_row(row) for row in patients]
    if len({row["stay_id"] for row in rows}) != len(rows):
        raise ValueError("patients must have unique stay_id")
    return sorted(
        rows,
        key=lambda row: (-row["priority_weight"], -row["sofa_total"], row["stay_id"]),
    )


def _row_for_assignment(patient: Mapping[str, Any]) -> dict:
    return {
        "stay_id": int(patient["stay_id"]),
        "priority_weight": float(patient["priority_weight"]),
        "sofa_total": float(patient["sofa_total"]),
        "first_careunit": patient.get("first_careunit") or "",
    }


def _decision_view(result: Mapping[str, Any]) -> dict:
    """Keep the part of the solve result that the plan/explain layer consumes."""
    return {
        "run_id": result.get("run_id"),
        "solver_status": result.get("solver_status"),
        "assigned": result.get("assigned", 0),
        "n_stays": result.get("n_stays", 0),
        "n_beds": result.get("n_beds", 0),
        "objective": result.get("objective", {}),
        "evaluation": result.get("evaluation", {}),
        "resources": result.get("resources", {}),
        "top_assignments": list(result.get("top_assignments") or []),
        "ward_patients": list(result.get("ward_patients") or []),
        "transferred": list(result.get("transferred") or []),
    }


def run_rolling_simulation(
    n_steps: int = 12,
    discharge_rate: float | None = None,
    admission_rate: float | None = None,
    *,
    patients: Sequence[Mapping[str, Any]] | None = None,
    solve: Callable[..., dict] | None = None,
    store: Any | None = None,
    run_id: str | None = None,
    seed: int = 42,
    initial_candidates: int | None = None,
    max_moves: int | None = None,
    max_time_seconds: float = 30.0,
    resource_overrides: Mapping[str, Any] | None = None,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Run an H=1 rolling loop and commit one decision per step.

    Args:
        n_steps: number of transitions; history has ``n_steps + 1`` snapshots.
        patients: optional pre-loaded rows; when omitted, rows are loaded from
            the configured PostgreSQL staging/feat tables.
        solve: optional CP-SAT-compatible callable; defaults to
            ``run_assignment``.  It must accept ``candidate_rows``,
            ``previous_beds``, ``retain_occupied``, ``persist=False`` and
            ``resource_overrides``.
        store: optional object with ``start_run(run_id, config)``,
            ``save_step(run_id, record)`` and ``finish_run(run_id, summary)``.
        resource_overrides: per-run bed/ward resources, merged over config.

    The solver is called once per snapshot with a snapshot-specific candidate
    list.  A patient is admitted only if that solve places them, so this is a
    true re-optimization loop rather than the old "fill free beds in order"
    simulation.
    """
    if n_steps < 0:
        raise ValueError("n_steps must be nonnegative")
    if seed < 0:
        raise ValueError("seed must be nonnegative")
    if max_moves is not None and max_moves < 0:
        raise ValueError("max_moves must be nonnegative")
    if max_time_seconds <= 0:
        raise ValueError("max_time_seconds must be positive")

    opt = load_yaml("optimizer.yaml")
    rolling_cfg = opt.get("rolling", {}) or {}
    step_hours = int(rolling_cfg.get("step_hours", 2))
    if discharge_rate is None:
        discharge_rate = float(rolling_cfg.get("discharge_rate", 0.05))
    if admission_rate is None:
        admission_rate = float(rolling_cfg.get("admission_rate", 0.05))
    if not 0 <= discharge_rate <= 1 or not 0 <= admission_rate <= 1:
        raise ValueError("discharge/admission rates must lie in [0,1]")

    resources = dict(opt.get("resources", {}))
    resources.update(resource_overrides or {})
    n_beds = int(resources.get("n_beds", 20))
    if n_beds < 1:
        raise ValueError("n_beds must be positive")

    rows = (
        _normalise_patients(patients)
        if patients is not None
        else _load_patients()
    )
    if not rows:
        raise ValueError("no patients available for rolling")
    by_id = {int(row["stay_id"]): row for row in rows}
    all_ids = set(by_id)

    if initial_candidates is None:
        initial_candidates = min(len(rows), 2 * n_beds)
    initial_candidates = max(1, min(int(initial_candidates), len(rows)))
    waiting = set(int(row["stay_id"]) for row in rows[:initial_candidates])
    pending = [int(row["stay_id"]) for row in rows[initial_candidates:]]
    occupied: dict[int, int] = {}  # bed_id -> stay_id
    discharged: set[int] = set()
    transferred: set[int] = set()
    warded: set[int] = set()
    ever_admitted: set[int] = set()
    solve = solve or run_assignment
    run_id = run_id or f"roll_{uuid.uuid4().hex[:8]}"
    rng = random.Random(seed)
    history: list[dict] = []
    config = {
        "n_beds": n_beds,
        "n_steps": n_steps,
        "step_hours": step_hours,
        "seed": seed,
        "initial_candidates": initial_candidates,
        "admission_rate": admission_rate,
        "discharge_rate": discharge_rate,
        "max_moves": max_moves,
        "max_time_seconds": max_time_seconds,
        "resources": resources,
        "solver": "cp_sat",
    }
    if store is not None:
        store.start_run(run_id, config)

    for step in range(n_steps + 1):
        hour = step * step_hours
        departed: list[int] = []
        arrivals: list[int] = []
        if step:
            if discharge_rate > 0 and occupied:
                count = min(
                    len(occupied),
                    max(1, int(len(occupied) * discharge_rate)),
                )
                departed = rng.sample(sorted(occupied.values()), count)
                for sid in departed:
                    for bed, occupant in list(occupied.items()):
                        if occupant == sid:
                            del occupied[bed]
                            break
                    discharged.add(sid)
            if admission_rate > 0 and pending:
                count = min(len(pending), max(1, int(n_beds * admission_rate)))
                arrivals = pending[:count]
                pending = pending[count:]
                waiting.update(arrivals)

        candidate_ids = sorted(waiting | set(occupied.values()))
        if not candidate_ids:
            record = {
                "run_id": run_id,
                "step": step,
                "hour": hour,
                "status": "empty",
                "occupied": 0,
                "admitted": 0,
                "discharged_count": 0,
                "assignments": {},
                "top_assignments": [],
                "waiting": [],
                "pending": list(pending),
                "discharged": sorted(discharged),
                "transferred": sorted(transferred),
                "warded": sorted(warded),
                "ward_census": len(warded),
                "patient_conservation": True,
                "objective": {},
                "evaluation": {},
                "decision": {},
            }
            history.append(record)
            if store is not None:
                store.save_step(run_id, record)
            if progress:
                progress({"step": step, "hour": hour, "status": "empty"})
            continue

        candidate_rows = [_row_for_assignment(by_id[sid]) for sid in candidate_ids]
        previous_beds = {sid: bed for bed, sid in occupied.items()}
        try:
            result = solve(
                candidate_rows=candidate_rows,
                previous_beds=previous_beds,
                retain_occupied=True,
                persist=False,
                resource_overrides=resources,
                max_moves=max_moves,
                solver_seed=0,
                max_time_seconds=max_time_seconds,
                ward_occupancy=len(warded),
            )
        except AssignmentSolveError as exc:
            raise RuntimeError(f"rolling solve failed: {exc.solver_status}") from exc
        status = str(result.get("solver_status"))
        if status not in FEASIBLE:
            raise RuntimeError(f"rolling solve failed: {status}")

        bed_map = {
            int(a["stay_id"]): int(a["bed_id"])
            for a in result.get("top_assignments", [])
        }
        if len(set(bed_map.values())) != len(bed_map):
            raise RuntimeError("solver returned duplicate bed assignments")
        if any(not 1 <= bed <= n_beds for bed in bed_map.values()):
            raise RuntimeError("solver returned a bed outside the configured range")
        stepped_down = {int(sid) for sid in (result.get("transferred") or [])}
        ward_step = {int(sid) for sid in (result.get("ward_patients") or [])}
        if not (set(bed_map) | stepped_down | ward_step) <= set(candidate_ids):
            raise RuntimeError("solver returned a patient outside the candidate set")
        if not set(previous_beds) <= (set(bed_map) | stepped_down | ward_step):
            raise RuntimeError("solver dropped an incumbent without a disposition")

        occupied = {bed: sid for sid, bed in bed_map.items()}
        waiting = set(candidate_ids) - set(bed_map) - stepped_down - ward_step
        transferred |= stepped_down
        warded |= ward_step
        ever_admitted |= set(bed_map)

        parts = [
            set(pending),
            waiting,
            set(occupied.values()),
            discharged,
            transferred,
            warded,
        ]
        conservation = set.union(*parts) == all_ids and sum(
            map(len, parts)
        ) == len(all_ids)
        if not conservation:
            raise RuntimeError("patient state is not a disjoint partition")

        decision = _decision_view(result)
        record = {
            "run_id": run_id,
            "step": step,
            "hour": hour,
            "status": status,
            "occupied": len(occupied),
            "admitted": len(arrivals),
            "discharged_count": len(departed),
            "assignments": dict(bed_map),
            "top_assignments": decision["top_assignments"],
            "waiting": sorted(waiting),
            "pending": list(pending),
            "discharged": sorted(discharged),
            "transferred": sorted(transferred),
            "warded": sorted(warded),
            "ward_census": len(warded),
            "arrivals": arrivals,
            "departed": departed,
            "patient_conservation": conservation,
            "objective": decision["objective"],
            "evaluation": decision["evaluation"],
            "decision": decision,
        }
        history.append(record)
        if store is not None:
            store.save_step(run_id, record)
        if progress:
            progress(
                {
                    "step": step,
                    "hour": hour,
                    "status": status,
                    "occupied": len(occupied),
                    "waiting": len(waiting),
                    "patient_conservation": conservation,
                }
            )

    total_admissions = len(ever_admitted)
    summary = {
        "run_id": run_id,
        "status": "ok",
        "total_steps": n_steps,
        "step_hours": step_hours,
        "total_hours_simulated": n_steps * step_hours,
        "total_discharges": len(discharged),
        "total_admissions": total_admissions,
        "total_served": len(ever_admitted | warded),
        "final_occupancy": len(occupied),
        "final_waiting": len(waiting),
        "n_beds": n_beds,
        "n_patients": len(rows),
        "bed_utilization_pct": round(len(occupied) / n_beds * 100, 1),
        "history": history,
        "config": config,
    }
    if store is not None:
        store.finish_run(run_id, {k: v for k, v in summary.items() if k != "history"})
    return summary


def max_patients(n_beds: int) -> int:
    return n_beds * 5
