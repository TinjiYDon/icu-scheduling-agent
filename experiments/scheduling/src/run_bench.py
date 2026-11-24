"""调度对比实验批量运行器。

用法：
  python experiments\scheduling\src\run_bench.py --scenarios 80_seed11 --methods M0_fcfs M1_greedy_sofa
  python experiments\scheduling\src\run_bench.py --all --time-limit 1.0
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
from sim import N_BEDS, run_episode, summarize  # noqa: E402

DATA = SRC.parent / "data"
RES = SRC.parent / "results"

METHODS = ["M0_fcfs", "M1_greedy_sofa", "M2_greedy_priority", "M3_greedy_reserve",
           "M4_cpsat_ws", "M5_cpsat_lex", "M6_cpsat_eps", "M7_rolling"]


def load_scenario(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def jaccard_steps(a: pd.DataFrame, b: pd.DataFrame) -> float:
    """两个方法在相同时间点上"在床病人集合"的平均 Jaccard（衡量决策差异）。"""
    sa = {r.t: set(str(r.assigned).split("|")) - {""} for r in a.itertuples()}
    sb = {r.t: set(str(r.assigned).split("|")) - {""} for r in b.itertuples()}
    vals = []
    for t in sorted(set(sa) & set(sb)):
        inter = len(sa[t] & sb[t])
        union = len(sa[t] | sb[t])
        vals.append(inter / union if union else 1.0)
    return float(np.mean(vals)) if vals else 1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--scenarios", nargs="*", default=[])
    ap.add_argument("--methods", nargs="*", default=METHODS)
    ap.add_argument("--time-limit", type=float, default=2.0)
    ap.add_argument("--max-steps", type=int, default=0, help="冒烟测试用，>0 时截断")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    files = sorted(DATA.glob("scenario_*.json"))
    files = [f for f in files if f.name != "scenario_meta.json"]
    if args.scenarios:
        files = [f for f in files if any(s in f.name for s in args.scenarios)]
    if args.all:
        pass
    assert files, "no scenario files"

    RES.mkdir(parents=True, exist_ok=True)
    (RES / "episodes").mkdir(exist_ok=True)
    rows, traces = [], {}
    t_start = time.time()
    for f in files:
        sc = load_scenario(f)
        if args.max_steps:
            t0 = sc["t0"]
            import datetime as _dt
            t1 = (_dt.datetime.fromisoformat(t0) + _dt.timedelta(days=14)).isoformat()
            sc["t1"] = min(sc["t1"], t1)
        for method in args.methods:
            st = time.time()
            ep = run_episode(sc, method, time_limit=args.time_limit)
            rec = summarize(ep)
            rec["elapsed_s"] = round(time.time() - st, 2)
            rows.append(rec)
            trace = pd.DataFrame(ep.steps)
            traces[(sc["name"], method)] = trace
            trace.to_csv(RES / "episodes" / f"{sc['name']}__{method}{args.tag}.csv", index=False)
            print(f"[run] {sc['name']:24s} {method:18s} "
                  f"hr_wait={rec['hr_wait_mean']:6.2f}h queue={rec['avg_queue']:5.2f} "
                  f"util={rec['utilization']:.3f} undisplaced={rec['displaced']} "
                  f"t={rec['elapsed_s']:.1f}s solve={rec['solve_ms_mean']:.0f}ms")

    df = pd.DataFrame(rows)
    df.to_csv(RES / f"bench_raw{args.tag}.csv", index=False)

    # 决策差异（H5）：M1 vs M2 / M4 vs M7 的同刻在床集合 Jaccard
    jac = []
    for (name, _m), _tr in traces.items():
        pass
    for name in df["scenario"].unique():
        for a, b in [("M1_greedy_sofa", "M2_greedy_priority"), ("M4_cpsat_ws", "M7_rolling")]:
            ta, tb = traces.get((name, a)), traces.get((name, b))
            if ta is not None and tb is not None and len(ta) and len(tb):
                jac.append({"scenario": name, "pair": f"{a}|{b}", "jaccard": jaccard_steps(ta, tb)})
    if jac:
        pd.DataFrame(jac).to_csv(RES / f"decision_jaccard{args.tag}.csv", index=False)

    print(f"\n[done] {len(rows)} runs in {time.time() - t_start:.1f}s -> {RES}")
    print(df.groupby("method")[["hr_wait_mean", "hr_within6", "avg_queue", "utilization",
                                "benefit_served", "displaced"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
