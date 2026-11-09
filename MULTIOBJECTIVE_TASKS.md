# 多目标优化实施任务清单

> 目标：把当前"线性加权单目标 CP-SAT"升级为"ε-约束 + Pareto 前沿"，并完成前沿质量检验。
> 理论依据见 [`MULTIOBJECTIVE_THEORY.md`](MULTIOBJECTIVE_THEORY.md)。
>
> 路线：P0–P3（已完成）→ P4 ε 扫描 → P5 持久化 → **P6 滚动层接入（已完成）** → **P7 前沿质量检验（进行中）**
> P7 对齐 `origin/main` 的 **S4 前沿质量协议 / I1**（自适应 ε + NSGA-II 对照 + HV/IGD/膝点/规模 + 6 场景 × 5 seed）。
>
> 数据问题：D1（隔离）、D2（优先级共线）、D3（六分量 SOFA）、D4（呼吸机 / 候选池 / los 单位）**均已完成**。

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

## 0.1 数据问题

数据探查结果详见 [`data_example.md`](data_example.md)。**D1、D2、D3、D4 均已完成**。

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

### D3 SOFA 区分度低且无时间序列（小样本入口已实现）

- 旧数据：0–12 分（仅肾/肝/凝血），71.7% 集中在 4–5 分；`sofa_timeseries` 只有 `hour_index = 0`。
- 影响：$f_2$ 分辨率不足；无法建模等待期间的病情演变。
- 修复方向：补齐呼吸/循环/神经分量；或按时间窗生成多小时 SOFA；或改用 SOFA 分段/阈值约束。
- 交付：`application.prepare_sofa_sample` 从 MIMIC-IV 3.1 固定抽样，按 2h 端点生成 24h 回顾窗的六分量 SOFA。留存证据时间、缺失标记与分量值。评分规则、数据覆盖条件与官方 SQL 的差异见 [SOFA_SCORING.md](SOFA_SCORING.md)。原数据库入口仍沿用历史评分口径。

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
| $f_5$ 挪床 | **排除** | 无 `previous_beds` 时恒为 0，扫描无信息量；待 P6 滚动层接入后单独评估 |

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

- [ ] 新增迁移 `migrations/005_pareto_solutions.sql`

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

## P6 滚动层接入（已完成 2026-11-07）

**目标**：让 $f_5$（挪床）从「恒为 0」变为真实有效维度，并把静态前沿接到滚动重解上。

> 交付：`domain/rolling/timed_pareto.py`（小样本回放入口）+ `application/run_timed_pareto.py`。
> 数学口径见 `MULTIOBJECTIVE_THEORY.md` 第 8 节「带时间标签的滚动 Pareto」。
> 旧 `domain/rolling/engine.py` 保留兼容，其随机出入院逻辑未改动。

- [x] `timed_pareto.py` 每步读取当时可用的 SOFA，把决策前床位传给求解器
- [x] 保存每步的 $f_5$、方案相似度、六目标值与备选分配
- [x] 保存稳定性与收益原始值，交给后续分析绘图
- [x] 每步重跑锚点：先跑加权和 reference，再用单目标求解构造 payoff 表，并设占用下限 $f_0\ge\lfloor\rho f_0^{I}\rfloor$（$\rho=0.9$）
- [x] 第 0 步另记初始状态，24h 回放共 **13 个决策快照**

**验收**

- 24h 回放含 13 个决策快照；按床位映射独立重算 $f_5$ 与相似度，并检查患者状态守恒
- 构造例验证非零挪床成立；**真实执行方案可为零**（不为满足"不再恒 0"而制造换床）
- 使用同一评分输入和种子复跑，核对决策与备选解一致

```powershell
.\.venv\Scripts\python.exe -m application.prepare_sofa_sample --zip ..\mimic-iv-3.1.zip --size 50 --seed 42
.\.venv\Scripts\python.exe -m application.run_timed_pareto --input artifacts/sofa_sample/sofa_sample.json --steps 12 --seed 42 --levels 2 --max-time 3
```

首次准备数据时逐块筛选压缩包；评分缓存可用 `application.prepare_sofa_sample --score-only` 重算。评分与轨迹分别写入 `artifacts/sofa_sample/` 和 `reports/rolling/`，两者均受 Git 忽略。

