# 调度实验 RUNLOG

> 记录人：sched-exp2。格式：`时间 | 动作/命令 | 参数 | 耗时 | 产物 | 异常`。
> 只追加，不修改历史条目；作废的结果不删除，标注 `[作废]`。

---

## 2026-11-13 12:49  接手与状态盘点

- **动作**：盘点 `experiments/scheduling/` 现状，确认 Lead 的后台网格进度。
- **命令**：`Get-ChildItem results/episodes -Filter *_g1.csv`；`Get-CimInstance Win32_Process`
- **状态**：`_g1` 网格进行中（41/54，PID 47436/46284 在跑 `run_bench.py --all --methods M0..M4,M7 --time-limit 0.5 --tag _g1`，12:34:42 启动）。
- **产物**：无（只读盘点）。
- **异常**：无。**未重复启动任何批量任务。**

## 12:50  为 ε-Pareto 增加 `eps_cap` 透传（`sim.py`）

- **动作**：`run_episode(..., eps_cap=None)` 新增关键字参数并透传到 `cp_assign`；`None` 时保持原硬编码逻辑（空床≥3 → ε=0，否则 ε=1），即默认轨迹不变。
- **文件**：`src/sim.py`（2 处小改，不动任何决策逻辑）。
- **动机**：M6 的 ε 上限原本写死在 `run_episode` 内部，无法扫描。
- **异常**：无。后续 Lead 的 LOS 修复没有覆盖这两处改动（13:00 已复查确认仍在）。

## 12:52  新增 `src/run_pareto.py`

- **用途**：固定场景扫描 ε∈{0,1,2,3,4,6,8}，并把 M1/M4 作为参照点写入同一张表；内置"重跑必须与 `bench_raw` 逐位一致"的回归自检。
- **产物（待生成）**：`results/pareto_sched<tag>.csv`。
- **状态**：**已写好，未运行**（Lead 12:59 指示暂缓所有新仿真）。

## 12:55  新增 `src/verify.py`

- **检查项**：① 逐场景逐方法一行摘要 ② episode 行数 = 4296（4380−84）③ `displaced == 0` ④ 轨迹级隔离床 ≤5 / 呼吸机设备 ≤8 / 床位 ≤20 ⑤ benefit 上界（含跨方法防重复计数）⑥ `metrics_sched.json` ↔ `table_sched.csv` 均值一致（1e-6）⑦ SECTION.md 数字可溯源（warning only）。
- **参数**：`--tag`。
- **异常**：首版用 U+2212（`−`）写"4380 − 84"，在 GBK 控制台下 `UnicodeEncodeError`；已改为 ASCII `-`。建议所有脚本运行时设 `PYTHONIOENCODING=utf-8`。

## 12:54  `_g1` 网格完成

- **结果**：`bench_raw_g1.csv`（54 行 = 9 场景 × 6 方法）、`episodes/*_g1.csv` 54 个、`decision_jaccard_g1.csv`（18 行）。
- **耗时**：Lead 报告 1179 s（12:34:42 → 12:54:21）。
- **状态**：**[作废]** —— 12:59 Lead 发现 LOS 口径 bug，`_g1` 全部作废，仅保留作为"修复前"档案，不进 SECTION、不进图。

## 12:56  聚合 `_g1`（作废档案，仅用于暴露流程问题）

- **命令**：`icu-scheduling-agent\.venv\Scripts\python.exe experiments\scheduling\src\aggregate.py --tags _g1`
- **首次失败**：`UnboundLocalError: cannot access local variable 'load'` —— `main()` 里 `for load, g in df.groupby("load")` 遮蔽了模块级函数 `load()`。Lead 同时段已改为 `load_raw()` / `lv`，我未重复改动，随后直接跑通。
- **产物（作废）**：`table_sched.csv`、`pairwise_sched.csv`、`metrics_sched.json`（12:56）。
- **异常**：`scipy.stats.wilcoxon` 抛 `RuntimeWarning: invalid value encountered in scalar divide`（n=9 且差值为 0 时的退化情形），不影响产出值。

## 12:57  修 `src/figures.py` 的四处硬伤（未运行）

