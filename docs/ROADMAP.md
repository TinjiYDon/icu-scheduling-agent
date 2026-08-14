# Roadmap · icu-scheduling-agent

> 更新：2026-08-14  
> 人读：下一版本 = 预测进目标、CP-SAT 仍做分配。  
> AI：禁止实现「读取 decision 风险分」除非本文件改写且用户确认。

## Agent 上下文

```text
repo: icu-scheduling-agent
vnext_p0: in-repo GBDT priority_weight; optional LOS
vnext_p1: arrival intensity; lambda write-back
vnext_p2: PPO only with trajectory protocol
forbidden: hard couple to icu-decision-agent risk API
```

## 原则

1. 生产默认 CP-SAT；硬约束可审计。
2. 预测层输出标量（优先级 / LOS / 到达）喂给优化器。
3. 与 decision 仓零硬耦合。

## vNext

| 优先级 | 项 | 说明 |
|--------|----|------|
| P0 | ~~预测 → 优化~~ | **代码完成**：`python -m application.train_priority` |
| P0 | ~~λ 定稿写回~~ | **已写回** `optimizer.yaml`（0.5/0.1/0.1/0.1） |
| P1 | 到达强度写回滚动 | `estimate_arrival_intensity` 已有；待跑库后改 `rolling.*` |
| P2 | PPO | 轨迹规范齐备前不宣称 online |

## 纠正

旧文档「预警风险 → 优先级」**本版本不做**。紧迫度来自仓内病情参数 + 本仓预测。见 [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md)。

## 相关

- [CHANGELOG.md](CHANGELOG.md) · [PROGRESS.md](PROGRESS.md) · [STATUS.md](STATUS.md)
