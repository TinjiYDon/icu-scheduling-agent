# ICU 床位分配项目 · 创新点集合

> 版本：v1.0（2026-10-31）｜状态：创新点梳理（不涉及新实现）
> 范围：`icu-scheduling-agent`（双创）
> 结论先行：**不要主张“Pareto 排序/非支配解集”**（教科书，且仓库已有 4 点前沿）。可辩护主线是 **Pareto 决策层**（S1+S2+S3），前置是 **前沿质量协议**（S4）与 **数据质量修复**（S5）；RFCC/CARE（S6）是负结果，不主张。

---

## 0. 一页看懂

### 0.1 推荐主张

| 交付物 | 主创新 | 支撑 | 不主张 |
|---|---|---|---|
| 双创 · scheduling | S1 Pareto 决策层（VoF/CoM/MMR） | S2 HV–churn；S3 适配器；S4 前沿质量；S5 数据修复 | S6 RFCC/CARE；S8 四机理对照；S9 PPO |
| 论文/备选 | S1+S2 的决策价值与稳定性 | S4 多场景多 seed；S5 可信基线 | 不称新求解器/Pareto 排序 |

### 0.2 一句话版本

> 不是“再做一个 Pareto 排序”，而是回答“**前沿值多少钱、选哪个最稳、滚动时稳不稳**”；前置是先把前沿质量和数据质量修好。

---

## 1. 创新点总表

| ID | 名称 | 一句话 | 类型 | 状态 | 证据强度 | 可主张性 |
|---|---|---|---|---|---|---|
| **S1** | Pareto 决策层 | 在给定前沿上量化 VoF/CoM/MMR，而不是只给非支配解 | 机制/指标 | 已实现（合成） | B | **强（主线）** |
| **S2** | 滚动稳定性 HV–churn | 滚动重解的 HV 与换床率/前沿周转的权衡 | 机制/指标 | 已实现（合成） | B | **强（差异化）** |
| **S3** | 前沿适配 | 统一 moo_phase3/外部 JSON/裸矩阵三种 schema | 基础设施 | 已实现 | B | 中（支撑） |
| **S4** | 前沿质量协议 | 自适应 ε 扫描 + NSGA-II 对照 + HV/IGD/膝点 + 多 seed | 协议 | 设计 | C | **前置（不是卖点）** |
| **S5** | 数据质量修复 | 隔离/priority/候选池/los 单位的 D1/D2/D4 修复 | 工程前提 | 部分（archive 有） | B | **前置（必须）** |
| **S6** | RFCC + CARE/UHRM | 稀缺门控词典序 + 临床分配指数 | 撤回 | 五法同值 | B | **不主张（负结果）** |
| **S7** | 同池 bake-off 方法学 | 同池同资源比较五种方法 | 工程方法学 | 已实现 | B | 弱（工程） |
| **S8** | 四机理对照 | WS/Lex/ε/RFCC 在同一硬约束下对照 | 基线 | 已实现（4 点前沿） | B | 不主张（基线） |
| **S9** | PPO 离线对照 | 离线 PPO vs CP-SAT | 基线 | 代码在，模型缺失 | C | **不主张** |

---

## 2. 逐个创新点说清楚

### S1 Pareto 决策层（主线）

**一句话**：前沿生成之后，回答“选哪个、值多少钱、选错的代价”。

**痛点**：多目标床位分配没有单一最优；现有工作给一组非支配解就结束，医生仍要自己选；而“选”的代价没有被量化。

**机制**：

```text
F（非支配解集） + 偏好分布 w ~ Dirichlet
  → c(x;w) = −w·f(x)
  → VoF = E_w[c(single;w) − min_{x∈F} c(x;w)]
  → CoM = max_w[c(single;w) − min_{x∈F} c(x;w)]
  → MMR(x) = max_w[c(x;w) − min_{y∈F} c(y;w)]，按 MMR 升序排序
```

**证据（合成 60 点前沿，1000 组偏好）**：

