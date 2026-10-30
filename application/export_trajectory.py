"""CLI: export rolling trajectory pack for RL protocol."""

from __future__ import annotations

import argparse
import json

from domain.rl.trajectory import MAX_EXPORT_STEPS, export_rolling_trajectory


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=12, help=f"Simulation steps (0..{MAX_EXPORT_STEPS})")
    p.add_argument("--name", type=str, default=None, help="JSON basename inside artifacts/trajectories")
    args = p.parse_args()
    try:
        out = export_rolling_trajectory(n_steps=args.steps, out_name=args.name)
    except ValueError as exc:
        p.error(str(exc))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
