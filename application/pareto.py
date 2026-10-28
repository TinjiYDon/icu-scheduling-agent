"""CLI: P3 anchor solves and payoff table."""

from __future__ import annotations

import argparse

from domain.optimizer.pareto import format_payoff, save_anchors, solve_anchors


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve anchor points (P3)")
    parser.add_argument("--guard-ratio", type=float, default=0.9)
    parser.add_argument("--split", choices=["calib", "eval"], default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = solve_anchors(
        practical_guard_ratio=args.guard_ratio,
        split=args.split,
    )
    print(format_payoff(result))
    path = save_anchors(result, args.output)
    print("\nsaved:", path)


if __name__ == "__main__":
    main()
