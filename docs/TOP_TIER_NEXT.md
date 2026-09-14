# 本仓顶尖视角下一步（scheduling）

> 2026-09-13 · **独立项目** · 多目标多约束滚动调度 + RL 深化  
> 不接 decision 风险分。

## 总原则

1. 生产默认 CP-SAT；硬约束可审计。
2. 紧迫度来自仓内 SOFA / GBDT priority。
3. RL 须有轨迹协议；未齐备不宣称 online MIMIC-PPO。
4. 与 decision **零硬耦合**。

## vNext 对齐 ROADMAP Wave S0–S3

| 优先级 | 项 | 建议落地 |
|--------|----|----------|
| P0 | 约束诚实化 | `PARAM_STORY` + `constraint_rules.yaml` |
| P0 | 到达强度写回 | `train_priority --intensity-only` → `rolling.*` |
| P1 | 违反可解释 | explain 披露 ISO/vent 规则来源 |
| P1 | 轨迹协议 | rolling 导出 `artifacts/trajectories/` |
| P2 | 多目标约束 RL | `rl.reward_weights`；CP-SAT/Greedy/PPO 对照 |

## 非目标

- `priority_weight ← decision risk_score`
- dump/artifacts 入 Git
- 无轨迹即宣称 online PPO 成功
