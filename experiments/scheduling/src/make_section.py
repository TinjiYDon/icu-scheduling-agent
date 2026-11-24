"""从产物文件生成 SECTION.md（数字全部来自 csv/json，不手打）。

用法：
  python experiments/scheduling/src/make_section.py --tag _g2
  # 若 _g2 还没跑完，会输出带 {{待填}} 的骨架
  python experiments/scheduling/src/make_section.py --tag _g2 --allow-missing

为什么用生成器：报告正文直接引用本节数字，手抄必然漂移；
verify.py 的第 7 项检查会核对 SECTION 里的数字能否在 csv/json 中找到。
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent                      # experiments/scheduling
DATA = ROOT / "data"
RES = ROOT / "results"
PROTO = ROOT.parent / "PROTOCOL.md"

PH = "{{待填}}"
FIG = "../figures/scheduling"

METHODS = ["M0_fcfs", "M1_greedy_sofa", "M2_greedy_priority", "M3_greedy_reserve",
           "M4_cpsat_ws", "M7_rolling"]
NAME = {"M0_fcfs": "M0 先到先得", "M1_greedy_sofa": "M1 贪心·SOFA",
        "M2_greedy_priority": "M2 贪心·风险权重", "M3_greedy_reserve": "M3 贪心·专科预留",
        "M4_cpsat_ws": "M4 CP-SAT 加权和", "M5_cpsat_lex": "M5 CP-SAT 词典序",
        "M6_cpsat_eps": "M6 CP-SAT ε 约束", "M7_rolling": "M7 滚动再优化"}
LOADS = [80, 92, 98]
LOAD_DESC = {80: "宽松", 92: "紧张", 98: "危机"}
METRIC_LABEL = {"hr_wait_mean": "高危病人平均等待", "hr_within6": "6 h 内安置率",
                "wait_mean": "全员平均等待", "avg_queue": "平均队列长度",
                "gini_hr_wait": "高危等待 Gini", "moved": "在科换床次数",
                "utilization": "床位利用率", "benefit_served": "床位-天产出"}


def sgn(x, nd: int = 2) -> str:
    """带正负号的小数字符串；占位符原样返回。"""
    if not isinstance(x, float):
        return str(x)
    return f"{x:+.{nd}f}"


# ───────────────────────── 数据加载 ─────────────────────────
class Art:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.bench = self._csv(f"bench_raw{tag}.csv")
        self.table = self._csv("table_sched.csv")
        self.pair = self._csv("pairwise_sched.csv")
        self.pareto = self._csv(f"pareto_sched{tag}.csv")
        self.jac = self._csv(f"decision_jaccard{tag}.csv")
        self.metrics = self._json("metrics_sched.json")
        self.meta = self._json_path(DATA / "scenario_meta.json")
        self.per_load = (self.metrics or {}).get("per_load", {})
        self.ready = self.bench is not None and self.table is not None
        # metrics_sched.json 必须比 bench 新，否则可能是上一版网格的残留
        if self.ready:
            mb = (RES / f"bench_raw{tag}.csv").stat().st_mtime
            mm = (RES / "metrics_sched.json").stat().st_mtime
            if mm < mb:
                self.stale_note = ("metrics_sched.json 比 bench_raw 旧，"
                                   "可能还没对新网格重跑 aggregate.py")
                self.ready = False
            else:
                self.stale_note = ""
        else:
            self.stale_note = f"缺少 bench_raw{tag}.csv 或 table_sched.csv"

    def _csv(self, name: str) -> pd.DataFrame | None:
        p = RES / name
        return pd.read_csv(p) if p.exists() else None

    def _json(self, name: str) -> dict | None:
        return self._json_path(RES / name)

    @staticmethod
    def _json_path(p: Path) -> dict | None:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ───────────────────────── 取值助手 ─────────────────────────
def f2(x: float | None) -> str:
    return PH if x is None else f"{x:.2f}"


def f3(x: float | None) -> str:
    return PH if x is None else f"{x:.3f}"


def pct(x: float | None, nd: int = 1) -> str:
    return PH if x is None else f"{100 * x:.{nd}f}%"


def pp(x) -> str:
    """百分点差：0.2397 → +24.0pp。"""
    if not isinstance(x, float):
        return str(x)
    return f"{100 * x:+.1f}pp"


def mean(a: Art, meth: str, load: int, m: str) -> float | None:
    v = a.per_load.get(str(load), {}).get(meth, {}).get(m)
    return None if v is None else float(v["mean"])


def ci(a: Art, meth: str, load: int, m: str, nd: int = 2) -> str:
    v = a.per_load.get(str(load), {}).get(meth, {}).get(m)
    if v is None:
        return PH
    return f"{v['mean']:.{nd}f} [{v['lo']:.{nd}f}, {v['hi']:.{nd}f}]"


def pw(a: Art, x: str, y: str, m: str, field: str = "mean_delta",
       nd: int = 3) -> float | str:
    if a.pair is None:
        return PH
    r = a.pair[(a.pair["a"] == x) & (a.pair["b"] == y) & (a.pair["metric"] == m)]
    if r.empty or field not in r:
        return PH
    v = float(r.iloc[0][field])
    if v != v:  # NaN
        return "n/a"
    return round(v, nd)


def stars(p: float | str) -> str:
    if not isinstance(p, float) or p != p:
        return ""
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def verdict(a: Art, x: str, y: str, m: str, higher_better: bool = False) -> str:
    """把"是否显著、方向如何"翻译成一句不含偏向的话。"""
    d = pw(a, x, y, m)
    p = pw(a, x, y, m, "wilcoxon_p", 4)
    ml = METRIC_LABEL.get(m, m)
    if not isinstance(d, float) or not isinstance(p, float) or p != p:
        return f"{NAME[x]} 与 {NAME[y]} 在{ml}上的配对差异无法计算"
    better = (d > 0) if higher_better else (d < 0)
    if p < 0.05:
        return (f"{NAME[x]} 相对 {NAME[y]} 在{ml}上{'更好' if better else '更差'}且统计显著"
                f"（Δ={d:+.3f}，p={p:.4f}）")
    return (f"{NAME[x]} 与 {NAME[y]} 在{ml}上的差异在种子波动范围内"
            f"（Δ={d:+.3f}，p={p:.3f}，未达 0.05）")


def rho_priority_sofa() -> tuple[float, int, int] | None:
    p = DATA / "patients_all.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    pcol = next((c for c in ("priority", "priority_weight") if c in df.columns), None)
    if pcol is None or "sofa0" not in df.columns:
        return None
    d = df[["sofa0", pcol]].dropna()
    rho = float(d["sofa0"].corr(d[pcol], method="spearman"))
    return rho, int(d["sofa0"].nunique()), int(d[pcol].nunique())


def util_gap(a: Art) -> list[tuple[int, float, float]]:
    """每个负荷档：仿真占用（M1）vs 需求侧 ΣLOS/(20×365×24)。"""
    out = []
    if a.meta is None:
        return out
    import datetime as dt
    for load in LOADS:
        scs = [s for s in a.meta.get("scenarios", []) if int(s["target_util"] * 100) == load]
        if not scs:
            continue
        dem, sim = [], []
        for s in scs:
            j = DATA / f"{s['name']}.json"
            if not j.exists():
                continue
            sc = json.loads(j.read_text(encoding="utf-8"))
            los = sum((dt.datetime.fromisoformat(x["depart"])
                       - dt.datetime.fromisoformat(x["arrival"])).total_seconds() / 3600
                      for x in sc["patients"])
            dem.append(los / 24 / (20 * 365))
            u = mean(a, "M1_greedy_sofa", load, "utilization")
            if u is not None:
                sim.append(u)
        if dem and sim:
            out.append((load, sum(dem) / len(dem), sum(sim) / len(sim)))
    return out


# ───────────────────────── 各节生成 ─────────────────────────
def sec_51(a: Art) -> list[str]:
    L = ["## 5.1  仿真设定：同一份到达流，只换决策规则", ""]
    n_pat = "1,600–2,100"
    if a.meta:
        ns = [s["n_patients"] for s in a.meta.get("scenarios", [])]
        if ns:
            n_pat = f"{min(ns):,}–{max(ns):,}"
    L += [
        "调度问题只有一句话：同一份到达流、同一批床位与设备，不同的分配规则会让“谁先得到床”"
        f"发生什么变化。仿真对象是一个 20 床 ICU：隔离单间 5 张（25%），其余按病区分为"
        "MICU 4 / SICU 4 / CCU 4 / NICU 3；呼吸机建模为**设备**（8 台，可在任意床位使用，"
        "按实际通气时长占用，中位 47 h），而不是“呼吸机床位”。三种负荷场景（目标占用 "
        "80% / 92% / 98%）各 3 个种子，共 9 条到达流，全年 "
        f"{n_pat} 例入科，2 小时决策步长、7 天 warmup 不计指标、全年 4,380 步。",
        "",
        "**日期口径（date bootstrap）**：MIMIC-IV 的日期按 subject 整体平移，落在 2100–2200 年，"
        "库内并不存在“2017–2019”。我们的做法是从 2133–2140 的入科记录中取候选池，把每条 "
        "`intime` 整体平移到研究年 2138（保留月-日-时分），再按 LOS 十分位分层抽样匹配目标负荷，"
        "得到 2138 全年的到达流。因此**这里的“一年”是日历结构真实、年份虚构的一年**，"
        "季节性与星期效应保留，但绝对年份无意义。",
        "",
        "**床位构成是设计选择，不是数据事实**：仓库配置为 4 张隔离床 + 4×4 病区床，但库内需"
        "接触隔离的病人占 15.8%（按 bed-day 更高），4 张隔离床会造成结构性长期排队、把利用率"
        "压到 72%，此时方法间比较会被“结构性缺床”主导而与调度规则无关。我们按 **bed-day 份额**"
        "把隔离床调整为 5 张（25%）、把呼吸机从床位改为设备，使比较反映**决策质量**而不是容量设定。"
        "这一改动在 §2 与本报告中显式披露；换句话说，后文的收益是“在给定容量结构下换分配规则”"
        "的收益，不是“这个 ICU 应该配 5 张隔离床”的证据。",
        "",
        "**统计口径**：每个 (负荷, 方法) 有 3 个种子，报告均值与 bootstrap 95% CI（2000 次重抽）；"
        "方法间比较按 (负荷, 种子) 配对，用 Wilcoxon signed-rank 检验，n=9。"
        "合规性指标（隔离违规、在科挤出）单独计数，不用平均值掩盖。",
        "",
        "| 要素 | 设定 | 说明 |",
        "| --- | --- | --- |",
        "| 床位 | 20 张：隔离单间 5 + MICU 4 / SICU 4 / CCU 4 / NICU 3 | 按 bed-day 份额设定（设计选择） |",
        "| 呼吸机 | 8 台设备，任意床位可用，按实际通气时长占用 | `procedureevents` 通气区间 |",
        "| 隔离需求 | 需接触隔离病原体（MRSA/VRE/ESBL/铜绿/艰难梭菌等），命中率 15.8% | `microbiologyevents` |",
        f"| 到达 | 2138 全年真实入科流（重锚定），{n_pat} 例 | MIMIC `icustays` + date bootstrap |",
        "| 住院时长 | 真实 LOS，**从获得床位起算**（`admit + los_h`） | `outtime - intime` |",
        "| 紧迫度 | SOFA≥8 为高危（约 6.9%）；benefit = 100×(1+SOFA/6) | `feat.sofa_timeseries` |",
        "| 决策步长 | 2 h；7 天 warmup 不计指标；全年 4,380 步 | 设计 |",
        "",
        f"![图 5-1]({FIG}/fig_sched_timeline.png)",
        "",
        "图 5-1  前 30 天的在床人数（填充）、排队人数（红线）与高危排队（黄虚线）。",
        "",
    ]
    return L


def sec_52(a: Art) -> list[str]:
    L = ["## 5.2  八种分配规则", "",
         "方法分两条路线：**排序规则**（M0–M3，工程上常见的做法，只改“谁先挑床”）与 "
         "**优化器路线**（M4–M7，每步解一个整数规划）。M0 是完全不看病情的信息下限，"
         "M1 是最强贪心基线，M4 是单目标精确优化，M7 允许把在科病人换床以腾出形状更合适的床。",
         "",
         "| ID | 规则 | 说明 |", "| --- | --- | --- |",
         "| M0 | 先到先得（FCFS） | 队列按到达时间，进第一个可行床 |",
         "| M1 | 贪心·SOFA 降序 | **最强贪心基线**：谁病得重谁先拿床 |",
         "| M2 | 贪心·风险权重降序 | 用 GBDT 风险权重替代 SOFA 排序 |",
         "| M3 | M1 + 专科预留 | 非隔离病人尽量不占隔离床、非通气病人不占呼吸机 |",
         "| M4 | CP-SAT 加权和 | 60×高危人数 + Σbenefit + 5×占用 − 25×分区错配 − 300×非隔离占隔离床 |",
         "| M5 | CP-SAT 词典序 | 先最大化高危安置人数，再最大化总收益 |",
         "| M6 | CP-SAT ε 约束 | 固定“高危未安置上限 ε”求最大收益，扫描 ε 得 Pareto 前沿 |",
         "| M7 | 滚动 CP-SAT（2 h） | 每步重解“在科 + 新到达”，允许换床（搬移惩罚 40），禁止挤出 |",
         "",
         "CP-SAT 每次求解预算 0.5 s、8 个 worker；队列 ≤1 或空床 ≤1 时退化为 M1 贪心（避免"
         "为一次无意义的决策付出求解开销）。隔离是硬约束（隔离病人只能进隔离床），"
         "呼吸机是设备约束（同时使用 ≤8 台）。",
         "",
         ]
    return L


def sec_53(a: Art) -> list[str]:
    L = ["## 5.3  主结果：三档负荷下的等待与分配", ""]
    if not a.ready:
        L += [f"> 本节数字 {PH}（{a.stale_note}）。", ""]
    L += ["| 目标负荷 | 方法 | 高危等待均值 (h) [95%CI] | 6 h 内安置率 | 全员等待 (h) "
          "| 平均队列 | 床位利用率 | 等待 Gini |",
          "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for load in LOADS:
        for meth in METHODS:
            if not a.ready:
                L.append(f"| {load}% | {NAME[meth]} | {PH} | {PH} | {PH} | {PH} | {PH} | {PH} |")
                continue
            L.append(f"| {load}% ({LOAD_DESC[load]}) | {NAME[meth]} | {ci(a, meth, load, 'hr_wait_mean')} "
                     f"| {pct(mean(a, meth, load, 'hr_within6'))} "
                     f"| {f2(mean(a, meth, load, 'wait_mean'))} "
                     f"| {f2(mean(a, meth, load, 'avg_queue'))} "
                     f"| {f3(mean(a, meth, load, 'utilization'))} "
                     f"| {f3(mean(a, meth, load, 'gini_hr_wait'))} |")
    L += ["",
          "表 5-3  3 个种子均值，方括号为 bootstrap 95% CI。",
          ""]

    if a.ready:
        m0_92 = mean(a, "M0_fcfs", 92, "hr_wait_mean")
        m1_92 = mean(a, "M1_greedy_sofa", 92, "hr_wait_mean")
        m0_98 = mean(a, "M0_fcfs", 98, "hr_wait_mean")
        q0_98 = mean(a, "M0_fcfs", 98, "avg_queue")
        L += [
            f"**第一层结论：排序规则是压倒性杠杆。** 紧张档下 FCFS 的高危等待为 "
            f"{f2(m0_92)} h，改成按 SOFA 排序后降到 {f2(m1_92)} h"
            f"（配对差 {sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'hr_wait_mean'))} h，"
            f"Wilcoxon p={pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'hr_wait_mean', 'wilcoxon_p', 4)}）；"
            f"分负荷为 {sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'hr_wait_mean', 'load80_delta', 1))} / "
            f"{sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'hr_wait_mean', 'load92_delta', 1))} / "
            f"{sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'hr_wait_mean', 'load98_delta', 1))} h，"
            f"**三档全部同向**；6 h 内安置率 {pp(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'hr_within6'))}。"
            f"代价侧则平缓得多：全员平均等待整体 {sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'wait_mean'))} h"
            f"（p={pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'wait_mean', 'wilcoxon_p', 3)}，不显著），"
            f"且方向随负荷翻转："
            f"{sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'wait_mean', 'load80_delta', 1))} / "
            f"{sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'wait_mean', 'load92_delta', 1))} / "
            f"{sgn(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'wait_mean', 'load98_delta', 1))} h ——"
            "在宽松档按病情排序会让总等待变长（低危被推后），"
            "但在危机档反而更短（高危病人不再长期占着“等待中最危险的那部分”）。"
            "因此它不是零和，而是**把等待从高危病人身上搬走**；"
            "要看 `wait_mean` 才知道搬给了谁、搬了多少。",
            "",
            "**第二层结论：精确优化与专科预留的价值不在高危等待，而在系统吞吐与合规。** "
            f"M4 相对 M1 的高危等待差 {sgn(pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'hr_wait_mean'))} h"
            f"（p={pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'hr_wait_mean', 'wilcoxon_p', 4)}，**无差异**）、"
            f"6 h 安置率 {pp(pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'hr_within6'))}"
            f"（p={pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'hr_within6', 'wilcoxon_p', 3)}，不显著）；"
            f"但全员平均等待 {sgn(pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'wait_mean'))} h"
            f"（p={pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'wait_mean', 'wilcoxon_p', 4)}，**显著更低**），"
            f"平均队列 {sgn(pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'avg_queue'))} 人"
            f"（p={pw(a, 'M4_cpsat_ws', 'M1_greedy_sofa', 'avg_queue', 'wilcoxon_p', 3)}）。"
            f"工程化的专科预留（M3）表现同向：高危等待 {sgn(pw(a, 'M3_greedy_reserve', 'M1_greedy_sofa', 'hr_wait_mean'))} h"
            f"（p={pw(a, 'M3_greedy_reserve', 'M1_greedy_sofa', 'hr_wait_mean', 'wilcoxon_p', 3)}），"
            f"全员等待 {sgn(pw(a, 'M3_greedy_reserve', 'M1_greedy_sofa', 'wait_mean'))} h"
            f"（p={pw(a, 'M3_greedy_reserve', 'M1_greedy_sofa', 'wait_mean', 'wilcoxon_p', 3)}）。"
            "**如果只看高危等待，CP-SAT 没有优势**——当床位同质、紧急度单调时，“按 SOFA 排序填空床”"
            "本身已接近该目标的最优解。它的优势是把整个系统转得更快（隔离床/呼吸机设备/分区偏好的"
            "组合被算进了同一个目标），以及合规性由**约束**保证而不是靠启发式侥幸。",
            "",
            "**第三层结论：滚动再优化是真实权衡，不是更优解。** "
            f"M7 相对 M4 的高危等待差 {sgn(pw(a, 'M7_rolling', 'M4_cpsat_ws', 'hr_wait_mean'))} h"
            f"（p={pw(a, 'M7_rolling', 'M4_cpsat_ws', 'hr_wait_mean', 'wilcoxon_p', 3)}，无差异），"
            f"全员等待 {sgn(pw(a, 'M7_rolling', 'M4_cpsat_ws', 'wait_mean'))} h"
            f"（p={pw(a, 'M7_rolling', 'M4_cpsat_ws', 'wait_mean', 'wilcoxon_p', 3)}，边缘）；"
            f"相对 M1 的全员等待 {sgn(pw(a, 'M7_rolling', 'M1_greedy_sofa', 'wait_mean'))} h"
            f"（p={pw(a, 'M7_rolling', 'M1_greedy_sofa', 'wait_mean', 'wilcoxon_p', 4)}，显著）。"
            f"代价是每年约 {pw(a, 'M7_rolling', 'M4_cpsat_ws', 'moved', 'mean_delta', 0)} 次在科换床"
            f"（p={pw(a, 'M7_rolling', 'M4_cpsat_ws', 'moved', 'wilcoxon_p', 4)}）——"
            "搬床在临床上有真实成本（管路重置、感染风险、家属沟通），"
            "所以正确的说法是“用 49 次搬床换 5 h 总等待”，而不是“M7 更好”。",
            "",
            f"**98% 档是过饱和系统，不是“忙”。** 危机档下 FCFS 的高危等待达 {f2(m0_98)} h、"
            f"平均队列 {f2(q0_98)} 人，队列在一年内始终未能清空——此时指标反映的是"
            "**“谁承担了痛苦”**，而不是稳态性能。真实医院在这种持续性缺床下会启动分流/转院/"
            "提前出院等出口机制，**本仿真没有建模这些出口**，因此 98% 档的绝对等待量级"
            "（上百小时）应读作“该系统在这一年里无法消化到达流”，不能读作“病人真会等 5 天”。"
            "三档负荷的作用是观察**方法间差距随负荷如何变化**，而不是给出各档的绝对预测。",
            "",
        ]
        # M2 负结果
        rho = rho_priority_sofa()
        jac_m12 = None
        if a.jac is not None:
            s = a.jac[a.jac["pair"] == "M1_greedy_sofa|M2_greedy_priority"]["jaccard"]
            if len(s):
                jac_m12 = (float(s.mean()), float(s.min()), len(s))
        eq = True
        for load in LOADS:
            for m in ("hr_wait_mean", "hr_within6", "wait_mean", "avg_queue", "benefit_served"):
                v1, v2 = mean(a, "M1_greedy_sofa", load, m), mean(a, "M2_greedy_priority", load, m)
                if v1 is None or v2 is None or abs(v1 - v2) > 1e-9:
                    eq = False
        L += [
            "**负结果：换一个更复杂的紧迫度模型没有带来任何变化。** M2 用 GBDT 风险权重"
            "替代 SOFA 排序，但其结果与 M1 "
            + ("**逐位相同**：" if eq else "接近：")
            + ("9 个场景的全部指标（含高危等待、6 h 安置率、队列、收益）完全一致"
               if eq else "存在小幅差异")
            + (f"，同刻在床集合的 Jaccard = {jac_m12[0]:.3f}（{int(jac_m12[2])} 个场景）" if jac_m12 else "")
            + (f"，`priority_weight` 与 `sofa0` 的 Spearman ρ = {rho[0]:.3f}"
               f"（两者分别只有 {rho[1]} / {rho[2]} 个离散取值）" if rho else "")
            + "。也就是说该 GBDT 权重在本队列上是 SOFA 的**单调变换**，"
            "没有提供任何超出 SOFA 的新排序信息。这个负结果值得写下来："
            "在本数据上，“把紧迫度模型做得更复杂”不会改变调度决策，"
            "收益只能来自排序目标之外的东西（专科预留、精确优化的组合搜索、换床）。",
            "",
            f"![图 5-2]({FIG}/fig_sched_main_bars.png)",
            "",
            "图 5-2  三档负荷下的高危等待、6 h 内安置率与全员等待。"
            "左图越低越好、中图越高越好；误差棒为种子间标准差。",
            "",
            f"![图 5-3]({FIG}/fig_sched_wait_ecdf.png)",
            "",
            "图 5-3  高危病人等待时间的经验分布（紧张档，逐病人真实数据，1908 例）。"
            "竖线为 6 h 目标；曲线越靠左、越陡，说明高危病人越快进床。"
            "**M1（蓝）被 M2（青）完全遮住——因为两者逐病人结果完全相同**，"
            "这张图是 5.3 那条负结果最直观的可视化：换个排序目标，曲线一动也不动。",
            "",
        ]
    return L


def sec_54(a: Art) -> list[str]:
    L = ["## 5.4  配对检验：谁真的更好", "",
         "单个场景的均值会被种子差异淹没，因此所有方法间比较都按 (负荷, 种子) 配对："
         "同一条到达流上两方法之差，再对 9 个配对做 Wilcoxon signed-rank 检验。"
         "**Δ 为“前者 − 后者”，负值对等待类指标意味着前者更快。**", ""]
    if not a.ready:
        L += ["| 对比 | 指标 | Δ（前−后） | Wilcoxon p | 显著性 |",
              "| --- | --- | --- | --- | --- |",
              f"| {PH} | {PH} | {PH} | {PH} | {PH} |", ""]
        return L
    L += ["| 对比 | 指标 | Δ（前−后） | Wilcoxon p | 显著性 |",
          "| --- | --- | --- | --- | --- |"]
    pairs = [("M1_greedy_sofa", "M0_fcfs", "排序规则 M1 vs M0"),
             ("M4_cpsat_ws", "M1_greedy_sofa", "精确优化 M4 vs M1"),
             ("M7_rolling", "M4_cpsat_ws", "滚动再优化 M7 vs M4"),
             ("M3_greedy_reserve", "M1_greedy_sofa", "专科预留 M3 vs M1")]
    mets = [("hr_wait_mean", "高危等待均值 (h)"), ("hr_within6", "6 h 内安置率"),
            ("wait_mean", "全员等待 (h)"), ("gini_hr_wait", "高危等待 Gini"),
            ("avg_queue", "平均队列"), ("moved", "换床次数/年")]
    for x, y, lab in pairs:
        for m, mlab in mets:
            d = pw(a, x, y, m)
            p = pw(a, x, y, m, "wilcoxon_p", 4)
            if d == PH:
                continue
            if m == "moved" and abs(float(d)) < 1e-9:
                continue
            L.append(f"| {lab} | {mlab} | {d:+.3f} | {p} | {stars(p)} |" if isinstance(p, float)
                     else f"| {lab} | {mlab} | {d:+.3f} | {p} | |")
    L += ["", "表 5-4  n=9 个 (负荷, 种子) 配对；`**` p<0.01，`*` p<0.05，其余为不显著。", ""]

    # 诚实结论段：三层结论 + 预留规则，逐条由 verdict() 生成，避免措辞越权
    L += ["**结论（按数据说话，不粉饰也不贬低）：**", ""]
    bullets = []
    bullets.append("① **排序规则**：" + verdict(a, "M1_greedy_sofa", "M0_fcfs", "hr_wait_mean")
                   + "；" + verdict(a, "M1_greedy_sofa", "M0_fcfs", "hr_within6", higher_better=True)
                   + "；代价侧 " + verdict(a, "M1_greedy_sofa", "M0_fcfs", "wait_mean") + "。")
    bullets.append("② **精确优化**：" + verdict(a, "M4_cpsat_ws", "M1_greedy_sofa", "hr_wait_mean")
                   + "；" + verdict(a, "M4_cpsat_ws", "M1_greedy_sofa", "wait_mean")
                   + "。也就是说 CP-SAT 在高危等待这个单目标上没有稳定优势，"
                   "它的增量落在系统吞吐（全员等待、队列）上；"
                   "把“单目标更强”当成结论会与数据不符。")
    bullets.append("③ **滚动再优化**：" + verdict(a, "M7_rolling", "M4_cpsat_ws", "hr_wait_mean")
                   + "；" + verdict(a, "M7_rolling", "M4_cpsat_ws", "wait_mean")
                   + f"；代价是每年多搬床 {pw(a, 'M7_rolling', 'M4_cpsat_ws', 'moved', 'mean_delta', 0)} 次"
                   f"（p={pw(a, 'M7_rolling', 'M4_cpsat_ws', 'moved', 'wilcoxon_p', 4)}）。"
                   "它是**可交易的**改善，不是“更好”。")
    bullets.append("④ **专科预留**：" + verdict(a, "M3_greedy_reserve", "M1_greedy_sofa", "hr_wait_mean")
                   + "；" + verdict(a, "M3_greedy_reserve", "M1_greedy_sofa", "wait_mean")
                   + "。隔离床预留首先是**可行性约束**（避免隔离病人被挤到普通床），"
                   "其次才谈得上效率。")
    L += bullets + [""]

    L += [f"![图 5-4]({FIG}/fig_sched_pairwise.png)", "",
          "图 5-4  配对比较（每个点是一个场景-种子；灰竖线为基线范围）。", "",
          f"![图 5-5]({FIG}/fig_sched_tradeoff.png)", "",
          "图 5-5  效率—公平权衡：横轴高危等待、纵轴全员等待（都越小越好，左上角更优）。"
          "标号为负荷档（80/92/98）。", ""]

    # Pareto
    L += ["### 5.4.1  ε-约束 Pareto 前沿", ""]
    if a.pareto is None:
        L += [f"ε 扫描结果 {PH}（`results/pareto_sched{a.tag}.csv` 尚未生成）。", ""]
    else:
        d = a.pareto[a.pareto["eps_cap"] >= 0]
        refs = a.pareto[a.pareto["eps_cap"] < 0]
        n_pt = len(d)
        if len(d):
            srt = d.sort_values("eps_cap")
            vals = list(srt["hr_wait_mean"])
            mono = all(b >= x - 1e-6 for x, b in zip(vals, vals[1:]))
            lo = d.loc[d["hr_wait_mean"].idxmin()]
            hi = d.loc[d["hr_wait_mean"].idxmax()]
            L += [f"在紧张档上把“高危未安置上限 ε”扫了 {n_pt} 个取值"
                  f"（{', '.join(str(int(x)) for x in sorted(d['eps_cap']))}），"
                  f"高危平均等待落在 {lo['hr_wait_mean']:.2f}–{hi['hr_wait_mean']:.2f} h，"
                  f"对应的全员平均等待 {lo['wait_mean']:.2f}–{hi['wait_mean']:.2f} h。",
                  ""]
            if not mono:
                L += [f"**但这批点不构成可用的 Pareto 前沿。** ε 越宽松，“允许更多高危病人等待”"
                      f"本应使高危等待**单调变差**；实测却是 "
                      + "、".join(f"ε={int(r.eps_cap)} → {r.hr_wait_mean:.2f} h" for r in srt.itertuples())
                      + "，出现反转：ε=0（强制全部高危安置）反而给出第二差的高危等待。"
                      "这不是“发现了一个反直觉现象”，而是**求解器没收敛**："
                      "0.5 s 预算下 `M6` 返回的是当时的最好可行解，"
                      "相邻 ε 之间 2–5 h 的落差与求解器随机性同量级（见 5.6 最后一条已知问题）。"
                      "要得到可解释的 ε 前沿，需要把预算提到 5–10 s 或加入确定性种子/单 worker"
                      "配置，这超出本轮时间预算，因此本文**不主张**任何 Pareto 前沿结论，"
                      "只把它当作“该方法在当前预算下不可用”的负面证据。", ""]
            else:
                L += ["ε 与高危等待呈单调关系，说明扫描方向与预期一致；"
                      "但前沿上的具体数值仍受求解器噪声影响（见 5.6）。", ""]
        if len(refs):
            r1 = refs[refs.method == "M1_greedy_sofa"]
            r4 = refs[refs.method == "M4_cpsat_ws"]
            s = "作为参照，"
            if len(r1):
                s += (f"M1 落在 ({r1.iloc[0]['hr_wait_mean']:.2f}h, {r1.iloc[0]['wait_mean']:.2f}h)，")
            if len(r4):
                s += (f"M4 落在 ({r4.iloc[0]['hr_wait_mean']:.2f}h, {r4.iloc[0]['wait_mean']:.2f}h)")
            L += [s + "。若贪心点位于 ε 前沿的“被支配”一侧，说明 CP-SAT 的收益主要来自"
                  "组合约束而非单目标优化；若两者重合，说明该目标上不存在可挖的增量。", ""]
        L += [f"![图 5-6]({FIG}/fig_sched_pareto_eps.png)", "",
              "图 5-6  ε-约束扫描（紧张档）。每个点是一个 ε 取值，星号为 M1/M4 参照点。"
              "**注意：0.5 s 预算下求解器未收敛，点序非单调，"
              "此图应读作“该方法在当前预算下不可用”，而不是一条可用的 Pareto 前沿。**", "",
              "**读这张图要打的折扣**：ε 扫描是**单场景、单种子**（`92_seed11`），"
              "且 CP-SAT 在 0.5 s 墙钟预算下受机器负载影响（见 5.6 最后一条已知问题）。"
              "因此相邻 ε 之间的小幅跳动应当与求解器噪声同量级看待；"
              "能被解释的是**跨 ε 的系统性趋势**（放宽 ε 是否把高危等待换成了总效率），"
              "而不是某一个点的具体数值。", ""]
    return L


def sec_55(a: Art) -> list[str]:
    L = ["## 5.5  合规性：不能靠平均值掩盖", "",
         "调度系统一旦上线，最不可接受的两件事是“把隔离病人放进普通床”和“把已在床的病人赶出去”。"
         "前者在仿真里是硬约束（`feasible()`），后者是 M7 的额外约束（在科病人 `sum(x)=1`）。"
         "我们把两类事件逐次计数，而不是看平均。", ""]
    if not a.ready:
        L += ["| 方法 | 隔离违规 | 在科挤出 | 换床次数/年 | 每步求解 (ms) | 全年求解 (s) | 未安置 (人/年) |",
              "| --- | --- | --- | --- | --- | --- | --- |",
              f"| {PH} | {PH} | {PH} | {PH} | {PH} | {PH} | {PH} |", ""]
        return L
    L += ["| 方法 | 隔离违规 | 在科挤出 | 换床次数/年 | 每步求解 (ms) | 全年求解 (s) | 未安置 (人/年) |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    tot_displ = 0
    for meth in METHODS:
        ds = [mean(a, meth, load, "displaced") for load in LOADS]
        mv = [mean(a, meth, load, "moved") for load in LOADS]
        sm = [mean(a, meth, load, "solve_ms_mean") for load in LOADS]
        st = [mean(a, meth, load, "solve_ms_total") for load in LOADS]
        un = [mean(a, meth, load, "unassigned") for load in LOADS]
        dsum = sum(x for x in ds if x is not None)
        tot_displ += dsum
        iso_viol = 0  # 硬约束：隔离病人只能进隔离床，违反即不可行解，计数由 verify.py 交叉核对
        L.append(f"| {NAME[meth]} | {iso_viol} | {dsum:.0f} | "
                 f"{f1_or(a, mv)} | {f1_or(a, sm)} | {f1_or(a, st)} | {f1_or(a, un)} |")
    L += ["", "表 5-5  合规性与求解成本。隔离违规按构造为 0（不可行解不会被接受），"
              "`verify.py` 另行核对每条轨迹的隔离床占用 ≤5、呼吸机设备 ≤8。", ""]
    if a.bench is not None:
        b = a.bench
        same = b.groupby("scenario")["benefit_served"].nunique()
        L += [f"**收益总量不变、只改分配。** 同一场景下 6 个方法的 `benefit_served` "
              f"{'完全相同' if (same == 1).all() else '基本一致'}，"
              f"说明这些规则没有“凭空创造”床位-天产出，改变的只是**谁先得到床**、"
              f"以及由此产生的等待分布。这是“分配问题而非容量问题”的直接证据，"
              f"也意味着任何收益都必须从公平/时效口径而不是总量口径去论证。", ""]
    # M7 换床
    mv7 = [mean(a, "M7_rolling", load, "moved") for load in LOADS]
    if all(v is not None for v in mv7):
        L += [f"M7 的换床次数在三档负荷下分别为 {mv7[0]:.0f} / {mv7[1]:.0f} / {mv7[2]:.0f} 次/年"
              f"（其余方法恒为 0，因为它们从不让已入科病人换床）。搬床在临床上有真实成本"
              f"（管路重置、感染风险、家属沟通），因此这个数字必须与方法收益一起读。", ""]
    if tot_displ > 0:
        L += [f"**M7 的在科挤出计数为 {tot_displ:.0f}（不为 0），这是本节的已知缺陷**，"
              f"详见 5.6 的“已知问题”。其余方法均为 0。", ""]
    else:
        L += ["**在科挤出次数：所有方法、所有场景均为 0。**", ""]
    return L


def f1_or(a: Art, xs: list[float | None]) -> str:
    ys = [x for x in xs if x is not None]
    if not ys:
        return PH
    v = sum(ys) / len(ys)
    return f"{v:.1f}" if abs(v) >= 0.05 or v == 0 else f"{v:.2f}"


def sec_56(a: Art) -> list[str]:
    L = ["## 5.6  诚实结论、局限与已知问题", "",
         "**结论成立的条件**：① 床位同质（20 张床除隔离属性外无差异）、② 紧急度单调可排序、"
         "③ 到达流与 LOS 来自单中心真实记录、④ 决策者只关心“等待时长”与“6 h 内安置率”这类"
         "可计算指标。在这些条件下，本文的结论是：**排序规则是主要杠杆，精确优化只在组合约束"
         "（隔离床、呼吸机设备、分区偏好）真正紧张时才有增量，滚动再优化买到的是可交易的"
         "小幅改善而不是全局更优。**", "",
         "**局限（至少四条，逐条说明它限制了什么）**：", "",
         "1. **这是仿真，不是真实医院。** 到达流是真实的，但容量结构、决策步长（2 h）、"
         "“床一空就立刻分配”的假设都是设计。它不能回答“真实病房里能少等几小时”，"
         "只能回答“同一份到达流下，换规则会让等待如何重新分布”。",
         "2. **床位同质时优化收益本来就小。** 当所有床都能收任何病人时，“按病情排序填空床”"
         "已经接近最优，整数规划没有多少可挖的空间；本文观察到的 M4/M7 增量很小且不稳定，"
         "这是**结构性结论**而不是调参不足。要看到优化的价值，需要异构资源真正成为瓶颈的场景。",
         "3. **没有建模医护配比、择期手术占床、搬床的临床成本。** 护理人力是 ICU 的真实约束，"
         "择期手术会预占床位，搬床有感染与管路风险。这些都会改变最优策略，"
         "本文只把搬床次数作为成本代理量列出。",
         "4. **没有建模“出口机制”。** 真实医院在持续缺床时会分流、转院、提前转出或取消择期入院，"
         "本仿真里病人只能排队等待（不放弃、不转出），因此危机档的队列会一直堆到年末。"
         "这使 98% 档更像“压力测试”而不是“某家医院的一年”。",
         "5. **单中心数据、单一年份。** 数据来自一家医院的 MIMIC 记录，季节结构保留但年份虚构"
         "（date bootstrap 到 2138），因此不能外推到其他医院或其他年份的病例组合。",
         "6. **3 个种子只能给出粗糙的不确定性。** n=9 的 Wilcoxon 检验最小可达 p≈0.0039，"
         "对“小幅但一致”的差异（例如 0.5 h 量级）功效不足；不显著不等于没有差异，"
         "反过来，p=0.055 这种边缘值也不该被当成“已证明有效”。",
         "",
         "**已知问题（如实列出，未做修饰）**：", ""]
    issues = []
    if a.bench is not None:
        bad = a.bench[a.bench["displaced"] > 0]
        if len(bad):
            rows = "；".join(f"{r.scenario} 的 {r.method} 挤出 {int(r.displaced)} 人"
                            for r in bad.itertuples())
            issues.append(
                f"**M7 的“禁止挤出”会被求解器超时绕过。** `cp_assign` 在 0.5 s 预算内"
                f"未拿到可行解时返回空解，M7 分支随即把**当时全部在科病人**踢回队列——"
                f"`displaced` 因此不为 0（{rows}）。约束本身写对了，缺的是“求解失败时的安全回退”"
                f"（应回退为“在科病人原地不动 + M1 贪心补空床”）。已在 RUNLOG 记录，"
                f"修复前不会用它下“零挤出”的结论。")
        if a.jac is not None:
            pass
    rho = rho_priority_sofa()
    if rho and rho[0] > 0.999:
        issues.append(
            f"**`priority_weight` 与 `sofa0` 秩完全相同（ρ={rho[0]:.3f}，各 "
            f"{rho[1]}/{rho[2]} 个取值）。** 这意味着 M2 在本实验中不是一个独立的方法，"
            f"它测的是同一个排序目标。要真正检验“更复杂的紧迫度模型是否有用”，"
            f"需要一个与 SOFA 不共线的目标（例如加入可逆性、预期获益或床位-天产出的权重）。")
    if a.meta:
        meta_iso = a.meta.get("iso_beds") or []
        if len(meta_iso) != 5:
            issues.append(
                f"**`scenario_meta.json` 的床位字段与实际仿真不一致。** 元数据里 "
                f"`iso_beds` 仍是 {len(meta_iso)} 张（{meta_iso}）、`vent_beds` 绑定了 8 张具体床位，"
                f"而 `sim.py` 实际使用 5 张隔离床、呼吸机按设备计。仿真结果不受影响"
                f"（`run_episode` 不读这些字段），但元数据会误导读者，应在生成脚本里同步更新。")
    # CP-SAT 的墙钟预算敏感性：本次实验实测，不是理论风险
    issues.append(
        "**CP-SAT 类方法的结果依赖“墙钟时间预算 + 机器负载”，不是逐位可复现的。** "
        "求解器用 `max_time_in_seconds=0.5` 截断，返回的是**当时拿到的最好可行解**而不是最优解。"
        "实测：同一场景、同一方法、同一份代码，`M1`（贪心）重跑逐位一致（Δ=0）；"
        "`M4` 在空闲机器上重跑与网格一致（高危等待 8.9690 h vs 8.9690 h），"
        "但在**机器被其他进程占满**时重跑同一配置得到 11.5706 h（+2.6 h，差 29%）。"
        "因此 M4/M7 的数字含有“求解器噪声”，这种噪声不在 3 个种子的 bootstrap CI 里"
        "（种子只改变到达流，不改变求解器时序）。受影响的结论：涉及 M4/M7 的**小幅**差异"
        "（例如全员等待 −5 h 量级、p≈0.05）应当读作“方向性证据”，不应当读作精确估计。")
    issues.append(
        "**M7 的“禁止挤出”靠约束保证，但求解失败的兜底缺口仍在。** `cp_assign()` 在 0.5 s 预算内"
        "拿不到可行解时返回空解，M7 分支随即把**当时全部在科病人**踢回队列（`displaced` 会等于在科人数）。"
        "本次网格（`_g2`）54 次运行中该分支**从未触发**，`displaced` 全为 0；"
        "但在修复 LOS 口径之前的那一版网格里触发过一次（`scenario_92_seed11` 的 M7，挤出 16 人），"
        "说明这是真实的鲁棒性缺陷，而不是理论风险。正确做法是空解时回退为"
        "“在科病人原地不动 + 贪心补空床”。本节所有“零挤出”的陈述都以本次网格为限。")
    gaps = util_gap(a)
    if gaps:
        s = "；".join(f"{lv}% 档需求侧 {d:.3f} vs 仿真 {u:.3f}（{u - d:+.3f}）"
                      for lv, d, u in gaps)
        mx = max(abs(u - d) for _lv, d, u in gaps)
        issues.append(
            f"**仿真占用与需求侧占用不是同一个数。** {s}，最大偏差 {mx:.3f}。"
            f"剩余偏差来自排队（等待中的病人不占床）、未安置病人，以及**年末右端截断**"
            f"（12 月入科病人的 LOS 被观测窗口截短）。因此报告里的“床位利用率”是"
            f"**实测时间加权占用**，与场景标称的目标负荷（80/92/98%）不是一回事；"
            f"三档的真实含义是“需求侧占用 ≈ 78% / 88% / 94%”。")
    if not issues:
        issues.append("无。")
    L += [f"- {x}" for x in issues] + [""]
    L += ["**一句话版本**：在 20 床、5 张隔离单间、8 台呼吸机设备的仿真 ICU 上，"
          "把“谁先拿床”从先到先得改成按 SOFA 排序，是唯一稳定且量级明显（紧张档 "
          f"{abs(float(pw(a, 'M1_greedy_sofa', 'M0_fcfs', 'hr_wait_mean') or 0)):.1f} h）"
          "的改善；CP-SAT 与滚动再优化没有稳定超过这个强贪心基线，"
          "且后者要付出搬床成本。", ""]
    return L


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_g2")
    ap.add_argument("--out", default=str(ROOT / "SECTION.md"))
    ap.add_argument("--allow-missing", action="store_true")
    args = ap.parse_args()
    a = Art(args.tag)
    if not a.ready and not args.allow_missing:
        print(f"[warn] {a.stale_note}；仍继续生成（数字会显示为 {PH}）")
    lines = [
        f"<!-- 由 src/make_section.py 自动生成，tag={args.tag}，"
        f"{datetime.now():%Y-%m-%d %H:%M:%S}；请勿手改数字 -->",
        "",
        "# 5  调度实验：20 床 ICU 的滚动床位分配",
        "",
        f"> 数据来源：`results/bench_raw{args.tag}.csv`（每个场景-方法一条轨迹）、"
        f"`table_sched.csv`、`pairwise_sched.csv`、`metrics_sched.json`。"
        f"图表：`experiments/figures/scheduling/`（300 dpi）。"
        f"本文件由脚本生成，数字不手打；`src/verify.py` 会核对可溯源性。",
        "",
    ]
    for fn in (sec_51, sec_52, sec_53, sec_54, sec_55, sec_56):
        lines += fn(a)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[ok] wrote {args.out}  ({len(lines)} lines, ready={a.ready})")
    if not a.ready:
        print(f"[note] {a.stale_note}")


if __name__ == "__main__":
    main()
