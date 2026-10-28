# 多目标优化实施任务清单

> 目标：把当前"线性加权单目标 CP-SAT"升级为"ε-约束 + Pareto 前沿"。
> 理论依据见 [`MULTIOBJECTIVE_THEORY.md`](MULTIOBJECTIVE_THEORY.md)。

---

## 0. 现状基线

| 项 | 状态 |
|----|------|
| 分支 | `main-archive` |
| 模型 | 0-1 ILP + 加权和标量化 |
| 目标 | $f_0$ 占床、$f_1$ 加权收治、$f_2$ 重症错配、$f_3$ 负载极差、$f_4$ 病区失配、$f_5$ 挪床 |
| 入口 | `domain.optimizer.cp_sat.run_assignment()` |
| 配置文件 | `configs/optimizer.yaml` |
| 测试 | 68 passed |
| 数据库 | PostgreSQL 16，容器 `icu_scheduling_pg16`，端口 5434 |

---

## 0.1 数据问题（阻塞，待修复）

数据探查结果详见 [`data_example.md`](data_example.md)。D1、D2、D4 已完成；D3 依赖 Layer0 数据恢复。

### D1 隔离标记失真（已完成）

- 原问题：`first_careunit` 关键词（`micu/sicu/cvicu/nsicu`）判定隔离需求，等价于把"来自重症病区的患者"默认当作"需要隔离"。
- 证据：全库约 76,000 人命中；模型取数顺序下前 200 名命中 191 人（95.5%）；隔离床仅 4 张。
- 影响：单轮可分配上限约 13 人；$f_2$ 仅作用于非隔离患者，几乎失效。
- 修复方式：新增 `isolation.mode`（`none` / `careunit_keyword` / `real`），默认 `none`；`none` 模式下 C3 不启用，ISO 床按普通床参与优化。
- 实测对比（同一份数据、`persist=False`）：

| 模式 | 分配人数 | 隔离需求人数 | $f_2$ | $f_3$ | 病区匹配率 |
|------|----------|--------------|-------|-------|------------|
| `none` | 20 | 0 | 192 | 0 | 0.600 |
| `careunit_keyword` | 13 | 191 | 103 | 3 | 0.615 |

- 涉及文件：`domain/optimizer/cp_sat.py`、`configs/optimizer.yaml`、`tests/test_isolation_mode.py`。
- 状态：已完成（2026-10-27）。

### D2 优先级与 SOFA 完全共线（已完成）

- 原问题：`priority_weight = 1 + sofa_total / 10`，94,458 条记录全部精确成立。
- 数学后果：$f_1=f_0+0.1f_2$，$f_0$、$f_1$、$f_2$ 只有两个自由度。
- 修复方式（A1）：新增 `domain/scoring/priority.py` 与 `priority.mode`：
  - `sofa_rule`：保留旧公式，仅作基线；
  - `composite`：$w_i=1+0.6\cdot s_i/12+0.4\cdot\tilde L_i$，其中 $\tilde L_i$ 为住院时长的经验分位数。
- 等待时间说明：MIMIC 日期按患者偏移，跨患者日历时间不可对齐，故采用**已住院时长（LOS）的经验分位数**作为等待代理；`staging.los_hours` 实际单位为天。
- 实测（前 200 名候选）：
  - 优先级取值由 13 个离散值增至 **175** 个；
  - $\mathrm{corr}(w,s)=0.685$，$\mathrm{corr}(w,\tilde L)=0.134$；
  - $f_1$ 不再等于 $1000f_0+100f_2$（39,446 vs 43,300）。
- 涉及文件：`domain/scoring/priority.py`、`domain/optimizer/cp_sat.py`、`configs/optimizer.yaml`、`tests/test_priority.py`。
- 状态：已完成（2026-10-27）。

### D3 SOFA 区分度低且无时间序列

