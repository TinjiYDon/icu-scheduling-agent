# icu-scheduling-agent · 技术总览（Technical Overview）

> 版本：v2.0（2026-11-02）｜代码基线：`main@42471c6`
> 本文档定位：**意图与责任分离**的完整技术说明——「为什么这样做」（意图）与「谁来做、在哪做」（责任）分开写，供介绍/展示/答辩/交接四方使用。
> 索引方式：① `docs/README.md` 分类索引（按用途找文档）；② 本文档 §9 目录树；③ 代码内 docstring。

---

## 0. 文档导航

| 你想做什么 | 读什么 |
|---|---|
| 一句话讲清项目 | 本文 §1、§2 |
| 讲创新点、答"差在哪" | 本文 §3、§4 |
| 讲架构与分层 | 本文 §1.3–1.5 |
| 讲为什么选这些技术 | 本文 §5 |
| 讲实验与数据 | 本文 §6、`docs/STATUS.md`、`docs/AIGC_CONTRACT.md` |
| 答辩被追问 | 本文 §4（调研结果）与 §10（边界） |

---

## 1. 架构

### 1.1 意图（为什么这么分）

总目标 SSOT：**可审计 · 可对照 · 可滚动**。

| 意图 | 落点 |
|---|---|
| 可审计：每个分床决策能解释 | `domain/optimizer/explain.py`（目标分项 + 约束绑定） |
| 可对照：改目标/滤波器会改写候选池，必须同池 | 同池协议 + `pool_effect.py`（B_pool 分解） |
| 可滚动：每 2h 重解且换床有惩罚 | `domain/rolling/engine.py` + move 惩罚 |
| AIGC 生成前必须自证字段可用 | `data_contract.py`（DAC） |
| 评测不能被数据语义污染 | `fd_stress.py`、`pool_effect.py` |

### 1.2 责任（谁做、在哪做）

| 层 | 目录 | 责任 | 关键文件 |
|---|---|---|---|
| L1 | `infra/` | 配置/引擎 | `config.py`、`db.py` |
| L2 | `data_access/` | MIMIC 只读、结果写库 | `mimic_repo.py`、`assignments_repo.py` |
| L3 | `domain/` | 业务逻辑（无 IO） | `scoring/`、`optimizer/`、`rolling/`、`rl/`、`ops/` |
| L4 | `application/` | 用例编排（页面只调这里） | `plan.py`、`simulate.py`、`run_moo_phase3/4`、`run_method_bakeoff`、`run_pto_ablation`、`run_rolling_contrast` |
| L5 | `presentation/` | UI/MCP | `streamlit_app.py`、`ui/*`、`mcp_tools.py` |

### 1.3 数据流

```text
MIMIC Layer0 (mimiciv_hosp/mimiciv_icu)
  → domain/scoring: SOFA(肾/肝/凝血, 0–12) → feat.sofa_timeseries
  → 优先级: u_sofa/u_formula/u_gbdt → feat.patient_priority
  → DAC 校验（AIGC 生成模型前）→ fd_stress 度量
  → cp_sat.run_assignment（4 硬约束 / 7 目标 / 4 机理）
  → sched.assignments + moo_phase3 前沿(HV) + pareto_decision(VoF/CoM/MMR)
  → rolling 重解 → pool_effect(B_pool) → Streamlit/MCP
```

### 1.4 求解模型

- 变量 `x[i,b]∈{0,1}`；硬约束：一床一人、一人一床、隔离患者只用隔离床、呼吸机总数 ≤ V。
- 目标 7 个：occupancy、high_risk、wait(=priority_served)、overload、balance、zone_mismatch、move。
- 目标归一化系数 `c_k = round(λ_k·10^6 / UB_k)`；λ 来自 `configs/optimizer.yaml`（occupancy 2.0、wait 0.5、overload/balance/zone 0.1、high_risk 0.0）。
- 4 种机理：`weighted_sum` / `lexicographic` / `epsilon_constraint` / `clinical_cascade`（H7 RFCC，负结果不主张）。

---

## 2. 主要创新点（一览）

| ID | 创新点 | 状态 | 证据 | 可主张性 |
|---|---|---|---|---|
| S-A1 | 语义可用性契约（DAC） | 已实现 | raw→refuse(3 违规)/repaired→pass；refusal_accuracy=1.0 | 强（主线） |
| S-A2 | FD 压测 | 已实现 | spurious_DoF 3→0 | 强（配套） |
| S-A3 | 同池反事实 B_pool | 已实现 | 合成 B_pool=0.130；H5/H6/H7 口径自检 | 强（评测方法论） |
| S-B | 数据可用性诊断（三条实证发现） | 已验证 | 隔离 76,157/94,458；priority corr=1.0；los 单位错 | 强（证据底座） |
| S-C | Pareto 决策层（VoF/CoM/MMR + HV–churn） | 已实现 | HV 0.4834/VoF 0.2418/CoM 0.5394 | 中（依赖前沿质量） |
| — | RFCC/CARE、PPO、四机理、"Pareto 排序" | 负结果/基线 | 五法同值 −0.0965 | 不主张 |

