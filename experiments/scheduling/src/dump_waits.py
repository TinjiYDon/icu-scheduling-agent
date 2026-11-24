"""导出逐病人等待时间（用于 ECDF 图），复跑少量场景。

用法：python experiments/scheduling/src/dump_waits.py --scenario 92_seed11
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
from sim import run_episode  # noqa: E402

DATA = SRC.parent / "data"
RES = SRC.parent / "results"
METHODS = ["M0_fcfs", "M1_greedy_sofa", "M2_greedy_priority", "M3_greedy_reserve",
           "M4_cpsat_ws", "M7_rolling"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", default=["92_seed11"])
    ap.add_argument("--methods", nargs="+", default=METHODS)
    ap.add_argument("--time-limit", type=float, default=0.5)
    args = ap.parse_args()
    for sc_name in args.scenarios:
        sc = json.loads((DATA / f"scenario_{sc_name}.json").read_text(encoding="utf-8"))
        for meth in args.methods:
            ep = run_episode(sc, meth, time_limit=args.time_limit)
            rows = []
            for p in ep.patients.values():
                end = p.admit if p.admit is not None else ep.horizon_end
                rows.append({"pid": p.pid, "stay_id": p.stay_id, "sofa0": p.sofa0,
                             "high_risk": p.high_risk, "need_iso": p.need_iso,
                             "vent_hours": p.vent_hours,
                             "wait_h": (end - p.arrival).total_seconds() / 3600.0,
                             "admitted": p.admit is not None, "moves": p.moves})
            out = RES / f"waits_{sc_name}__{meth}.csv"
            pd.DataFrame(rows).to_csv(out, index=False)
            print("wrote", out.name, len(rows))


if __name__ == "__main__":
    main()
