# Progress · icu-scheduling-agent

> 更新：2026-08-14  
> 人读：本仓进度与边界。  
> AI：`couples_to_decision_risk=false`；无 MIMIC 轨迹则勿写 online PPO 已交付。

## Agent 上下文

```text
repo: icu-scheduling-agent
product: rolling-horizon ICU bed allocation
solver_default: cp_sat
ppo: contrast_only
predict_then_optimize: planned (in-repo features)
couples_to_decision_risk: false
```

## 里程碑

| 里程碑 | 状态 | 证据 |
|--------|------|------|
| CP-SAT 滚动床位分配 | 完成 | 默认 `cp_sat` |
| λ 调参 + calib/eval | 完成 | PR #3 · LAMBDA_TUNING |
| MaskablePPO 研究路径 | 完成 | PR #3；非默认 |
| Ops 演示台 v4 | 完成 | main |
| 仓内预测 → CP-SAT | 规划 | GBDT/LOS/到达；不接 decision |

## Issue / PR

- Issues #1–#6：全部关闭。
- Open PR：无。
- 遗留：λ 推荐值待写回配置；无 MIMIC 轨迹 → **不宣称 online PPO**。

## 边界（已定）

| 项 | 决定 |
|----|------|
| 与 decision | **不接** 风险分 / 无运行时依赖 |
| 病情输入 | 仓内 `priority_weight` / SOFA 等 |
| 生产策略 | CP-SAT；PPO 仅对照 |

## 下一冲刺

见 [ROADMAP.md](ROADMAP.md)。