---

## 3. 创新点详细解释

### S-A1 DAC（语义可用性契约）

- **问题**：AIGC 生成优化模型前，字段语义没人检查；`priority=1+SOFA/10` 是函数依赖、`los_hours` 实为天、隔离需求是 careunit 关键词启发式。
- **做法**：每条约束/目标声明 `FieldContract`（字段、可用级别 exact/proxy/heuristic/stale/unit_error/missing、depends_on、redundant_with）+ `ConstraintContract`；`check_contract(contracts, columns, fd_map)` 返回 `pass|degrade|refuse`；`degrade_or_refuse(report, policy)` 给动作。
- **与先行工作差异**：OptiTrust 验证“解对不对”，我们验证“字段语义够不够”，且契约是**生成前置条件**。
- **边界**：契约工具报“未声明”的冗余，不自动发现新 FD。

### S-A2 FD 压测

- **问题**：生成器会把冗余字段当独立自由度（虚假变量/约束）。
- **做法**：`KNOWN_FDS` 注入三条实证发现的函数依赖；`spurious_dof(model_spec, fds)` 计数；`field_alignment`、`refusal_accuracy`、`ranking_stability`。
- **与先行工作差异**：OptiBench/ReSocratic 测数学正确性，不测 FD 盲区。

### S-A3 B_pool（同池反事实）

- **问题**：改目标/滤波器会改写候选池，方法对比不可信。
- **做法**：`B_pool = Δ_naive − Δ_match`；`decompose` 拆成 pool/mechanism/interaction；`summarize_pool_effect` 汇总。
- **证据**：合成例 0.130；现有 H5/H6/H7 报告 B_pool=0（共享池，池效应未分离——口径自检）。

### S-B 三条实证发现（数据底座）

1. 隔离启发式 76,157/94,458；top-20 中 19/20 被判需隔离 → 4 张 ISO 床只能收 5 人，方法同解。
2. `priority ≡ 1+SOFA/10`（corr=1.0、13 个值）→ 目标退化。
3. `los_hours` 实为天 → 滚动时间轴错。

### S-C Pareto 决策层

- `pareto_decision.py`：VoF（前沿价值）、CoM（误配代价）、MMR（最小最大后悔）、HV、turnover/churn。
- `pareto_io.py`：三种 schema 适配 + 滚动 HV–churn。
- 主张“决策层”，不主张“Pareto 排序/非支配集”（教科书）。

---

## 4. 调研结果（撞车尽调摘要）

