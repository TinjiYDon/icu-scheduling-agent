"""Objective registry for the CP-SAT bed-assignment model.

Each objective is built exactly once per model and exposed as a linear
expression.  The registry makes three workflows possible without duplicating
modelling code:

* weighted-sum scalarization (default, backwards compatible);
* anchor solves that optimize a single objective (P3);
* epsilon-constraint scans that turn the remaining objectives into bounds (P4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from ortools.sat.python import cp_model


def zone_label(zone_idx: int) -> str:
    """Map a preferred-zone index to its label."""
    return ["UNK", "MICU", "SICU", "CCU", "NICU"][zone_idx] if 0 <= zone_idx <= 4 else "UNK"


@dataclass
class ModelContext:
    """Everything the objective builders need, assembled once by the caller."""

    n: int
    n_beds: int
    n_iso_beds: int
    weights: Sequence[int]
    sofa_vals: Sequence[int]
    regular_beds: Sequence[int]
    iso_flags: Sequence[bool]
    iso_active: bool
    patient_zones: Sequence[int]
    bed_zone_start: Mapping[str, int]
    bed_zone_count: Mapping[str, int]
    zone_specs: Sequence[tuple[str, Sequence[int]]]
    prev_bed: Mapping[int, int]
    stay_ids: Sequence[int]
    zone_load_vars: list = field(default_factory=list)


@dataclass(frozen=True)
class ObjectiveSpec:
    name: str
    sense: str  # "max" | "min"
    bound: Callable[[ModelContext], int]
    build: Callable[[cp_model.CpModel, Mapping[tuple[int, int], cp_model.IntVar], ModelContext], object]


def _occupancy(model, x, ctx: ModelContext):
    return sum(x[i, b] for i in range(ctx.n) for b in range(ctx.n_beds))


def _wait(model, x, ctx: ModelContext):
    return sum(ctx.weights[i] * x[i, b] for i in range(ctx.n) for b in range(ctx.n_beds))


def _overload(model, x, ctx: ModelContext):
    return sum(ctx.sofa_vals[i] * x[i, b] for i in range(ctx.n) for b in ctx.regular_beds)


def _balance(model, x, ctx: ModelContext):
    loads = []
    for z_idx, (label, bed_ids) in enumerate(ctx.zone_specs):
        zl = model.NewIntVar(0, len(bed_ids), f"zone_load_{z_idx}_{label}")
        model.Add(zl == sum(x[i, b] for i in range(ctx.n) for b in bed_ids))
        loads.append(zl)
    ctx.zone_load_vars = loads

    if len(loads) >= 2:
        zone_max = model.NewIntVar(0, ctx.n_beds, "zone_max_load")
        zone_min = model.NewIntVar(0, ctx.n_beds, "zone_min_load")
        for zl in loads:
            model.Add(zone_max >= zl)
            model.Add(zone_min <= zl)
        load_range = model.NewIntVar(0, ctx.n_beds, "zone_load_range")
        model.Add(load_range == zone_max - zone_min)
    else:
        load_range = model.NewIntVar(0, 0, "zone_load_range")
        model.Add(load_range == 0)
    return load_range


def _zone_mismatch(model, x, ctx: ModelContext):
    penalty = model.NewIntVar(0, ctx.n_beds * 100, "zone_mismatch")
    terms = []
    for i in range(ctx.n):
        pz = ctx.patient_zones[i]
        if pz <= 0:
            continue
        pref_label = zone_label(pz)
        pref_start = ctx.bed_zone_start.get(pref_label)
        pref_count = ctx.bed_zone_count.get(pref_label, 0)
        if pref_start is None or pref_label == "ISO":
            continue

        in_pref_zone = sum(x[i, b - 1] for b in range(pref_start, pref_start + pref_count))
        assigned_anywhere = sum(x[i, b] for b in range(ctx.n_beds))
        if not ctx.iso_active or ctx.iso_flags[i]:
            # ISO beds are ordinary (none) or a valid match for isolation patients
            in_iso = sum(x[i, b] for b in range(ctx.n_iso_beds))
        else:
            in_iso = 0

        mismatch = model.NewIntVar(0, 1, f"mismatch_{i}")
        # Equality is valid: the right-hand side is always 0 or 1 here.
        model.Add(mismatch == assigned_anywhere - in_pref_zone - in_iso)
        terms.append(mismatch)

    if terms:
        model.Add(penalty == sum(terms))
    else:
        model.Add(penalty == 0)
    return penalty


def _move(model, x, ctx: ModelContext):
    terms = []
    for i, stay_id in enumerate(ctx.stay_ids):
        prev = ctx.prev_bed.get(int(stay_id))
        if prev is None:
            continue
        assigned_any = sum(x[i, b] for b in range(ctx.n_beds))
        b_prev = prev - 1
        if 0 <= b_prev < ctx.n_beds:
            # 1 iff assigned to a different bed; 0 if same bed or unassigned
            terms.append(assigned_any - x[i, b_prev])
        else:
            terms.append(assigned_any)
    return sum(terms) if terms else 0


def _bound_occupancy(ctx: ModelContext) -> int:
    return max(1, ctx.n_beds)


def _bound_wait(ctx: ModelContext) -> int:
    return max(1, ctx.n_beds * max(ctx.weights, default=1))


def _bound_overload(ctx: ModelContext) -> int:
    return max(1, ctx.n_beds * max(ctx.sofa_vals, default=1))


def _bound_balance(ctx: ModelContext) -> int:
    return max(1, ctx.n_beds)


def _bound_zone_mismatch(ctx: ModelContext) -> int:
    return max(1, ctx.n_beds)


def _bound_move(ctx: ModelContext) -> int:
    return max(1, ctx.n_beds)


OBJECTIVES: dict[str, ObjectiveSpec] = {
    "occupancy": ObjectiveSpec("occupancy", "max", _bound_occupancy, _occupancy),
    "wait": ObjectiveSpec("wait", "max", _bound_wait, _wait),
    "overload": ObjectiveSpec("overload", "min", _bound_overload, _overload),
    "balance": ObjectiveSpec("balance", "min", _bound_balance, _balance),
    "zone_mismatch": ObjectiveSpec("zone_mismatch", "min", _bound_zone_mismatch, _zone_mismatch),
    "move": ObjectiveSpec("move", "min", _bound_move, _move),
}


def build_objectives(model, x, ctx: ModelContext) -> dict[str, object]:
    """Build every objective once; callers decide which ones to optimize."""
    return {name: spec.build(model, x, ctx) for name, spec in OBJECTIVES.items()}


def objective_bounds(ctx: ModelContext) -> dict[str, int]:
    return {name: spec.bound(ctx) for name, spec in OBJECTIVES.items()}


def apply_objective(
    model,
    exprs: Mapping[str, object],
    ctx: ModelContext,
    coefficients: Mapping[str, int],
    *,
    pivot: str | None = None,
    epsilon: Mapping[str, float] | None = None,
    active: Sequence[str] | None = None,
) -> dict:
    """Attach either a single-objective or weighted-sum objective to the model."""
    if epsilon and pivot is None:
        raise ValueError("epsilon requires an explicit pivot objective")
    if pivot is not None:
        if pivot not in OBJECTIVES:
            raise ValueError(f"unknown pivot objective: {pivot}")
        if epsilon and pivot in epsilon:
            raise ValueError("epsilon must not constrain the pivot objective")

        spec = OBJECTIVES[pivot]
        if spec.sense == "max":
            model.Maximize(exprs[pivot])
        else:
            model.Minimize(exprs[pivot])

        for name, bound in (epsilon or {}).items():
            if name not in OBJECTIVES:
                raise ValueError(f"unknown epsilon objective: {name}")
            if name == "balance":
                # Exact encoding of max(L) - min(L) <= bound without relying
                # on auxiliary max/min variables being pinned by the objective.
                for left in ctx.zone_load_vars:
                    for right in ctx.zone_load_vars:
                        model.Add(left - right <= bound)
            elif OBJECTIVES[name].sense == "min":
                model.Add(exprs[name] <= bound)
            else:
                model.Add(exprs[name] >= bound)
        return {"mode": "pivot", "pivot": pivot, "epsilon": dict(epsilon or {})}

    names = list(active) if active else list(OBJECTIVES)
    unknown = set(names) - set(OBJECTIVES)
    if unknown:
        raise ValueError(f"unknown objective(s): {', '.join(sorted(unknown))}")

    total = 0
    for name in names:
        spec = OBJECTIVES[name]
        term = coefficients[name] * exprs[name]
        total += term if spec.sense == "max" else -term
    model.Maximize(total)
    return {"mode": "weighted_sum", "active": names}