**验收记录（2026-11-07）**

复用 MIMIC-IV 3.1 的 50 例缓存，重新生成 1,250 条评分，与功能分支评分逐字节一致。第 24 小时有 12 例六分量均可评分，其他缺项保留标记。20 床、种子 42、稀疏网格（`levels=2`）跑两遍 24h，13 个时点的执行分配、六目标及前沿备选一致。执行方案均为 OPTIMAL 且未发生挪床，前沿备选中存在 $f_5>0$ 的可行方案。首轮验收 100 次 ε 求解中 87 次 OPTIMAL、2 次 FEASIBLE、11 次 INFEASIBLE。逐步核对评分可见时间、患者守恒、床位映射、挪床计数、ε 边界与非支配关系，全部通过。

补验使用本机 PostgreSQL 16 的 `127.0.0.1:5432`（在 `configs/database.yaml` 配置实际连接）。`test_db.py` 检查数据库连接与 `mock.icustays` 样例，`test_get_plan_not_found` 检查 `sched.assignments` 中不存在的方案；三项均通过，完整测试共 **105 项通过**。Docker 的 `5434` 是另一种部署方式，见 `README.md#快速开始`。复跑完整测试前可先创建 `artifacts/`。

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp artifacts/pytest_archive
```

**遗留问题（转交 P7）**

- `levels=2` 是接线验证用的稀疏网格，**不保证覆盖完整 Pareto 集**；每轮采样非支配点仅 1–4 个
- 该入口的优先级沿用 `sofa_rule`（$1+s/10$）作为明确基线，**未解决 D2 共线性**；不使用 `composite` 模式
- 默认 `retain_occupied=True`（住院患者必须保留床位），避免通过把住院者踢出队列规避换床代价

**2026-11-09 补充：$f_5$ 的分辨率与硬约束**

原验收项"能画出换床数↑时 $f_1$↑ 的权衡曲线"未兑现，根因是 `levels=2` 时 `move` 轴只有 $\{0,\ \text{实用最差}\}$ 两档。已补两项：

| 能力 | 接口 | 说明 |
|------|------|------|
| **$f_5$ 硬约束** | `run_assignment(max_moves=K)` 或 `max_moves_ratio=ρ` | $K=\lfloor\rho\,\lvert C_k\rvert\rfloor$；`max_moves` 优先。结果写入 `max_moves` / `max_moves_ratio` 字段。$K=0$ 等价于 main 文档的 **freeze** 基线 |
| **$f_5$ 单轴稠密扫描** | `run_timed_pareto(..., move_levels=q)` 或 CLI `--move-levels q` | 只施加占用下限与 $f_5$ 上界，其余 ε 轴**留空**（不钉在理想值，否则会把软目标变成硬约束）。每步 $q$ 次求解 |

**重要事实**：$f_5\le\lvert O_k^-\rvert\le n_{\text{beds}}=20$，所以 $f_5$ 最多 21 个取值，**与样本量、与 SOFA 完整度都无关**。`move_levels=10` 已饱和。

### 实测（2026-11-09，真实 MIMIC 50 例 / 20 床 / 13 步）

数据来源 `artifacts/sofa_sample/sofa_sample.json`（50 stays、1250 条评分；24h 六分量完整 12/50）。

**结论 1：$f_5$ 与 $f_1$ 之间不存在权衡。**

`pivot="wait"` 下扫描 $\varepsilon_5\in[0,19]$，$f_1$ **完全不变**。原因是结构性的：

$$f_1=\sum_i w_i\sum_b x_{ib}$$

只依赖"是否收治"，与**具体哪张床**无关。而 $f_5$ 只依赖床位身份。因此两者正交，不存在可交换的前沿。

> ⚠️ 原验收项"换床数↑ 时 $f_1$↑ 的权衡曲线"**在数学上不存在**，须替换。

**结论 2：$f_5$ 与 $f_4$（病区失配）之间存在真实权衡，但收益很快饱和。**

固定占用下限、以 `pivot="zone_mismatch"` 扫描 $\varepsilon_5$：

| 步 | $\varepsilon_5=0$ | $\varepsilon_5=2$ | $\varepsilon_5\ge4$ |
|----|------------------|------------------|---------------------|
| step 8（h=16） | $f_4=1$ | $f_4=\mathbf{0}$ | 恒为 0 |
| step 11（h=22） | $f_4=2$ | $f_4=1$ | 恒为 1（**下不去**） |

即：**挪 2 张床可修复 1 个病区失配，但继续挪无收益**。

**结论 3：三元权衡 $f_0\leftrightarrow f_4\leftrightarrow f_5$。**

以 step 8 为例：

| 策略 | $f_0$ | $f_4$ | $f_5$ |
|------|------:|------:|------:|
| 加权和执行（占满 + 冻结） | 20 | 2 | 0 |
| 冻结 + 少收 1 人 | 19 | 1 | 0 |
| 挪 2 床 + 少收 1 人 | 19 | 0 | 2 |

多收 1 人使 $f_4$ 恶化 1；修复这 1 个失配需挪 2 床且退掉 1 个床位。

**结论 4：`max_moves` 对加权和**从不 binding**。**

在 step 2/5/8 上令 $K\in\{0,1,\dots,19,\text{None}\}$，**所有目标值完全一致**（$f_0=20$，$f_1$ 不变，$f_3=f_4=f_5=0$）。

说明：加权和的全局最优解本身就是 $f_5=0$。因此

- 执行方案 $f_5\equiv0$ **不是因为 $\lambda_{\text{move}}$ 调得太大**，而是"不动"同时是最优策略；
- 要让 $f_5$ 参与决策，必须**换主目标**（如 `pivot=zone_mismatch`）或**把前沿纳入选解规则**，仅调 $\lambda$ 无效。

### 转出作为决策变量（2026-11-09 新增，不加 $f_6$）

**动机**：$f_5$ 不含患者流转，时间滚动缺少决策抓手。把"转出"由外生随机事件改为决策变量后，$\tau_k$ 通过资格闸门进入模型。

**接口**

| 参数 | 位置 | 说明 |
|------|------|------|
| `transferable=[...]` | `run_assignment` | 本步可转出的 stay_id；必须已在 `previous_beds` 中 |
| `max_transfers=K` | `run_assignment` | 每步转出上限（**约束**，防止"转出免费"导致一次转空） |
| `sofa_transfer_max=s*` | `run_timed_pareto` / `--sofa-transfer-max` | SOFA 闸门，默认 `None` = 关闭 |
| `min_icu_hours=m` | `run_timed_pareto` / `--min-icu-hours` | 最短 ICU 时长，默认 24 |

**约束**：$i\in O_k^-$ 时 $\sum_b x_{ib}+x^{out}_i=1$；$x^{out}_i\le\mathbb{1}[i\in E_k]$；$\sum_i x^{out}_i\le K$。

**守恒扩展为五态**：待到达 / 等待 / 占床 / **已转出** / 已出院。

#### 实测（真实 MIMIC 50 例 / 20 床 / 13 步，$s^*=2$，$m=24$，$K=2$）

| 指标 | 关闭转出 | 启用转出 | 差 |
|------|--------:|--------:|---:|
| 累计转出 | 0 | **3** | +3 |
| 符合条件的累计人次 | 0 | 19 | +19 |
| $\sum f_0$ | 260 | 260 | 0 |
| $\sum f_1$ | 431,200 | 432,000 | **+800** |
| $\sum f_2$ | 1,712 | 1,720 | +8 |
| $\sum f_4$ | 11 | 16 | **+5**（变差） |
| $\sum f_5$ | 0 | 0 | 0 |
| 非支配点合计 | 49 | 43 | −6 |
| 期末等待人数 | 18 | 15 | −3 |

转出患者：`30361469`(SOFA=2)、`31361473`(SOFA=2)、`35945552`(SOFA=1)，**全部满足闸门**。

#### 关键发现：转出存在**池效应**，跨配置对比被污染

逐步 $f_1$ 变化：

| 步 | 0–3 | 4–9 | 10–12 |
|----|-----|-----|-------|
| $\Delta f_1$ | 0 | **+500 ~ +1100** | **−200 ~ −1800** |

- **中段改善**：腾出的床位被更高优先级患者占用 → $f_1$ 上升
- **后段恶化**：转出者**永久离开候选池**，末期可收治人数减少 → $f_1$ 下降

因此 $\sum f_1$ 的 +800 **不能**解释为"转出更优" —— 两个配置的候选池不同。这正是 `docs/AIGC_CONTRACT.md` 中 $B_{\text{pool}}$ 所要剔除的偏差；**转出的效果评估必须在同池协议下重做**（P7）。

#### 其他须披露的语义

- 转出即**离开床池且不返回**，未建模普通病房
- 优先级并列时转出对目标无差别，求解器在并列解中任意选取
- 转出**不计入 $f_5$**（离开不是挪床），$f_5$ 语义不变
- 当前闸门 $s^*=2$ 下 13 步只有 19 人次达标，转出机会稀疏

---

## P7 前沿质量检验（预计 2–3 天）

**定位**：对齐 `origin/main` 文档的 **S4 前沿质量协议 / I1**。这一项是**前置方法学支撑**，不作为创新点主张（见 `docs/INNOVATION_PORTFOLIO.md` §S4）。

> main 文档对当前状态的描述：「当前“前沿”= 81 点 ε 网格里的 4 个点；单实例、参考点自定、无统计检验；有效维度只有 2–3」。
> 本阶段要回答三个不同层次的问题：**结果好不好**、**方法值不值得**、**结论可不可信**。

### 7.1 前沿规模（回答"结果好不好"）

- [ ] 扫描输出 `n_grid / n_feasible / n_nondominated`
- [ ] 非支配率 $|F| / |F_{\text{feasible}}|$
- [ ] spacing（Schott）：$\sqrt{\frac{1}{|F|-1}\sum_{i}(\bar d - d_i)^2}$，衡量间距均匀性
- [ ] 跨 seed 汇总（均值 ± 95% CI）

**为什么**：4 个点连曲线都画不出；且 VoF 公式里的 $\min_{x\in F}$ 会因前沿稀疏而被系统性低估。

### 7.2 IGD（回答"前沿有没有漏区"）

$$\text{IGD}(F, P^*) = \frac{1}{|P^*|}\sum_{p^*\in P^*} \min_{f\in F} d(p^*, f)$$

- [ ] `igd(front, ref_front, ideal, nadir) -> float`（越小越好）
- [ ] 参考前沿 $P^*$ = **全方法并集**再做一次非支配过滤（CP-SAT 稠密扫描 ∪ NSGA-II 存档 ∪ WS ∪ Lex）
- [ ] **禁止**用单一方法自己的前沿当 $P^*$（循环论证）
- [ ] 与 HV 使用同一套 ideal/nadir，避免口径不一致

**为什么**：HV 只看"包住多少体积"，不惩罚中间空洞；IGD 从参考前沿逐点回看，能抓住"前沿某一段完全缺失"。

### 7.3 NSGA-II 对照（回答"方法值不值得"）

- [ ] 编码：解 = 患者的一个排列 $\pi$；解码 = 按 $\pi$ 顺序贪婪放床，**构造上保证满足硬约束**
- [ ] 交叉：PMX（部分匹配交叉）；变异：两点交换
- [ ] 封装 `pymoo` 的 `Problem`（变量 = 排列，目标 = 六项 $f_0$–$f_5$）
- [ ] **同池、同 split、同时限**（与 CP-SAT 完全同一实例）
- [ ] 对比维度：HV / IGD / 前沿规模 / 可行性违反数 / 耗时 / 是否可证明最优

**为什么**：多目标优化的标准答案是 NSGA-II，且领域内最接近的工作（SciRep 2023 ICU 两阶段分床）用的就是 NSGA-II。不做对照就无法回答"为何不用标准方法"。

**预期结论**：CP-SAT 每点可证明最优但前沿密度受网格限制；NSGA-II 密度高但无最优性保证。这是一个**真实的成本–质量权衡**，本身就是可写的结论。

### 7.4 多场景 × 多 seed（回答"结论可不可信"）

**场景（6 个，可直接复用 main 的 `moo_scenarios.SCENARIOS`）**

| ID | 场景 | 变化 |
|----|------|------|
| S1_normal | 正常容量 | 20 床 / 4 ISO / 8 呼吸机 |
| S2_bed_shortage | 总床位不足 | n_beds=12 |
| S3_iso_shortage | 隔离床不足 | n_isolation_beds=1 |
| S4_vent_shortage | 呼吸机不足 | n_ventilators=2 |
| S5_high_sofa | 高 SOFA 集中 | 候选池 SOFA≥8 |
| S6_zone_skew | 科室需求不均 | 候选池偏 MICU |

**随机源（5 个 seed）**：候选池抽样、calib/eval 划分、CP-SAT tie-breaking、NSGA-II 初始化。

- [ ] $6 \times 5 = 30$ 次实验，**配对设计**（同场景同 seed 下所有方法共用同一实例）
- [ ] 锚点与 ε 网格只在 **calib** 上确定；**eval** 上只做前向评估，不调参
- [ ] 报均值 ± 95% CI：$\bar x \pm 1.96\,s/\sqrt{n}$
- [ ] 方法间比较用 **Wilcoxon 符号秩检验**（配对、不假设正态），报 p 值

**规模**：$240\ \text{网格点} \times 6\ \text{场景} \times 5\ \text{seed} = 7200$ 次求解（仅 CP-SAT 部分）；单次 20–200 ms，串行 2.4–24 min，多进程可压到 1–3 min。

### 7.5 验收

| 指标 | 最低要求 |
|------|----------|
| 前沿规模 | 阶段 B 单场景单 seed 非支配点 ≥ 20；30 次实验报均值 ± CI |
| HV | 已有精确实现（参考 main 的 `_hv_exact`）；跨 seed 报均值 ± CI |
| IGD | 已实现且只用**全方法并集**作参考前沿；30 次均有值 |
| NSGA-II | 能跑通、可行性违反 = 0（靠解码器保证）；产出 HV/IGD/规模/耗时四行对比表 |
| 统计 | 方法与场景的热图表 + Wilcoxon p 值表 |
| 闭环 | 若 IGD 显示某段空洞，需回到 P4 加密网格并重跑，直到不再改善 |

**产出**：`reports/pareto/front_quality_<run_id>.json`（含 30 次原始指标、汇总、CI、p 值）+ 成对投影图数据。

---

## 附：常用命令

```powershell
$env:PYTHONPATH = (Get-Location)