1. **import 期必崩**：原文件引用 `style.GRAY / BLUE / TEAL / PURPLE / ORANGE / GOLD / RED / GREEN / PALETTE`，但 `experiments/common/style.py` 只导出小写调色板字典 `C` 与 `METHOD_COLORS` → `AttributeError`。已加兼容层（`_col()` 从 `style.C` 取值 + 本地 `PALETTE`），**未修改 `experiments/common/style.py`**（其他实验共用）。
2. **dpi 不符要求**：`style.savefig.dpi=200`，报告要求 300 → 在 `figures.main()` 里覆盖 `rcParams["savefig.dpi"]=300`，并新增 `--dpi`。
3. **ECDF 图永远画不出来**：`dump_waits.py` 写 `waits_92_seed11__M0_fcfs.csv`（无 tag），而 `fig_ecdf` glob 的是 `waits_*{tag}.csv`（`waits_*_g1.csv`）→ 永远匹配不到。已改为 `waits_*.csv` + 按 `__` 切方法名 + 只取单一场景。
4. **Pareto 图缺参照点**：新增 M1/M4 星标参照、多场景分组。

## 12:58  ⚠️ 发现 M7 挤出计数不为 0（影响"合规性"结论）

- **事实**：`bench_raw_g1.csv` 中 `scenario_92_seed11` 的 `M7_rolling` → `displaced = 16`；其余 53 次运行均为 0。
- **机制**：`cp_assign()` 在求解器 `status ∉ {OPTIMAL, FEASIBLE}`（0.5 s 预算超时 → `UNKNOWN`）时 `return []`；M7 分支随后执行 `displaced = admitted_pids - placed_pids`，当解为空时等于**当时全部在科病人**，全部被踢回队列。即"在科病人不得被挤出"是**约束层写对、但被求解器超时绕过**。
- **影响**：SECTION 不能写"在科挤出 0"；且 Lead 的 LOS 修复会让病人占用更久 → 队列更长 → 超时概率更高。
- **处置**：已 13:00 上报 Lead；`sim.py` 的 M7 逻辑由 Lead 修改（我不并发改仿真器）。修复前 `verify.py` 会在第 ③ 项 FAIL。

## 12:59  Lead 通知：LOS 口径 bug（影响全部结果）

- **Bug**：`depart` 原本固定为 `arrival + los_h`（从**到达**起算），于是等待越久的病人占床越短 → 系统性压低利用率，且对等待最长的 FCFS 反而有利，方法间差异被低估。
- **修复**：`Patient` 增 `los_h`，入院时改写 `depart = admit + los_h`（LOS 从**真正获得床位**起算）。
- **处置**：`_g1` 作废；Lead 重跑 `_g2`（9 场景 × 6 方法）。我暂停一切新仿真与新图。

## 13:00  诊断 A 与 D（纯 pandas，不跑仿真）

- **命令**：`... \python.exe experiments/scheduling/src/diag_checks.py a` / `... d`
- **A（优先级 vs SOFA）**：`patients_all.csv` n=8151，列名为 `priority_weight`；**Spearman ρ = 1.0000、Kendall τ = 1.0000、Pearson r = 1.0000**，两者各只有 13 个唯一值 → `priority_weight` 是 `sofa0` 的确定性单调变换。
- **B/C（跑仿真）**：按 Lead 指示暂缓。
- **D（需求侧 vs 仿真占用，`_g1` 档案）**：

  | 场景 | 需求侧 ΣLOS/(20×365×24) | `_g1` 仿真占用 | 差 |
  | --- | --- | --- | --- |
  | 80_seed11 / 22 / 33 | 0.790 / 0.756 / 0.766 | 0.730 / 0.729 / 0.724 | −6.0 / −2.7 / −4.2 pp |
  | 92_seed11 / 22 / 33 | 0.893 / 0.872 / 0.881 | 0.795 / 0.806 / 0.804 | −9.8 / −6.7 / −7.7 pp |
  | 98_seed11 / 22 / 33 | 0.948 / 0.928 / 0.943 | 0.826 / 0.842 / 0.838 | −12.1 / −8.6 / −10.6 pp |

- **解读**：缺口随负荷单调扩大（−3 pp → −10 pp），与"等待越久占床越短"的压缩效应一致，且负荷越高等待越长、偏差越大。**验收标准**：`_g2` 的仿真占用应逼近需求侧的 0.79 / 0.88 / 0.94；若仍在 0.73 一档，说明修复未生效或另有原因，SECTION 将如实写实测值。

## 13:05  `aggregate.py` 扩充 `per_load`（向后兼容）

