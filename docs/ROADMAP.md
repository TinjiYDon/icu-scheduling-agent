# Roadmap · icu-scheduling-agent

> 更新：2026-09-24（采入 S2-MOO 为正式创新波次）  
> 人读：多目标多约束滚动调度；默认 CP-SAT；不接 decision 风险分。  
> AI：**S2-MOO** ≠ **S2-TRAJ**；无轨迹不宣称 online MIMIC-PPO。

## Agent 上下文

```text
repo: icu-scheduling-agent
adopted: S2-MOO weighted/lex/epsilon
vnext_p0: S2-TRAJ trajectory export acceptance; S2-MOO phase2 metric semantics (pick one focus)
vnext_p1: payoff/Pareto grid; calib scenario pack → STATUS
vnext_p2: Streamlit three-mode UI; S3 RL compare on same pool
forbidden: decision risk_score; claim online PPO without trajectories
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

## 下一阶段计划

| 优先级 | 项 | 说明 |
|--------|----|------|
| **P0** | **S2-TRAJ** | 轨迹导出验收（旧 ROADMAP「S2」）；与 MOO **并行不互相替代** |
| **P0** | S2-MOO 阶段 2 | 真实 wait / overload 床日语义（见 [S2_MULTI_OBJECTIVE.md](S2_MULTI_OBJECTIVE.md)）— **与 TRAJ 二选一做透后再并行** |
| **P1** | payoff / ε 网格 | 阶段 3 Pareto 扫描 |
| **P1** | calib 场景包 | 写入 STATUS 对照表 |
| **P2** | Streamlit 三模式 | 展示 MOO 结果 |
| **P2** | S3 | 同候选池 RL 对照深化 |

## 纠正

旧文档「预警风险 → 优先级」**不做**。见 [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md)。

## 相关

- [TEAM_DIRECTION.md](TEAM_DIRECTION.md) · [S2_MULTI_OBJECTIVE.md](S2_MULTI_OBJECTIVE.md) · [INTEGRATION_PREP.md](INTEGRATION_PREP.md)  
- [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md) · [SOTA_SURVEY.md](SOTA_SURVEY.md)
