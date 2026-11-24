"""ε-约束 Pareto 前沿：固定场景，扫 M6_cpsat_eps 的 ε 上限，并把 M1/M4 作为参照点。

用法：
  python experiments/scheduling/src/run_pareto.py --scenarios 92_seed11 --eps 0 1 2 3 4 6 8
  python experiments/scheduling/src/run_pareto.py --scenarios 92_seed11 92_seed22 --tag _g1

产出：results/pareto_sched<tag>.csv
  列：load, eps_cap, hr_wait_mean, wait_mean, hr_within6, benefit_served,
      method, scenario, moved, displaced, unassigned, solve_ms_mean, elapsed_s
  参照点（M1 / M4）的 eps_cap 记为 -1，method 列区分。

说明：ε 只对 M6 有意义。ε=0 表示"高危未安置人数上限 0"（最公平端），
ε 越大越偏向总收益，因此该曲线就是"可显式交易的效率—公平前沿"。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
from sim import run_episode, summarize  # noqa: E402

DATA = SRC.parent / "data"
RES = SRC.parent / "results"
COLS = ["load", "eps_cap", "hr_wait_mean", "wait_mean", "hr_within6", "benefit_served",
        "method", "scenario", "moved", "displaced", "unassigned", "solve_ms_mean",
        "elapsed_s"]


def _row(rec: dict, load: int, eps: int, method: str, scenario: str,
         elapsed: float) -> dict:
    return {"load": load, "eps_cap": eps,
            "hr_wait_mean": rec["hr_wait_mean"], "wait_mean": rec["wait_mean"],
            "hr_within6": rec["hr_within6"], "benefit_served": rec["benefit_served"],
            "method": method, "scenario": scenario, "moved": rec["moved"],
            "displaced": rec["displaced"], "unassigned": rec["unassigned"],
            "solve_ms_mean": rec["solve_ms_mean"], "elapsed_s": elapsed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", default=["92_seed11"])
    ap.add_argument("--eps", nargs="+", type=int, default=[0, 1, 2, 3, 4, 6, 8])
    ap.add_argument("--time-limit", type=float, default=0.5)
    ap.add_argument("--tag", default="_g1")
    ap.add_argument("--refs", nargs="+", default=["M1_greedy_sofa", "M4_cpsat_ws"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else RES / f"pareto_sched{args.tag}.csv"
    bench_p = RES / f"bench_raw{args.tag}.csv"
    bench = pd.read_csv(bench_p) if bench_p.exists() else None

    rows: list[dict] = []
    t_all = time.time()
    for sc_name in args.scenarios:
        sp = DATA / f"scenario_{sc_name}.json"
        sc = json.loads(sp.read_text(encoding="utf-8"))
        load = int(sc_name.split("_")[0])
        print(f"\n=== {sc['name']}  (n_patients={len(sc['patients'])}, load={load}%) ===")
        for eps in args.eps:
            st = time.time()
            ep = run_episode(sc, "M6_cpsat_eps", time_limit=args.time_limit, eps_cap=eps)
            rec = summarize(ep)
            el = time.time() - st
            rows.append(_row(rec, load, eps, "M6_cpsat_eps", sc["name"], round(el, 2)))
            print(f"  [eps={eps}] hr_wait={rec['hr_wait_mean']:7.3f}h "
                  f"wait={rec['wait_mean']:7.3f}h within6={rec['hr_within6']:.4f} "
                  f"benefit={rec['benefit_served']:8.1f} solved={rec['solve_ms_mean']:6.1f}ms "
                  f"({el:.1f}s)")
        for meth in args.refs:
            st = time.time()
            ep = run_episode(sc, meth, time_limit=args.time_limit)
            rec = summarize(ep)
            el = time.time() - st
            rows.append(_row(rec, load, -1, meth, sc["name"], round(el, 2)))
            print(f"  [ref {meth}] hr_wait={rec['hr_wait_mean']:7.3f}h "
                  f"wait={rec['wait_mean']:7.3f}h within6={rec['hr_within6']:.4f} "
                  f"({el:.1f}s)")
            # 回归校验：重跑结果必须与 bench_raw 完全一致（同场景同方法同 time_limit）
            if bench is not None:
                b = bench[(bench["scenario"] == sc["name"]) & (bench["method"] == meth)]
                if not b.empty:
                    for m in ("hr_wait_mean", "wait_mean", "hr_within6", "benefit_served"):
                        d = abs(float(b.iloc[0][m]) - rec[m])
                        flag = "OK" if d < 1e-9 else "MISMATCH"
                        print(f"      regress {m}: bench={float(b.iloc[0][m]):.6f} "
                              f"rerun={rec[m]:.6f} d={d:.2e} {flag}")

    df = pd.DataFrame(rows)[COLS]
    df.to_csv(out_path, index=False)
    print(f"\n[done] {len(df)} runs in {time.time() - t_all:.1f}s -> {out_path}")
    print(df[["scenario", "method", "eps_cap", "hr_wait_mean", "wait_mean",
              "hr_within6", "benefit_served"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
