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

- 独立深挖叙事：`ROADMAP` Wave S0–S3；零硬耦合 decision。
- **S-LIT / S-FLY**：[`SOTA_SURVEY.md`](SOTA_SURVEY.md)、[`DATA_FLYWHEEL.md`](DATA_FLYWHEEL.md)；`simulate`/`evaluate_ppo` 归档 `reports/flywheel/`。
- S0–S1：`configs/constraint_rules.yaml` + explain 披露；`write_rolling_rates` / `train_priority --write-rolling`。
- S2：`docs/TRAJECTORY_PROTOCOL.md` + `application.export_trajectory` → `artifacts/trajectories/`。
- S3：`rl.reward_weights`（含 occupancy）与 CP-SAT λ 解耦；默认仍 `cp_sat`。
- λ 推荐值写回 `configs/optimizer.yaml`（0.5 / 0.1 / 0.1 / 0.1）。
- 仓内 GBDT 优先级：`python -m application.train_priority`。

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
