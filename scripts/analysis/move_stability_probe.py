"""Probe the f5 (bed-move) trade-off on one real decision step.

Two experiments, both replayed from a ``timed_pareto`` report so the candidate
pool, as-of SOFA scores and pre-decision bed map are the real ones:

1. **Cost of stability** — weighted sum under ``max_moves=K``.  If every metric
   is flat across K, freezing the beds is already the weighted-sum optimum, so
   no stability/yield curve exists against f1.
2. **f5 vs f4** — ``pivot=zone_mismatch`` while sweeping the f5 cap.  If f4 drops
   as the cap loosens, moves can repair zone mismatch; if it is flat, they
   cannot.

Usage
-----
    python -m scripts.analysis.move_stability_probe
    python -m scripts.analysis.move_stability_probe --steps 2 5 8
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

from domain.optimizer.cp_sat import run_assignment

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = ROOT / "reports" / "rolling" / "timed_pareto_move10_v2.json"
DEFAULT_SAMPLE = ROOT / "artifacts" / "sofa_sample" / "sofa_sample.json"

CAPS = (0, 1, 2, 3, 4, 6, 8, 10, 14, 19)


def _load(report_path: Path, sample_path: Path):
    rep = json.load(io.open(report_path, encoding="utf-8"))
    payload = json.load(io.open(sample_path, encoding="utf-8"))
    careunit = {
        int(s["stay_id"]): s.get("first_careunit") or "" for s in payload["stays"]
    }
    return rep, careunit


def _rows(snapshot, careunit):
    return [
        {
            "stay_id": int(r["stay_id"]),
            "priority_weight": float(r["priority_weight"]),
            "sofa_total": float(r["sofa_total"]),
            "first_careunit": careunit.get(int(r["stay_id"]), ""),
        }
        for r in snapshot["scores"]
    ]


def cost_of_stability(rep, careunit, step: int) -> str:
    snap = rep["history"][step]
    rows = _rows(snap, careunit)
    prev = {int(k): int(v) for k, v in snap["predecision_beds"].items()}
    out = [
        f"=== cost of stability: weighted sum under max_moves (step {step}, "
        f"h={snap['hour']}, incumbents={len(prev)})",
        f"{'K':>5} {'status':>9} {'f0':>3} {'f1':>7} {'f2':>5} {'f3':>3} {'f4':>3} {'f5':>3}",
        "-" * 45,
    ]
    for cap in CAPS + (None,):
        kwargs = {} if cap is None else {"max_moves": cap}
        res = run_assignment(
            persist=False,
            candidate_rows=rows,
            previous_beds=prev,
            retain_occupied=True,
            resource_overrides=rep["config"]["resources"],
            solver_seed=0,
            max_time_seconds=10.0,
            **kwargs,
        )
        o = res["objective"]
        label = "None" if cap is None else str(cap)
        out.append(
            f"{label:>5} {res['solver_status']:>9} {o['f0_occupancy']:>3} "
            f"{o['f1_priority_total']:>7} {o['f2_overload_penalty']:>5} "
            f"{o['f3_balance_deviation']:>3} {o['f4_zone_mismatch']:>3} "
            f"{o['f5_move']:>3}"
        )
    return "\n".join(out)


def move_vs_zone(rep, careunit, step: int) -> str:
    snap = rep["history"][step]
    rows = _rows(snap, careunit)
    prev = {int(k): int(v) for k, v in snap["predecision_beds"].items()}
    out = [
        f"=== f5 vs f4: pivot=zone_mismatch under an f5 cap (step {step}, "
        f"h={snap['hour']})",
        f"{'cap':>5} {'status':>9} {'f0':>3} {'f4':>3} {'f5':>3}",
        "-" * 28,
    ]
    for cap in CAPS:
        try:
            res = run_assignment(
                persist=False,
                candidate_rows=rows,
                previous_beds=prev,
                retain_occupied=True,
                resource_overrides=rep["config"]["resources"],
                solver_seed=0,
                max_time_seconds=10.0,
                pivot="zone_mismatch",
                epsilon={"move": cap},
            )
        except Exception as exc:  # noqa: BLE001 - infeasible caps are expected
            out.append(f"{cap:>5} {type(exc).__name__:>9}")
            continue
        o = res["objective"]
        out.append(
            f"{cap:>5} {res['solver_status']:>9} {o['f0_occupancy']:>3} "
            f"{o['f4_zone_mismatch']:>3} {o['f5_move']:>3}"
        )
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    p.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    p.add_argument("--steps", type=int, nargs="+", default=[2, 5, 8])
    args = p.parse_args()

    rep, careunit = _load(args.report, args.sample)
    for step in args.steps:
        print(cost_of_stability(rep, careunit, step))
        print()
        print(move_vs_zone(rep, careunit, step))
        print()


if __name__ == "__main__":
    main()