- 现状：0–12 分（仅肾/肝/凝血），71.7% 集中在 4–5 分；`sofa_timeseries` 只有 `hour_index = 0`。
- 影响：$f_2$ 分辨率不足；无法建模等待期间的病情演变。
- 修复方向：补齐呼吸/循环/神经分量；或按时间窗生成多小时 SOFA；或改用 SOFA 分段/阈值约束。
- 状态：待修复。

### D4.1 呼吸机标记（已完成）

- 原问题：`_needs_ventilator()` 用 MD5 生成约 35% 标记，与临床无关。
- 数据核查：所有 schema 中均无 `vent/ventilat/respirat` 字段；`mock.icustays` 仅有时间字段。
- 修复：新增 `vent.mode`：
  - `none`（默认）：C4 不启用；
  - `pseudo_random`：保留原 MD5 逻辑，仅作对照；
  - `proxy_rule`：$s_i\ge$ `proxy_sofa_min` 且来自 ICU 病区，作为**构造式代理**；
  - `real`：读取 `feat.stay_flags(stay_id, needs_vent)`，缺失时报错。
- 代理规则覆盖率：全库 `SOFA≥5 且 ICU 病区` 为 **34.7%**；固定抽样 200 人中命中 71 人（35.5%）。
- 保留假设：**任何床位均可接呼吸机**，C4 仍为全局计数 $\sum \beta_i x_{ib}\le 8$，无逐床设备台账。
- 实测：`none` 需气人数 0、`pseudo_random` 60、`proxy_rule` 71（$f_1$ 为 33,274 / 33,274 / 32,699）。
- 状态：已完成（2026-10-28）。

### D4.2 候选池（已完成）

- 原问题：全库按分数取前 200，跨年份混合；改变权重会改变候选集，导致敏感性实验不可比。
- 限制：MIMIC 日期按患者偏移，无法构造日历时间上的并发队列。
- 修复：新增 `candidates.mode`：
  - `top_score`：旧逻辑，仅作对照；
  - `fixed_sample`（默认）：`ORDER BY md5(stay_id || seed)` 的确定性抽样；
  - `stratified`：按 SOFA 分位分层抽样。
- 实测：同 seed 两次运行 `f1` 完全一致（33,274）；三种模式均可正常求解。
- 涉及文件：`domain/optimizer/cp_sat.py`、`configs/optimizer.yaml`、`tests/test_candidates.py`。
- 状态：已完成（2026-10-28）。

### D4.3 `los_hours` 单位（已完成）

- 原问题：字段名为 hours，实际存储天（1.64 对应 39.3 小时）。
- 修复：新增 `migrations/004_icustays_units.sql`，创建 `staging.icustays_v`：
  - `los_days`：原值；
  - `elapsed_hours = los_days * 24`。
- 代码改用 `staging.icustays_v.elapsed_hours`，不再在 Python 中做 `* 24` 换算。
- 状态：已完成（2026-10-28）。

### 验收标准

- D1：`isolation.mode=none` 时单轮分配数明显高于 13，且模型可正常求解。
- D2：目标值相关矩阵中 $|\rho(f_0,f_1)|$ 与 $|\rho(f_1,f_2)|$ 显著低于 1（目标 < 0.9）。
- D3：SOFA 分布不再集中于两个取值，或明确以分段/阈值形式使用。
- D4.2：同 seed 的候选集合完全一致；改变优先级权重时候选集合不变。
- D4.3：`elapsed_hours = los_days * 24`，代码中不再出现隐式换算。
- D4.1：若采用代理标签，需报告规则、覆盖率与敏感性；否则保持 `vent.mode=none`。

---

## P0 已修复

- [x] `optimizer.yaml` 中 `occupancy` 键与代码不匹配导致 `ValueError`
- [x] 负载均衡硬编码 4 区，改为按 `resources.bed_zones` 的语义病区计算
- [x] 均衡目标由"最大偏差"改为"负载极差" $\max_z L_z-\min_z L_z$

**验收**：`run_assignment` 可正常解析配置；`pytest tests -q` 全通过。

