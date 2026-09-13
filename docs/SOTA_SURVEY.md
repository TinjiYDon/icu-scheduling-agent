# SOTA / 文献与市面对标 · icu-scheduling-agent

> 更新：2026-09-13 · Wave **S-LIT**  
> **规则**：未完成本文档「创新假设」验收前，STATUS/答辩稿 **禁止** 宣称「首创 / SOTA / online MIMIC-PPO 成功」。  
> 创新点须能一句话回答：**相对谁、改了什么、指标如何更好**。

## 本仓基线（对标锚点）

| 能力 | 现状 |
|------|------|
| 优化主路径 | OR-Tools CP-SAT · 多目标 λ · 默认 `policy.default=cp_sat` |
| 滚动 | `domain/rolling` 多步仿真 · MIMIC 可校准到达强度 |
| 优先级 | 仓内 SOFA + GBDT → `feat.patient_priority`（**不接** decision risk） |
| RL 对照 | MaskablePPO · `rl.reward_weights` · 轨迹协议 v1.0 导出 |

---

## 核心文献与系统条目（≥8）

| # | 条目 | 类型 | 与本仓关系 |
|---|------|------|------------|
| 1 | OR-Tools CP-SAT / MIP 医院床位与手术室排程文献 | 运筹 | CP-SAT 主路径对标 |
| 2 | ICU capacity / bed management 综述（运筹与仿真） | 运筹 | 滚动时域与利用率指标 |
| 3 | Rolling-horizon scheduling（制造/医疗迁移） | 时域 | `run_rolling_simulation` |
| 4 | SOFA / SAPS 等病情评分用于分诊优先级 | 临床规则 | 仓内 SOFA 特征 |
| 5 | Predict-then-optimize / decision-focused learning | 预测→优化 | GBDT priority → CP-SAT |
| 6 | Schulman et al. **PPO**；MaskablePPO（动作掩码） | RL | 本仓 PPO 对照轨 |
| 7 | Constrained / safe RL、多目标 RL 综述 | RL | `rl.reward_weights` 与约束惩罚方向 |
| 8 | Pareto 多目标优化在医疗资源分配中的应用 | 多目标 | λ 网格 + Pareto 报告 |
| 9 | 医院信息系统床位看板类产品（市面） | 产品 | 可解释分配 vs 黑盒推荐 |
| 10 | MIMIC 用于运筹仿真的数据边界说明 | 数据 | dump 可支撑 CP-SAT，不可妄称 online RL |

---

## 差距矩阵

| 轴 | 文献/市面常见做法 | 本仓 | 差距 | 拟切口 |
|----|-------------------|------|------|--------|
| 运筹分床 | MIP/CP-SAT 硬约束可审计 | CP-SAT + λ/Pareto | ISO/vent **需求**仍为启发式 | 可配置规则 + explain 披露 |
| 滚动调度 | 到达过程校准 + 重优化 | rolling + intensity 写回 | 过程仍简化 | MIMIC 校准 + 轨迹导出 |
| 学习调度 | 约束 RL、离线评估协议 | MaskablePPO smoke + 三方评估 | 无完整 MIMIC sim 轨迹表 | 轨迹协议后再谈 online |
| 优先级 | 学习紧迫度或接预警分 | 仓内 GBDT；禁接 decision | 与「风险耦合」论文叙事不同 | **独立** A/B SOFA vs GBDT |

---

## 三条可验证创新假设（答辩绑定）

| ID | 假设 | 相对谁 | 改什么 | 验收指标 |
|----|------|--------|--------|----------|
| **H1** | 可配置约束规则 + 披露，比「隐式启发式」更可审计 | 黑盒分床或未披露伪随机需求 | `constraint_rules.yaml` + explain | 规则字段出现在解释报告；违反/利用率可复现 |
| **H2** | 滚动仿真 + MIMIC 校准到达，优于固定随意 `admission_rate` 演示 | 固定费率 demo | `write_rolling_rates` / intensity | `simulate_ok`；利用率与入出转曲线可解释 |
| **H3** | 在相同候选池上，CP-SAT / Greedy / PPO 三方对照可界定 RL 增益边界 | 仅展示 PPO 训练曲线 | `evaluate_ppo` + 轨迹协议 | 分配率、高危等待、约束相关指标对照表；**无协议不宣称 online** |

---

## 非宣称

- 不接 `icu-decision-agent` risk_score 作为创新。
- schemas_only dump ≠ online MIMIC-PPO。
- 默认策略保持 `cp_sat`。

## 相关

- [ROADMAP.md](ROADMAP.md) · [DATA_FLYWHEEL.md](DATA_FLYWHEEL.md) · [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md) · [PARAM_STORY.md](PARAM_STORY.md)
