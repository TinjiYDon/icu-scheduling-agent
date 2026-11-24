"""调度实验图表（系统 python + matplotlib）。

用法：python experiments/scheduling/src/figures.py --tag _g1
输出：experiments/figures/scheduling/*.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "common"))
import style  # noqa: E402

# experiments/common/style.py 只导出调色板字典 C 和 METHOD_COLORS，
# 没有大写别名/PLAETTE；这里做一层兼容层，避免 import 期 AttributeError。
_C = getattr(style, "C", {}) or {}


def _col(key: str, default: str) -> str:
    return _C.get(key, default)


BLUE = _col("blue", "#2E5AAC")
ORANGE = _col("orange", "#E8833A")
TEAL = _col("teal", "#2A9D8F")
RED = _col("red", "#C8443F")
GOLD = _col("gold", "#D9A521")
GRAY = _col("gray", "#8A8F98")
PURPLE = _col("purple", "#6B5B95")
GREEN = _col("green", "#4C9F70")
PALETTE = [BLUE, ORANGE, RED]  # 三档负荷配色

RES = ROOT / "scheduling" / "results"
FIG = ROOT / "figures" / "scheduling"

LABEL = {
    "M0_fcfs": "M0 先到先得",
    "M1_greedy_sofa": "M1 贪心·SOFA",
    "M2_greedy_priority": "M2 贪心·风险权重",
    "M3_greedy_reserve": "M3 贪心·专科预留",
    "M4_cpsat_ws": "M4 CP-SAT 加权和",
    "M5_cpsat_lex": "M5 CP-SAT 词典序",
    "M6_cpsat_eps": "M6 CP-SAT ε约束",
    "M7_rolling": "M7 滚动再优化",
}
COLOR = {
    "M0_fcfs": GRAY, "M1_greedy_sofa": BLUE, "M2_greedy_priority": TEAL,
    "M3_greedy_reserve": PURPLE, "M4_cpsat_ws": ORANGE,
    "M5_cpsat_lex": GOLD, "M6_cpsat_eps": RED, "M7_rolling": GREEN,
}
LOAD_LABEL = {80: "宽松档（目标 80%）", 92: "紧张档（目标 92%）", 98: "危机档（目标 98%）"}


def load_raw(tag: str) -> pd.DataFrame:
    df = pd.read_csv(RES / f"bench_raw{tag}.csv")
    df["load"] = df["scenario"].str.extract(r"scenario_(\d+)_")[0].astype(int)
    df["seed"] = df["scenario"].str.extract(r"seed(\d+)")[0].astype(int)
    return df


def fig_main_bars(df: pd.DataFrame) -> None:
    methods = [m for m in LABEL if m in df["method"].unique()]
    loads = sorted(df["load"].unique())
    panels = [("hr_wait_mean", "高危病人平均等待（h）", False),
              ("hr_within6", "6h 内安置率", True),
              ("wait_mean", "全员平均等待（h）", False)]
    f, axes = plt.subplots(1, 3, figsize=(13.5, 4.3))
    x = np.arange(len(methods))
    w = 0.26
    for ax, (m, title, is_rate) in zip(axes, panels):
        for k, load in enumerate(loads):
            sub = df[df["load"] == load]
            means = [sub.loc[sub.method == meth, m].mean() for meth in methods]
            errs = [sub.loc[sub.method == meth, m].std(ddof=1) for meth in methods]
            ax.bar(x + (k - 1) * w, means, w, yerr=errs, capsize=2,
                   label=LOAD_LABEL.get(load, str(load)), alpha=0.9,
                   color=PALETTE[k % len(PALETTE)])
            if is_rate:
                for xi, v, e in zip(x + (k - 1) * w, means, errs):
                    ee = 0.0 if (e is None or e != e) else float(e)  # NaN 保护
                    ax.text(xi, v + ee + 0.018, f"{v:.0%}", ha="center", va="bottom",
                            fontsize=6.2, zorder=6, color=style.C.get("ink", "#1B1F24"))
        ax.set_xticks(x)
        ax.set_xticklabels([LABEL[m2] for m2 in methods], rotation=32, ha="right", fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", alpha=0.25)
        if is_rate:
            ax.set_ylim(0, 1.0)
            ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    axes[0].legend(frameon=False, fontsize=8, title="负荷档", title_fontsize=8)
    f.tight_layout()
    style.save(f, FIG / "fig_sched_main_bars.png")


def fig_ecdf(tag: str, load: int = 92) -> None:
    """高危病人等待时间 ECDF（真实逐病人数据，由 dump_waits.py 产出）。

    dump_waits.py 写出的文件名是 waits_<scenario>__<method>.csv（不带 tag），
    这里按 "__" 切出方法名；若存在多个场景，只画第一个（避免把不同到达流混在一张图）。
    """
    files = [p for p in sorted(RES.glob("waits_*.csv")) if "__" in p.name]
    if not files:
        print("[skip] 无 waits_*.csv（先跑 dump_waits.py）")
        return
    scen = sorted({p.stem.split("__")[0].replace("waits_", "") for p in files})[0]
    files = [p for p in files if p.stem.split("__")[0].replace("waits_", "") == scen]
    if len(scen) > 3:
        pass
    load = int(scen.split("_")[0]) if scen.split("_")[0].isdigit() else load
    f, ax = plt.subplots(figsize=(6.4, 4.3))
    for p in files:
        meth = p.stem.split("__", 1)[1]
        if meth == "M2_greedy_priority":
            continue  # 与 M1 逐位重合（见正文 5.4）
        d = pd.read_csv(p)
        hr = np.sort(d.loc[d["high_risk"], "wait_h"].to_numpy())
        if len(hr) < 5:
            continue
        ax.step(np.concatenate([[0], hr]), np.concatenate([[0], np.arange(1, len(hr) + 1) / len(hr)]),
                where="post", lw=1.6, color=COLOR.get(meth, GRAY),
                label=LABEL.get(meth, meth))
    ax.axvline(6, ls="--", c=RED, lw=1)
    ax.text(6.2, 0.05, "6h 目标", color=RED, fontsize=8)
    ax.set_xlim(0, 60)
    ax.set_xlabel("高危病人等待时间（h）")
    ax.set_ylabel("累计比例")
    ax.set_title(f"高危病人等待分布（{scen}，{LOAD_LABEL.get(load, load)}）", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.grid(alpha=0.25)
    f.tight_layout()
    style.save(f, FIG / "fig_sched_wait_ecdf.png")


def fig_tradeoff(df: pd.DataFrame) -> None:
    f, ax = plt.subplots(figsize=(6.4, 4.7))
    # M2 与 M1 逐位相同（见正文 5.4），画两条重合线只会糊住图，故只画 M1 并注明
    for meth in LABEL:
        if meth == "M2_greedy_priority":
            continue
        sub = df[df.method == meth]
        if sub.empty:
            continue
        ax.plot(sub.groupby("load")["hr_wait_mean"].mean(),
                sub.groupby("load")["wait_mean"].mean(),
                marker="o", ms=5.5, lw=1.5, color=COLOR[meth], label=LABEL[meth],
                alpha=0.95)
        for load in sorted(sub["load"].unique()):
            s2 = sub[sub.load == load]
            dx, dy = (5, 4) if meth != "M0_fcfs" else (-16, 6)
            ax.annotate(f"{load}%", (s2["hr_wait_mean"].mean(), s2["wait_mean"].mean()),
                        fontsize=6.5, color=COLOR[meth], xytext=(dx, dy),
                        textcoords="offset points")
    ax.set_xlabel("高危病人平均等待（h）↓")
    ax.set_ylabel("全员平均等待（h）↓")
    ax.set_title("效率—公平权衡（左上角更优）", fontsize=10)
    ax.text(0.98, 0.02, "M2（风险权重排序）与 M1 逐位重合，图中省略",
            transform=ax.transAxes, fontsize=6.5, color="#6B7280", ha="right")
    ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="center right")
    ax.grid(alpha=0.25)
    f.tight_layout()
    style.save(f, FIG / "fig_sched_tradeoff.png")


def fig_timeline(tag: str, scenario: str = "scenario_92_seed11") -> None:
    files = {m: RES / "episodes" / f"{scenario}__{m}{tag}.csv" for m in
             ["M0_fcfs", "M1_greedy_sofa", "M4_cpsat_ws", "M7_rolling"]}
    files = {m: p for m, p in files.items() if p.exists()}
    if not files:
        return
    f, axes = plt.subplots(len(files), 1, figsize=(11, 1.75 * len(files)), sharex=True)
    if len(files) == 1:
        axes = [axes]
    for ax, (meth, p) in zip(axes, files.items()):
        d = pd.read_csv(p)
        d = d.iloc[: int(30 * 12)]  # 前 30 天
        t = pd.to_datetime(d["t"])
        ax.fill_between(t, 0, d["occupancy"], color=COLOR[meth], alpha=0.30, label="在床")
        ax.plot(t, d["queue"], color=RED, lw=1.1, label="排队")
        ax.plot(t, d["hr_waiting"], color=GOLD, lw=1.1, ls="--", label="高危排队")
        ax.set_ylim(0, 21)
        ax.set_ylabel("人数", fontsize=8)
        ax.set_title(LABEL[meth], fontsize=8.5, loc="left")
        ax.grid(alpha=0.2)
    axes[0].legend(frameon=False, fontsize=7, ncol=3, loc="upper right")
    axes[-1].set_xlabel("仿真时间（前 30 天）")
    f.tight_layout()
    style.save(f, FIG / "fig_sched_timeline.png")


def fig_pairwise(df: pd.DataFrame) -> None:
    pairs = [("M1_greedy_sofa", "M0_fcfs", "排序规则（M1 vs M0）"),
             ("M4_cpsat_ws", "M1_greedy_sofa", "精确优化（M4 vs M1）"),
             ("M7_rolling", "M4_cpsat_ws", "滚动再优化（M7 vs M4）"),
             ("M3_greedy_reserve", "M1_greedy_sofa", "专科预留（M3 vs M1）")]
    f, axes = plt.subplots(1, 4, figsize=(13, 3.6))
    for ax, (a, b, title) in zip(axes, pairs):
        piv = df.pivot_table(index=["load", "seed"], columns="method", values="hr_wait_mean")
        if a not in piv or b not in piv:
            continue
        loads = sorted(piv.index.get_level_values("load").unique())
        for k, load in enumerate(loads):
            sub = piv.loc[load]
            for s in sub.index:
                ax.scatter(k + (0.12 if s % 2 else -0.12), sub.loc[s, a], s=22,
                           color=ORANGE if a.startswith(("M4", "M7")) else BLUE,
                           alpha=0.85, zorder=3)
                ax.scatter(k, sub.loc[s, b], s=14, color=GRAY, alpha=0.6, zorder=2)
            ax.vlines(k, sub[b].min(), sub[b].max(), color=GRAY, lw=1, alpha=0.4)
        ax.set_xticks(range(len(loads)))
        ax.set_xticklabels([str(l) for l in loads], fontsize=8)
        ax.set_xlabel("负荷档（%）", fontsize=8)
        ax.set_title(title, fontsize=8.5)
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("高危病人平均等待（h）")
    f.tight_layout()
    style.save(f, FIG / "fig_sched_pairwise.png")


def fig_pareto_eps(tag: str) -> None:
    """ε-约束前沿：x=高危平均等待、y=全员平均等待，另有 M1/M4 参照点。"""
    p = RES / f"pareto_sched{tag}.csv"
    if not p.exists():
        print(f"[skip] 无 {p.name}（先跑 run_pareto.py）")
        return
    d = pd.read_csv(p)
    d["eps_cap"] = pd.to_numeric(d["eps_cap"], errors="coerce").fillna(-1).astype(int)
    front = d[d["eps_cap"] >= 0]
    refs = d[d["eps_cap"] < 0]
    groups = "scenario" if front["scenario"].nunique() > 1 else "load"
    f, ax = plt.subplots(figsize=(6.4, 4.5))
    for k, (key, g) in enumerate(front.groupby(groups)):
        g = g.sort_values("eps_cap")
        col = PALETTE[k % len(PALETTE)]
        ax.plot(g["hr_wait_mean"], g["wait_mean"], marker="o", ms=4.5, lw=1.5, color=col,
                label=(f"ε 扫描 [{key}]" if groups == "scenario" else f"ε 扫描（负荷 {key}%）"))
        for r in g.itertuples():
            ax.annotate(f"ε={r.eps_cap}", (r.hr_wait_mean, r.wait_mean), fontsize=6,
                        color=col, xytext=(3, 4), textcoords="offset points")
    for r in refs.itertuples():
        ax.scatter([r.hr_wait_mean], [r.wait_mean], marker="*", s=110,
                   color=COLOR.get(r.method, GRAY), zorder=4,
                   label=f"参照 {LABEL.get(r.method, r.method)}")
        ax.annotate(LABEL.get(r.method, r.method).split(" ")[0],
                    (r.hr_wait_mean, r.wait_mean), fontsize=6, color=COLOR.get(r.method, GRAY),
                    xytext=(4, -9), textcoords="offset points")
    ax.set_xlabel("高危病人平均等待（h）↓")
    ax.set_ylabel("全员平均等待（h）↓")
    ax.set_title("ε-约束扫描（紧张档）：0.5 s 预算下点序非单调，尚不构成 Pareto 前沿", fontsize=9)
    ax.legend(frameon=False, fontsize=7.5, ncol=2)
    ax.grid(alpha=0.25)
    f.tight_layout()
    style.save(f, FIG / "fig_sched_pareto_eps.png")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_g1")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()
    style.apply()
    # style.py 默认 200dpi，报告要求 300dpi
    from matplotlib import rcParams
    rcParams["savefig.dpi"] = args.dpi
    FIG.mkdir(parents=True, exist_ok=True)
    cjk = style._pick_cjk_font()
    print(f"[font] 中文字体 = {cjk}   dpi = {args.dpi}")
    if cjk is None:
        print("[warn] 未找到中文字体，图中中文会显示为方框")
    df = load_raw(args.tag)
    fig_main_bars(df)
    fig_ecdf(df)
    fig_tradeoff(df)
    fig_pairwise(df)
    fig_timeline(args.tag)
    fig_pareto_eps(args.tag)
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
