"""Compare a transfer-enabled replay against a transfer-disabled one.

Transferring a patient out removes them from the bed pool *permanently* (general
wards are not modelled), so the two configurations end up with different
candidate pools.  Any difference in f1 is therefore contaminated by a pool
effect -- this script makes that contamination explicit instead of reporting the
naive delta as a gain.

Usage
-----
    python -m scripts.analysis.transfer_pool_effect
    python -m scripts.analysis.transfer_pool_effect --on A.json --off B.json
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLLING = ROOT / "reports" / "rolling"


def aggregate(path: Path) -> dict:
    rep = json.load(io.open(path, encoding="utf-8"))
    hist = rep["history"]

    def col(name: str) -> list[int]:
        return [(h.get("objective_values") or {}).get(name, 0) for h in hist]

    front = [(h.get("epsilon_scan") or {}).get("n_nondominated", 0) for h in hist]
    return {
        "f0_sum": sum(col("occupancy")),
        "f1_sum": sum(col("wait")),
        "f2_sum": sum(col("overload")),
        "f4_sum": sum(col("zone_mismatch")),
        "f5_sum": sum(h.get("f5_move", 0) for h in hist),
        "front_sum": sum(front),
        "front_mean": sum(front) / len(front) if front else 0.0,
        "transferred": len(hist[-1].get("transferred_total") or []),
        "eligible_person_steps": sum(h.get("n_eligible_transfer", 0) for h in hist),
        "waiting_end": len(hist[-1].get("waiting") or []),
        "sample_size": rep["config"]["sample_size_actual"],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--off", type=Path, default=ROLLING / "timed_pareto_notransfer.json")
    p.add_argument("--on", type=Path, default=ROLLING / "timed_pareto_transfer.json")
    args = p.parse_args()

    off = aggregate(args.off)
    on = aggregate(args.on)
    print(f"{'metric':>22} {'transfer OFF':>14} {'transfer ON':>13} {'delta':>8}")
    print("-" * 60)
    for key in off:
        a, b = off[key], on[key]
        delta = f"{b - a:+.4f}" if isinstance(a, float) else f"{b - a:+d}"
        print(f"{key:>22} {a:>14} {b:>13} {delta:>8}")

    print()
    print("per-step f1 (occupancy is usually saturated in both runs)")
    print(f"{'step':>4} {'hour':>4} {'OFF f1':>8} {'ON f1':>8} {'delta':>8}")
    h_off = json.load(io.open(args.off, encoding="utf-8"))["history"]
    h_on = json.load(io.open(args.on, encoding="utf-8"))["history"]
    for a, b in zip(h_off, h_on):
        va = (a.get("objective_values") or {}).get("wait", 0)
        vb = (b.get("objective_values") or {}).get("wait", 0)
        print(f"{a['step']:>4} {a['hour']:>4} {va:>8} {vb:>8} {vb - va:>+8d}")

    print()
    print("CAVEAT: the transferred patients leave the pool for good, so the two")
    print("runs do not share a candidate pool.  The naive f1 delta above is NOT a")
    print("clean mechanism effect; a matched-pool protocol (B_pool) is required.")


if __name__ == "__main__":
    main()
