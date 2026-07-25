# 执行路线图 ROADMAP_EXEC（人机双可读）

> 更新：2026-07-25 · Wave1 calib/eval 骨架 · Wave2 等 B SOFA 数值 · PPO 不合 main

## 人读摘要

| Wave | 含义 | 状态 | 主责 |
|------|------|------|------|
| **1** | calib/eval 协议 + simulate `metrics` | ✅ 骨架 | C |
| **2** | SOFA→feat + STATUS 数字 | ⏳ 等 B/A | B |
| **PPO** | Draft PR #3 | 保持 Draft | B |

| 划分 | 名称 | 规则 |
|------|------|------|
| 70% / 30% | **calib / eval** | seed=42；eval 只评估不回写调参 |

## Agent 上下文

```text
配置：configs/optimizer.yaml → eval_split
代码：domain/optimizer/eval_split.py · application/simulate.py metrics
验收：pytest tests/test_simulate_metrics.py tests/test_plan.py -q
仿真：python -m application.simulate
禁止：在 eval 集上调 lambda；宣称 schemas_only dump 可训 PPO
Wave1 注：assignment 仍可跑全量；Wave2 应由 B 按 calib/eval 子集限制求解
```

## Wave2 等待清单

- [ ] B：SOFA 写入 feat + simulate 指标入 STATUS（#4）
- [ ] A：labs/完整 dump（#5）
