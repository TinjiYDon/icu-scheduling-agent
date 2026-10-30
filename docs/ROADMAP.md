# Roadmap · icu-scheduling-agent

> 更新：2026-10-30（**MASTER_NARRATIVE** 总目标主线 + bake-off / H5/H6）
> 人读：先 [MASTER_NARRATIVE.md](MASTER_NARRATIVE.md)；默认 CP-SAT；不接 decision 风险分。  
> AI：**S2-MOO** ≠ **S2-TRAJ**；有离线轨迹仍不宣称 online MIMIC-PPO。

## Agent 上下文

```text
repo: icu-scheduling-agent
SSOT_narrative: docs/MASTER_NARRATIVE.md
goal: auditable + comparable + rolling ICU bed allocation
adopted: S2-MOO; fair H3; S3; bake-off A; H5 PtO; H6 rolling; ACADEMIC_VALUE; L4
merged: PR#16; HEAD=34fe955
environment: local icu_scheduling DB read-only verified; staging/sofa/priority each 94458
verified_stage: 2026-10-30 PPO single/3-episode fair; trajectory v2 4 steps; bake-off/H5 40; shared-initial H6 before boundary fixes
fixed: retain_occupied defaults true + hard retention/output checks; CP/RL zone mismatch semantics; regressions added
vnext_p0: clinical temporal states + held-out/multi-seed validation; engineering reruns completed
research_gaps: patient-level clinical chronology; fixed-dataset offline RL algorithms; independent held-out/multi-seed evidence
forbidden: decision risk_score; claim online PPO from offline traj alone
```

## 原则

1. **独立项目**：床位/资源运筹唯一主叙事。  
2. **先对标、再创新**：见 [SOTA_SURVEY.md](SOTA_SURVEY.md)。  
3. 生产默认 **CP-SAT**；硬约束可审计。  
4. 紧迫度来自仓内 SOFA/GBDT。  
5. 轨迹协议已实现；仿真交互 PPO / 离线评估不等于固定数据 offline RL，也不证明临床 online RL。

## 已采入创新点（正式波次）

下表保留工程落点及注明日期的历史验收；✅ 不表示 H1–H7 已充分验证、文献对标已完成严格复核或具备临床有效性证据。研究结论仍须绑定场景、对照与局限。

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
| **H6 滚动对照** | reoptimize vs 贪心填床 | 历史 2026-10-09 保留；2026-10-30 最终共享初态且保留在院患者，8 步 18/18 打平，均无违约 | H6 |
| **学术价值** | ACADEMIC_VALUE 诚实够格表 | ✅ 2026-10-09 | — |
| **总目标主线** | MASTER_NARRATIVE 串全仓 | ✅ 2026-10-09 | 叙事 SSOT |
| **H7 具名创新** | RFCC 机制 + CARE/UHRM 指数 | ✅ 2026-10-09 | H7 |

方法 bake-off / H5 / H6 的 PR #16 已合 main（`34fe955`），不再列为待合并。

## 下一阶段计划

| 优先级 | 项 | 说明 |
|--------|----|------|
| **P1** | 现有 PPO zip 真跑冒烟 | ✅ 2026-10-30 `evaluate_ppo`；同池 20 人 + 20 床，三策略各 assigned=5、constraint_violations=0；报告与 flywheel 已生成，证据非 29 项合成 smoke |
| **P1** | PPO 3 episode benchmark | ✅ 2026-10-30 同池同资源；三策略 mean_assigned=5、mean_high_risk_wait=15、mean_constraint_violations=0 |
| **P1** | 滚动仿真轨迹复验 | ✅ 协议 2.0 真跑 4 transitions，连续性/每步守恒/checked 且无违规已断言；非床旁轨迹 |
| **P1** | 40 人 bake-off / H5 | ✅ 两报告已生成；候选 40 被默认 20 截断问题已修复 |
| **P1** | 多目标重跑 | ✅ eval 六场景 18 个求解全部 OPTIMAL；阶段 3 新结果 27/17/3/HV=0.052130，旧版本结果保留 |
| **P1** | 测试与依赖核验 | ✅ 最终 pytest 217 passed / 6 skipped，另只读 DB 3 passed；ETL 写数据测试未运行，`scikit-learn` 已补入依赖 |
| **P1** | 独立代码复核边界 | ✅ 默认 `retain_occupied=True`、CP 强制留院且校验返回不丢人；CP/RL 仅真正隔离患者使用 ISO 床豁免错配，其余非偏好分配计错配；回归与最终重跑均通过 |
| **研究支线** | 临床时序状态 + 独立留出 / 多种子科学验证 | 尚未闭环；真实床旁轨迹和固定数据 offline RL 算法未实现，普通 PPO 为仿真交互训练 |
| **P2** | STATUS / 本次完整验证记录 | ✅ 已同步 `STATUS.md` 与 `LOCAL_VALIDATION_20261030.md`；历史与新结果分版本保存 |
| **P2** | 文献对标扩写 | ✅ SciRep 2023 / EJOR 2025 等写入 SOTA |

本次环境与证据核对见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md)，检查点验收标准见 [PPO_SMOKE.md](PPO_SMOKE.md)。文献扩写完成仅表示条目已写入；`hybrid` 为有意预留的非必做扩展。

## 纠正

旧文档「预警风险 → 优先级」**不做**。见 [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md)。

## 相关

- [TEAM_DIRECTION.md](TEAM_DIRECTION.md) · [S2_MULTI_OBJECTIVE.md](S2_MULTI_OBJECTIVE.md) · [INTEGRATION_PREP.md](INTEGRATION_PREP.md)  
- [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md) · [SOTA_SURVEY.md](SOTA_SURVEY.md)
