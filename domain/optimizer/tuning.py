"""Utilities for reproducible lambda grid searches and result selection."""

from __future__ import annotations

import csv
from itertools import product
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from domain.optimizer.cp_sat import run_assignment

LAMBDA_NAMES = ("wait", "overload", "balance", "zone_mismatch")
MAXIMIZE_METRICS = (
    "high_risk_assigned_rate",
    "priority_total",
    "zone_match_rate",
)
MINIMIZE_METRICS = (
    "overload_penalty",
    "balance_deviation",
    "solve_time_seconds",
)


def iter_lambda_grid(
    search_space: Mapping[str, Sequence[float]],
) -> Iterable[dict[str, float]]:
    unknown = set(search_space) - set(LAMBDA_NAMES)
    missing = set(LAMBDA_NAMES) - set(search_space)
    if unknown or missing:
        raise ValueError(
            f"lambda grid keys must be {LAMBDA_NAMES}; "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    values = [search_space[name] for name in LAMBDA_NAMES]
    if any(not candidates for candidates in values):
        raise ValueError("every lambda grid dimension must contain at least one value")
    for combination in product(*values):
        yield dict(zip(LAMBDA_NAMES, map(float, combination), strict=True))


def run_lambda_grid(
    search_space: Mapping[str, Sequence[float]],
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for index, weights in enumerate(iter_lambda_grid(search_space), start=1):
        run_id = "tune_{:04d}_{}".format(
            index,
            "_".join(f"{name[:1]}{value:g}" for name, value in weights.items()),
        )
        result = run_assignment(
            run_id=run_id, lambda_weights=weights, persist=False
        )
        evaluation = result.get("evaluation", {})
        rows.append(
            {
                "run_id": run_id,
                **weights,
                "solver_status": result.get("solver_status", result.get("status", "unknown")),
                "assigned": float(result.get("assigned", 0)),
                **{name: float(evaluation.get(name, 0)) for name in (
                    "assignment_rate",
                    "priority_total",
                    "avg_assigned_priority",
                    "high_risk_assigned_rate",
                    "overload_penalty",
                    "balance_deviation",
                    "zone_match_rate",
                    "solve_time_seconds",
                )},
            }
        )
    return rows


def pareto_front(rows: Sequence[Mapping[str, float | str]]) -> list[dict]:
    """Return non-dominated rows using raw business metrics, not objective score."""

    def dominates(left: Mapping, right: Mapping) -> bool:
        no_worse = all(float(left[m]) >= float(right[m]) for m in MAXIMIZE_METRICS)
        no_worse &= all(float(left[m]) <= float(right[m]) for m in MINIMIZE_METRICS)
        strictly_better = any(float(left[m]) > float(right[m]) for m in MAXIMIZE_METRICS)
        strictly_better |= any(float(left[m]) < float(right[m]) for m in MINIMIZE_METRICS)
        return no_worse and strictly_better

    return [dict(row) for row in rows if not any(
        other is not row and dominates(other, row) for other in rows
    )]


def recommend_row(rows: Sequence[Mapping[str, float | str]]) -> dict:
    """Choose transparently from the Pareto front using a documented ordering."""
    front = pareto_front(rows)
    if not front:
        raise ValueError("cannot recommend lambda weights from empty results")
    return max(
        front,
        key=lambda row: (
            float(row["high_risk_assigned_rate"]),
            float(row["zone_match_rate"]),
            -float(row["overload_penalty"]),
            -float(row["balance_deviation"]),
            float(row["priority_total"]),
            -float(row["solve_time_seconds"]),
        ),
    )


def write_csv(rows: Sequence[Mapping], path: str | Path) -> Path:
    if not rows:
        raise ValueError("cannot write an empty tuning result")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output
