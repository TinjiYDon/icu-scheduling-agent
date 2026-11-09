"""Small, DB-free relative-time SOFA replay and per-decision Pareto scans.

This is a synthetic queue replay, not reconstruction of concurrent MIMIC stays
and not a look-ahead model. See ROLLING_PARETO_MODEL.md.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from bisect import bisect_right
from collections.abc import Callable, Mapping
from copy import deepcopy
from itertools import product
from pathlib import Path
from typing import Any

from domain.optimizer.cp_sat import AssignmentSolveError, run_assignment
from domain.optimizer.objectives import OBJECTIVES
from domain.optimizer.pareto import objective_vector, solve_anchors
from infra.config import load_yaml

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


def _replay_resources(configured: Mapping[str, Any], n_beds: int) -> dict:
    """Keep the archive layout, scaling cumulative zone boundaries for small demos."""
    base_beds = int(configured["n_beds"])
    if n_beds == base_beds:
        return deepcopy(dict(configured))
    result = dict(configured)
    zones = []
    for start, count, name in configured["bed_zones"]:
        lo = round((int(start) - 1) * n_beds / base_beds)
        hi = round((int(start) - 1 + int(count)) * n_beds / base_beds)
        if hi > lo:
            zones.append([lo + 1, hi - lo, name])
    result.update(
        n_beds=n_beds,
        n_isolation_beds=round(
            int(configured["n_isolation_beds"]) * n_beds / base_beds
        ),
        n_ventilators=round(int(configured["n_ventilators"]) * n_beds / base_beds),
        bed_zones=zones,
    )
    return result


def _epsilon_grid(
    payoff: Mapping[str, Any],
    levels: int,
    *,
    move_levels: int | None = None,
) -> list[dict[str, int]]:
    """Build the epsilon grid for one decision step.

    Default mode sweeps all of ``GRID_OBJECTIVES`` with the same ``levels``.
    ``move_levels`` switches to a dense 1-D scan on ``move``: only the occupancy
    floor and the f5 cap are constrained, so f5 is the single swept quantity.

    The other two axes are deliberately *omitted* rather than pinned at their
    practical ideal.  Pinning ``zone_mismatch`` at its ideal value turns a soft
    objective into a hard "every patient in its preferred zone" constraint,
    which caps occupancy and makes the sweep measure the wrong thing.

    Note that f5 is bounded by the bed count, not by the candidate pool, so a
    small q already saturates the reachable resolution.
    """
    floor = payoff["guard"]["occupancy_min"]
    if move_levels is not None:
        if move_levels < 2:
            raise ValueError("move_levels must be >= 2")
        best = payoff["practical_ideal"]["move"]
        worst = payoff["practical_nadir"]["move"]
        cap_values = sorted(
            {
                math.ceil(best + j * (worst - best) / (move_levels - 1))
                for j in range(move_levels)
            }
        )
        return [{"occupancy": floor, "move": cap} for cap in cap_values]

    axes = []
    for name in GRID_OBJECTIVES:
        best = payoff["practical_ideal"][name]
        worst = payoff["practical_nadir"][name]
        # All scan axes are minimized; round upper bounds outward.
        axes.append(
            sorted(
                {
                    math.ceil(best + j * (worst - best) / (levels - 1))
                    for j in range(levels)
                }
            )
        )
    return [
        {"occupancy": floor, **dict(zip(GRID_OBJECTIVES, bounds, strict=True))}
        for bounds in product(*axes)
    ]


def _dominates(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    return left != right and all(
        (
            left[name] >= right[name]
            if spec.sense == "max"
            else left[name] <= right[name]
        )
        for name, spec in OBJECTIVES.items()
    )


def _front(points: list[dict]) -> list[dict]:
    unique: dict[tuple, dict] = {}
    for point in points:
        if point["status"] in FEASIBLE:
            unique.setdefault(tuple(point["values"].values()), point)
    return [
        point
        for point in unique.values()
        if not any(
            _dominates(other["values"], point["values"]) for other in unique.values()
        )
    ]


def run_timed_pareto(
    payload: Mapping[str, Any],
    *,
    solve: Callable[..., dict] | None = None,
    sample_size: int = 50,
    n_beds: int | None = None,
    n_steps: int = 12,
    step_hours: int = 2,
    warmup_hours: int = 24,
    seed: int = 42,
    initial_candidates: int | None = None,
    admission_rate: float = 0.05,
    discharge_rate: float = 0.05,
    levels: int = 2,
    move_levels: int | None = None,
    occupancy_ratio: float = 0.9,
    max_time_seconds: float = 3.0,
    retain_occupied: bool = True,
    sofa_transfer_max: float | None = None,
    min_icu_hours: int = 24,
    max_transfers: int | None = None,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Run t=0 initial fill plus at most twelve two-hour transitions.

    Execute the existing weighted baseline; compare its per-step alternatives
    with an epsilon scan, all sharing the exact same predecision state.
    """
    config = load_yaml("optimizer.yaml")
    configured = config["resources"]
    if n_beds is None:
        n_beds = int(configured["n_beds"])
    if sample_size < 1 or n_beds < 1 or not 0 <= n_steps <= 12:
        raise ValueError("Positive sample/beds and 0..12 transitions required")
    if step_hours != 2 or warmup_hours < 0 or levels < 2:
        raise ValueError("Use a 2h decision step, nonnegative warmup, and levels>=2")
    if move_levels is not None and move_levels < 2:
        raise ValueError("move_levels must be >= 2 when provided")
    if min_icu_hours < 0:
        raise ValueError("min_icu_hours must be nonnegative")
    if max_transfers is not None and max_transfers < 0:
        raise ValueError("max_transfers must be nonnegative")
    if not 0 <= occupancy_ratio <= 1 or not all(
        0 <= r <= 1 for r in (admission_rate, discharge_rate)
    ):
        raise ValueError("Occupancy and event rates must lie in [0,1]")
    if not math.isfinite(max_time_seconds) or max_time_seconds <= 0:
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
    transferred_total: set[int] = set()
    history: list[dict] = []
    solve = solve or run_assignment
    resources = _replay_resources(configured, n_beds)
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
                    "first_careunit": stays[sid].get("first_careunit") or "",
                }
            )
            score_refs.append(
                {
                    "stay_id": sid,
                    "clinical_hour": age,
                    "score_hour": int(score["hour_index"]),
                    "score_age_hours": age - int(score["hour_index"]),
                    "sofa_total": float(score["sofa_total"]),
                    "priority_weight": weight,
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
                    "previous_assignments": previous,
                    "assignments": {},
                    "candidate_ids": [],
                    "arrivals": arrivals,
                    "discharged": departed,
                    "displaced_to_waiting": [],
                    "waiting": [],
                    "pending": list(pending),
                    "discharged_total": sorted(discharged),
                    "transferred": [],
                    "transferred_total": sorted(transferred_total),
                    "eligible_for_transfer": [],
                    "n_eligible_transfer": 0,
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

        # Transfer-out eligibility: a clinical gate over as-of scores only, so no
        # future information enters.  The transfer itself is a decision variable.
        sofa_now = {ref["stay_id"]: float(ref["sofa_total"]) for ref in score_refs}
        age_now = {ref["stay_id"]: int(ref["clinical_hour"]) for ref in score_refs}
        if sofa_transfer_max is None:
            eligible_transfer: list[int] = []
        else:
            eligible_transfer = sorted(
                sid
                for sid in predecision
                if sofa_now.get(sid) is not None
                and sofa_now[sid] <= float(sofa_transfer_max)
                and age_now.get(sid, 0) >= int(min_icu_hours)
            )

        def invoke(
            *,
            _rows=candidate_rows,
            _previous=predecision,
            _transferable=tuple(eligible_transfer),
            **kwargs: Any,
        ) -> dict:
            kwargs.pop("persist", None)
            result = solve(
                candidate_rows=deepcopy(_rows),
                previous_beds=dict(_previous),
                persist=False,
                resource_overrides=deepcopy(resources),
                max_time_seconds=max_time_seconds,
                solver_seed=0,
                retain_occupied=retain_occupied,
                transferable=list(_transferable),
                max_transfers=max_transfers,
                **kwargs,
            )
            if result.get("solver_status") not in FEASIBLE:
                return result
            values = objective_vector(result)
            amap = _assignments(result, {r["stay_id"] for r in _rows}, n_beds)
            stepped_down = {int(sid) for sid in (result.get("transferred") or [])}
            if not stepped_down <= set(_transferable):
                raise RuntimeError(
                    "Solver transferred a patient outside the eligible set"
                )
            if not stepped_down <= set(_previous):
                raise RuntimeError("Solver transferred a non-incumbent")
            if retain_occupied and not set(_previous) <= (set(amap) | stepped_down):
                raise RuntimeError(
                    "Solver dropped an incumbent without transferring it out"
                )
            moved = sum(
                bed != _previous[sid] for sid, bed in amap.items() if sid in _previous
            )
            if values["move"] != moved or values["occupancy"] != len(amap):
                raise RuntimeError(
                    "Move/occupancy objectives differ from assigned bed maps"
                )
            return result

        def require_solution(*, _invoke=invoke, **kwargs: Any) -> dict:
            try:
                result = _invoke(**kwargs)
            except AssignmentSolveError as exc:
                raise RuntimeError(
                    f"Reference/payoff solve failed: {exc.solver_status}"
                ) from exc
            if result.get("solver_status") not in FEASIBLE:
                raise RuntimeError(
                    f"Reference/payoff solve failed: {result.get('solver_status')}"
                )
            return result

        reference = require_solution()
        assignments = _assignments(reference, set(candidate_ids), n_beds)
        values = objective_vector(reference)
        payoff = solve_anchors(
            practical_guard_ratio=occupancy_ratio, solve=require_solution
        )
        # Anchor run IDs are ephemeral and do not affect this replay.
        payoff.pop("run_id")
        occupancy_floor = payoff["guard"]["occupancy_min"]
        grid = _epsilon_grid(payoff, levels, move_levels=move_levels)
        points = []
        for idx, bounds in enumerate(grid, start=1):
            try:
                result = invoke(pivot="wait", epsilon=bounds)
                status = str(result.get("solver_status"))
            except AssignmentSolveError as exc:
                result = {}
                status = exc.solver_status
            point = {
                "source": f"epsilon:{idx}",
                "status": status,
                "values": {},
                "extras": {"epsilon_bounds": bounds},
            }
            if status in FEASIBLE:
                point_values = objective_vector(result)
                if any(
                    point_values[name] < bound
                    if OBJECTIVES[name].sense == "max"
                    else point_values[name] > bound
                    for name, bound in bounds.items()
                ):
                    raise RuntimeError(
                        "Solver returned an assignment outside its epsilon bounds"
                    )
                point["values"] = point_values
                point["extras"]["assignments"] = _assignments(
                    result, set(candidate_ids), n_beds
                )
            points.append(point)
        front = _front(points)
        scan = {
            "primary": "wait",
            "grid_objectives": list(GRID_OBJECTIVES),
            "levels": levels,
            "move_levels": move_levels,
            "n_grid": len(grid),
            "n_feasible": sum(p["status"] in FEASIBLE for p in points),
            "n_nondominated": len(front),
            "grid": grid,
            "points": points,
        }
        common = set(predecision) & set(assignments)
        moved = sum(predecision[sid] != assignments[sid] for sid in common)
        if values.get("move") != moved:
            raise RuntimeError("Reference f5 does not match predecision bed comparison")
        churn = moved / len(common) if common else 0.0
        stepped_down = {int(sid) for sid in (reference.get("transferred") or [])}
        transferred_total |= stepped_down
        displaced = sorted(set(predecision) - set(assignments) - stepped_down)
        # Future discharges mutate live state, never the saved decision map.
        occupied = dict(assignments)
        waiting = set(candidate_ids) - set(assignments) - stepped_down
        parts = [
            set(pending),
            waiting,
            set(occupied),
            transferred_total,
            discharged,
        ]
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
                "transferred": sorted(stepped_down),
                "transferred_total": sorted(transferred_total),
                "eligible_for_transfer": eligible_transfer,
                "n_eligible_transfer": len(eligible_transfer),
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
                    "objective_mode": reference.get("objective_mode"),
                    "active_objectives": deepcopy(
                        reference.get("active_objectives") or []
                    ),
                    "priority_mode": reference.get("priority_mode"),
                    "wait_source": reference.get("wait_source"),
                    "isolation_mode": reference.get("isolation_mode"),
                    "vent_mode": reference.get("vent_mode"),
                    "n_iso_required": reference.get("n_iso_required"),
                    "n_vent_required": reference.get("n_vent_required"),
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
            "move_levels": move_levels,
            "grid_objectives": list(GRID_OBJECTIVES),
            "occupancy_ratio": occupancy_ratio,
            "retain_occupied": retain_occupied,
            "sofa_transfer_max": sofa_transfer_max,
            "min_icu_hours": min_icu_hours,
            "max_transfers": max_transfers,
            "solver_seed": 0,
            "max_time_seconds": max_time_seconds,
            "constraint_modes": {
                "isolation": config.get("isolation", {}).get("mode", "none"),
                "ventilator": config.get("vent", {}).get("mode", "none"),
            },
            "priority_formula": "1 + sofa_total / 10 (legacy baseline; collinear)",
            "selection_rule": "existing_weighted_sum_reference",
        },
        "sample_stay_ids": selected,
        "excluded_no_observed_warmup_score": excluded,
        "objective_names": list(OBJECTIVES),
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
    parser.add_argument("--beds", type=int, help="override configured ward size")
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--warmup-hours", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--levels", type=int, default=2)
    parser.add_argument(
        "--move-levels",
        type=int,
        default=None,
        help="dense 1-D scan on move (f5); pins the other epsilon axes at their "
        "practical ideal to trace the stability-yield curve",
    )
    parser.add_argument("--max-time", type=float, default=3.0)
    parser.add_argument(
        "--sofa-transfer-max",
        type=float,
        default=None,
        help="enable transfer-out decisions: incumbents whose latest available "
        "SOFA is <= this threshold become eligible (default: disabled)",
    )
    parser.add_argument(
        "--min-icu-hours",
        type=int,
        default=24,
        help="minimum clinical ICU hours before a patient may be transferred out",
    )
    parser.add_argument(
        "--max-transfers",
        type=int,
        default=None,
        help="hard cap on transfers per step; a constraint, not an objective",
    )
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
        move_levels=args.move_levels,
        max_time_seconds=args.max_time,
        sofa_transfer_max=args.sofa_transfer_max,
        min_icu_hours=args.min_icu_hours,
        max_transfers=args.max_transfers,
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
