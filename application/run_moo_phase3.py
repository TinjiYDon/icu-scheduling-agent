"""CLI: S2-MOO phase 3 payoff + epsilon grid + hypervolume (A2)."""

from __future__ import annotations

import argparse
import json
from functools import partial

from domain.optimizer.cp_sat import run_assignment
from domain.optimizer.moo_phase3 import (
    DEFAULT_GRID_OBJECTIVES,
    DEFAULT_OBJECTIVES,
    DEFAULT_PRIMARY,
    run_baselines,
    run_epsilon_grid_scan,
    run_payoff_table,
    write_phase3_reports,
)


def main() -> None:
    p = argparse.ArgumentParser(description="S2-MOO phase 3 payoff / epsilon grid")
    p.add_argument("--split", default="calib", choices=["calib", "eval", "all"])
    p.add_argument("--levels", type=int, default=3)
    p.add_argument(
        "--grid",
        default=",".join(DEFAULT_GRID_OBJECTIVES),
        help="comma-separated secondary objectives for the epsilon grid",
    )
    p.add_argument("--primary", default=DEFAULT_PRIMARY)
    p.add_argument("--max-time", type=float, default=30.0)
    p.add_argument("--baseline-max-time", type=float, default=60.0)
    p.add_argument(
        "--max-points",
        type=int,
        default=None,
        help="optional cap on grid solves (debug); default = full A2 grid",
    )
    p.add_argument("--skip-baselines", action="store_true")
    args = p.parse_args()

    split = None if args.split == "all" else args.split
    grid_objectives = tuple(x.strip() for x in args.grid.split(",") if x.strip())
    solve = partial(run_assignment, max_time_seconds=args.max_time)
    solve_baseline = partial(run_assignment, max_time_seconds=args.baseline_max_time)

    print(
        json.dumps(
            {
                "phase": 3,
                "split": split,
                "primary": args.primary,
                "grid_objectives": list(grid_objectives),
                "levels": args.levels,
                "max_time_seconds": args.max_time,
                "baseline_max_time_seconds": args.baseline_max_time,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    payoff = run_payoff_table(
        solve, objectives=DEFAULT_OBJECTIVES, split=split, persist=False
    )
    print(
        json.dumps(
            {"payoff_ideal": payoff["ideal"], "payoff_nadir": payoff["nadir"]},
            ensure_ascii=False,
        ),
        flush=True,
    )

    def _progress(i: int, n: int, bounds: dict) -> None:
        print(f"[grid] {i}/{n} bounds={bounds}", flush=True)

    scan = run_epsilon_grid_scan(
        solve,
        payoff=payoff,
        primary=args.primary,
        grid_objectives=grid_objectives,
        levels=args.levels,
        split=split,
        persist=False,
        max_points=args.max_points,
        progress=_progress,
    )
    # Persist scan even if baselines fail later.
    baselines: list = []
    paths = write_phase3_reports(payoff=payoff, scan=scan, baselines=baselines)
    print(
        json.dumps(
            {
                "n_grid": scan["n_grid"],
                "n_feasible": scan["n_feasible"],
                "n_nondominated": scan["n_nondominated"],
                "hypervolume": scan["hypervolume"],
                "paths_pre_baseline": paths,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    if not args.skip_baselines:
        baselines = run_baselines(
            solve_baseline, objectives=DEFAULT_OBJECTIVES, split=split, persist=False
        )
        paths = write_phase3_reports(payoff=payoff, scan=scan, baselines=baselines)

    print(
        json.dumps(
            {
                "n_grid": scan["n_grid"],
                "n_feasible": scan["n_feasible"],
                "n_nondominated": scan["n_nondominated"],
                "hypervolume": scan["hypervolume"],
                "baselines": baselines,
                "paths": paths,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