| 指标 | 值 |
|---|---:|
| hypervolume | 0.483364 |
| VoF | 0.241821 |
| CoM | 0.539427 |
| front_turnover（示例） | 0.032787 |
| assignment_churn（示例） | 0.2 |

8 项单测；PR #17。

**与文献**：NSGA-II/ε-constraint 解决“生成”；DICA 做 allocation conformal；Yang 2026 做 CVaR+滚动+Pareto，但没有“前沿价值/选择/稳定性”的量化。本项填的是**决策层**。

**可主张**：强（问题设定 + 指标）；但必须承认前沿质量不足（4 点），先做 S4。

**状态/入口**：`domain/optimizer/pareto_decision.py`；`docs/PARETO_DECISION.md`。

---

### S2 滚动稳定性（HV–churn，差异化）

**一句话**：滚动重解时，质量（HV）与稳定性（换床/前沿周转）是权衡，不是越高越好。

**痛点**：每 2h 重解会改善分配，但频繁换床有临床/护理成本；现有滚动工作多只报质量，不报 churn。

**公式**：

\[
\tau_t=1-\frac{|F_t\cap F_{t+1}|}{|F_t\cup F_{t+1}|},\qquad
\chi_t=\frac{\#\{i:a_t(i)\ne a_{t+1}(i)\}}{\#\{i:\text{两期都有}\}}
\]

`hv_churn_series()` 逐步返回 `hv/n_front/turnover/churn`；`summarize_hv_churn()` 汇总。

**证据（合成 5 步）**：

| step | hv | turnover | churn |
|---:|---:|---:|---:|
| 0 | 0.517990 | 0.0 | 0.0 |
| 1 | 0.336053 | 0.647059 | 0.1 |
| 2 | 0.450693 | 0.705882 | 0.1 |
| 3 | 0.430709 | 0.600000 | 0.1 |
| 4 | 0.341402 | 0.647059 | 0.1 |

汇总：`mean_hv=0.415369`、`total_churn=0.4`、`mean_turnover=0.52`。18 项单测。

**与文献**：滚动时域（Spratt 2018、Learning-Guided RHO 2025）与公平排班有，但“HV–churn 权衡曲线”在 ICU 床位分配上未见系统实证；Yang 2026 未做稳定性。

**可主张**：强（差异化）；但 demo 是合成，真实 rolling 解集未接。

**状态/入口**：`domain/optimizer/pareto_io.py`；`docs/HV_CHURN.md`。

---

### S3 前沿适配（支撑）

**一句话**：把 `moo_phase3` 的 `ObjectivePoint`、外部 JSON、裸矩阵统一成 `(points, ids)`。

**痛点**：三种 schema 不统一；没有适配层，S1/S2 无法接真实解集。

**API**：`parse_front / normalize_points / FrontSnapshot / hv_churn_series`。

**证据**：三种 schema 单测；18 项测试含适配边界；PR #17。

**可主张**：中（基础设施贡献）；不单独作为创新点讲。

---

### S4 前沿质量协议（前置，不是卖点）

**一句话**：把“4 个非支配点”变成可发表的前沿：自适应 ε 扫描 + NSGA-II 对照 + HV/IGD/膝点 + 6 场景 × 5 seed。

**痛点**：当前“前沿”= 81 点 ε 网格里的 4 个点；单实例、参考点自定、无统计检验；有效维度只有 2–3。

**协议**：

1. payoff → ideal/nadir，归一化；
2. ε 自适应扫描 ≥1000 次精确求解（或分层网格）；
3. NSGA-II 对照（pymoo 或自写）；
4. HV/IGD/膝点/前沿规模；
5. 6 场景 × 5 seed，报均值±CI；
6. 固定 `num_search_workers=1`、seed，避免次目标抖动。

**证据**：尚未做；`main-archive` 有 P0–P3 基础设施，P4–P8 未实现。

**可主张**：前置/方法学；不能单独当创新点。

---

### S5 数据质量修复（必须）

**一句话**：不修数据，所有方法同解，S1/S2 没有意义。

**证据（本地 SQL/文档）**：

- 隔离启发式命中 76,157/94,458；top-20 中 19/20 被判需隔离，4 张 ISO 床只能收 5 人 → 五法同解；
- `priority ≡ 1+SOFA/10`（corr=1.0000，仅 13 个离散值）→ f0/f1/f2 近似退化；
- 候选池随权重重排 → 不同方法不在同池；
- `los_hours` 实为“天” → 滚动时间轴错误；
- SOFA 0–12、71.7% 集中在 4–5、只有 h0 → 高危/overload 区分弱。

**修复**：合 archive D1（isolation.mode=none）、D2（composite 权重）、D4.1（呼吸机 proxy）、D4.2（fixed_sample）、D4.3（elapsed_hours）。

**可主张**：工程前提；答辩可讲“我们定位并修复了会改变结论的数据缺陷”，但不要包装成算法创新。

---

### S6 RFCC + CARE/UHRM（负结果，不主张）

**一句话**：稀缺门控词典序 + CARE 指数，在同池五法上**没有任何判别力**。

**机制**：`n_patients > n_beds` 时切 risk-first 词典序；CARE = cover − 0.35·overload_norm − 0.35·UHMR_norm。

**证据**：bake-off 五种方法目标值与 CARE **完全相同**（assigned=5、high_risk=5、wait=11000、overload=12、CARE=−0.0965、UHRM=33.0）。CARE 系数 0.35 无出处、无敏感性；真实池上五法同解，机制从未触发差异。

**定位**：**负结果/撤回**。可以写“在修复数据前无法证明其价值”，但不能当创新。

---

### S7 同池 bake-off 方法学（工程）

**一句话**：同一批 stay、同一资源布局、同一硬约束下比较 greedy/WS/Lex/ε/RFCC。

**证据**：`run_method_bakeoff` 五法同池；但池被隔离床卡死，五法同解——目前只能证明“同池协议可跑”，不能证明方法差异。

**可主张**：弱（工程规范）；修数据后可升级为方法学证据。

---

### S8 四机理对照（基线）

**一句话**：WS/Lex/ε（+RFCC）在同一 CP-SAT 模型上对照。

**证据**：81 点 ε 网格 → 54 可行 → 4 非支配；HV=0.038794；WS occ=20/hr=4/wait=57937；Lex occ=20/hr=12/wait=58892/ov=84。

**定位**：**基线**；不是创新。教科书方法对照本身有价值，但不能当卖点。

---

### S9 PPO 离线对照（不主张）

**一句话**：离线 PPO 与 CP-SAT 的对照；模型文件缺失，且指标量纲不可比。

**证据**：`PPO_MODEL_HANDOFF.md` 写 PPO 73.1 vs Greedy 73.6 vs CP-SAT 13/200；奖励与“13/200”不同量纲，不可比。无轨迹协议，不宣称 online MIMIC-PPO。

**定位**：不主张；最多作为“为什么默认 CP-SAT”的工程说明。

---

## 3. 创新点关系

```text
S5 数据质量修复（前提）
        │
        ▼
S4 前沿质量协议（前提）
        │
        ▼
S3 前沿适配（基础设施）
        │
        ├──────────► S1 Pareto 决策层（VoF/CoM/MMR）
        │                    │
        │                    ▼
        └──────────► S2 滚动稳定性（HV–churn）
                             │
                             ▼
                  报告/选择/Streamlit/论文图表

S6 RFCC/CARE、S7 bake-off、S8 四机理、S9 PPO = 基线/负结果，不进入主 claim
```

---

## 4. 可主张 / 不可主张（答辩口径）

### 能说

- “我们提出 **Pareto 决策层**：量化前沿价值（VoF）、误配代价（CoM）、偏好稳健排序（MMR）。”
- “我们给出**滚动 HV–churn** 指标，把质量与稳定性放在同一张图上。”
- “我们提供统一的前沿适配层，能接 moo_phase3/外部 JSON。”
- “我们定位并修复了会改变结论的数据缺陷（隔离/priority/池/los）。”

### 不能说

- “我们提出了 Pareto 排序/非支配解集”（NSGA-II 教科书，且已有 4 点）。
- “RFCC/CARE 是有效的新机制/新指数”（五法同值）。
- “我们提出了新 CP-SAT 求解器”（没有）。
- “PPO 在线优于 CP-SAT”（无轨迹协议、量纲不可比）。

---

## 5. 证据台账与缺口

| 创新点 | 已有证据 | 缺什么 | 下一步 |
|---|---|---|---|
| S1 | 合成 60 点、8 单测、PR #17 | 真实前沿、6 场景×5 seed | 接 `summary_*.json` |
| S2 | 合成 5 步、18 单测 | 真实 rolling 解集 | 接 `run_rolling_contrast` |
| S3 | 三 schema 单测 | 真实 summary 适配 | 写 adapter 到 phase3 输出 |
| S4 | archive P0–P3 | P4–P8 | 自适应 ε + NSGA-II 对照 |
| S5 | SQL 实测 + archive 修复方案 | 合入 main + 重跑 | 先修 D1/D2/D4 |
| S6 | 五法同值 | 无 | 撤回/负结果 |
| S7 | bake-off 可跑 | 可区分机制的池 | 修数据后重跑 |
| S8 | 81/54/4、HV | 多 seed/统计 | P4 |
| S9 | 代码/文档 | 模型/轨迹/量纲 | 不主张 |

---

## 6. 推荐叙事（按交付物）

### 双创 · scheduling

> “我们不做第 N 个 Pareto 排序；我们做 **Pareto 决策层**：给定前沿，算它值多少钱（VoF）、选错多后悔（CoM/MMR）、滚动时稳不稳（HV–churn）；前提是先把数据质量和前沿质量修好。”

顺序：S5 → S4 → S3 → S1 → S2；S6/S7/S8/S9 只作为对照/负结果。

### 论文/备选

> “在 ICU 床位分配的多目标前沿上，我们量化偏好不确定下的前沿价值与滚动稳定性；并诚实报告：在修复数据缺陷前，RFCC/CARE 无可测差异。”

---

## 7. 公式速查

| 名称 | 公式 |
|---|---|
| 支配 | \(x\succ y \iff \forall k f_k(x)\ge f_k(y)\wedge\exists k f_k(x)>f_k(y)\) |
| 归一化 | \(\tilde f_k=(f_k-nadir_k)/(ideal_k-nadir_k)\)，clip [0,1] |
| 超体积 | \(HV=\mathrm{Vol}(\cup_{x\in F}[r,\tilde f(x)])\) |
| 代价 | \(c(x;w)=-\sum_k w_k\tilde f_k(x)\) |
| VoF | \(\mathbb{E}_w[c(single;w)-V^*(w)]\) |
| CoM | \(\max_w[c(single;w)-V^*(w)]\) |
| MMR | \(\max_w[c(x;w)-V^*(w)]\) |
| turnover | \(1-|F_t\cap F_{t+1}|/|F_t\cup F_{t+1}|\) |
| churn | 换床人数 / 两期共同患者数 |

---

## 8. 文件索引

| 内容 | 位置 |
|---|---|
| 代码 | `domain/optimizer/{pareto_decision,pareto_io}.py` |
| 测试 | `tests/test_{pareto_decision,pareto_io}.py` |
| 文档 | `docs/{PARETO_DECISION,HV_CHURN}.md` |
| 技术文档 | `analysis/docs-tech/技术文档-scheduling-H10-Pareto决策层.*` |
| PR | `icu-scheduling-agent#17` |
| 数据质量任务 | archive `MULTIOBJECTIVE_TASKS.md` D1/D2/D4 |