# 测试
.\.venv\Scripts\python.exe -m pytest tests -q

# 单次加权和求解
.\.venv\Scripts\python.exe -m application.simulate

# 锚点求解（P3）
.\.venv\Scripts\python.exe -m application.pareto

# 六分量 SOFA 小样本 + 滚动 Pareto 回放（P6，已完成）
.\.venv\Scripts\python.exe -m application.prepare_sofa_sample --zip ..\mimic-iv-3.1.zip --size 50 --seed 42
.\.venv\Scripts\python.exe -m application.run_timed_pareto --input artifacts/sofa_sample/sofa_sample.json --steps 12 --seed 42 --levels 2 --max-time 3

# 后续：前沿质量检验（P7）
.\.venv\Scripts\python.exe -m application.front_quality --scenarios all --seeds 5
```

## 附：文件改动地图

| 阶段 | 新增 | 修改 |
|------|------|------|
| P1 | — | `domain/optimizer/cp_sat.py`、`configs/optimizer.yaml`、`tests/test_lambda_weights.py` |
| P2 | `domain/optimizer/objectives.py` | `domain/optimizer/cp_sat.py` |
| P3–P4 | `domain/optimizer/pareto.py` | — |
| P5 | `data_access/pareto_repo.py`、`migrations/005_pareto_solutions.sql` | — |
| **D3** | `domain/scoring/sofa_full.py`、`data_access/mimic_sample.py`、`application/prepare_sofa_sample.py` | — |
| **P6** | `domain/rolling/timed_pareto.py`、`application/run_timed_pareto.py` | `domain/optimizer/cp_sat.py`、`domain/optimizer/pareto.py` |
| **P7** | `domain/optimizer/front_quality.py`、`domain/optimizer/nsga2.py`、`application/front_quality.py` | — |
