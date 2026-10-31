# ICU 床位分配 Agent · H10 Pareto 决策层技术文档

> 版本：v1.1（2026-10-31）｜状态：研究原型（合成前沿）｜代码：`domain/optimizer/pareto_decision.py`、`domain/optimizer/pareto_io.py`
> PR：[icu-scheduling-agent#17](https://github.com/TinjiYDon/icu-scheduling-agent/pull/17)
> 关联：`moo_phase3`（前沿生成/HV）、H4-S（WS/Lex/ε 对照）、H6 滚动、H7 RFCC/CARE（不作为依据）。

---

## 0. 文档范围与结论

本文说明 scheduling 项目的**主要创新点、方法论、公式、函数定义与架构**。核心结论：

1. 多目标床位分配没有单一最优解，Pareto 前沿是正确的**表示层**；但“提出 Pareto 排序/非支配解集”是教科书内容，不能当卖点。
2. 可辩护的创新在**前沿之后**：前沿价值（VoF）、误配代价（CoM）、偏好稳健排序（MMR）、滚动稳定性（HV–churn）。
3. 当前 main 的“前沿”只有 81 点 ε 网格里的 4 个非支配解；H10 是决策层原型，**不重复**前沿生成，也不改变 CP-SAT 求解路径。
4. H7 的 RFCC/CARE 在同池五法中完全相同（CARE=−0.0965），不能作为 H10 的输入质量依据。

---

## 1. 系统现状与架构

### 1.1 分层

| 层 | 目录 | 职责 |
|---|---|---|
| L1 基础设施 | `infra/` | 配置、DB、日志 |
| L2 数据访问 | `data_access/` | `mimic_repo`、`assignments_repo` |
| L3 领域 | `domain/` | `scoring`（SOFA/priority）、`optimizer`（CP-SAT/多目标/H10）、`rolling`、`rl`、`ops` |
| L4 应用 | `application/` | `plan`、`simulate`、`moo_ui`、`run_moo_phase3/4`、`run_rolling_contrast`、`run_method_bakeoff` |
| L5 展示 | `presentation/` | Streamlit Ops 台 + MCP `optimize_beds` |

### 1.2 数据流（现状）

```text
MIMIC Layer0
  │  SOFA（肾/肝/凝血 3 项）+ 优先级
  ▼
staging.icustays → feat.sofa_timeseries → feat.patient_priority
  ▼
cp_sat.run_assignment()  ← 唯一建模入口
  ├─ 4 条硬约束：一床一人 / 一人一床 / 隔离床 / 呼吸机≤8
  ├─ 7 个目标：occupancy, high_risk, wait, overload, balance, zone_mismatch, move
  └─ 4 种机理：weighted_sum / lexicographic / epsilon_constraint / clinical_cascade
  ▼
sched.assignments（只存 run_id/stay_id/bed_id） + reports/*.json
  ▼
rolling.engine（每 2h 重解） → application.plan → Streamlit / MCP
```

### 1.3 当前 Pareto 能力（事实）

- `moo_phase3` 已实现：7 维方向感知支配判断、非支配过滤、精确超体积（`_hv_exact`）。
- 81 点 ε 网格 → 54 可行 → **4 非支配**；HV=0.038794（单实例、参考点自定）。
- 结果不落库；`sched.assignments` 无目标值/前沿表。
- `main-archive` 有目标注册表 + 锚点 + payoff + 理论（P0–P3），但 P4–P8 未实现，且与 main 未合并。

### 1.4 数据质量前提（不做就没有意义）

| 问题 | 影响 | 处理 |
|---|---|---|
| 隔离启发式误判（top-20 中 19/20 需 ISO） | 只能收 5 人，五法同解 | 合 archive D1：`isolation.mode=none` |
| `priority ≡ 1+SOFA/10`（corr=1.0） | f0/f1/f2 近似退化 | D2：composite 权重 |
| 候选池随权重重排 | 不同方法不在同池 | D4.2：`fixed_sample` |
| `los_hours` 实为“天” | 滚动时间轴错误 | D4.3：`elapsed_hours` |
| SOFA 只有 h0、分辨率低 | 高危/overload 区分弱 | D3（未修） |

---

## 2. 问题定义

### 2.1 多目标床位分配

给定患者集 \(\mathcal{P}\)、床位 \(\mathcal{B}\)、资源（隔离/呼吸机），选择分配 \(x_{ib}\in\{0,1\}\)：

```text
max  f(x) = (f_1,...,f_m)      # m=7（实际有效 2–3 维）
s.t. 硬约束（一床一人、一人一床、隔离、呼吸机）
```

目标互相冲突（占用 vs 高危覆盖 vs 错配 vs 换床），没有单一最优。

### 2.2 偏好未知

医生/管理者对不同目标的权重 \(w\) 未知，且随场景变化（容量紧张 vs 充裕）。单一加权和只给一个由 \(w_0\) 决定的解；换一组权重就要重解。

### 2.3 滚动

每 2h 有入出院，分配要重解；重解会带来**换床**与**前沿漂移**。稳定性和质量同样重要。

### 2.4 为什么“Pareto 排序”不够

非支配排序（NSGA-II 的一步）是标准算法；仓库已有基础版。真正缺的是：

1. 前沿**质量**（4 个点不是前沿）；
2. 前沿**值多少钱**（VoF）；
3. 选错的**后悔**（CoM/MMR）；
4. 滚动**稳不稳**（turnover/churn）。

---

## 3. 主要创新点

### I1 前沿质量（P4，前置）

自适应 ε 扫描 + NSGA-II 对照 + HV/IGD/膝点 + 6 场景 × 5 seed + 95% CI。把“4 个点”变成可发表的前沿。**不是 H10 代码，但 H10 的数值依赖它。**

### I2 前沿价值 VoF

在偏好不确定下，量化“有前沿 + 知道偏好”比“固定单解”多值多少钱：

```text
VoF = E_w[ c(x_single;w) − min_{x∈F} c(x;w) ]
```

### I3 误配代价与偏好稳健排序（CoM / MMR）

```text
CoM = max_w[ c(x_single;w) − min_{x∈F} c(x;w) ]     # 最坏偏好下的后悔
MMR(x) = max_w[ c(x;w) − min_{y∈F} c(y;w) ]          # 按最坏后悔升序排序
```

给医生一个“最坏情况下也不至于太差”的默认选择。

### I4 滚动稳定性（HV–churn，已实现）

```text
turnover = 1 − |F_t ∩ F_{t+1}| / |F_t ∪ F_{t+1}|
churn    = 换床人数 / 两期共同患者数
```

`domain/optimizer/pareto_io.py` 的 `hv_churn_series()` 逐步计算 `HV / turnover / churn`，`summarize_hv_churn()` 汇总；与 H6 滚动结合可画 HV–churn 曲线，策略：naive / freeze / 两步 lookahead / 迟滞。

### I5 前沿适配（已实现）

`moo_phase3` 的 `ObjectivePoint`、外部 JSON、裸矩阵三种 schema 不统一；`parse_front()` 统一为 `(points, ids)`，`normalize_points()` 做 max 型 [0,1] 归一化，`FrontSnapshot` 承载单步前沿。没有这一层，H10 的指标无法接真实解集。

### 不主张什么

- 不主张“Pareto 排序/非支配解集”是创新（教科书，且已有 4 点）；
- 不主张 RFCC/CARE（五法同值，判别力未证明）；
- 不主张新 CP-SAT 求解器；
- 不把合成 demo 写成 ICU 实证。

---

## 4. 方法论

### 4.1 A posteriori 多目标

先求一组非支配解，再让决策者在其中选；而不是把偏好提前压成单一权重。H10 只做“选”的量化，不重写求解。

### 4.2 偏好不确定性

用单纯形上的权重分布 \(w\sim \mathrm{Dirichlet}(1,\dots,1)\) 表示“未知偏好”；也可用三情景（效率/公平/安全）或医生问卷。VoF/CoM/MMR 都是对 \(w\) 的统计量。

### 4.3 后悔框架

- 期望后悔：\(E_w[c(x;w)-V^*(w)]\)；
- 最坏后悔：\(\max_w[\cdot]\)；
- MMR：选择最坏后悔最小的解。

这是决策论里的标准准则，但**在 ICU 床位分配上**尚未见系统实证。

### 4.4 滚动时域

每步重解后比较：

- 前沿周转（解集变化）；
- 分配换床（患者层面）；
- HV（质量）与 churn（稳定性）的权衡。

### 4.5 分阶段验证

| 阶段 | 数据 | 目的 | 状态 |
|---|---|---|---|
| V1 合成前沿 | `make_front` | 验证指标/排序 | ✅ 本 PR |
| V2 真实解集 | `reports/moo/summary_*.json` | 6 场景 × 5 seed 的 VoF/CoM | 待接 |
| V3 滚动 | `run_rolling_contrast` + `hv_churn_series` | HV–churn 曲线 | 指标已实现；待接真实多步解集 |
| V4 MIMIC 实证 | 数据授权后 | 论文级证据 | 等 F1 |

### 4.6 数据质量前置

不修 D1/D2/D4，所有方法在 5 人池上同解，VoF/MMR 也没有意义。H10 的 V2 必须发生在数据修复之后。

---

## 5. 公式

### 5.1 支配与前沿

对最大化目标：

\[
x\succ y \iff \forall k\, f_k(x)\ge f_k(y)\ \wedge\ \exists k\, f_k(x)>f_k(y)
\]

\[
F=\{x\in X\mid \nexists y\in X: y\succ x\}
\]

### 5.2 归一化

\[
\tilde f_k(x)=\mathrm{clip}\left(\frac{f_k(x)-\mathrm{nadir}_k}{\mathrm{ideal}_k-\mathrm{nadir}_k},0,1\right)
\]

### 5.3 超体积

\[
HV(F,\mathbf{r})=\mathrm{Vol}\left(\bigcup_{x\in F}[\mathbf{r},\tilde f(x)]\right)
\]

`hypervolume()` 复用 `moo_phase3._hv_exact` 的递归切片实现。

### 5.4 代价与后悔

\[
c(x;w)=-\sum_k w_k\tilde f_k(x),\qquad V^*(w)=\min_{x\in F}c(x;w)
\]

\[
VoF=\mathbb{E}_w[c(x_{single};w)-V^*(w)]
\]

\[
CoM=\max_w[c(x_{single};w)-V^*(w)]
\]

\[
MMR(x)=\max_w[c(x;w)-V^*(w)]
\]

### 5.5 稳定性

\[
\tau=1-\frac{|F_t\cap F_{t+1}|}{|F_t\cup F_{t+1}|}
\]

\[
\chi=\frac{|\{i:a_t(i)\ne a_{t+1}(i)\}|}{|\{i:a_t(i),a_{t+1}(i)\ \text{都存在}\}|}
\]

### 5.6 滚动序列

对每步 \(t\)：`hv_t = HV(F_t, ref)`；`turnover_t` 与 `churn_t` 相对 \(t-1\)（首步为 0）。汇总：

\[
\text{mean\_hv}=\frac1T\sum_t hv_t,\qquad
\text{total\_churn}=\sum_t churn_t,\qquad
\text{mean\_turnover}=\frac1T\sum_t turnover_t
\]

---

## 6. 函数定义

模块：`domain/optimizer/pareto_decision.py`。全部为纯函数/轻量类，不读 DB、不调求解器。

### 6.1 函数表

| 函数 / 类 | 签名 | 返回 | 说明 |
|---|---|---|---|
| `as_matrix` | `(points) -> np.ndarray` | 2D 数组 | 校验 shape |
| `dominates` | `(a, b) -> bool` | 是否支配 | 全最大化 |
| `nondominated_indices` | `(points) -> list[int]` | 索引 | 保留输入顺序 |
| `normalize_front` | `(values, ideal, nadir) -> np.ndarray` | [0,1] 矩阵 | 每维线性 |
| `hypervolume` | `(points, ref) -> float` | HV | 复用 `_hv_exact` |
| `simplex_weights` | `(n_samples, n_objectives, seed=0) -> np.ndarray` | 权重矩阵 | Dirichlet(1) |
| `value_of_front` | `(front, single, weights) -> dict` | VoF/CoM 等 | 含 regret_matrix |
| `expected_regret` | `(front, weights, solution_index) -> float` | 期望后悔 | 单解 |
| `minimax_regret_ranking` | `(front, weights) -> list[dict]` | 排序 | index/max_regret/mean_regret |
| `front_turnover` | `(ids_t, ids_t1) -> float` | 周转率 | Jaccard 距离 |
| `assignment_churn` | `(assign_t, assign_t1) -> float` | 换床率 | 共同患者 |
| `FrontSummary` | dataclass | 汇总 | `as_dict()` |
| `summarize_front` | `(front, single, weights, ref=None) -> FrontSummary` | 汇总 | HV+VoF+CoM+MMR |

### 6.2 关键代码

```python
def value_of_front(front, single, weights):
    f, w = as_matrix(front), as_matrix(weights)
    single = np.asarray(single, dtype=float)
    cost = -(f @ w.T)                 # (n, s)
    oracle = cost.min(axis=0)         # (s,)
    single_cost = -(single @ w.T)     # (s,)
    regret = cost - oracle
    single_regret = single_cost - oracle
    return {
        "VoF": float(np.mean(single_regret)),
        "CoM": float(np.max(single_regret)),
        ...
    }
```

```python
def minimax_regret_ranking(front, weights):
    cost = -(as_matrix(front) @ as_matrix(weights).T)
    oracle = cost.min(axis=0)
    regret = cost - oracle
    worst = regret.max(axis=1)
    order = np.argsort(worst)
    return [{"index": int(i), "max_regret": float(worst[i]),
             "mean_regret": float(regret[i].mean())} for i in order]
```

### 6.3 使用示例

```python
from domain.optimizer.pareto_decision import (
    normalize_front, simplex_weights, summarize_front,
)

front = normalize_front(raw_values, ideal, nadir)   # (n, m)
single = front[0]                                    # 固定 λ 的解
weights = simplex_weights(1000, front.shape[1], seed=0)
summary = summarize_front(front, single, weights)
print(summary.as_dict())  # HV / VoF / CoM / MMR top-5
```

---

### 6.4 前沿适配与滚动序列函数表（`domain/optimizer/pareto_io.py`）

| 函数 / 类 | 签名 | 返回 | 说明 |
|---|---|---|---|
| `FrontSnapshot` | `(step, ids, points, raw=None)` | dataclass | 单步前沿；`points` 已归一化、max 型 |
| `parse_front` | `(payload, objectives=None) -> (np.ndarray, list[str])` | (points, ids) | 支持裸矩阵 / `{"points":[{"values":...}]}` / `{"front":[...]}` |
| `normalize_points` | `(points, ideal=None, nadir=None) -> np.ndarray` | [0,1] 矩阵 | 默认 per-array min-max；常量维=1.0 |
| `hv_churn_series` | `(fronts, assignments, ref=None) -> list[dict]` | 逐步指标 | `hv/n_front/turnover/churn`；首步 turnover/churn=0 |
| `summarize_hv_churn` | `(series) -> dict` | 汇总 | `n_steps/mean_hv/total_churn/mean_turnover/last_hv` |

约定：
- `parse_front` 只解析、不归一化；`objectives` 缺省取所有行键并集排序；ids 优先 `source→id→name`，否则 `sol_<i>`。
- 空输入/非二维/行列不一致/NaN/Inf → `ValueError`；`fronts` 与 `assignments` 长度不一致 → `ValueError`。
- `ref` 维数必须与目标维数一致；默认全 0。

## 7. 架构展示

### 7.1 总架构（H10 位置）

```text
┌──────────────────────────── 求解层（现状） ────────────────────────────┐
│ cp_sat.run_assignment()                                                │
│   ├─ 4 硬约束                                                          │
│   ├─ 7 目标                                                           │
│   └─ 4 机理：WS / Lex / ε / clinical_cascade                           │
└───────────────────────────────┬───────────────────────────────────────┘
                                ▼
┌──────────────────────────── 评估层（现状） ────────────────────────────┐
│ moo_phase3: 支配判断 / 非支配过滤 / 精确 HV                            │
│ 81 点 ε 网格 → 54 可行 → 4 非支配 → HV=0.038794                        │
└───────────────────────────────┬───────────────────────────────────────┘
                                ▼
┌──────────────────────────── 决策层（H10，本 PR） ─────────────────────┐
│ pareto_decision:                                                       │
│   normalize_front → hypervolume                                         │
│   → value_of_front (VoF/CoM) → minimax_regret_ranking (MMR)            │
│   → front_turnover / assignment_churn（滚动）                          │
└───────────────────────────────┬───────────────────────────────────────┘
                                ▼
                    报告 / 选择 / Streamlit / 论文图表
```

### 7.2 与滚动的关系

```text
t=0  解集 F0 ──► parse_front → FrontSnapshot → H10: HV0, MMR 排序
       │
       ▼ 2h 重解
t=1  解集 F1 ──► parse_front → H10: HV1, turnover(F0,F1), churn(a0,a1)
       │
       ▼ hv_churn_series
    HV–churn 曲线 → 选择 freeze / lookahead / 迟滞
```

### 7.3 模块依赖

```text
moo_phase3 (DB-free helpers)
    ▲
    │ _hv_exact
pareto_decision (H10)
    ▲
    ├─ pareto_io (H10 适配/滚动)
    ├─ scripts/pareto_decision_demo.py
    ├─ scripts/hv_churn_demo.py
    ├─ tests/test_pareto_decision.py
    └─ tests/test_pareto_io.py
```

---

## 8. 算法伪代码

### 8.1 summarize_front

```text
Input: front[n,m] (normalized, max), single[m], weights[s,m], ref[m]
1. HV = hypervolume(front, ref)
2. cost = -(front @ weights.T)          # n×s
3. oracle = min over n for each s
4. single_cost = -(single @ weights.T)
5. VoF = mean(single_cost - oracle)
6. CoM = max(single_cost - oracle)
7. worst_regret[i] = max_s(cost[i,s] - oracle[s])
8. MMR order = argsort(worst_regret)
9. return {HV, VoF, CoM, MMR top-5}
```

### 8.2 滚动稳定性

```text
Input: F_t, F_{t+1}, assign_t, assign_{t+1}
1. turnover = 1 - |F_t ∩ F_{t+1}| / |F_t ∪ F_{t+1}|
2. churn = #changed / #common_patients
3. 与 HV_t/HV_{t+1} 一起画权衡曲线
```

---

## 9. 实验与证据

### 9.1 合成 demo（60 点前沿，2 目标，1000 组 Dirichlet 偏好）

| 指标 | 值 |
|---|---:|
| front size | 60 |
| hypervolume | 0.483364 |
| VoF | 0.241821 |
| CoM | 0.539427 |
| front_turnover（示例） | 0.032787 |
| assignment_churn（示例） | 0.2 |

**解读**：固定单解在最坏偏好下的后悔（CoM）很大，说明“给一组前沿 + 选择规则”有价值；但这是合成前沿，不能外推。

### 9.2 滚动 HV–churn（合成，5 步）

| step | n_front | hv | turnover | churn |
|---:|---:|---:|---:|---:|
| 0 | 10 | 0.517990 | 0.0 | 0.0 |
| 1 | 13 | 0.336053 | 0.647059 | 0.1 |
| 2 | 9 | 0.450693 | 0.705882 | 0.1 |
| 3 | 12 | 0.430709 | 0.600000 | 0.1 |
| 4 | 11 | 0.341402 | 0.647059 | 0.1 |
| **summary** | — | mean_hv 0.415369 | total_churn 0.4 | mean_turnover 0.52 |

**解读**：合成前沿每步独立归一化后，HV 只反映“形状”；跨步绝对可比需共用 ideal/nadir。turnover 高说明前沿组成变化大，需与 churn 一起看，不能只报 HV。

### 9.3 测试与 CI

- 本地：`pytest tests/test_pareto_io.py tests/test_pareto_decision.py tests/test_moo_phase3.py -q` → **35 passed**；
- PR #17 CI pytest **pass**（1m41s，首次推送时）；Sourcery 为外部 bot（pending）。

### 9.4 复现命令

```powershell
cd "C:\Users\lenovo\Desktop\decision shcedule\icu-scheduling-agent"
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_pareto_io.py tests/test_pareto_decision.py tests/test_moo_phase3.py -q
.\.venv\Scripts\python.exe scripts/pareto_decision_demo.py --n 60 --objectives 2 --seed 0
.\.venv\Scripts\python.exe scripts/hv_churn_demo.py --steps 5 --seed 0
```

---

## 10. 工程与复现

| 项 | 内容 |
|---|---|
| 依赖 | Python ≥3.11；numpy；无 DB/求解器（H10 本身） |
| 数据 | 合成前沿；真实解集待接 |
| 入口 | `scripts/pareto_decision_demo.py`、`scripts/hv_churn_demo.py` |
| 产物 | `reports/pareto_decision/demo.json`、`hv_churn_demo.json`（gitignored） |
| 测试 | `tests/test_pareto_decision.py`、`tests/test_pareto_io.py` |
| 文档 | `docs/PARETO_DECISION.md`、`docs/HV_CHURN.md`、本文 |
| PR | [icu-scheduling-agent#17](https://github.com/TinjiYDon/icu-scheduling-agent/pull/17) |

---

## 11. 局限与下一步

1. **前沿质量不足**：main 只有 4 个非支配点；需 P4（自适应 ε + NSGA-II + 多 seed）。
2. **偏好假设**：合成用 Dirichlet；真实偏好需医生问卷/选择实验。
3. **适配器已实现、真实数据未接**：`parse_front` 支持三种 schema，但尚未在 `reports/moo/summary_*.json` 上跑 6 场景 × 5 seed。
4. **滚动指标已实现、rolling 未接**：`hv_churn_series` 可算，但尚未接 `run_rolling_contrast` 的真实多步解集。
5. **HV 口径**：demo 每步独立 min-max，跨步只可比“形状”；绝对可比需全窗共用 ideal/nadir。
6. **数据质量**：D1/D2/D4 未修前，任何 VoF/MMR 结论都不可靠。
7. **H7 不可用**：CARE 五法同值，不能作为前沿质量依据。

---

## 12. 附录

### 12.1 符号表

| 符号 | 含义 |
|---|---|
| \(F\) | 非支配解集（前沿） |
| \(f_k\) | 第 k 个目标（越大越好） |
| \(w\) | 偏好权重（单纯形） |
| \(c(x;w)\) | 加权代价 |
| \(V^*(w)\) | 偏好 w 下的前沿最优代价 |
| \(HV\) | 超体积 |
| \(\tau\) | 前沿周转率 |
| \(\chi\) | 换床率 |

### 12.2 默认参数

| 参数 | 默认 | 说明 |
|---|---:|---|
| `objectives` | 2（demo） | 真实为 7（有效 2–3） |
| `weights` | 1000 | Dirichlet 采样数 |
| `ref` | 0 向量 | HV 参考点 |
| `n` | 60 | 合成前沿规模 |

### 12.3 已知不主张

- 不主张 Pareto 排序为创新；
- 不主张 RFCC/CARE；
- 不主张新求解器；
- 不把合成 demo 写成 MIMIC 实证。
