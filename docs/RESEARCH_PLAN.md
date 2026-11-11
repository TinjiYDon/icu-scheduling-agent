# RESEARCH PLAN（scheduling · 2026-11-11）

> 总目标、当前架构、下一步目标与验收。阶段门见 [STAGE.md](STAGE.md)；技术总览见 [TECHNICAL_OVERVIEW.md](TECHNICAL_OVERVIEW.md)。

---

## 1. 总目标

> 在 MIMIC 可复现设定下，做一个**可审计、可对照、可滚动**的 ICU 床位动态调度系统；当前可主张的是“数据语义审计 + 同池评测 + 决策层”，不是新求解器。

| 子目标 | 验收 |
|---|---|
| 可审计 | 每个分床决策能给出目标分项与硬约束绑定 |
| 可对照 | 改目标/滤波器必须同池；B_pool 拆池效应与机制效应 |
| 可滚动 | 每 2h 重解、换床惩罚；HV–churn 能算出稳定性 |

---

## 2. 架构

```text
MIMIC Layer0
  → staging.icustays → feat.sofa_timeseries / feat.patient_priority
  → 候选池（priority DESC, max 200）
  → CP-SAT（4 硬约束 / 7 目标 / 4 机理）
  → sched.assignments
  → ε 网格 → 非支配前沿 / HV
  → H10 决策层（VoF/CoM/MMR）
  → 滚动重解 → HV–churn
  → Streamlit / MCP
```

代码落点：

| 模块 | 路径 |
|---|---|
| CP-SAT | `domain/optimizer/cp_sat.py` |
| 多目标 / HV | `domain/optimizer/moo_phase3.py` |
| DAC/FD/B_pool | `domain/optimizer/{data_contract,fd_stress,pool_effect}.py` |
| H10 | `domain/optimizer/{pareto_decision,pareto_io}.py` |
| 滚动 | `domain/rolling/engine.py` |
| HV–churn 工程链路 | `application/run_hv_churn.py`（2026-11-11 已打通） |
| 网格运行器 | `scripts/aigc_mimic_grid.py` |

---

## 3. 当前证据（截至 2026-11-11）

| 项 | 结果 |
|---|---|
| 三条实证发现 | 隔离 76,157/94,458；priority≡1+SOFA/10（corr=1.0）；`los_hours` 实为天 |
| 真实网格 | 6 场景 × 5 seed；hv 0.0045–0.0094；assigned≈6–8（隔离启发式压缩候选池） |
| B_pool | 资源场景=0；仅 `small_pool=−0.004864` |
| HV–churn | `run_hv_churn --steps 2 --levels 2 --max-time 3`：mean_hv 0.271885、mean_turnover 0.25、total_churn 0.0 |
| 测试/预检 | 核心 79 passed；preflight 16/16；PR #23 已合并（main `d240006`） |

**关键短板**：正常负载未验证（assigned 6–8）；db 源 5 seed 不是独立重采样；前沿只有 4–8 点；B_pool 缺独立对照。

---

## 4. 下一步目标（4–6 周）

| ID | 任务 | 交付 | 验收 |
|---|---|---|---|
| S1 | 修隔离字段/替代口径，正常负载重跑 | 新字段 + 新网格 JSON | assigned 15–20；preflight 过 |
| S2 | 前沿质量：加网格点 / NSGA-II 对照 / IGD/膝点 | 新前沿 + HV 表 | 非支配点 ≥20，或给出不能更多的证据 |
| S3 | seed 独立重采样（5 个候选池） | 新采样脚本 + 结果 | hv_std≠0 |
| S4 | B_pool 独立对照（池真变、机制不变） | 对照表 | ≥2 个非零池效应场景 |
| S5 | H10 接真实 `reports/moo` 前沿（6 场景×5 seed） | VoF/CoM 表 | 替代当前合成 demo |
| S6 | CI 白名单补 DAC/FD/B_pool/网格测试 | workflow 改动 | 新测试进 CI |
| S7 | 科研 harness literature 门（10 条核验来源） | `literature/sources.json` | literature gate PASS |
| S8 | 四张证据表定稿 | `docs/EVIDENCE_TABLES.md` | 每行数字+artifact |

---

## 5. 判定门

| 门 | 条件 | 决策 |
|---|---|---|
| G1 | 正常负载 assigned 15–20，且隔离约束仍可解释 | 继续调度主实验 |
| G2 | 前沿 ≥20 点或 NSGA-II 对照显示质量瓶颈 | 决定 H10 是否保留 |
| G3 | B_pool 独立对照出现非零 | B_pool 作为可主张评测方法 |
| G4 | 以上都成立 | 投 application/workshop；否则退回双创成果 |

---

## 6. 论文定位（现实版）

- **不是**“新调度算法”主论文；定位为 **数据语义审计 + 同池评测协议 + 决策层** 的应用/评测论文；
- 目标 venue：ML4H / CHIL application track、DSHealth；主会需更强 baseline 与外部验证；
- 时间线：先做 S1/S2（4–6 周），再决定是否成稿；不先写论文再补数据；
- 与 decision 的关系：独立项目；scheduling 不读 decision risk_score。

---

## 7. 明确不主张

- RFCC/CARE（五法同池同值 −0.0965，已撤回）；
- Pareto 排序/非支配集（教科书）；
- PPO online（无轨迹协议）；
- 全面超越医院现网；
- “新 CP-SAT 求解器”。

---

## 8. 关联文档

| 文档 | 用途 |
|---|---|
| [STAGE.md](STAGE.md) | 阶段门禁 |
| [TECHNICAL_OVERVIEW.md](TECHNICAL_OVERVIEW.md) | 技术总览 |
| [AIGC_CONTRACT.md](AIGC_CONTRACT.md) | DAC/FD/B_pool |
| [PARETO_DECISION.md](PARETO_DECISION.md) / [HV_CHURN.md](HV_CHURN.md) | H10 / HV–churn |
| [STATUS.md](STATUS.md) | 当前数字 |
| [MASTER_NARRATIVE.md](MASTER_NARRATIVE.md) | 叙事 SSOT |
