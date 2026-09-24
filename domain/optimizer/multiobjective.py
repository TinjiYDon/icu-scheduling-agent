"""Reusable multi-objective solve strategies for CP-SAT.

The scheduling model owns the decision variables and hard constraints.  This
module only decides how a shared set of objective expressions is optimized, so
weighted-sum, lexicographic and epsilon-constraint runs remain comparable.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

from ortools.sat.python import cp_model

ObjectiveSense = Literal["max", "min"]
ObjectiveMode = Literal["weighted_sum", "lexicographic", "epsilon_constraint"]

SUPPORTED_MODES = ("weighted_sum", "lexicographic", "epsilon_constraint")


@dataclass(frozen=True)
class ObjectiveSpec:
    """One integer CP-SAT objective and the scale used for normalization."""

    name: str
    expression: Any
    sense: ObjectiveSense
    upper_bound: int


@dataclass
class MultiObjectiveSolveResult:
    solver: cp_model.CpSolver
    status: int
    objective_values: dict[str, int]
    stages: list[dict[str, int | float | str | bool]]
    wall_time_seconds: float
    exact_hierarchy: bool


def normalized_coefficient(
    weight: float, upper_bound: int = 1, scale: int = 1_000_000
) -> int:
    """Convert a non-negative weight to a normalized integer coefficient."""
    if weight == 0:
        return 0
    return max(1, round(float(weight) * scale / max(int(upper_bound), 1)))


def _validate_specs(specs: Sequence[ObjectiveSpec]) -> dict[str, ObjectiveSpec]:
    if not specs:
        raise ValueError("at least one objective is required")
    by_name: dict[str, ObjectiveSpec] = {}
    for spec in specs:
        if spec.name in by_name:
            raise ValueError(f"duplicate objective: {spec.name}")
        if spec.sense not in ("max", "min"):
            raise ValueError(f"invalid sense for objective {spec.name}: {spec.sense}")
        if int(spec.upper_bound) <= 0:
            raise ValueError(f"upper_bound for objective {spec.name} must be positive")
        by_name[spec.name] = spec
    return by_name


def _validate_order(
    order: Sequence[str] | None, by_name: Mapping[str, ObjectiveSpec]
) -> list[str]:
    resolved = list(order or by_name.keys())
    if not resolved:
        raise ValueError("objective_order cannot be empty")
    if len(set(resolved)) != len(resolved):
        raise ValueError("objective_order cannot contain duplicates")
    unknown = set(resolved) - set(by_name)
    if unknown:
        raise ValueError(f"unknown objective(s): {', '.join(sorted(unknown))}")
    return resolved


def _integer_bound(name: str, raw_value: float) -> int:
    value = float(raw_value)
    if not math.isfinite(value) or not value.is_integer():
        raise ValueError(f"epsilon bound for {name} must be a finite integer")
    return int(value)


def _new_solver(max_time_seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(float(max_time_seconds), 0.001)
    return solver


def _status_label(status: int) -> str:
    if status == cp_model.OPTIMAL:
        return "OPTIMAL"
    if status == cp_model.FEASIBLE:
        return "FEASIBLE"
    if status == cp_model.INFEASIBLE:
        return "INFEASIBLE"
    if status == cp_model.MODEL_INVALID:
        return "MODEL_INVALID"
    return "UNKNOWN"


def _set_objective(model: cp_model.CpModel, spec: ObjectiveSpec) -> None:
    if spec.sense == "max":
        model.Maximize(spec.expression)
    else:
        model.Minimize(spec.expression)


def solve_multiobjective(
    model: cp_model.CpModel,
    specs: Sequence[ObjectiveSpec],
    *,
    mode: ObjectiveMode = "weighted_sum",
    weights: Mapping[str, float] | None = None,
    objective_order: Sequence[str] | None = None,
    epsilon_primary: str | None = None,
    epsilon_bounds: Mapping[str, int | float] | None = None,
    max_time_seconds: float = 30.0,
) -> MultiObjectiveSolveResult:
    """Solve one CP-SAT model with a selected multi-objective strategy.

    Epsilon bounds are direction aware: a maximization objective receives a
    lower bound, while a minimization objective receives an upper bound.
    Lexicographic stages lock the incumbent value exactly.  If an intermediate
    stage is only FEASIBLE because of the time limit, the returned hierarchy is
    marked non-exact instead of being presented as a proven lexicographic optimum.
    """
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"objective_mode must be one of {SUPPORTED_MODES}")
    if not math.isfinite(float(max_time_seconds)) or float(max_time_seconds) <= 0:
        raise ValueError("max_time_seconds must be a finite positive number")

    by_name = _validate_specs(specs)
    stages: list[dict[str, int | float | str | bool]] = []
    started = perf_counter()
    exact_hierarchy = True

    if mode == "weighted_sum":
        resolved_weights = dict(weights or {})
        unknown = set(resolved_weights) - set(by_name)
        if unknown:
            raise ValueError(f"unknown objective weight(s): {', '.join(sorted(unknown))}")
        terms = []
        for spec in specs:
            raw_weight = float(resolved_weights.get(spec.name, 0.0))
            if not math.isfinite(raw_weight) or raw_weight < 0:
                raise ValueError(f"weight for {spec.name} must be finite and non-negative")
            coefficient = normalized_coefficient(raw_weight, spec.upper_bound)
            sign = 1 if spec.sense == "max" else -1
            terms.append(sign * coefficient * spec.expression)
        if not any(float(resolved_weights.get(spec.name, 0.0)) > 0 for spec in specs):
            raise ValueError("at least one objective weight must be greater than zero")
        model.Maximize(sum(terms))
        solver = _new_solver(max_time_seconds)
        status = solver.Solve(model)
        stages.append(
            {
                "objective": "weighted_sum",
                "sense": "max",
                "status": _status_label(status),
                "wall_time_seconds": round(solver.WallTime(), 6),
            }
        )

    elif mode == "lexicographic":
        order = _validate_order(objective_order, by_name)
        solver = _new_solver(max_time_seconds)
        status = cp_model.UNKNOWN
        for index, name in enumerate(order):
            elapsed = perf_counter() - started
            solver.parameters.max_time_in_seconds = max(max_time_seconds - elapsed, 0.001)
            spec = by_name[name]
            _set_objective(model, spec)
            status = solver.Solve(model)
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                stages.append(
                    {
                        "objective": name,
                        "sense": spec.sense,
                        "status": _status_label(status),
                        "wall_time_seconds": round(solver.WallTime(), 6),
                    }
                )
                break
            value = int(solver.Value(spec.expression))
            stage_exact = status == cp_model.OPTIMAL
            exact_hierarchy &= stage_exact
            stages.append(
                {
                    "objective": name,
                    "sense": spec.sense,
                    "value": value,
                    "status": _status_label(status),
                    "exact": stage_exact,
                    "wall_time_seconds": round(solver.WallTime(), 6),
                }
            )
            if index < len(order) - 1:
                model.Add(spec.expression == value)

    else:
        primary_name = epsilon_primary or next(iter(by_name))
        if primary_name not in by_name:
            raise ValueError(f"unknown epsilon primary objective: {primary_name}")
        bounds = dict(epsilon_bounds or {})
        unknown = set(bounds) - set(by_name)
        if unknown:
            raise ValueError(f"unknown epsilon objective(s): {', '.join(sorted(unknown))}")
        if primary_name in bounds:
            raise ValueError("epsilon_primary cannot also have an epsilon bound")
        for name, raw_bound in bounds.items():
            spec = by_name[name]
            bound = _integer_bound(name, raw_bound)
            if spec.sense == "max":
                model.Add(spec.expression >= bound)
            else:
                model.Add(spec.expression <= bound)
        primary = by_name[primary_name]
        _set_objective(model, primary)
        solver = _new_solver(max_time_seconds)
        status = solver.Solve(model)
        stages.append(
            {
                "objective": primary_name,
                "sense": primary.sense,
                "status": _status_label(status),
                "wall_time_seconds": round(solver.WallTime(), 6),
                "epsilon_bounds": str(bounds),
            }
        )

    objective_values: dict[str, int] = {}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        objective_values = {
            spec.name: int(solver.Value(spec.expression)) for spec in specs
        }
    return MultiObjectiveSolveResult(
        solver=solver,
        status=status,
        objective_values=objective_values,
        stages=stages,
        wall_time_seconds=round(perf_counter() - started, 6),
        exact_hierarchy=exact_hierarchy,
    )
