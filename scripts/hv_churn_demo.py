"""H10 演示：滚动 HV–churn（合成前沿 + 合成换床）。

不读数据库、不跑求解器；真实前沿/分配由 `application.run_moo_phase3` 或
`reports/moo/summary_*.json` / `reports/rolling_contrast.json` 注入。

    python scripts/hv_churn_demo.py --steps 5 --seed 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # 允许 `python scripts/hv_churn_demo.py` 直接跑
    sys.path.insert(0, str(ROOT))

from domain.optimizer.pareto_decision import nondominated_indices  # noqa: E402
from domain.optimizer.pareto_io import (  # noqa: E402
    FrontSnapshot,
    hv_churn_series,
    normalize_points,
    summarize_hv_churn,
)

OUT = ROOT / "reports" / "pareto_decision"


def make_candidates(n_solutions: int = 20, n_objectives: int = 2, seed: int = 0) -> np.ndarray:
    """候选解池（Dirichlet 采样），id 固定为 `sol_<index>`，跨步可追踪。"""
    rng = np.random.default_rng(seed)
    return rng.dirichlet(np.ones(n_objectives), size=max(n_solutions, 1))


def step_front(
    base: np.ndarray,
    rng: np.random.Generator,
    noise: float = 0.06,
) -> tuple[list[str], np.ndarray]:
    """在候选池上叠加小幅扰动，再取非支配子集（模拟滚动重解的集合抖动）。"""
    jittered = np.clip(base + rng.normal(0.0, noise, base.shape), 0.0, 1.0)
    keep = nondominated_indices(jittered)
    ids = [f"sol_{i}" for i in keep]
    return ids, jittered[keep]


def make_assignments(n_patients: int = 20, n_beds: int = 20) -> dict:
    """第 0 步分配：patient_i → bed_(i mod n_beds)。"""
    n_beds = max(n_beds, 1)
    return {f"p{i}": f"b{i % n_beds}" for i in range(max(n_patients, 1))}


def move_beds(assign: dict, ratio: float, rng: np.random.Generator, n_beds: int) -> dict:
    """把约 `ratio` 的患者换到**别的**床（同床不算换）。"""
    out = dict(assign)
    keys = sorted(out)
    if not keys or n_beds < 2:
        return out
    n_move = max(1, int(round(len(keys) * ratio)))
    for key in rng.choice(keys, size=min(n_move, len(keys)), replace=False):
        key = str(key)
        candidates = [b for b in (f"b{i}" for i in range(n_beds)) if b != out[key]]
        out[key] = str(rng.choice(candidates))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="H10 rolling HV–churn demo (synthetic)")
    ap.add_argument("--steps", type=int, default=5)
    ap.add_argument("--solutions", type=int, default=20)
    ap.add_argument("--patients", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output", default="")
    args = ap.parse_args()

    if args.steps < 1:
        ap.error("--steps 必须 >= 1")

    n_beds = max(args.patients, 1)
    base = make_candidates(args.solutions, 2, seed=args.seed)
    rng = np.random.default_rng(args.seed + 1)

    fronts: list[FrontSnapshot] = []
    assignments: list[dict] = []
    current = make_assignments(args.patients, n_beds)
    for step in range(args.steps):
        ids, raw = step_front(base, rng)
        snap = FrontSnapshot(
            step=step,
            ids=ids,
            points=normalize_points(raw),
            raw=[
                {"values": {"f0": float(a), "f1": float(b)}, "source": sid}
                for sid, (a, b) in zip(ids, raw)
            ],
        )
        fronts.append(snap)
        assignments.append(dict(current))
        current = move_beds(current, 0.10, rng, n_beds)

    series = hv_churn_series(fronts, assignments)
    summary = summarize_hv_churn(series)

    print("| step | n_front | hv | turnover | churn |")
    print("|---:|---:|---:|---:|---:|")
    for row in series:
        print(
            f"| {row['step']} | {row['n_front']} | {row['hv']} | "
            f"{row['turnover']} | {row['churn']} |"
        )
    print()
    print("| summary | value |")
    print("|---|---:|")
    for key in ("n_steps", "mean_hv", "total_churn", "mean_turnover", "last_hv"):
        print(f"| {key} | {summary[key]} |")

    output = {
        "config": {
            "steps": args.steps,
            "solutions": args.solutions,
            "patients": args.patients,
            "seed": args.seed,
            "objectives": 2,
            "bed_churn_ratio": 0.10,
            "normalization": "per-step min-max to [0,1] (max)",
            "ref_point": [0.0, 0.0],
        },
        "series": series,
        "summary": summary,
        "note": "synthetic only; not ICU/MIMIC evidence",
    }

    path = Path(args.output) if args.output else OUT / "hv_churn_demo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
