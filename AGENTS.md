# icu-scheduling-agent — AGENTS.md

> 资源动态调度 · SOFA + CP-SAT

## 一句话

ICU stays → SOFA/优先级 → CP-SAT 分床 → `sched.assignments`。

## 先读

1. `docs/PROJECT_GUIDE.md`
2. `docs/PARAM_STORY.md`
3. `docs/DUMP_READY.md` · `docs/TUNING_LOCAL.md`

## 命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py tests/test_smoke.py tests/test_simulate_metrics.py -q
.\.venv\Scripts\python.exe -m application.simulate
```

## 关键契约

- L4：`run_simulation_with_plan()` / `get_plan()`
- 评估：calib/eval（`domain.optimizer.eval_split`）· **不是** train/val/test
- 参数故事：`docs/PARAM_STORY.md`
- 默认策略：`cp_sat`；PPO 代码在仓内但**未启用**，无 MIMIC 轨迹包

## 分层

L4（`application/`）→ L3（`domain/`）→ L2（`data_access/`）→ L1（`infra/`）；SQL 在 `data_access/`。
仓库**不再包含**任何展示层（Streamlit / MCP 已移除）。

## 数据

schemas_only dump + 缺轨迹表 → 不能宣称真实 PPO 训练成功。
