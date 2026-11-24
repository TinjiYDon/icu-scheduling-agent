"""调度实验结果聚合：多种子均值/CI、配对检验、Pareto 前沿。

输入：experiments/scheduling/results/bench_raw*.csv（run_bench.py 产出）
输出：metrics_sched.json / table_sched.csv / pairwise_sched.csv / pareto_sched.csv
"""
from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RES = Path(__file__).resolve().parents[1] / "results"
METRICS = ["hr_wait_mean", "hr_wait_median", "hr_wait_p90", "hr_within6", "wait_mean",
           "avg_queue", "max_queue", "utilization", "benefit_served", "gini_hr_wait",
           "iso_util", "vent_device_util", "moved", "displaced", "fallbacks", "unassigned",
           "solve_ms_mean", "solve_ms_total"]
LOWER_BETTER = {"hr_wait_mean", "hr_wait_median", "hr_wait_p90", "wait_mean",
                "avg_queue", "max_queue", "gini_hr_wait", "moved", "displaced", "fallbacks",
                "unassigned", "solve_ms_mean", "solve_ms_total"}


def load_raw(tag: str) -> pd.DataFrame:
    p = RES / f"bench_raw{tag}.csv"
    df = pd.read_csv(p)
    df["load"] = df["scenario"].str.extract(r"scenario_(\d+)_")[0].astype(int)
    df["seed"] = df["scenario"].str.extract(r"seed(\d+)")[0].astype(int)
    return df


def agg(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["load", "method"])
    cols = [c for c in METRICS if c in df.columns]
    out = g[cols].agg(["mean", "std", "count"]).round(4)
    out.columns = [f"{m}_{s}" for m, s in out.columns]
    return out.reset_index()


def paired(df: pd.DataFrame, a: str, b: str, metric: str) -> dict:
    """按 (load, seed) 配对比较 a 与 b。"""
    piv = df.pivot_table(index=["load", "seed"], columns="method", values=metric)
    if a not in piv or b not in piv:
        return {}
    d = (piv[a] - piv[b]).dropna()
    if len(d) < 3:
        return {"n": int(len(d)), "mean_delta": float(d.mean()) if len(d) else np.nan}
    # 整体 + 分负荷
    res = {"n": int(len(d)), "mean_delta": float(d.mean()),
           "median_delta": float(d.median()),
           "rel_delta": float(d.mean() / piv[b].mean()) if piv[b].mean() else np.nan}
    try:
        w = stats.wilcoxon(d)
        res["wilcoxon_p"] = float(w.pvalue)
    except Exception:
        res["wilcoxon_p"] = np.nan
    for load in sorted(piv.index.get_level_values("load").unique()):
        sub = piv.loc[load]
        dd = (sub[a] - sub[b]).dropna()
        res[f"load{load}_delta"] = float(dd.mean()) if len(dd) else np.nan
    return res


def bootstrap_ci(x: np.ndarray, n: int = 2000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    if len(x) < 2:
        return (float("nan"), float("nan"))
    means = [rng.choice(x, size=len(x), replace=True).mean() for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", default=["_g1"])
    args = ap.parse_args()
    frames = [load_raw(t) for t in args.tags if (RES / f"bench_raw{t}.csv").exists()]
    df = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["scenario", "method"], keep="last")
    table = agg(df)
    table.to_csv(RES / "table_sched.csv", index=False)

    # 主比较：M1 vs M0（是否按病情排序）、M4 vs M1（精确优化 vs 贪心）、
    #           M7 vs M4（滚动再优化）、M3 vs M1（预留策略）
    pairs = [("M1_greedy_sofa", "M0_fcfs"), ("M2_greedy_priority", "M0_fcfs"),
             ("M3_greedy_reserve", "M1_greedy_sofa"), ("M4_cpsat_ws", "M1_greedy_sofa"),
             ("M7_rolling", "M4_cpsat_ws"), ("M7_rolling", "M1_greedy_sofa")]
    rows = []
    for a, b in pairs:
        for m in ["hr_wait_mean", "hr_within6", "wait_mean", "gini_hr_wait",
                  "avg_queue", "benefit_served", "utilization", "moved"]:
            r = paired(df, a, b, m)
            if r:
                rows.append({"a": a, "b": b, "metric": m, **r})
    pw = pd.DataFrame(rows)
    pw.to_csv(RES / "pairwise_sched.csv", index=False)

    out = {"n_runs": int(len(df)), "scenarios": sorted(df["scenario"].unique().tolist()),
           "methods": sorted(df["method"].unique().tolist()),
           "table": table.to_dict(orient="records"),
           "pairwise": pw.to_dict(orient="records")}

    # 各负荷下的均值 + bootstrap CI
    # 主指标（报告正文按名取用，字段名不可改）+ 附加指标（合规性/耗时，同样给 mean/lo/hi/n）
    ci_metrics = ["hr_wait_mean", "hr_within6", "wait_mean", "avg_queue",
                  "utilization", "gini_hr_wait"]
    extra_metrics = ["solve_ms_mean", "solve_ms_total", "moved", "displaced",
                     "unassigned", "max_queue", "benefit_served", "iso_util",
                     "vent_device_util", "hr_wait_p90"]
    per_load = {}
    for lv, g in df.groupby("load"):
        d = {}
        for meth, gg in g.groupby("method"):
            e = {}
            for m in ci_metrics + extra_metrics:
                if m not in gg:
                    continue
                lo, hi = bootstrap_ci(gg[m].to_numpy())
                e[m] = {"mean": float(gg[m].mean()), "lo": lo, "hi": hi, "n": int(len(gg))}
            d[meth] = e
        per_load[int(lv)] = d
    out["per_load"] = per_load
    (RES / "metrics_sched.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    print(table[["load", "method", "hr_wait_mean_mean", "hr_within6_mean",
                 "wait_mean_mean", "avg_queue_mean", "utilization_mean",
                 "gini_hr_wait_mean"]].round(3).to_string(index=False))
    print("\n" + pw[["a", "b", "metric", "mean_delta", "wilcoxon_p"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