---

## P1 已完成：补齐 $f_0$ 与 $f_5$

- [x] $f_0=\sum_{i,b}x_{ib}$（占床总量，方向 max）
- [x] $f_5=\sum_{i:o_i\ne\varnothing}\sum_{b\ne o_i}x_{ib}$（挪床惩罚，方向 min）
- [x] `run_assignment(..., previous_beds=...)` 支持传入上一轮 `stay_id → bed_id`
- [x] 返回值新增 `objective.f0_occupancy`、`objective.f5_move`、`evaluation.moved_patients`
- [x] 权重默认值/配置/测试同步更新

**验收标准**

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests -q
```

- 全绿
- 调用 `run_assignment(persist=False, previous_beds={stay_id: bed_id})` 时，`f5_move` 等于"被分配到不同床位的患者数"

**说明**：六项目标全部保留，$f_0$ 与 $f_1$ 的共线性由 P3 的共线性检验记录，不作为剔除依据。

---

## P2 目标注册表（已完成）

**动机**：原先 6 个目标写死在 `run_assignment` 里，无法按需开关、无法复用锚点求解。

- [x] 新建 `domain/optimizer/objectives.py`
- [x] 每个目标统一为 `ObjectiveSpec(name, sense, bound, build)`
- [x] 注册表 `OBJECTIVES` 包含六个目标
- [x] `build_objectives(model, x, ctx)` 一次性构建全部表达式
- [x] `objective_bounds(ctx)` 统一提供归一化上界
- [x] `apply_objective(...)` 支持三种模式：加权和 / 单目标 pivot / ε 上界
- [x] `run_assignment` 新增参数：
  - `active_objectives`：加权和只使用指定子集；
  - `pivot`：单目标优化（锚点求解）；
  - `epsilon`：对非 pivot 目标加上界（或下界），必须与 `pivot` 同时使用。

### 重构中发现并修复的两个问题

1. **$f_4$ 的辅助变量不精确**：原约束为 `mismatch >= ...`，在 $f_4$ 未优化时可取任意 0/1，导致锚点结果虚高。已改为等式 `mismatch == ...`（右侧恒为 0/1）。
2. **$f_3$ 的 ε 约束不精确**：`load_range` 依赖 max/min 变量，未被目标压制时不紧。ε 约束改为两两负载差：$L_a-L_b\le\varepsilon$，与 $\max L-\min L\le\varepsilon$ 等价。

### 实测

| 调用 | 模式 | $f_0$ | $f_1$ | $f_2$ |
|------|------|------|------|------|
| 默认（全部加权） | `weighted_sum` | 20 | 33,274 | 121 |
| `pivot="wait"` | `pivot` | 20 | 33,899 | 145 |
| `pivot="wait", epsilon={"overload":100}` | `pivot` | 20 | 32,522 | 100 |
| `pivot="wait", epsilon={"overload":50}` | `pivot` | 20 | 27,303 | 50 |
| `active_objectives=["wait"]` | `weighted_sum` | 20 | 33,899 | 145 |

默认路径结果与重构前完全一致；ε 收紧时 $f_1$ 单调下降，符合预期。

### 验收

- [x] 全量测试 **65 passed**
- [x] 默认加权和结果不变
- [x] 六个目标可单独构建与优化
- [x] ε 约束生效且可验证
- [x] 非法 pivot / 缺少 pivot 的 ε 均报错

**状态**：已完成（2026-10-28）。

---

## P3 锚点求解（已完成）

**目标**：为 ε-扫描提供归一化尺度与实际取值范围。

- [x] 新建 `domain/optimizer/pareto.py`
- [x] `solve_anchors()`：对六个目标各求解一次
- [x] **纯锚点**：不加额外约束，用于计算数学理想点
- [x] **实用锚点**：加占用下限 $f_0\ge\lfloor r\cdot f_0^I\rfloor$（默认 $r=0.9$），避免零分配退化解
- [x] `_ideal_nadir()`：按目标方向计算理想点/最差点
- [x] `save_anchors()`：输出 `reports/pareto/anchors_<run_id>.json`
- [x] CLI：`python -m application.pareto`

### 实测（2026-10-28）

运行配置：`candidates.mode=fixed_sample (seed=42, size=200)` · `priority.mode=composite (0.6/0.4)` · `isolation.mode=none` · `vent.mode=none` · `split=calib` · $B=20$（ISO 床 4、呼吸机 8）

**表 1 纯锚点单目标扫描结果**（无额外约束，$\min/\max f_k$ 单独求解）

| 锚点（被优化的目标） | $f_0$ 占用 | $f_1$ 优先级加权等待 | $f_2$ 超载惩罚 | $f_3$ 负载偏差 | $f_4$ 病区失配 | $f_5$ 挪床 |
|------|-------|-------|-------|-------|-------|-------|
| occupancy（max） | **20** | 28,668 | 93 | 0 | 9 | 0 |
| wait（max） | 20 | **33,899** | 145 | 0 | 12 | 0 |
| overload（min） | 0 | 0 | **0** | 0 | 0 | 0 |
| balance（min） | 20 | 28,766 | 98 | **0** | 12 | 0 |
| zone_mismatch（min） | 0 | 0 | **0** | 0 | **0** | 0 |
| move（min） | 0 | 0 | **0** | 0 | 0 | **0** |

粗体为该项锚点的最优值。注意 `overload`/`zone_mismatch`/`move` 三行全部为 0，说明它们的纯最优解是「一个患者都不收」——数学上合法，但不可执行。

> **可复现性提醒**：`cp_sat.py` 目前只设了 `max_time_in_seconds = 30.0`，未固定 `num_search_workers` 与 `random_seed`。CP-SAT 默认多线程搜索，同一模型多次运行在**存在并列最优解**时会返回不同的具体解。实测中纯 `wait` 锚点的 $f_4$ 在两次运行间从 14 变为 12，而 $f_1=33{,}899$ 保持不变——即**主目标值稳定，次目标值可能有 ±2 的浮动**。P4 做前沿比较前需固定种子（`num_search_workers=1`, `random_seed=0`），否则非支配过滤会受抖动干扰。

**表 2 实用锚点单目标扫描结果**（附加占用下限 $f_0\ge\lfloor 0.9\times 20\rfloor=18$）

| 锚点（被优化的目标） | $f_0$ 占用 | $f_1$ 优先级加权等待 | $f_2$ 超载惩罚 | $f_3$ 负载偏差 | $f_4$ 病区失配 | $f_5$ 挪床 |
|------|-------|-------|-------|-------|-------|-------|
| occupancy（max） | **20** | 28,668 | 93 | 0 | 9 | 0 |
| wait（max） | 20 | **33,899** | 145 | 0 | 11 | 0 |
| overload（min） | 18 | 22,003 | **39** | 1 | 10 | 0 |
| balance（min） | 20 | 28,866 | 94 | **0** | 6 | 0 |
| zone_mismatch（min） | 19 | 27,635 | 83 | 1 | **0** | 0 |
| move（min） | 18 | 25,809 | 85 | 1 | 10 | 0 |

**表 3 理想点 / 最差点**

| 量 | $f_0$ | $f_1$ | $f_2$ | $f_3$ | $f_4$ | $f_5$ |
|----|-------|-------|-------|-------|-------|-------|
| 纯理想点 $f^I$ | 20 | 33,899 | 0 | 0 | 0 | 0 |
| 纯最差点 $f^N$ | 0 | 0 | 145 | 0 | 12 | 0 |
| **实用理想点** $\tilde f^I$ | 20 | 33,899 | 39 | 0 | 0 | 0 |
| **实用最差点** $\tilde f^N$ | 18 | 22,003 | 145 | 1 | 11 | 0 |
| 实用极差（$\tilde f^N-\tilde f^I$） | 2 | 11,896 | 106 | 1 | 11 | 0 |

### 单目标扫描结论

1. **$f_0$（占用）纯最优 = 20 = 床位数**，即容量饱和，没有继续提升空间。$f_0$ 的实用范围只有 $[18,20]$，跨度太窄，**主要作用是硬下限**；在 ε 网格中只取 3 档（$\{18,19,20\}$），用于验证提高占用下限能否带来新的非支配点。
2. **$f_1$（优先级加权等待）与 $f_2$（超载）是唯一真实的权衡对**：把 $f_1$ 从 22,003 推高到 33,899 的代价是 $f_2$ 从 39 恶化到 145（+271%），且 $f_4$ 从 0 恶化到 11。
3. **$f_3$（负载偏差）不是独立目标，它由 $f_0$ 完全决定**。$f_3$ 的定义是「病区最大负载 − 最小负载」，现实例为 5 个病区 × 4 床，因此给定占用数 $m$ 后 $f_3$ 的最小可达值是确定的：

   $$f_3^{\min}(m) = 0 \iff m \in \{0,5,10,15,20\},\quad \text{否则} \ge 1$$

   实测验证：$m=18\to1$、$m=19\to1$、$m=20\to0$。因此 $f_3$ 在锚点表中恒为 0 / 1 并非巧合，而是**结构必然**。它不携带超出 $f_0$ 的独立信息，**应从 ε 网格中剔除**（仅作诊断量保留）。
4. **$f_5$（挪床）恒为 0**：调用时未传 `previous_beds`，$f_5\equiv0$，该项在 P4 中**暂不参与扫描**。
5. **退化维度**：纯锚点下 `balance`、`move` 理想值 = 最差值；实用锚点下仅 `move`。
6. 纯锚点中 `overload`/`zone_mismatch`/`move` 会返回零分配，**仅用于归一化，不作为可执行方案**。
7. 归一化时 $f_0,f_1,f_2$ 用纯理想点作分母上限，但 $ε$ 的取值范围必须用**实用**最差点 $\tilde f^N$，否则网格点会落在不可执行区域。

**状态**：已完成（2026-10-28）。

### ε 网格设计（供 P4 使用）

#### 主目标与 ε 目标的选取理由

| 目标 | 角色 | 理由 |
|------|------|------|
| $f_1$ 优先级加权等待 | **主目标（pivot）** | 唯一连续、幅度大（11,896 跨度）、且临床上有明确含义（重症优先收治）的目标；与 $f_2$ 存在真实冲突，是前沿的主延伸方向 |
| $f_2$ 超载惩罚 | **ε 维度 1（稠密）** | 与 $f_1$ 冲突最强（39↔145），且实用极差 106，是整个前沿最有信息量的一维 |
| $f_4$ 病区失配 | **ε 维度 2** | 与 $f_1$ 中等冲突（0↔11），实用极差 11，可作为第二维展开二维前沿面 |
| $f_0$ 占用 | **ε 维度 3（稀疏）** | 极差只有 2，但它是「多收一人」与「少收一人」的硬区别；取值 $\{18,19,20\}$ 三档即可 |
| $f_3$ 负载偏差 | **从 ε 网格中剔除** | 已证明 $f_3$ 的最小值由 $f_0$ 唯一确定（见上节结论 3），不携独立信息；只作为可行性诊断量 |
| $f_5$ 挪床 | **排除** | 无 `previous_beds` 时恒为 0，扫描无信息量；待 P8 滚动层接入后单独评估 |

#### 为什么不用纯锚点范围做 ε

$f_2$ 的纯理想值是 0，但取得 0 的唯一方式是 **$f_0=0$（零分配）**。若直接令 $\varepsilon_2=0$，模型要么不可行、要么退化成空方案。因此：

- **归一化**用纯理想点 $f^I$ / 纯最差点 $f^N$（数学上界，保证 $z_k\in[0,1]$）；
- **ε 取值**用实用区间 $[\tilde f^I_k,\tilde f^N_k]$（$f_0\ge18$ 下可达）；
- 两者都写入 `anchors_<run_id>.json`，各自独立可查。

#### 网格定义

$$
\varepsilon_k^{(j)} = \left\lceil \tilde f^I_k + \frac{j}{q_k-1}\left(\tilde f^N_k-\tilde f^I_k\right) \right\rceil,\quad j=0,\dots,q_k-1
$$

取整用向上取整（`math.ceil`）：ε 约束为 $f_k\le\varepsilon_k$，向上取整只会略微放松、保证端点可行；向下取整在 $\tilde f^I_k$ 附近可能使网格点不可行。

| 维度 | 目标 | 实用区间 | 档数 $q_k$ | 网格值 |
|------|------|----------|-----------|--------|
| 1 | $f_2$ overload | $[39,145]$ | 10 | 39, 51, 63, 75, 87, 98, 110, 122, 134, 145 |
| 2 | $f_4$ zone_mismatch | $[0,11]$ | 8 | 0, 2, 4, 5, 7, 8, 10, 11 |
| 3 | $f_0$ occupancy | $[18,20]$ | 3 | 18, 19, 20 |

**扫描规模**：$10\times8\times3 = 240$ 次求解。按单次 20–200 ms 估计，串行 5 s – 48 s，多进程后可压到 10 s 内，远低于原计划 $q^5=3{,}125$ 的规模。

#### 两阶段执行

| 阶段 | ε 维度 | 次数 | 目的 |
|------|--------|------|------|
| **A 稠密二维** | $f_2^{10}\times f_4^{8}$ | 80 | 得到主前沿曲线；$f_0$ 固定为 18（最保守） |
| **B 全维度** | $f_2^{10}\times f_4^{8}\times f_0^{3}$ | 240 | 检验提高占用下限是否带来新非支配点 |

阶段 A 先跑通求解、非支配过滤、超体积与拐点计算；阶段 B 在 A 的非支配集基础上对比，若新增点数 < 5% 则记录「$f_0\ge 19$ 对本实例无实质收益」作为结论，并在报告中给出这一结构性发现。


---

## P4 ε-约束扫描（预计 2 天）

扫描配置已由 P3 锚点确定为：主目标 $f_1$，ε 维度 $\{f_2, f_4, f_0\}$，$f_3$ 剔除、$f_5$ 排除。详见「P3 → ε 网格设计」。

- [ ] `epsilon_grid(pivot, ranges, qs) -> Iterable[dict]`：按公式 $\varepsilon_k^{(j)}=\lceil \tilde f^I_k + \frac{j}{q_k-1}(\tilde f^N_k-\tilde f^I_k)\rceil$ 生成
- [ ] `solve_with_epsilon(pivot, eps, hint=None) -> dict`
- [ ] 固定求解器种子（`num_search_workers=1`、`random_seed=0`），消除并列解抖动
- [ ] 相邻网格解作为 CP-SAT solution hint（`model.AddHint`）
- [ ] `nondominated_filter(solutions) -> list[dict]`
- [ ] `hypervolume(front, ref) -> float`
- [ ] `knee_point(front) -> dict`
- [ ] 多进程并行扫描（按 ε 组合分片）

**扫描规模**

| 阶段 | ε 维度 | 次数 | 预估耗时（单次 20–200 ms） |
|------|--------|------|----------------------------|
| A 稠密二维 | $f_2^{10}\times f_4^{8}$ | 80 | 2 s – 16 s |
| B 全维度 | $f_2^{10}\times f_4^{8}\times f_0^{3}$ | 240 | 5 s – 48 s |

**验收**

- 阶段 A（$f_2\times f_4$，$q=10\times8$）产出 ≥ 20 个非支配解
- 阶段 B 相对阶段 A 的新增非支配点 < 5% 时，记录「$f_0\ge19$ 对本实例无实质收益」
- 每个点都满足 $f_k\le\varepsilon_k$（$k\ne1$）
- 前沿中不存在被支配点
- 验证 $f_3$ 始终等于 $f_0$ 对应的结构最小值（诊断断言）
- 全扫描在 15 分钟内完成（B=20，n≤200）
- 输出六维目标值 + 成对投影图数据

---

## P5 结果持久化（预计半天）

- [ ] 新增迁移 `migrations/004_pareto_solutions.sql`

```sql
CREATE TABLE IF NOT EXISTS sched.pareto_solutions (
    run_id        TEXT NOT NULL,
    solution_id   INTEGER NOT NULL,
    f0_occupancy  INTEGER,
    f1_priority   BIGINT,
    f2_overload   BIGINT,
    f3_balance    INTEGER,
    f4_mismatch   INTEGER,
    f5_move       INTEGER,
    is_knee       BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (run_id, solution_id)
);
```

- [ ] `data_access/pareto_repo.py`：写入 / 读取前沿
- [ ] 分配明细可复用 `sched.assignments`（`run_id` 带 `#sN` 后缀）

