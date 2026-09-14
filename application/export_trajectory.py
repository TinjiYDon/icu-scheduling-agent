"""CLI: export rolling trajectory pack for RL protocol."""

from __future__ import annotations

import argparse
import json

from domain.rl.trajectory import export_rolling_trajectory


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=12)
    p.add_argument("--name", type=str, default="")
    args = p.parse_args()
    out = export_rolling_trajectory(n_steps=args.steps, out_name=args.name or None)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
