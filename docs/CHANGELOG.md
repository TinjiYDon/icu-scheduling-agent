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

- λ 推荐值写回 `configs/optimizer.yaml`（0.5 / 0.1 / 0.1 / 0.1）。
- 仓内 GBDT 优先级：`python -m application.train_priority`（已在本机 94458 stays 跑通）。
- 到达强度：LOS 按 **天** 换算；`rolling` 费率写回 **0.05**；`simulate_ok`。

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
