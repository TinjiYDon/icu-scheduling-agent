"""P0 scheduling simulation: SOFA → CP-SAT assignment (+ calib/eval meta)."""

from __future__ import annotations

from domain.optimizer.cp_sat import run_assignment
from domain.optimizer.eval_split import split_stay_ids
from domain.scoring.sofa import compute_sofa_timeseries
from infra.db import get_engine
from sqlalchemy import text


def run_simulate(*, use_eval_split: bool = True) -> dict:
    meta: dict = {}
    meta.update(compute_sofa_timeseries())

    engine = get_engine()
    with engine.connect() as conn:
        stay_ids = [int(r[0]) for r in conn.execute(text("SELECT stay_id FROM staging.icustays")).all()]

    if use_eval_split and stay_ids:
        split_meta = split_stay_ids(stay_ids)
        meta["eval_split"] = {
            "seed": split_meta["seed"],
            "calib_ratio": split_meta["calib_ratio"],
            "n_calib": split_meta["n_calib"],
            "n_eval": split_meta["n_eval"],
            "note": "Wave1 skeleton: assignment still uses full cohort; Wave2 B should restrict calib/eval runs",
        }
    else:
        meta["eval_split"] = {"n_calib": 0, "n_eval": 0, "note": "disabled"}

    assign = run_assignment()
    meta.update(assign)
    meta["metrics"] = {
        "n_stays": assign.get("n_stays", 0),
        "n_beds": assign.get("n_beds", 0),
        "assigned": assign.get("assigned", 0),
        "unassigned": max(int(assign.get("n_stays", 0)) - int(assign.get("assigned", 0)), 0),
        "solver_status": assign.get("solver_status"),
    }
    meta["status"] = "simulate_ok"
    return meta


if __name__ == "__main__":
    import json

    print(json.dumps(run_simulate(), indent=2, ensure_ascii=False, default=str))
