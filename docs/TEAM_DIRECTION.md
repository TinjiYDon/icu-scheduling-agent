# 方向同步（组员必读）· 2026-09-13

> Owner：`TinjiYDon` · 已合入：PR [#8](https://github.com/TinjiYDon/icu-scheduling-agent/pull/8) → `main`  
> 请 `git pull origin main` 后按本文调整本周工作；有异议在 Issue / 群内回复。

## 人读摘要

| 项 | 内容 |
|----|------|
| 定位 | **独立** 多目标多约束滚动床位调度 + RL 对照轨 |
| 禁止 | 读取 decision `risk_score`；无轨迹协议宣称 online MIMIC-PPO |
| 默认策略 | **CP-SAT**；PPO / Greedy 为对照 |
| 本周请做 | Review `main`；跑 simulate / `compare_policies`；补约束披露与轨迹导出验收 |

## 本周方向调整

1. 本仓独立出成果，**不**做「预警风险→优先级→分床」跨仓硬耦合。  
2. 深挖：可配置约束规则、滚动到达强度、轨迹协议、CP-SAT/Greedy/PPO 对照表。  
3. 见 [`SOTA_SURVEY.md`](SOTA_SURVEY.md) H1–H3 · [`TRAJECTORY_PROTOCOL.md`](TRAJECTORY_PROTOCOL.md) · [`DATA_FLYWHEEL.md`](DATA_FLYWHEEL.md)。

## 已合入改动（请 Review）

- `constraint_rules.yaml` + explain 披露  
- 轨迹导出约定 · `rl.reward_weights`  
- simulate / evaluate 飞轮归档 `reports/flywheel/`  
- `compare_policies` / `comparison_table`（H3 对照）  
- Nightly #7：删除死代码 `synthetic_sofa` 等（已合）

## 验收命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_compare_policies.py tests/test_trajectory_export.py tests/test_flywheel_archive.py -q
.\.venv\Scripts\python.exe -m application.compare_policies --from-report reports/ppo_evaluation.json
```

（若尚无 evaluation 报告，可先 `python -m application.evaluate_ppo`，需模型与数据就绪。）

## Draft PR

本仓当前无 Draft。历史 Draft 清理类已随 #7 处理。

## Agent 上下文

```text
SSOT: docs/STATUS.md · docs/TEAM_DIRECTION.md · docs/PARAM_STORY.md
禁区: dumps/ artifacts/ · 禁止 priority_weight ← decision risk_score
```
