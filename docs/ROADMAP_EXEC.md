# 执行路线图 ROADMAP_EXEC

> 更新：2026-08-02 · **滚动时域实时调度**为主叙事

## 人读摘要

| Wave | 含义 | 状态 |
|------|------|------|
| **1** | calib/eval + simulate metrics | ✅ |
| **2** | SOFA→feat + STATUS 数字 | ✅ |
| **实时** | 滚动每步状态→CP-SAT | ✅ 主路径 |
| **PPO** | 代码在 main | 默认未启用 · 无轨迹 |

## Agent 上下文

```text
主路径：python -m application.simulate（rolling）
配置：policy.default=cp_sat
验收：pytest tests/test_simulate_metrics.py tests/test_plan.py -q
禁止：宣称 online PPO 已用 MIMIC 训好
```
