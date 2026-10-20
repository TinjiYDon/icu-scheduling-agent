# icu-scheduling-agent — AGENTS.md

> 精简版 · L1 + L2 + L3(CP-SAT / SOFA)

## 一句话

ICU stays → SOFA → CP-SAT 分床 → `sched.assignments`。

## 先读

1. `README.md`

## 命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m application.simulate
```

## 关键契约

- L4：`run_simulation_with_plan()` / `get_plan()`（`application/plan.py`）
- 评估：calib/eval（`domain.optimizer.eval_split`）· **不是** train/val/test
- 唯一调度策略：`cp_sat`（`domain.optimizer.cp_sat.run_assignment`）
- SQL 只在 `data_access/` 与 `migrations/`

## 分层

L4（`application/`）→ L3（`domain/`）→ L2（`data_access/`）→ L1（`infra/`）。

## 已移除

展示层、RL/PPO、GBDT 优先级预测、`docs/`、`scripts/`、`dumps/`、`.github/`。
