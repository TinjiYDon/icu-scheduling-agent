# SOTA / 文献与市面对标 · icu-scheduling-agent

> 更新：2026-10-09 · Wave **S-LIT**（扩写近刊 ICU/OR 多目标）  
> **规则**：未完成本文档「创新假设」验收前，STATUS/答辩稿 **禁止** 宣称「首创 / SOTA / online MIMIC-PPO 成功」。  
> 创新点须能一句话回答：**相对谁、改了什么、指标如何更好**。  
> 够格判断：[ACADEMIC_VALUE.md](ACADEMIC_VALUE.md)

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
| 11 | **SciRep 2023**：Two-stage multi-objective ICU bed allocation（NSGA-II，不确定到达/LOS） | ICU 多目标 | 他们：元启发式 + 不确定；我们：**精确 CP-SAT** + 可解释硬约束 + MIMIC 特征管道 |
| 12 | **EJOR 2025**：Robust MSS + ε-constraint（手术主排程，下游 ICU） | OR→ICU | 主叙事是手术室；我们聚焦 **ICU 床位分配** 本身 |
| 13 | OR 排程 + enhanced ε-constraint（择期/急诊，含 ICU 下游） | 多目标 ε | 机理可对标；场景不同（OR vs 床位） |
| 14 | CP 2026 方向：ε-grid + lexicographic global constraint on CP-SAT | 求解器方法 | 印证「CP-SAT 上做 ε/Lex」是活跃方向；**本仓不做求解器论文**，做 ICU 应用协议 |

### 相对近刊的一句话切口

> 相对 SciRep 2023 的 ICU 两阶段 NSGA-II：我们不拼「不确定下更多目标」，而拼 **可审计精确分配 + 同池多机理/PtO/滚动对照协议（H4–H6）+ MIMIC 可复现特征**。

---

## 差距矩阵

| 轴 | 文献/市面常见做法 | 本仓 | 差距 | 拟切口 |
|----|-------------------|------|------|--------|
| 运筹分床 | MIP/CP-SAT 硬约束可审计；ICU 亦见 NSGA-II | CP-SAT + λ/Pareto + Lex/ε | ISO/vent **需求**仍为启发式 | 可配置规则 + explain 披露 |
| 滚动调度 | 到达过程校准 + 重优化 | rolling + intensity + **H6 对照** | 过程仍简化 | MIMIC 校准 + 轨迹导出 |
| 学习调度 | 约束 RL、离线评估协议 | MaskablePPO smoke + 三方评估 | 无完整 MIMIC sim 轨迹表 | 轨迹协议后再谈 online |
| 优先级 | 学习紧迫度或接预警分 | 仓内 GBDT；禁接 decision；**H5 决策消融** | 监督信号仍为构造公式 | 独立 A/B + Jaccard 决策差 |

---

## 三条可验证创新假设（答辩绑定）

| ID | 假设 | 相对谁 | 改什么 | 验收指标 |
|----|------|--------|--------|----------|
| **H1** | 可配置约束规则 + 披露，比「隐式启发式」更可审计 | 黑盒分床或未披露伪随机需求 | `constraint_rules.yaml` + explain | 规则字段出现在解释报告；违反/利用率可复现 |
| **H2** | 滚动仿真 + MIMIC 校准到达，优于固定随意 `admission_rate` 演示 | 固定费率 demo | `write_rolling_rates` / intensity | `simulate_ok`；利用率与入出转曲线可解释 |
| **H3** | 同候选池 CP-SAT / Greedy / PPO 对照可界定 RL 增益边界 | 仅展示 PPO 训练曲线 | `evaluate_ppo` + **S2-TRAJ** | 分配率、高危等待、约束指标；**无协议不宣称 online** |
| **H4（采入）** | **S2-MOO**：同硬约束下三种多目标机理对照，优于「只调一组 λ」 | 单一加权和黑箱折中 | Weighted / Lex / ε-Constraint | 三模式状态/目标值/耗时可复现表；默认仍 `cp_sat` |
| **H5（采入）** | **PtO 决策质量**：换紧迫度模型会改变分床结果 | 只报 Spearman/top-k | `priority_overrides` + 同池求解 | Jaccard/指标差；`run_pto_ablation` |
| **H6（采入）** | **滚动再优化**优于只贪心填空床 | 一次性/无重优化滚动 | `reoptimize` 开关 | 时段均值 SOFA/权重；`run_rolling_contrast` |

### 已采入工程落点（2026-09-24 · H5/H6 2026-10-09）

| 假设 | 落点 | 备注 |
|------|------|------|
| H4 | `domain/optimizer/multiobjective.py` · PR#10 | **正式创新波次**；≠ 轨迹协议 |
| H3 | 对照表骨架已有 | 须 S2-TRAJ 闭合后才能强化 online 叙事 |
| H5 | `application/run_pto_ablation.py` | 预测→决策闭环；不接 decision |
| H6 | `application/run_rolling_contrast.py` | 滚动增益证据 |

---

## 非宣称

- 不接 `icu-decision-agent` risk_score 作为创新。
- schemas_only dump ≠ online MIMIC-PPO。
- 默认策略保持 `cp_sat`。

## 相关

- [ROADMAP.md](ROADMAP.md) · [DATA_FLYWHEEL.md](DATA_FLYWHEEL.md) · [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md) · [PARAM_STORY.md](PARAM_STORY.md)
