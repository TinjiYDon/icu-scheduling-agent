"""Engineering runner: real rolling assignments + per-step ε fronts → HV–churn.

This wires the previously separate pieces:
  `run_rolling_simulation` (per-step assignments/candidates)
  + `run_payoff_table` / `run_epsilon_grid_scan` (per-step front)
  → `hv_churn_series` / `summarize_hv_churn`.

Default is deliberately small (2 steps, 2 levels) to be runnable locally;
scale up with --steps/--levels/--max-time after the wiring is verified.

Usage:
  .\\.venv\\Scripts\\python.exe -m application.run_hv_churn --steps 2 --levels 2 --max-time 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from domain.optimizer.cp_sat import run_assignment
from domain.optimizer.moo_phase3 import (
    DEFAULT_GRID_OBJECTIVES,
    DEFAULT_OBJECTIVES,
    DEFAULT_PRIMARY,
    OBJECTIVE_SENSES,
    normalize_for_maximization,
    run_epsilon_grid_scan,
    run_payoff_table,
)
from domain.optimizer.pareto_io import (
    FrontSnapshot,
    hv_churn_series,
    summarize_hv_churn,
)
from domain.rolling.engine import run_rolling_simulation

ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "reports" / "pareto_decision" / "hv_churn_rolling.json"


def _front_for_snapshot(
    snapshot: Mapping[str, Any],
    *,
    levels: int,
    max_time: float,
) -> FrontSnapshot:
    """Build one normalized front for a rolling snapshot using a small ε grid."""
    assignments = {
        int(k): int(v) for k, v in (snapshot.get("assignments") or {}).items()
    }
    candidates = [int(x) for x in (snapshot.get("candidate_ids") or [])]
    if not candidates:
        candidates = sorted(assignments)
    if not candidates:
        raise ValueError(f"step {snapshot.get('step')} 没有候选患者")

    def solve(**kwargs: Any) -> dict[str, Any]:
        kwargs.pop("persist", None)
        return run_assignment(
            stay_ids=candidates,
            occupied_beds=assignments,
            persist=False,
            max_time_seconds=max_time,
            **kwargs,
        )

    payoff = run_payoff_table(
        solve, objectives=DEFAULT_OBJECTIVES, split=None, persist=False
    )
    scan = run_epsilon_grid_scan(
        solve,
        payoff=payoff,
        primary=DEFAULT_PRIMARY,
        grid_objectives=DEFAULT_GRID_OBJECTIVES,
        levels=levels,
        split=None,
        persist=False,
    )

    senses = {o: OBJECTIVE_SENSES[o] for o in DEFAULT_GRID_OBJECTIVES}
    rows: list[list[float]] = []
    ids: list[str] = []
    for point in scan.get("front") or []:
        values = dict(point.get("values") or {})
        if not values:
            continue
        norm = normalize_for_maximization(
            values, ideal=payoff["ideal"], nadir=payoff["nadir"], senses=senses
        )
        rows.append([float(norm[o]) for o in DEFAULT_GRID_OBJECTIVES])
        ids.append(str(point.get("source") or f"sol_{len(ids)}"))
    if not rows:
        raise ValueError(f"step {snapshot.get('step')} 前沿为空")
    return FrontSnapshot(
        step=int(snapshot["step"]), ids=ids, points=np.asarray(rows, dtype=float)
    )


def run_hv_churn(
    *,
    n_steps: int = 2,
    levels: int = 2,
    max_time: float = 3.0,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    rolling = run_rolling_simulation(n_steps=n_steps, reoptimize=True, persist=False)
    history = list(rolling.get("history") or [])
    if len(history) < 2:
        raise ValueError("history 至少需要 2 步")

    fronts: list[FrontSnapshot] = []
    assignments: list[dict[str, str]] = []
    for snap in history:
        fronts.append(
            _front_for_snapshot(snap, levels=levels, max_time=max_time)
        )
        assignments.append(dict(snap.get("assignments") or {}))

    series = hv_churn_series(fronts, assignments)
    summary = summarize_hv_churn(series)
    report = {
        "status": "ok",
        "config": {
            "n_steps": n_steps,
            "levels": levels,
            "max_time_seconds": max_time,
            "grid_objectives": list(DEFAULT_GRID_OBJECTIVES),
            "source": "rolling_simulation + per-step epsilon grid",
        },
        "rolling": {
            "total_steps": rolling.get("total_steps"),
            "final_occupancy": rolling.get("final_occupancy"),
            "bed_utilization_pct": rolling.get("bed_utilization_pct"),
            "history": [
                {k: v for k, v in h.items() if k not in ("assignments", "candidate_ids")}
                for h in history
            ],
        },
        "series": series,
        "summary": summary,
        "note": "Fronts are per-step ε grids over the same candidate set; not a clinical claim.",
    }
    out = Path(output_path) if output_path else OUT_DEFAULT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["path"] = str(out)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="滚动 + 每步 ε 前沿 → HV–churn 工程链路")
    p.add_argument("--steps", type=int, default=2)
    p.add_argument("--levels", type=int, default=2)
    p.add_argument("--max-time", type=float, default=3.0)
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    report = run_hv_churn(
        n_steps=args.steps,
        levels=args.levels,
        max_time=args.max_time,
        output_path=args.out,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "path": report["path"],
                "summary": report["summary"],
                "series": report["series"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
