# Progress · icu-scheduling-agent

> 更新：2026-08-14（数据侧继续）

## 已跑通（本机 dump 库）

| 项 | 结果 |
|----|------|
| `train_priority` | ✅ sklearn_gbr · n=94458 · pred_mean≈2.13 → `feat.patient_priority` |
| 到达强度 | ✅ 检测 LOS 为 **天**；建议费率 **0.05** / 2h step（已写 `rolling.*`） |
| `simulate` | ✅ `simulate_ok` · 12 步满床占用 · avg_weight≈3.1 |

## 下一刀

1. Ops 台目视对比 SOFA 规则 vs GBDT priority（可选）  
2. 导出新 dump（含更新后的 priority）供队友  
3. PPO 仍对照
