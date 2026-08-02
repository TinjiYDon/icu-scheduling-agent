# 执行路线图 ROADMAP_EXEC（人机双可读）

> 更新：2026-08-02 · Wave2 SOFA 数值 ✅ · PR #3 已合 main · 默认仍 cp_sat · 无 MIMIC 轨迹

## 人读摘要

| Wave | 含义 | 状态 | 主责 |
|------|------|------|------|
| **1** | calib/eval + simulate metrics | ✅ | C |
| **2** | SOFA→feat + STATUS 数字 | ✅ 2026-07-31 | B |
| **PPO** | 代码在 main（PR #3） | ✅ 已合 · **默认未启用** · 无轨迹 | B |

| 划分 | 名称 | 规则 |
|------|------|------|
| 70% / 30% | **calib / eval** | seed=42；eval 只评估不回写调参 |

## Agent 上下文

```text
配置：configs/optimizer.yaml → policy.default=cp_sat · eval_split · ppo.*
验收：pytest tests/test_simulate_metrics.py tests/test_plan.py tests/test_ppo_training_smoke.py -q
仿真：python -m application.simulate
禁止：宣称已有 MIMIC online PPO 轨迹；在 eval 上调 lambda
```

## 清单

- [x] B：SOFA + simulate 指标入 STATUS
- [x] Owner dump / labs 底座
- [x] PR #3 merge（lambda + 合成 PPO 代码）
- [ ] MIMIC `sim` 轨迹包（**未做**）
