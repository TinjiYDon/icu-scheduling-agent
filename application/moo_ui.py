"""L4: S2-MOO report load + lightweight three-mode compare for Streamlit."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Mapping

from domain.optimizer.moo_display import (
    epsilon_bounds_from_phase3,
    load_latest_phase3,
    load_latest_scenarios,
    pivot_scenario_rows,
    three_mode_metrics,
)
from domain.optimizer.moo_epsilon_recal import DEFAULT_EPSILON_BOUNDS

ROOT = Path(__file__).resolve().parents[1]


def load_phase3_summary(root: Path | None = None) -> dict[str, Any]:
    payload = load_latest_phase3(root or ROOT)
    if payload is None:
        return {"status": "missing", "payload": None}
    return {"status": "ok", "payload": payload}


def load_scenarios_latest(root: Path | None = None) -> dict[str, Any]:
    payload = load_latest_scenarios(root or ROOT)
    if payload is None:
        return {"status": "missing", "payload": None}
    return {"status": "ok", "payload": payload}


def scenario_wide_table(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    return pivot_scenario_rows(list(payload.get("rows") or []))


def flatten_front(front: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for point in front or []:
        values = dict(point.get("values") or {})
        rows.append(
            {
                "source": point.get("source"),
                "status": point.get("status"),
                "wall_time_seconds": point.get("wall_time_seconds"),
                **values,
            }
        )
    return rows


def rows_to_csv(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(str(key))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({k: r.get(k) for k in fieldnames} for r in rows)
    return buf.getvalue()


def run_three_mode_live(
    *,
    split: str | None = "calib",
    max_time_seconds: float = 20.0,
    persist: bool = False,
    phase3: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """WS + Lex + one ε point. Does not write assignments."""
    from domain.optimizer.cp_sat import run_assignment

    bounds = epsilon_bounds_from_phase3(phase3) or dict(DEFAULT_EPSILON_BOUNDS)
    specs: list[tuple[str, dict[str, Any]]] = [
        ("weighted_sum", {"objective_mode": "weighted_sum"}),
        ("lexicographic", {"objective_mode": "lexicographic"}),
        (
            "epsilon_constraint",
            {
                "objective_mode": "epsilon_constraint",
                "epsilon_primary": "wait",
                "epsilon_bounds": bounds,
            },
        ),
    ]
    rows: list[dict[str, Any]] = []
    for _label, kwargs in specs:
        result = run_assignment(
            persist=persist,
            split=split,
            max_time_seconds=max_time_seconds,
            **kwargs,
        )
        rows.append(three_mode_metrics(result))
    return {"rows": rows, "epsilon_bounds": bounds, "split": split}
