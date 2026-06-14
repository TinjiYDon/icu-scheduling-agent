"""P0 scheduling simulation: SOFA → CP-SAT assignment."""

from __future__ import annotations

from domain.optimizer.cp_sat import run_assignment
from domain.scoring.sofa import compute_sofa_timeseries


def run_simulate() -> dict:
    meta = {}
    meta.update(compute_sofa_timeseries())
    meta.update(run_assignment())
    meta["status"] = "simulate_ok"
    return meta


if __name__ == "__main__":
    import json

    print(json.dumps(run_simulate(), indent=2, ensure_ascii=False))