- **动作**：保留报告正文依赖的 6 个主指标字段名与 `{mean,lo,hi,n}` 结构不变，**追加** `solve_ms_mean / solve_ms_total / moved / displaced / unassigned / max_queue / benefit_served / iso_util / vent_device_util / hr_wait_p90`。
- **动机**：`report/build_report.py` §5.5 里调用了 `sched('M4_cpsat_ws', 92, 'solve_ms_total')`，而旧 `per_load` 没有该字段（会取不到值）。追加不改变既有字段，`sched()` 兼容。

## 13:08  新增 `src/make_section.py`（SECTION.md 由脚本生成，数字不手打）

- **动机**：报告正文直接引用本节数字；手抄必然与 csv/json 漂移，且 `verify.py` 第 ⑦ 项要核对可溯源性。
- **命令**：`... \python.exe experiments/scheduling/src/make_section.py --tag _g2 --allow-missing`
- **产物**：`SECTION.md` 骨架（110 行，数字位为 `{{待填}}`），设定/规则/局限/已知问题段已按实际实现写好。
- **异常**：无。

## 13:09  `_g2` 完成（Lead）：LOS 修复生效

- **状态**：`bench_raw_g2.csv` 54 行（9 场景 × 6 方法）、`episodes/*_g2.csv` 54 个（Lead 把 3 个分档 tag 合并并统一复制）。
- **验收（我独立核算）**：仿真时间加权占用 0.768–0.937，对应需求侧 0.756–0.948，**最大偏差 2.4 pp**（`_g1` 时是 4–12 pp）→ 修复确实生效。
- **`displaced`**：54 次全为 0（上一版的 16 在本次未复现）。
- **异常**：Lead 只合并了 `bench_raw`，`decision_jaccard_g2a/b/c.csv` 三个分片未合并 → 我合并为 `decision_jaccard_g2.csv`（18 行，去重后 9 场景 × 2 对）。M1|M2 = 1.000000（9/9）；M4|M7 = 0.736（低于 `_g1` 的 0.95，因为 M7 现在真的在搬床）。

## 13:11  `aggregate.py --tags _g2`

- **命令**：`icu-scheduling-agent\.venv\Scripts\python.exe experiments\scheduling\src\aggregate.py --tags _g2`
- **产物**：`table_sched.csv` / `pairwise_sched.csv` / `metrics_sched.json`（含我 13:05 追加的 `solve_ms_total` 等字段，`per_load` 主字段名未变）。
- **异常**：期间 Lead 正在改 `aggregate.py`，撞上一次 `AttributeError: 'DataFrameGroupBy' object has no attribute 'columns'`（编辑中间态）；等其修好后重跑通过。**教训：同一文件多人并发编辑时，先 `Get-Content` 确认当前状态再跑。**

## 13:12–13:20  `dump_waits.py --scenarios 92_seed11`（6 方法，8 分钟）

- **产物**：`results/waits_92_seed11__<method>.csv`（每个 1908 行逐病人等待）。
- **异常**：与 pareto 首轮并行 → CPU 争用，M7 单集跑了约 6 分钟（空闲时应约 1 分钟）。**这是后续判断"哪些结果受负载污染"的关键线索。**

## 13:12–13:24  ε-Pareto 首轮 **[作废]**

- **命令**：`run_pareto.py --scenarios 92_seed11 --eps 0 1 2 3 4 6 8 --time-limit 0.5 --tag _g2`
- **回归自检**：`M1` 重跑与 `bench_raw_g2` **逐位一致（Δ=0.00e+00）** → 证明我加的 `eps_cap` 透传没有改变默认行为。
- **但 `M4` 重跑与网格差 +2.60 h**（8.969 → 11.571）。
- **作废原因**：该轮与 `dump_waits` 的 M7 并行，CP-SAT 的 **0.5 s 是墙钟预算**，机器一忙就返回更差的可行解。ε=0/1 两个点恰好在最拥挤时段跑出，导致 ε 序列非单调。**整轮不进 SECTION。**

## 13:21  CP-SAT 复现性专项测试（决定性）

- **命令**：同一场景 `92_seed11` 的 `M4_cpsat_ws` 连跑 2 次（空闲机器）。
- **结果**：`run1 = 8.9690 h`（与网格**完全一致**）、`run2 = 8.9690 h`（高危等待一致，但 `wait_mean` 82.1548 vs 82.1579、`benefit` 338991 vs 338824、决策次数 1974 vs 1968）。
- **结论**：① 贪心方法逐位可复现；② CP-SAT 在**相同负载**下高度一致但不逐位相同（决策点数量本身会漂移）；③ CP-SAT 在**高负载**下会明显退化（8.97 → 11.57 h，−29%）。
- **写入**：SECTION 5.6 已知问题第 4 条；并提示 Lead：`_g2` 的 3 个分档是并行跑的（3 进程 × 8 worker），但同场景复跑与网格一致，说明网格本身未受污染，受影响的是"边缘显著性"的解释力度。

