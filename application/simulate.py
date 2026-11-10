"""H=1 rolling simulation entry point."""

from __future__ import annotations

import argparse
import json

from domain.rolling.engine import run_rolling_simulation


def run_simulate(n_steps: int = 12, persist: bool = False) -> dict:
    """Run the H=1 rolling scheduler and return its decision history.

    Args:
        n_steps: number of 2-hour transitions (default 12 = 24 hours).
        persist: write runs/decisions to PostgreSQL when true.
    """
    store = None
    if persist:
        from data_access.rolling_repo import PostgresRollingStore

        store = PostgresRollingStore()
    result = run_rolling_simulation(n_steps=n_steps, store=store)
    result["status"] = "simulate_ok"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="H=1 rolling ICU scheduler")
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument(
        "--persist",
        action="store_true",
        help="write sched.rolling_runs / sched.rolling_decisions",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run_simulate(n_steps=args.steps, persist=args.persist),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
