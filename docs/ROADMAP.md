# Roadmap · icu-scheduling-agent

> 更新：2026-10-09（**MASTER_NARRATIVE** 总目标主线 + bake-off / H5/H6）  
> 人读：先 [MASTER_NARRATIVE.md](MASTER_NARRATIVE.md)；默认 CP-SAT；不接 decision 风险分。  
> AI：**S2-MOO** ≠ **S2-TRAJ**；有离线轨迹仍不宣称 online MIMIC-PPO。

## Agent 上下文

```text
repo: icu-scheduling-agent
SSOT_narrative: docs/MASTER_NARRATIVE.md
goal: auditable + comparable + rolling ICU bed allocation
adopted: S2-MOO; fair H3; S3; bake-off A; H5 PtO; H6 rolling; ACADEMIC_VALUE; L4
vnext_p0: merge PR#16; optional PPO zip smoke
forbidden: decision risk_score; claim online PPO from offline traj alone
```

## 原则

1. **独立项目**：床位/资源运筹唯一主叙事。  
2. **先对标、再创新**：见 [SOTA_SURVEY.md](SOTA_SURVEY.md)。  
3. 生产默认 **CP-SAT**；硬约束可审计。  
4. 紧迫度来自仓内 SOFA/GBDT。  
5. RL 须有轨迹协议后再谈 online。

## 已采入创新点（正式波次）

| 波次 | 创新点 | 状态 | 绑定假设 |
|------|--------|------|----------|
| S0–S1 | 约束诚实化 + 到达强度骨架 | ✅ PR#8 等 | H1 / H2 |
| **S2-MOO** | 同硬约束下 Weighted / Lex / ε-Constraint | ✅ PR#10 | 多目标方法对照（升格） |
| H3 对照表骨架 | CP-SAT / Greedy / PPO 表 | ✅ 部分 | H3 |
| **S2-TRAJ** | 滚动仿真轨迹协议 1.0 导出验收 | ✅ 2026-09-24 | H3 前置 |
| **S2-MOO 阶段 2** | wait/overload 语义（acuity） | ✅ 2026-09-24 | H4 |
| **S2-MOO 阶段 3** | payoff + A2 ε 网格 + HV | ✅ 2026-09-24 | H4 |
| **S2-MOO 阶段 4** | 六场景轻量对照 | ✅ 2026-09-29 | H4 |
| **S2-MOO 阶段 5** | Streamlit 三模式 + 对照页 | ✅ PR #11 | H4 / H3 |
| **H3 fair+L4** | 同资源布局 · `moo_ui`/`h3_ui` · restore 重建 | ✅ PR #12 | H3 |
| **S3 deepen** | 多 episode 同池+同资源 benchmark + 对照页 | ✅ PR #14 | H3 |
| **演示清单** | DEMO_SCRIPT 含多目标/对照口播 | ✅ 2026-10-09 | — |
| **方法 bake-off A** | 同池贪心/WS/Lex/ε + TEACHER_PLAIN | ✅ 2026-10-09 | H4 证据 |
| **H5 PtO** | 优先级→分床决策质量消融 | ✅ 2026-10-09 | H5 |
| **H6 滚动增益** | reoptimize vs 贪心填床 | ✅ 2026-10-09 | H6 |
| **学术价值** | ACADEMIC_VALUE 诚实够格表 | ✅ 2026-10-09 | — |
| **总目标主线** | MASTER_NARRATIVE 串全仓 | ✅ 2026-10-09 | 叙事 SSOT |
| **H7 具名创新** | RFCC 机制 + CARE/UHRM 指数 | ✅ 2026-10-09 | H7 |

## 下一阶段计划

| 优先级 | 项 | 说明 |
|--------|----|------|
| **P1** | PPO zip 真跑冒烟 | 无 `artifacts/ppo_icu` 时跳过 |
| **P2** | STATUS 回写 H5/H6 数字 | ✅ 2026-10-09 |
| **P2** | 文献对标扩写 | ✅ SciRep 2023 / EJOR 2025 等写入 SOTA |

## 纠正

旧文档「预警风险 → 优先级」**不做**。见 [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md)。

## 相关

- [TEAM_DIRECTION.md](TEAM_DIRECTION.md) · [S2_MULTI_OBJECTIVE.md](S2_MULTI_OBJECTIVE.md) · [INTEGRATION_PREP.md](INTEGRATION_PREP.md)  
- [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md) · [SOTA_SURVEY.md](SOTA_SURVEY.md)
