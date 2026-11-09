"""Summarise one timed_pareto replay report (per-step objectives + transfers).

Usage
-----
    python -m scripts.analysis.replay_summary reports/rolling/timed_pareto_transfer.json

Shows, per decision step, the six objective values, the executed f5 / churn /
similarity, the transfer eligibility gate, and the sampled front size.  This is
the reader used to check the P6 (rolling integration) acceptance record.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REPORT = ROOT / "reports" / "rolling" / "timed_pareto_transfer.json"


def summarise(path: Path) -> str:
    rep = json.load(io.open(path, encoding="utf-8"))
    cfg = rep["config"]
    hist = rep["history"]
    out: list[str] = []
    out.append(f"report      : {path}")
    out.append(f"status      : {rep['status']}  snapshots={len(hist)}")
    out.append(
        "config      : "
        f"n_beds={cfg['n_beds']} sample={cfg['sample_size_actual']} "
        f"levels={cfg['levels']} move_levels={cfg['move_levels']}"
    )
    out.append(
        "transfer    : "
        f"sofa_max={cfg.get('sofa_transfer_max')} "
        f"min_icu_hours={cfg.get('min_icu_hours')} "
        f"max_transfers={cfg.get('max_transfers')}"
    )
    out.append("")
    header = (
        f"{'step':>4} {'hour':>4} {'grid':>5} {'feas':>5} {'front':>5} {'ratio':>6} "
        f"{'HV':>10} {'knee':>10} {'prom':>6} {'f0':>3} {'f1':>7} {'f4':>3} {'f5':>3}"
    )
    out.append(header)
    out.append("-" * len(header))
    hvs: list[float] = []
    n_distinct_knee = 0
    for h in hist:
        ev = h.get("objective_values") or {}
        scan = h.get("epsilon_scan") or {}
        hv = scan.get("hypervolume")
        if isinstance(hv, (int, float)):
            hvs.append(float(hv))
        prom = scan.get("knee_prominence")
        if scan.get("knee_source"):
            n_distinct_knee += 1
        out.append(
            f"{h['step']:>4} {h['hour']:>4} {scan.get('n_grid', '-'):>5} "
            f"{scan.get('n_feasible', '-'):>5} {scan.get('n_nondominated', '-'):>5} "
            f"{scan.get('nondominated_ratio', '-'):>6} "
            f"{(f'{hv:.6f}' if isinstance(hv, (int, float)) else '-'):>10} "
            f"{str(scan.get('knee_source') or '-'):>10} "
            f"{(f'{prom:.4f}' if isinstance(prom, (int, float)) else '-'):>6} "
            f"{ev.get('occupancy', '-'):>3} {ev.get('wait', '-'):>7} "
            f"{ev.get('zone_mismatch', '-'):>3} {h.get('f5_move', 0):>3}"
        )
    out.append("")
    out.append("totals")
    out.append(f"  sum f0 (occupancy)        : {sum((h.get('objective_values') or {}).get('occupancy', 0) for h in hist)}")
    out.append(f"  sum f1 (priority served)  : {sum((h.get('objective_values') or {}).get('wait', 0) for h in hist)}")
    out.append(f"  sum f2 (overload)         : {sum((h.get('objective_values') or {}).get('overload', 0) for h in hist)}")
    out.append(f"  sum f3 (balance)          : {sum((h.get('objective_values') or {}).get('balance', 0) for h in hist)}")
    out.append(f"  sum f4 (zone mismatch)    : {sum((h.get('objective_values') or {}).get('zone_mismatch', 0) for h in hist)}")
    out.append(f"  sum f5 (bed moves)        : {sum(h.get('f5_move', 0) for h in hist)}")
    out.append(f"  sum front points          : {sum((h.get('epsilon_scan') or {}).get('n_nondominated', 0) for h in hist)}")
    if hvs:
        out.append(f"  mean hypervolume          : {sum(hvs) / len(hvs):.6f}")
        out.append(f"  hypervolume range         : {min(hvs):.6f} .. {max(hvs):.6f}")
    out.append(
        f"  steps with a distinct knee: {n_distinct_knee}/{len(hist)}"
        "  (rest are linear fronts, no knee)"
    )
    out.append(f"  eligible (person-steps)   : {sum(h.get('n_eligible_transfer', 0) for h in hist)}")
    transferred = hist[-1].get("transferred_total") or []
    out.append(f"  transferred (cumulative)  : {len(transferred)} {transferred}")
    out.append(f"  waiting at end            : {len(hist[-1].get('waiting') or [])}")
    out.append(
        f"  conservation ok           : {all(h.get('patient_conservation') for h in hist)}"
    )
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", nargs="?", type=Path, default=DEFAULT_REPORT)
    args = p.parse_args()
    print(summarise(args.report))


if __name__ == "__main__":
    main()
