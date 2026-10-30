# 本仓顶尖视角下一步（scheduling）

> 2026-10-30 · **独立项目** · S2-MOO 1–5 + fair H3 同资源（PR #12）+ ε 重标定

## 总原则

1. 生产默认 CP-SAT；硬约束可审计。
2. 紧迫度来自仓内 SOFA / GBDT priority。
3. **S2-TRAJ** 导出协议已实现；仿真轨迹及 PPO 离线评估不能证明床旁 online RL 或固定数据 offline RL 已实现。
4. 与 decision **零硬耦合**。
5. **S2-MOO** 为正式方法创新；与轨迹协议分列。

## vNext

已勾选项保留工程交付与历史场景验收，不代表研究充分验证。PR #16 已合 main（`HEAD=34fe955`）；本机 DB 已只读核对成功，当前待办以本次证据核验为准。

| 优先级 | 项 | 状态 |
|--------|----|------|
| P0 | S2-MOO 阶段 1–5 | ✅ |
| P0 | Fair H3 同池 + 同资源布局 | ✅ PR #11 / #12 |
| P1 | ε 按场景重标定 | ✅ `moo_epsilon_recal` |
| P1 | eval 六场景表 | ✅ 2026-10-30 WS/Lex/ε 共 18 个 OPTIMAL，`reports/moo/scenarios_latest.json` |
| P1 | 阶段 3 payoff / grid / HV | ✅ 本次 27/17/3/HV=0.052130；旧 81/54/4/HV=0.038794 保留历史 |
| P1 | S3 同池多 episode 深化 | ✅ fair stay_ids + resources |
| P1 | 老师演示清单 | ✅ `DEMO_SCRIPT.md` |
| P1 | 40 人 H5 / bake-off | ✅ 2026-10-30 两报告已生成；候选 40 被默认 20 截断已修复 |
| P1 | H6 滚动对照 | ✅ 2026-10-30 共享初态并保留在院患者，8 步 18/18 打平，均无违约 |
| P1 | 学术够格文档 | ✅ `ACADEMIC_VALUE.md` |
| P1 | 现有 PPO zip 真跑冒烟 | ✅ 2026-10-30 `evaluate_ppo`；同池 20 人 + 20 床，三策略各 assigned=5、constraint_violations=0；报告与 flywheel 已生成，非 29 项测试证明 |
| P1 | PPO 3 episode benchmark | ✅ 同池同资源；三策略 mean_assigned=5、mean_high_risk_wait=15、mean_constraint_violations=0 |
| P1 | 滚动仿真轨迹复验 | ✅ 协议 2.0 真跑 4 transitions，连续性/守恒/checked 且无违规已断言；非床旁轨迹 |
| P1 | 测试与依赖核验 | ✅ 最终 pytest 217 passed / 6 skipped，另只读 DB 3 passed；未运行 ETL 写数据测试，已补 `scikit-learn` 依赖 |
| P1 | 独立代码复核边界 | ✅ 默认保留在院患者、CP 强制留院及返回校验；CP/RL 真正隔离患者使用 ISO 床的错配豁免统一；回归与最终重跑均通过 |
| 核心研究 | 逐患者临床时间顺序状态 + 独立留出 / 多种子科学验证 | 尚未闭环；真实床旁轨迹、固定数据 offline RL 算法未实现，普通 PPO 为仿真交互训练 |
| P2 | 压力场景 ε 仍不可行时披露 | 持续 |

本次环境与证据见 [ROADMAP_EXEC.md](ROADMAP_EXEC.md)，PPO 历史/当前验收边界见 [PPO_SMOKE.md](PPO_SMOKE.md)。`hybrid` 是有意预留的非必做扩展。

## 非目标

- `priority_weight ← decision risk_score`
- dump/artifacts 入 Git
- 无轨迹即宣称 online PPO 成功
