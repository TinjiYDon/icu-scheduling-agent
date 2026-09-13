# Roadmap · icu-scheduling-agent

> 更新：2026-09-13  
> 人读：本仓独立出成果——多目标多约束滚动调度 + 深化 RL；不接 decision 风险分。  
> AI：禁止实现「读取 decision 风险分」；轨迹协议齐备前勿宣称 online MIMIC-PPO。

## Agent 上下文

```text
repo: icu-scheduling-agent
vnext_p0: S-LIT SOTA_SURVEY; constraint honesty
vnext_p1: rolling intensity; DATA_FLYWHEEL archive
vnext_p2: trajectory protocol; multi-obj RL vs CP-SAT
forbidden: hard couple to icu-decision-agent risk API; claim SOTA without LIT
independent: zero hard couple; own dump/acceptance/release
```

## 原则

1. **独立项目**：床位/资源运筹为本仓唯一主叙事；紧迫度来自仓内 SOFA/GBDT。
2. **先对标、再创新**：见 [SOTA_SURVEY.md](SOTA_SURVEY.md)；无 LIT 不宣称首创/SOTA。
3. 生产默认 CP-SAT；硬约束可审计。
4. 预测层输出标量（优先级 / LOS / 到达）喂给优化器。
5. RL 在现有 MaskablePPO 框架上深化；与 CP-SAT 同场景对照。

## vNext（Wave）

| 波次 | 项 | 说明 |
|------|----|------|
| **S-LIT** | 文献/市面对标 | [SOTA_SURVEY.md](SOTA_SURVEY.md) · 假设 H1–H3 |
| S0 | 文档诚实化 | ISO/vent 求解边界；λ 与 `optimizer.yaml` 一致 |
| S1 | 多目标多约束加深 | 可配置规则 + 违反报告；滚动到达强度写回 |
| S2 | 轨迹协议 | rolling 导出 → `artifacts/trajectories/` |
| S3 | 多目标约束 RL | `rl.reward_weights`；三方对照验收 |
| **S-FLY** | 数据飞轮 | [DATA_FLYWHEEL.md](DATA_FLYWHEEL.md) · `reports/flywheel/` |
## 纠正

旧文档「预警风险 → 优先级」**不做**。见 [TOP_TIER_NEXT.md](TOP_TIER_NEXT.md)。

## 相关

- [CHANGELOG.md](CHANGELOG.md) · [PROGRESS.md](PROGRESS.md) · [STATUS.md](STATUS.md) · [PARAM_STORY.md](PARAM_STORY.md)
- [SOTA_SURVEY.md](SOTA_SURVEY.md) · [DATA_FLYWHEEL.md](DATA_FLYWHEEL.md) · [TRAJECTORY_PROTOCOL.md](TRAJECTORY_PROTOCOL.md)
