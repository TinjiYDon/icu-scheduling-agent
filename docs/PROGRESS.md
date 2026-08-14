# Progress · icu-scheduling-agent

> 更新：2026-08-14（执行推进）

## Agent 上下文

```text
repo: icu-scheduling-agent
policy_default: cp_sat
lambda_written_back: wait0.5/overload0.1/balance0.1/zone0.1
predict_priority: application.train_priority (in-repo GBDT)
couples_to_decision_risk: false
```

## 里程碑

| 里程碑 | 状态 | 证据 |
|--------|------|------|
| CP-SAT / Ops / PPO 对照 | 完成 | main |
| λ 定稿写回 | **完成** | `configs/optimizer.yaml` |
| 仓内 GBDT → priority | **代码完成** | `domain/scoring/predict_priority.py` · 需 DB 跑 `train_priority` |
| 到达强度估计 | **代码完成** | `estimate_arrival_intensity`；rolling 可读 yaml 费率 |

## 下一冲刺（剩余）

1. 在 restore dump 的库上跑 `python -m application.train_priority`，把建议费率写回 `rolling.*`。  
2. 用新 priority 跑 `simulate` / Ops 对比 SOFA 规则基线。  
3. PPO 仍仅对照；无轨迹不宣称 online。
