"""Small, DB-free relative-time SOFA replay and per-decision Pareto scans.

This is a synthetic queue replay, not reconstruction of concurrent MIMIC stays
and not a look-ahead model. See docs/ROLLING_PARETO_MODEL.md.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from bisect import bisect_right
from collections.abc import Callable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from domain.optimizer.moo_phase3 import (
    DEFAULT_OBJECTIVES,
    ObjectivePoint,
    filter_nondominated,
    run_epsilon_grid_scan,
    run_payoff_table,
)
from domain.optimizer.resources import scale_bed_layout

FEASIBLE = {"OPTIMAL", "FEASIBLE"}
GRID_OBJECTIVES = ("overload", "zone_mismatch", "move")


def _score_index(payload: Mapping[str, Any]) -> dict[int, list[dict]]:
    index: dict[int, list[dict]] = {}
    seen: set[tuple[int, int]] = set()
    for raw in payload.get("scores", []):
        row = dict(raw)
        sid, hour = int(row["stay_id"]), int(row["hour_index"])
        if hour < 0 or (sid, hour) in seen:
            raise ValueError("SOFA times must be nonnegative and unique per stay")
        total = float(row["sofa_total"])
        if not math.isfinite(total) or not 0 <= total <= 24:
            raise ValueError("SOFA total must be finite and in [0, 24]")
        row.update(stay_id=sid, hour_index=hour, sofa_total=total)
        seen.add((sid, hour))
        index.setdefault(sid, []).append(row)
    for rows in index.values():
        rows.sort(key=lambda r: r["hour_index"])
    return index


def asof_score(rows: list[dict], clinical_hour: int) -> dict | None:
    """Latest already available score; never use a later endpoint."""
    pos = bisect_right([r["hour_index"] for r in rows], clinical_hour) - 1
    return rows[pos] if pos >= 0 else None


def _has_observation(score: Mapping[str, Any] | None) -> bool:
    if score is None:
        return False
    components = score.get("components") or {}
    return (
        any(v is not None for v in components.values())
        and len(score.get("missing_components") or []) < 6
    )


def _assignments(
    result: Mapping[str, Any], candidates: set[int], n_beds: int
) -> dict[int, int]:
    assignments: dict[int, int] = {}
    beds: set[int] = set()
    for row in result.get("top_assignments", []):
        sid, bed = int(row["stay_id"]), int(row["bed_id"])
        if (
            sid not in candidates
            or sid in assignments
            or bed in beds
            or not 1 <= bed <= n_beds
        ):
            raise RuntimeError(
                "Invalid assignment: candidate, capacity, or uniqueness violation"
            )
        assignments[sid] = bed
        beds.add(bed)
    if int(result.get("assigned", len(assignments))) != len(assignments):
        raise RuntimeError(
            "Solver assignments are truncated; complete bed map is required"
        )
    return assignments


def run_timed_pareto(
    payload: Mapping[str, Any],
    *,
    solve: Callable[..., dict] | None = None,
    sample_size: int = 50,
    n_beds: int = 20,
    n_steps: int = 12,
    step_hours: int = 2,
    warmup_hours: int = 24,
    seed: int = 42,
    initial_candidates: int | None = None,
    admission_rate: float = 0.05,
    discharge_rate: float = 0.05,
    levels: int = 2,
    occupancy_ratio: float = 0.9,
    max_time_seconds: float = 3.0,
    retain_occupied: bool = True,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Run t=0 initial fill plus at most twelve two-hour transitions.

    Execute the existing weighted baseline; compare its per-step alternatives
    with an epsilon scan, all sharing the exact same predecision state.
    """
    if sample_size < 1 or n_beds < 1 or not 0 <= n_steps <= 12:
        raise ValueError("Positive sample/beds and 0..12 transitions required")
    if step_hours != 2 or warmup_hours < 0 or levels < 2:
        raise ValueError("Use a 2h decision step, nonnegative warmup, and levels>=2")
    if not 0 <= occupancy_ratio <= 1 or not all(
        0 <= r <= 1 for r in (admission_rate, discharge_rate)
    ):
        raise ValueError("Occupancy and event rates must lie in [0,1]")
    if max_time_seconds <= 0:
        raise ValueError("max_time_seconds must be positive")
    score_index = _score_index(payload)
    stays = {int(row["stay_id"]): dict(row) for row in payload.get("stays", [])}
    eligible = sorted(
        sid
        for sid in stays
        if _has_observation(asof_score(score_index.get(sid, []), warmup_hours))
    )
    excluded = sorted(set(stays) - set(eligible))
    rng = random.Random(seed)
    selected = rng.sample(eligible, min(sample_size, len(eligible)))
    if not selected:
        raise ValueError("No stay has an observed SOFA component available at warmup")
    if initial_candidates is None:
        initial_candidates = min(len(selected), 2 * n_beds)
    if not 1 <= initial_candidates <= len(selected):
        raise ValueError("initial_candidates must be within the selected sample")
    waiting = set(selected[:initial_candidates])
    pending = list(selected[initial_candidates:])
    entry_hour = {sid: 0 for sid in waiting}
    occupied: dict[int, int] = {}
    discharged: set[int] = set()
    history: list[dict] = []
    if solve is None:
        from domain.optimizer.cp_sat import run_assignment

        solve = run_assignment

    resources = scale_bed_layout(n_beds)
    resources["max_patients"] = len(selected)
    for step in range(n_steps + 1):
        hour = step * step_hours
        previous = dict(occupied)
        departed: list[int] = []
        arrivals: list[int] = []
        if step:
            count = (
                min(len(occupied), max(1, int(len(occupied) * discharge_rate)))
                if discharge_rate
                else 0
            )
            departed = rng.sample(sorted(occupied), count)
            for sid in departed:
                del occupied[sid]
                discharged.add(sid)
            count = (
                min(len(pending), max(1, int(n_beds * admission_rate)))
                if admission_rate
                else 0
            )
            arrivals, pending = pending[:count], pending[count:]
            waiting.update(arrivals)
            entry_hour.update({sid: hour for sid in arrivals})

        predecision = dict(occupied)
        candidate_ids = sorted(waiting | set(occupied))
        candidate_rows: list[dict] = []
        score_refs: list[dict] = []
        for sid in candidate_ids:
            age = warmup_hours + hour - entry_hour[sid]
            score = asof_score(score_index[sid], age)
            if not _has_observation(score):
                raise ValueError(
                    f"stay {sid} has no observed SOFA at clinical hour {age}"
                )
            assert score is not None
            # Explicit legacy baseline, not a fitted predictor or LOS proxy.
            weight = round(1.0 + float(score["sofa_total"]) / 10.0, 4)
            candidate_rows.append(
                {
                    "stay_id": sid,
                    "priority_weight": weight,
                    "sofa_total": float(score["sofa_total"]),
                    "first_careunit": stays[sid].get("first_careunit") or "MICU",
                }
            )
            score_refs.append(
                {
                    "stay_id": sid,
                    "clinical_hour": age,
                    "score_hour": int(score["hour_index"]),
                    "score_age_hours": age - int(score["hour_index"]),
                    "sofa_total": float(score["sofa_total"]),
                    "components": deepcopy(score.get("components") or {}),
                    "missing_components": list(score.get("missing_components") or []),
                    "quality_flags": list(score.get("quality_flags") or []),
                }
            )

        if not candidate_ids:
            history.append(
                {
                    "step": step,
                    "hour": hour,
                    "status": "empty",
                    "predecision_beds": {},
                    "assignments": {},
                    "candidate_ids": [],
                    "arrivals": arrivals,
                    "discharged": departed,
                    "waiting": [],
                    "pending": list(pending),
                    "discharged_total": sorted(discharged),
                    "patient_conservation": True,
                    "f5_move": 0,
                    "common_patients": 0,
                    "churn": 0.0,
                    "similarity": 1.0,
                    "front": [],
                    "scores": [],
                    "objective_values": {},
                }
            )
            if progress:
                progress({"step": step, "hour": hour, "status": "empty", "occupied": 0})
            continue

        def invoke(
            *,
            _rows=candidate_rows,
            _previous=predecision,
            _allow_infeasible=False,
            **kwargs: Any,
        ) -> dict:
            kwargs.pop("persist", None)
            kwargs.pop("split", None)
            try:
                result = solve(
                    candidate_rows=deepcopy(_rows),
                    occupied_beds=dict(_previous),
                    persist=False,
                    split=None,
                    resource_overrides=deepcopy(resources),
                    max_time_seconds=max_time_seconds,
                    solver_seed=0,
                    retain_occupied=retain_occupied,
                    constraint_modes={"isolation": "none", "ventilator": "none"},
                    **kwargs,
                )
            except RuntimeError as exc:
                status = getattr(exc, "solver_status", None)
                if _allow_infeasible and status in {"INFEASIBLE", "UNKNOWN"}:
                    return {"solver_status": status, "multiobjective": {"values": {}}}
                raise
            status = result.get("solver_status")
            if status not in FEASIBLE:
                if _allow_infeasible:
                    return result
                raise RuntimeError(f"Reference/payoff solve failed: {status}")
            raw_values = (result.get("multiobjective") or {}).get("values") or {}
            if not all(name in raw_values for name in DEFAULT_OBJECTIVES):
                raise RuntimeError(
                    "Feasible solver result lacks one or more objective values"
                )
            amap = _assignments(result, {int(r["stay_id"]) for r in _rows}, n_beds)
            if retain_occupied and not set(_previous) <= set(amap):
                raise RuntimeError(
                    "Solver removed an incumbent despite retain_occupied=True"
                )
            moved = sum(
                bed != _previous[sid] for sid, bed in amap.items() if sid in _previous
            )
            if raw_values["move"] != moved:
                raise RuntimeError("Move value differs from predecision bed comparison")
            return result

        reference = invoke(objective_mode="weighted_sum")
        if reference.get("solver_status") not in FEASIBLE:
            raise RuntimeError(
                f"Weighted reference failed at step {step}: {reference.get('solver_status')}"
            )
        assignments = _assignments(reference, set(candidate_ids), n_beds)
        if retain_occupied and not set(predecision) <= set(assignments):
            raise RuntimeError(
                "Solver removed an incumbent despite retain_occupied=True"
            )
        payoff = run_payoff_table(invoke, split=None, persist=False)
        occupancy_floor = math.floor(
            occupancy_ratio * float(payoff["ideal"]["occupancy"])
        )
        scan_results: list[dict | None] = []

        def scan_solve(
            *,
            _floor=occupancy_floor,
            _results=scan_results,
            _invoke=invoke,
            **kwargs: Any,
        ) -> dict:
            bounds = dict(kwargs.get("epsilon_bounds") or {})
            bounds["occupancy"] = _floor
            kwargs["epsilon_bounds"] = bounds
            try:
                result = _invoke(_allow_infeasible=True, **kwargs)
            except Exception:
                _results.append(None)
                raise
            _results.append(result)
            return result

        scan = run_epsilon_grid_scan(
            scan_solve,
            payoff=payoff,
            primary="wait",
            grid_objectives=GRID_OBJECTIVES,
            levels=levels,
            split=None,
            persist=False,
        )
        # Keep complete assignments alongside vectors for audit/replay.
        points: list[ObjectivePoint] = []
        for row, result in zip(scan["points"], scan_results, strict=True):
            if row["status"] not in FEASIBLE or result is None:
                continue
            amap = _assignments(result, set(candidate_ids), n_beds)
            values = dict(row["values"])
            moved = sum(
                bed != predecision[sid]
                for sid, bed in amap.items()
                if sid in predecision
            )
            if values.get("move") != moved:
                raise RuntimeError(
                    "Pareto move value differs from predecision bed comparison"
                )
            points.append(
                ObjectivePoint(
                    values,
                    row["source"],
                    row["status"],
                    extras={
                        "assignments": amap,
                        "epsilon_bounds": {
                            **row["extras"]["epsilon_bounds"],
                            "occupancy": occupancy_floor,
                        },
                    },
                )
            )
        front = [point.as_dict() for point in filter_nondominated(points)]
        values = dict((reference.get("multiobjective") or {}).get("values") or {})
        common = set(predecision) & set(assignments)
        moved = sum(predecision[sid] != assignments[sid] for sid in common)
        if values.get("move") != moved:
            raise RuntimeError("Reference f5 does not match predecision bed comparison")
        churn = moved / len(common) if common else 0.0
        displaced = sorted(set(predecision) - set(assignments))
        # Future discharges mutate live state, never the saved decision map.
        occupied = dict(assignments)
        waiting = set(candidate_ids) - set(assignments)
        parts = [set(pending), waiting, set(occupied), discharged]
        conservation = set.union(*parts) == set(selected) and sum(
            map(len, parts)
        ) == len(selected)
        if not conservation:
            raise RuntimeError(
                "Patient state is not a disjoint partition of the sample"
            )
        history.append(
            {
                "step": step,
                "hour": hour,
                "status": str(reference["solver_status"]),
                "predecision_beds": predecision,
                "previous_assignments": previous,
                "assignments": assignments,
                "candidate_ids": candidate_ids,
                "scores": score_refs,
                "objective_values": values,
                "f5_move": moved,
                "common_patients": len(common),
                "churn": churn,
                "similarity": 1.0 - churn,
                "arrivals": arrivals,
                "discharged": departed,
                "displaced_to_waiting": displaced,
                "waiting": sorted(waiting),
                "pending": list(pending),
                "discharged_total": sorted(discharged),
                "patient_conservation": conservation,
                "occupancy_floor": occupancy_floor,
                "reference_meets_occupancy_floor": len(assignments) >= occupancy_floor,
                "selection_rule": "existing_weighted_sum_reference",
                "reference_details": {
                    "lambda": deepcopy(reference.get("lambda") or {}),
                    "objective_scaling": deepcopy(
                        reference.get("objective_scaling") or {}
                    ),
                    "multiobjective": deepcopy(reference.get("multiobjective") or {}),
                    "constraint_rules": deepcopy(
                        reference.get("constraint_rules") or {}
                    ),
                },
                "reference_on_sampled_front": any(p["values"] == values for p in front),
                "front": front,
                "payoff": payoff,
                "epsilon_scan": scan,
            }
        )
        if progress:
            progress(
                {
                    "step": step,
                    "hour": hour,
                    "status": str(reference["solver_status"]),
                    "occupied": len(assignments),
                    "f5_move": moved,
                    "n_front": len(front),
                    "patient_conservation": conservation,
                }
            )

    return {
        "status": "ok",
        "source": "synthetic_relative_time_replay",
        "input_config": deepcopy(payload.get("config") or {}),
        "config": {
            "seed": seed,
            "sample_size_requested": sample_size,
            "sample_size_actual": len(selected),
            "n_beds": n_beds,
            "resources": resources,
            "n_steps": n_steps,
            "step_hours": step_hours,
            "total_hours": n_steps * step_hours,
            "warmup_hours": warmup_hours,
            "initial_candidates": initial_candidates,
            "admission_rate": admission_rate,
            "discharge_rate": discharge_rate,
            "levels": levels,
            "grid_objectives": list(GRID_OBJECTIVES),
            "occupancy_ratio": occupancy_ratio,
            "retain_occupied": retain_occupied,
            "solver_seed": 0,
            "max_time_seconds": max_time_seconds,
            "constraint_modes": {"isolation": "none", "ventilator": "none"},
            "priority_formula": "1 + sofa_total / 10 (legacy baseline; collinear)",
            "selection_rule": "existing_weighted_sum_reference",
        },
        "sample_stay_ids": selected,
        "excluded_no_observed_warmup_score": excluded,
        "objective_names": list(DEFAULT_OBJECTIVES),
        "history": history,
        "limitations": [
            "Synthetic arrivals/discharges; not actual cross-patient concurrency",
            "Latest available SOFA is carried forward and its age is reported",
            "Executed policy is weighted reference; Pareto alternatives are recorded",
            "Missing SOFA components follow the explicitly recorded upstream policy",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Small SOFA relative-time rolling Pareto replay"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="reports/rolling/timed_pareto.json")
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--beds", type=int, default=20)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--warmup-hours", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--levels", type=int, default=2)
    parser.add_argument("--max-time", type=float, default=3.0)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = run_timed_pareto(
        payload,
        sample_size=args.sample_size,
        n_beds=args.beds,
        n_steps=args.steps,
        warmup_hours=args.warmup_hours,
        seed=args.seed,
        levels=args.levels,
        max_time_seconds=args.max_time,
        progress=lambda row: print(json.dumps(row), flush=True),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "path": str(output),
                "snapshots": len(report["history"]),
                "sample_size": report["config"]["sample_size_actual"],
            }
        )
    )


if __name__ == "__main__":
    main()