**验收**

- 一次扫描后可用 SQL 查出前沿并按 HV 排序
- 同一 `run_id` 重复运行不会产生重复行

---

## P6 calib / eval 评估协议（预计半天）

- [ ] 锚点与 ε 网格只在 **calib** 上确定（`split="calib"`）
- [ ] **eval** 上只做前向评估，不调参
- [ ] 对比基线：现行加权和（4 组 λ）+ 随机/贪心
- [ ] 输出指标：HV、spacing、收治率、高危收治率、负载极差

**验收**

- 生成 `reports/pareto/eval_summary.json`
- 报告中明确写出"calib 调参、eval 报告"的实验协议

---

## P7 可选扩展目标（在上述六项之外）

六项目标集已固定；以下为后续可选增强，不与 $f_0$–$f_5$ 冲突时才考虑：

- [ ] **公平性**：最小化等待时间基尼系数，或最大化最弱势组收治率
- [ ] **峰值占用/超载风险**：$\min\max_d \text{occ}_d$ 或 CVaR
- [ ] **方案稳定性**：$f_5$ 已有，可扩展为加权挪床距离

**验收**

- 每个新目标都有独立单测（构造小实例验证取值）
- 加入后前沿维度增加，且 HV 单调不减

---

## P8 滚动层接入（预计 1–2 天）

