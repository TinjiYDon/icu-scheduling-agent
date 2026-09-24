# 本仓顶尖视角下一步（scheduling）

> 2026-09-24 · **独立项目** · 已采入 **S2-MOO**  
> 不接 decision 风险分。

## 总原则

1. 生产默认 CP-SAT；硬约束可审计。
2. 紧迫度来自仓内 SOFA / GBDT priority。
3. RL 须有 **S2-TRAJ**；未齐备不宣称 online MIMIC-PPO。
4. 与 decision **零硬耦合**。
5. **S2-MOO** 为正式方法创新；与轨迹协议分列。

## vNext

| 优先级 | 项 | 建议落地 |
|--------|----|----------|
| P0 | S2-TRAJ **或** MOO 阶段 2（二选一做透） | [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md) / [S2_MULTI_OBJECTIVE.md](S2_MULTI_OBJECTIVE.md) |
| P0 | 整合 pytest + calib 三模式冒烟 | [INTEGRATION_PREP.md](INTEGRATION_PREP.md) |
| P1 | payoff / ε 网格 | MOO 阶段 3 |
| P1 | STATUS 三模式真数表 | C |
| P2 | Streamlit 三模式 · S3 RL 对照 | — |

## 非目标

- `priority_weight ← decision risk_score`
- dump/artifacts 入 Git
- 无轨迹即宣称 online PPO 成功
- 用 S2-MOO 替代轨迹协议验收
