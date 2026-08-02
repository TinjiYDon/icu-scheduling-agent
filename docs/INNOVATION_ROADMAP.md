# 创新路线

> 本仓库独立演进；MCP 仅作为对外标准接口，不与其他 ICU 项目耦合。

## 目标（实时落地）

**可解释资源动态调度**：当前 SOFA/占用状态 → CP-SAT → **滚动时域**再求解（每步用最新床旁状态）。

这与 decision 的「早期预警」同属 ICU **实时决策**族，代码零耦合。

## 里程碑

| 阶段 | 目标 | 交付物 |
|------|------|--------|
| **P0** ✓ | Demo 跑通 | ETL + SOFA + CP-SAT |
| **P1** ✓ | 可解释 Demo | Streamlit + 约束说明 |
| **P2** ✓ | 标准接口 | MCP `optimize_beds` |
| **实时主线** ✓ | 滚动仿真 | `domain/rolling` + `application.simulate` |
| **P3** | 学习型策略 | PPO 代码在 main；**默认 cp_sat**；无轨迹不宣称 online |

## 评测

calib/eval 划分；simulate 滚动指标入 STATUS。禁止在无 MIMIC 轨迹时宣称 online PPO 已交付。

## 当前重点

1. Streamlit：CP-SAT + 滚动占用时间线 + 验收门禁（已增强）
2. 预警风险耦合进 `priority_weight`（配置开关；见 `docs/TOP_TIER_NEXT.md`）
3. MIMIC `sim` 轨迹仍可选；默认 `policy.default=cp_sat`
