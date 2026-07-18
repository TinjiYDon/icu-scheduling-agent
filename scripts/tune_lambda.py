"""Run CP-SAT lambda sensitivity/grid experiments and write comparable CSVs."""

from __future__ import annotations

import argparse
import json

from domain.optimizer.tuning import pareto_front, recommend_row, run_lambda_grid, write_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run 16 one-factor sensitivity cases")
    parser.add_argument("--output", default="reports/lambda_tuning.csv")
    args = parser.parse_args()

    if args.quick:
        # A compact smoke/sensitivity grid: wait varies most because its raw
        # objective currently has the largest magnitude.
        search_space = {
            "wait": [0.1, 0.5, 1.0, 2.0],
            "overload": [0.5, 1.0],
            "balance": [0.1],
            "zone_mismatch": [0.5, 1.0],
        }
    else:
        search_space = {
            "wait": [0.1, 0.5, 1.0, 2.0],
            "overload": [0.1, 0.5, 1.0, 2.0],
            "balance": [0.1, 0.5, 1.0, 2.0],
            "zone_mismatch": [0.1, 0.5, 1.0, 2.0],
        }

    rows = run_lambda_grid(search_space)
    output = write_csv(rows, args.output)
    write_csv(pareto_front(rows), output.with_name("lambda_tuning_pareto.csv"))
    recommendation = recommend_row(rows)
    recommendation_path = output.with_name("lambda_tuning_recommended.json")
    recommendation_path.write_text(
        json.dumps(recommendation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"results={output}")
    print(f"recommendation={recommendation_path}")


if __name__ == "__main__":
    main()
