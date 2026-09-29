# OR / 合入检查 · 2026-09-29

> Owner：`TinjiYDon` · 范围：decision + scheduling（两仓独立）

## 结论（一句话）

**两仓均无待合 open PR**；创新/架构主线已在 `main`；scheduling 运筹（OR）主线已闭合到 MOO 阶段 4；decision 为预警+解释 CDSS（非床位 OR）。

## scheduling（运筹主线）

| 项 | 状态 |
|----|------|
| 默认策略 | `cp_sat` |
| S2-MOO 1–4 | ✅ 三模式内核 · 语义 · A2 网格 · 六场景轻量对照 |
| S2-TRAJ | ✅ 离线轨迹导出；**不**宣称 online PPO |
| open PR | **0** |
| 本批动作 | 无 PR 可合；阶段 4 直接落 `main` |

## decision（预警 / 解释 · 非床位 OR）

| 项 | 状态 |
|----|------|
| 主模型 | S2 mortality_12h v2 · 主指标 PR-AUC / Brier |
| DX-1/2/3 | ✅ 解释安全 · DCA · GRU-D 双轨（PR#18） |
| ADR-001 | ✅ UI→L4 `ui_queries`（PR#19） |
| open PR | **0** |
| 本批动作 | 无需 merge；chore PR 此前已关 |

## 禁区（仍成立）

- 不跨仓读 `risk_score` / 硬耦合  
- dumps/artifacts 不入 Git  
- 无外部验证不写泛化 SOTA  
