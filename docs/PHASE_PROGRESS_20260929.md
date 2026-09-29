# 阶段性进展总结 · icu-scheduling-agent · 2026-09-29

## 定位

独立 ICU **多目标多约束床位调度**（运筹 OR）：默认 CP-SAT；仓内 SOFA/GBDT 紧迫度；**不**接 decision 风险分。

## 本阶段已交付

| 波次 | 内容 | 证据 |
|------|------|------|
| S2-MOO 阶段 1 | Weighted / Lex / ε 统一内核 | PR#10 |
| 阶段 2 | `wait`≡priority_served；`overload`=高危落普通床 | `objective_semantics` |
| 阶段 3 | payoff + A2 ε 网格 81 点 · HV=0.038794 | `reports/moo/summary_latest.json` |
| 阶段 4 | 六压力场景 ×（WS+Lex+ε） | `reports/moo/scenarios_latest.json` |
| S2-TRAJ | 滚动轨迹协议 1.0 导出验收 | `TRAJECTORY_PROTOCOL.md` |

## 关键数字（calib）

- 正常容量 Lex：assigned=20 · wait=58892 · high_risk=12  
- 床不足：assigned=12；高 SOFA 池：assigned=10 且 high_risk=10  
- 六场景 WS/Lex **全部 OPTIMAL**；部分场景中位 ε 不可行（披露即可）

## 下一拍

Streamlit 三模式展示（阶段 5）；仍禁止 online MIMIC-PPO 宣称。