| 先行工作 | 做了什么 | 我们的差异 | 等级 |
|---|---|---|---|
| OptiTrust（[arXiv:2508.03117](https://arxiv.org/abs/2508.03117)） | 可验证合成数据 + NL→solver | 验证解 vs 验证字段语义 + 生成前拒绝 | 轻 |
| OptiBench/ReSocratic（[arXiv:2407.09887](https://arxiv.org/abs/2407.09887)） | 端到端优化 benchmark（含 tabular） | 数学正确性 vs FD 盲区 | 轻 |
| IJCAI26 tutorial（[Zenodo](https://zenodo.org/records/21998210)） | NL2MILP 全景（Nl4Opt/ComplexOr/IndustryOr…） | 我们不做生成器/benchmark 规模竞争 | — |
| NL→MILP validation-in-the-loop（[arXiv:2508.08147](https://export.arxiv.org/pdf/2508.08147)） | 生成后校验修复 | 我们生成**前**契约拒绝 | 轻 |

结论：**“生成优化模型”拥挤；“数据语义自证 + FD 盲区 + B_pool”未被覆盖。**

---

## 5. 选型原因

| 选择 | 原因 |
|---|---|
| OR-Tools CP-SAT | 整数精确求解，硬约束天然表达；换机理不换求解器，便于对照 |
| 4 机理（WS/Lex/ε/cascade） | 同一模型换目标语义，答“是不是只拼了 OR-Tools” |
| 仓内 GBDT 优先级 | 不接外部 risk_score，保持与 decision 解耦 |
| numpy 纯函数（DAC/FD/B_pool/H10） | 无 DB/网络，可单测、可复现、CI 友好 |
| PostgreSQL 16 | 与 decision 同构的本地数据层；dump 可迁移 |
| Streamlit + MCP | 演示台与对外接口 |
| PPO 离线对照 | 默认 cp_sat；无轨迹协议不宣称 online |
| LLM 只喂合成数据 | 患者数据不出本机；AIGC 环节不接触真实数据 |

---

## 6. 实现路径

1. **数据**：`mimic` 库（`mimiciv_hosp`/`mimiciv_icu`）→ staging（94,458 stays）→ feat（SOFA/priority）。
2. **新模块落点**（本轮 PR #18/#19）：
   - `domain/optimizer/data_contract.py`、`fd_stress.py`、`pool_effect.py`
   - `scripts/aigc_contract_demo.py`、`scripts/aigc_mimic_grid.py`
   - `tests/test_{data_contract,fd_stress,pool_effect,aigc_grid}.py`
   - `docs/AIGC_CONTRACT.md`
3. **测试矩阵**：no-DB 回归 **91 passed**；CI（`.github/workflows/ci.yml`）跑 8 个文件。
4. **MIMIC 网格**：`scripts/aigc_mimic_grid.py --source db --levels 3 --seeds 5`（6 场景 × 5 seed；F1 已确认后运行）。

---

## 7. 专有名词详解

| 术语 | 解释 |
|---|---|
| DAC | Data Availability Contract：字段可用性契约；生成前自证字段语义，否则拒绝/降级 |
| FD | 函数依赖：一个字段可由其它字段确定（如 priority=1+SOFA/10） |
| spurious_DoF | 虚假自由度：把冗余字段当独立变量的数量 |
| B_pool | 池效应偏差：朴素对比 − 同池对比；>0 表示整池高估机制增益 |
| CP-SAT | OR-Tools 的约束规划+SAT 混合求解器 |
| ε-约束 | 主目标优化 + 其余目标给下/上界，扫网格得到前沿 |
| HV | 超体积：前沿覆盖参考点区域的体积 |
| VoF / CoM / MMR | 前沿价值 / 误配代价 / 最小最大后悔（H10 决策层指标） |
| SOFA | 序贯器官衰竭评分（本仓只用肾/肝/凝血 3 项，0–12） |
| turnover / churn | 前沿周转率 / 换床率 |
| F1 | MIMIC DUA/CITI 合规门（2026-11-02 用户已确认，真实数据实验已开跑） |

---

## 8. 关键 API 与主要函数

| 函数 | 签名 | 说明 |
|---|---|---|
| `run_assignment` | `(run_id=None, lambda_weights=None, *, persist=True, split=None, stay_ids=None, occupied_beds=None, objective_mode="weighted_sum", objective_order=None, epsilon_primary="wait", epsilon_bounds=None, max_time_seconds=None, resource_overrides=None, priority_overrides=None)` | 单次分床；返回 assigned/evaluation/top_assignments |
| `run_rolling_simulation` | `(n_steps=12, discharge_rate=None, admission_rate=None, *, reoptimize=True, persist=True)` | 滚动仿真（同种子对照贪心） |
| `check_contract` | `(contracts, columns, fd_map) -> ContractReport` | DAC 校验 |
| `degrade_or_refuse` | `(report, policy="strict") -> dict` | 拒绝/降级判定 |
| `spurious_dof` | `(model_spec, fds) -> int` | FD 盲区计数 |
| `field_alignment` | `(model_spec, contracts) -> float` | 约束-字段对齐率 |
| `pool_effect` | `(naive_a, naive_b, matched_a, matched_b) -> dict` | 池效应分解 |
| `value_of_front` / `minimax_regret_ranking` | 见 `pareto_decision.py` | VoF/MMR |
| `parse_front` / `hv_churn_series` | 见 `pareto_io.py` | 前沿适配/滚动指标 |
| MCP `optimize_beds` | `(run_id?) -> JSON` | 对外接口 |

---

## 9. 文档位置与索引方式

```text
docs/
├── README.md              ← 分类索引入口（总览/创新/架构/实验/数据/移交）
├── TECHNICAL_OVERVIEW.md  ← 本文档（技术总览）
├── MASTER_NARRATIVE.md    ← 总目标叙事（SSOT）
├── AIGC_CONTRACT.md       ← DAC/FD/B_pool 详解
├── PARETO_DECISION.md / HV_CHURN.md  ← H10 决策层
├── MODEL_FORMULAS.md      ← 全部公式
├── STATUS.md / ROADMAP.md ← 进度与计划
├── archive/               ← 旧版本（保存不删）
```

**索引方式**：① `docs/README.md` 按用途分六类链接；② 本文 §0 导航表；③ 代码 docstring；④ 旧版文档在 `docs/archive/`。

---

## 10. 合规与移交

- **F1 状态**：DUA/CITI 已于 2026-11-02 经用户确认；真实 MIMIC 实验已启动（`mimic` 库 546,028 admissions / 158.4M labevents，schema `mimiciv_hosp`/`mimiciv_icu`）。
- 数据不入 Git；外部 LLM 只喂合成数据。
- 分工：A=ETL/dump；B=SOFA/CP-SAT/创新点；C=L4+UI。