- [ ] `domain/rolling/engine.py` 每步调用 `run_assignment(previous_beds=...)`
- [ ] 记录每步的 $f_5$ 与方案相似度
- [ ] 输出滚动轨迹中的"稳定性—收益"曲线

**验收**

- 跑完整 24h 仿真，$f_5$ 不再恒为 0
- 方案相似度指标可复现

---

## 附：常用命令

```powershell
$env:PYTHONPATH = (Get-Location)

# 测试
.\.venv\Scripts\python.exe -m pytest tests -q

# 单次加权和求解（现状）
.\.venv\Scripts\python.exe -m application.simulate

# 后续：Pareto 扫描（P4 完成后）
.\.venv\Scripts\python.exe -m application.pareto --pivot wait --q 5
```

## 附：文件改动地图

| 阶段 | 新增 | 修改 |
|------|------|------|
| P1 | — | `domain/optimizer/cp_sat.py`、`configs/optimizer.yaml`、`tests/test_lambda_weights.py` |
| P2 | `domain/optimizer/objectives.py` | `domain/optimizer/cp_sat.py` |
| P3–P4 | `domain/optimizer/pareto.py` | — |
| P5 | `data_access/pareto_repo.py`、`migrations/004_pareto_solutions.sql` | — |
| P6 | — | `application/`（新增评估入口） |
| P7 | — | `domain/optimizer/objectives.py` |
| P8 | — | `domain/rolling/engine.py` |
