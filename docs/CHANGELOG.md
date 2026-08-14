# Changelog · icu-scheduling-agent

> 更新：2026-08-14  
> 人读：本仓变更与 Release。  
> AI：默认策略 `cp_sat`；PPO 为对照；不消费 decision 风险分。

## Agent 上下文

```text
repo: icu-scheduling-agent
policy_default: cp_sat
ppo: research_contrast_only
couples_to_decision_risk: false
release: scheduling-ops-v4
```

## [Unreleased]

- 预测–优化层（仓内 GBDT / LOS / 到达强度 → CP-SAT）规划中。
- **不接** `icu-decision-agent` 风险分；紧迫度用仓内 SOFA / priority 等。

## 2026-07 / 08

- **Merged** [#3](https://github.com/TinjiYDon/icu-scheduling-agent/pull/3)：λ 可配与归一化、calib/eval、MaskablePPO 路径；默认仍 `cp_sat`。
- main：Ops 演示台 v4、滚动仿真、λ/PPO 文档与交接说明。
- Release：[scheduling-ops-v4](https://github.com/TinjiYDon/icu-scheduling-agent/releases/tag/scheduling-ops-v4)。

## 更早

- Issues #1–#6 关闭（MCP / Streamlit / ETL dump 等）。

## 相关文档

| 文档 | 用途 |
|------|------|
| [PROGRESS.md](PROGRESS.md) | 里程碑 |
| [ROADMAP.md](ROADMAP.md) | 下一版本 |
| [STATUS.md](STATUS.md) | 仿真与 λ |
| [PPO_MODEL_HANDOFF.md](PPO_MODEL_HANDOFF.md) | PPO zip 交接 |
