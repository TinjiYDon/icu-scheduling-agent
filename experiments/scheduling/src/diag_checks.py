"""一次性诊断：M1/M2 排序是否等价、M7 挤出事件、需求侧利用率。

用法：python experiments/scheduling/src/diag_checks.py

输出（只读，不写结果文件，除了打印）：
  A. patience_all.csv 中 priority 与 sofa0 的 Spearman / Kendall 相关
  B. 同场景 M1 与 M2 的排序是否逐病人一致（排序一致性比 Jaccard 更直接）
  C. M7 在 92_seed11 的挤出事件：cp_assign 是否返回空解（求解器未给出可行解）
  D. 需求侧利用率（ΣLOS/24/(20×365)）vs 仿真时间加权占用
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
from sim import N_BEDS, cp_assign, run_episode, summarize  # noqa: E402

DATA = SRC.parent / "data"
RES = SRC.parent / "results"


def part_a() -> None:
    print("\n=== A. priority vs sofa0 排序相关（patients_all.csv） ===")
    df = pd.read_csv(DATA / "patients_all.csv")
    print("columns:", list(df.columns))
    pcol = next((c for c in ("priority", "priority_weight", "prio") if c in df.columns), None)
    if pcol is None or "sofa0" not in df.columns:
        print(f"  [skip] 找不到优先级列（有 {list(df.columns)}）")
        return
    print(f"  优先级列 = {pcol}")
    d = df[["sofa0", pcol]].dropna()
    rho = stats.spearmanr(d["sofa0"], d[pcol])
    tau = stats.kendalltau(d["sofa0"], d[pcol])
    pr = stats.pearsonr(d["sofa0"], d[pcol])
    print(f"  n={len(d)}  Spearman rho={rho.statistic:.4f} (p={rho.pvalue:.3g})")
    print(f"            Kendall tau={tau.statistic:.4f} (p={tau.pvalue:.3g})")
    print(f"            Pearson r={pr[0]:.4f}")
    print(f"  {pcol} 唯一值 {df[pcol].nunique()} / sofa0 唯一值 {df['sofa0'].nunique()}")
    # 排序完全一致的比例（同分视为一致）
    a = d["sofa0"].rank(method="average")
    b = d[pcol].rank(method="average")
    print(f"  秩相关 ρ(rank) = {stats.spearmanr(a, b).statistic:.4f}")


def _prio_col(df: pd.DataFrame) -> str | None:
    return next((c for c in ("priority", "priority_weight", "prio") if c in df.columns), None)


def part_b() -> None:
    print("\n=== B. M1 vs M2 逐病人等待是否完全相同（3 场景抽样） ===")
    tot, same = 0, 0
    for sc_name in ("80_seed11", "92_seed11", "98_seed11"):
        sc = json.loads((DATA / f"scenario_{sc_name}.json").read_text(encoding="utf-8"))
        waits = {}
        for meth in ("M1_greedy_sofa", "M2_greedy_priority"):
            ep = run_episode(sc, meth, time_limit=0.5)
            waits[meth] = {p.pid: ((p.admit - p.arrival).total_seconds() / 3600.0
                                   if p.admit else np.nan) for p in ep.patients.values()}
        a = pd.Series(waits["M1_greedy_sofa"])
        b = pd.Series(waits["M2_greedy_priority"])
        eq = np.allclose(a.fillna(-1), b.fillna(-1))
        tot += 1
        same += int(eq)
        print(f"  {sc_name}: 逐病人等待完全相同 = {eq}  (max|Δ|={np.nanmax(np.abs(a - b)):.3e})")
    print(f"  结论：{same}/{tot} 场景上 M1 与 M2 逐病人等待完全一致")


def part_c() -> None:
    print("\n=== C. M7 挤出事件定位（92_seed11） ===")
    calls = {"n": 0, "empty": 0, "empty_sizes": []}
    orig = cp_assign

    def wrapped(*a, **kw):  # noqa: ANN001
        out = orig(*a, **kw)
        if kw.get("allow_moves"):
            calls["n"] += 1
            if not out:
                calls["empty"] += 1
                calls["empty_sizes"].append(len(a[1]) if len(a) > 1 else -1)
        return out

    import sim as _sim
    _sim.cp_assign = wrapped
    sc = json.loads((DATA / "scenario_92_seed11.json").read_text(encoding="utf-8"))
    ep = run_episode(sc, "M7_rolling", time_limit=0.5)
    rec = summarize(ep)
    print(f"  M7 cp_assign 调用 {calls['n']} 次，返回空解 {calls['empty']} 次 "
          f"(队列规模 {calls['empty_sizes'][:8]})")
    print(f"  M7: hr_wait={rec['hr_wait_mean']:.3f} displaced={rec['displaced']} "
          f"moved={rec['moved']} solve_ms={rec['solve_ms_mean']:.1f}")
    b = pd.read_csv(RES / "bench_raw_g1.csv")
    r = b[(b.scenario == "scenario_92_seed11") & (b.method == "M7_rolling")].iloc[0]
    print(f"  bench: hr_wait={r['hr_wait_mean']:.3f} displaced={int(r['displaced'])} "
          f"moved={int(r['moved'])}")
    _sim.cp_assign = orig


def part_d() -> None:
    print("\n=== D. 需求侧利用率 vs 仿真占用（含右端截断与排队的影响） ===")
    import datetime as dt
    b = pd.read_csv(RES / "bench_raw_g1.csv")
    for p in sorted(DATA.glob("scenario_*.json")):
        if p.name == "scenario_meta.json":
            continue
        sc = json.loads(p.read_text(encoding="utf-8"))
        los = [(dt.datetime.fromisoformat(x["depart"]) - dt.datetime.fromisoformat(x["arrival"])
                ).total_seconds() / 3600 for x in sc["patients"]]
        demand_util = sum(los) / 24 / (N_BEDS * 365)
        g = b[b.scenario == sc["name"]]
        sim_util = g["utilization"].mean()
        unassigned = g["unassigned"].mean()
        print(f"  {sc['name']:22s} n={len(los):5d} ΣLOS={sum(los):8.0f}h "
              f"需求侧={demand_util:.4f}  仿真={sim_util:.4f}  未安置均值={unassigned:.1f}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "abcd"
    if "a" in which:
        part_a()
    if "b" in which:
        part_b()
    if "c" in which:
        part_c()
    if "d" in which:
        part_d()