## 13:26  ε-Pareto 第二轮（solo，ε∈{0,2,4,8} + M1/M4 参照）

- **产物**：`results/pareto_sched_g2.csv`（6 行）。
- **结果**：ε=0 → 14.24 h、ε=2 → 10.06 h、ε=4 → 12.19 h、ε=8 → 8.97 h。**非单调**：ε=0（强制全部高危安置）反而第二差。
- **判定**：这不是反直觉发现，而是 **0.5 s 预算下求解器未收敛** → 本文**不主张** Pareto 前沿结论，只把它作为"该方法在当前预算下不可用"的负面证据（SECTION 5.4.1 与图 5-6 标题都按此改写）。
- **修正建议（未执行，超时间预算）**：预算提到 5–10 s，或 `num_search_workers=1` + 固定种子，才能得到可解释的 ε 前沿。

## 13:25  图表 6 张（系统 python，300 dpi）

- **命令**：`C:\Users\lenovo\AppData\Local\Programs\Python\Python312\python.exe experiments\scheduling\src\figures.py --tag _g2`
- **产物**：`experiments/figures/scheduling/` 下 6 张 PNG，全部 **300 dpi**、中文字体 `Microsoft YaHei`（`figcheck.py` 验证无缺字形警告）。
- **修图记录**：① 中间面板百分比标签与误差棒帽重叠 → 改为压在误差棒之上（`v+err+0.018`）；② pareto 图原标题写"可交易曲线"与数据矛盾 → 改为"0.5 s 预算下点序非单调，尚不构成 Pareto 前沿"，图例 "ε 前沿" → "ε 扫描"。
- **自查**：逐张看过——中文正常、无裁切、图例不遮挡数据（ECDF 图例在右下空白区；M1 被 M2 完全覆盖属预期，已在图注说明）。

## 13:27  `SECTION.md` 定稿 + `verify.py --tag _g2`

- **`SECTION.md`**（193 行，由 `make_section.py` 生成，**数字零手打**）：5.1 设定（date bootstrap / 床位构成设计选择 / 统计口径）、5.2 八规则、5.3 主结果 + 三层结论 + M2 负结果 + 过饱和说明、5.4 配对检验 + 四条诚实结论、5.4.1 ε 扫描（负面）、5.5 合规性、5.6 局限 6 条 + 已知问题 5 条。
- **`verify.py --tag _g2`**：**ALL CHECKS PASSED**（1 项 warning）。
  - 修了一处检查逻辑：原要求 `metrics_sched.json` 与 `table_sched.csv` 差 ≤1e-6，但 `table_sched.csv` 由 `agg()` 做 `.round(4)`，1e-6 在数学上不可能满足。改为"`round(json,4)` 逐位等于表中值 + |Δ| ≤ 5.1e-5"，实测 108 个组合最大 |Δ| = 4.97e-5（纯舍入）。
  - warning 的 5 个数字：`2100/2133/2140/2200` 是年份（正文叙述，不是结果），`125113.9` / `29111.3` 是"全年求解耗时按负荷取平均"的派生量（不在任何单个 csv 单元格里）→ 属正常。
- **`benefit_served` 检查**：每方法 ≤ 场景总收益（占比 0.982–1.000）；跨方法求和 ≤ 方法数 × 总收益（防重复计数）。**注意**：字面意义的"跨方法求和 ≤ 场景总收益"对 6 个并行方法是不可满足的（每个方法都服务了 98%+ 的病人），已在脚本注释里说明按"每方法上界 + 求和上界"实现。

## 待办（剩余，按优先级）

1. （可选，需 10+ 分钟）把 `run_pareto.py --time-limit` 提到 5–10 s 重扫 ε，看是否得到单调前沿。
2. （可选）`dump_waits.py` 补 `98_seed11`，ECDF 可加危机档面板。
3. Lead 的 `build_report.py` §5.3 第 3 条 bullet 与 §5.4 图 11 图注需要按新结论改口径（我已单独告知）。

