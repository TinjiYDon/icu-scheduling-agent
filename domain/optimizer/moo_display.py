"""Teacher-facing tables for S2-MOO reports (no database)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from domain.optimizer.moo_phase3 import OBJECTIVE_SENSES

REPORT_DIR = Path(__file__).resolve().parents[2] / "reports" / "moo"


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_latest_scenarios(root: Path | None = None) -> dict[str, Any] | None:
    directory = (root or REPORT_DIR.parent.parent) / "reports" / "moo"
    latest = directory / "scenarios_latest.json"
    return load_json(latest)


def load_latest_phase3(root: Path | None = None) -> dict[str, Any] | None:
    directory = (root or REPORT_DIR.parent.parent) / "reports" / "moo"
    latest = directory / "summary_latest.json"
    return load_json(latest)


def pivot_scenario_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One row per scenario; columns per method (teacher table)."""
    by_sc: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("scenario_id") or row.get("id") or "")
        name = str(row.get("scenario_name") or row.get("name") or sid)
        rec = by_sc.setdefault(
            sid,
            {"scenario_id": sid, "scenario_name": name},
        )
        method = str(row.get("method") or "unknown")
        rec[f"{method}_status"] = row.get("status")
        rec[f"{method}_assigned"] = row.get("assigned")
        rec[f"{method}_wait"] = row.get("obj_wait")
        rec[f"{method}_high_risk"] = row.get("obj_high_risk")
    return list(by_sc.values())


def three_mode_metrics(result: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten one run_assignment payload for Streamlit."""
    mo = result.get("multiobjective") or {}
    values = mo.get("values") or {}
    ev = result.get("evaluation") or {}
    return {
        "mode": result.get("objective_mode"),
        "status": result.get("solver_status"),
        "assigned": result.get("assigned"),
        "n_stays": result.get("n_stays"),
        "wait": values.get("wait"),
        "high_risk": values.get("high_risk"),
        "overload": values.get("overload"),
        "occupancy": values.get("occupancy"),
        "wall_time_seconds": mo.get("wall_time_seconds") or ev.get("solve_time_seconds"),
        "exact_hierarchy": mo.get("exact_hierarchy"),
    }


def midpoint_epsilon_bounds(
    ideal: Mapping[str, Any],
    nadir: Mapping[str, Any],
    *,
    senses: Mapping[str, str] | None = None,
    skip: frozenset[str] | None = None,
) -> dict[str, int]:
    """Midpoint of payoff ideal/nadir for epsilon-constraint (phase-3 style)."""
    ignored = skip or frozenset({"wait", "move", "zone_mismatch"})
    sense_map = dict(senses or OBJECTIVE_SENSES)
    bounds: dict[str, int] = {}
    for name, sense in sense_map.items():
        if name in ignored:
            continue
        if name not in ideal or name not in nadir:
            continue
        try:
            a = float(ideal[name])
            b = float(nadir[name])
        except (TypeError, ValueError):
            continue
        mid = (a + b) / 2.0
        bounds[name] = int(round(mid))
        _ = sense
    return bounds


def epsilon_bounds_from_phase3(summary: Mapping[str, Any] | None) -> dict[str, int] | None:
    if not summary:
        return None
    ideal = summary.get("payoff_ideal") or {}
    nadir = summary.get("payoff_nadir") or {}
    if not ideal or not nadir:
        return None
    bounds = midpoint_epsilon_bounds(ideal, nadir)
    return bounds or None

