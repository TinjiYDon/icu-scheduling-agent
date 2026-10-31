"""H10 演示：在合成前沿上计算 HV / VoF / MMR / 稳定性指标。

不读数据库、不跑求解器；用于验证实现与展示指标。真实前沿由
`application.run_moo_phase3` 或 `reports/moo/summary_*.json` 注入。

    python scripts/pareto_decision_demo.py --n 60 --seed 0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from domain.optimizer.pareto_decision import (
    assignment_churn,
    front_turnover,
    nondominated_indices,
    simplex_weights,
    summarize_front,
)

OUT = Path(__file__).resolve().parents[1] / "reports" / "pareto_decision"


def make_front(n: int = 60, m: int = 2, seed: int = 0) -> np.ndarray:
    """合成一个互不支配的前沿：m 维、和约束下的随机点。"""
    rng = np.random.default_rng(seed)
    pts = rng.dirichlet(np.ones(m), size=n * 3)
    keep = nondominated_indices(pts)
    pts = pts[keep][:n]
    return pts


def main() -> int:
    ap = argparse.ArgumentParser(description="H10 Pareto decision demo")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--objectives", type=int, default=2)
    ap.add_argument("--weights", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="demo")
    args = ap.parse_args()

    front = make_front(args.n, args.objectives, args.seed)
    # 现状：固定权重解（模拟 λ 加权和给出的单解）
    w0 = np.ones(args.objectives) / args.objectives
    single = front[int(np.argmax(front @ w0))]
    weights = simplex_weights(args.weights, args.objectives, seed=args.seed + 1)

    summary = summarize_front(front, single, weights)
    output = summary.as_dict()
    output.update({
        "tag": args.tag,
        "single": [round(float(x), 6) for x in single],
        "note": "synthetic front; metrics are decision-layer only",
    })

    print(f"front={summary.n_front} objectives={summary.n_objectives} "
          f"single={np.round(single, 4).tolist()}")
    print("| metric | value |")
    print("|---|---:|")
    print(f"| hypervolume | {summary.hypervolume} |")
    print(f"| VoF | {summary.VoF} |")
    print(f"| CoM | {summary.CoM} |")
    print("| MMR top-5 (index, max_regret) | "
          + "; ".join(f"{r['index']}={r['max_regret']}" for r in summary.mmr_top) + " |")

    # 稳定性示例：两期结果的前沿周转/换床率（合成）
    ids_t = [f"s{i}" for i in range(summary.n_front)]
    ids_t1 = ids_t[:-1] + ["s_new"]
    output["front_turnover_example"] = front_turnover(ids_t, ids_t1)
    output["assignment_churn_example"] = assignment_churn(
        {f"p{i}": f"b{i%7}" for i in range(20)},
        {f"p{i}": (f"b{i%7}" if i % 5 else f"b{(i+1)%7}") for i in range(20)},
    )
    print(f"| front_turnover(example) | {output['front_turnover_example']} |")
    print(f"| assignment_churn(example) | {output['assignment_churn_example']} |")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{args.tag}.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
