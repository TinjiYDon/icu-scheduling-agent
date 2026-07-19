"""P0 scheduling simulation: rolling-horizon ICU scheduling."""

from __future__ import annotations

import json
from domain.rolling.engine import run_rolling_simulation


def run_simulate(n_steps: int = 12) -> dict:
    """Run a rolling-horizon ICU scheduling simulation.

    Args:
        n_steps: number of 2-hour time steps (default 12 = 24 hours).
    """
    result = run_rolling_simulation(n_steps=n_steps)
    result["status"] = "simulate_ok"
    return result


if __name__ == "__main__":
    print(json.dumps(run_simulate(), indent=2, ensure_ascii=False))
