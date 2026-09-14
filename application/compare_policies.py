"""CLI: PPO / greedy / CP-SAT evaluation → H3 comparison table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.evaluate_ppo import evaluate_ppo
from domain.ops.policy_comparison import flatten_comparison

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--from-report",
        type=str,
        default="",
        help="Optional path to existing reports/ppo_evaluation.json (skip re-run)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="reports/policy_comparison.json",
    )
    args = parser.parse_args()
    if args.from_report:
        report = json.loads((ROOT / args.from_report).read_text(encoding="utf-8"))
    else:
        report = evaluate_ppo()
    table = flatten_comparison(report)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(table, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
