# 本仓顶尖视角下一步（scheduling）

> 2026-10-09 · **独立项目** · S2-MOO 1–5 + fair H3 同资源（PR #12）+ ε 重标定

## 总原则

1. 生产默认 CP-SAT；硬约束可审计。
2. 紧迫度来自仓内 SOFA / GBDT priority。
3. RL 须有 **S2-TRAJ**；未齐备不宣称 online MIMIC-PPO。
4. 与 decision **零硬耦合**。
5. **S2-MOO** 为正式方法创新；与轨迹协议分列。

## vNext

| 优先级 | 项 | 状态 |
|--------|----|------|
| P0 | S2-MOO 阶段 1–5 | ✅ |
| P0 | Fair H3 同池 + 同资源布局 | ✅ PR #11 / #12 |
| P1 | ε 按场景重标定 | ✅ `moo_epsilon_recal` |
| P1 | eval 六场景表 | ✅ STATUS |
| P1 | S3 同池多 episode 深化 | ✅ fair stay_ids + resources |
| P1 | 老师演示清单 | ✅ `DEMO_SCRIPT.md` |
| P1 | H5 PtO 决策消融 | ✅ `run_pto_ablation` |
| P1 | H6 滚动对照 | ✅ `run_rolling_contrast` |
| P1 | 学术够格文档 | ✅ `ACADEMIC_VALUE.md` |
| P1 | PPO zip 真跑冒烟 | 有 artifacts 时 |
| P2 | 压力场景 ε 仍不可行时披露 | 持续 |

## 非目标

- `priority_weight ← decision risk_score`
- dump/artifacts 入 Git
- 无轨迹即宣称 online PPO 成功
