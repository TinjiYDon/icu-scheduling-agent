# 项目状态

> 更新：2026-07-13

## 数据检查点（已完成）

| 项 | 状态 |
|----|------|
| ETL staging | ✓ 94,458 stays |
| dump | ✓ `dumps/icu_scheduling_P0-etl_mimic_94458stays_20260708.dump` |
| 冒烟测试 | ✓ `run_data_pipeline.ps1` |

## 仿真阶段

| 项 | 状态 |
|----|------|
| SOFA + CP-SAT | `application.simulate`（B 主责） |
| L4 `plan.get_plan` / `run_simulation_with_plan` | ✅ C 已完成 |
| Streamlit 分配方案页 | ✅ C 已完成 |
| PPO / MCP | P2+ 规划 |

## 成员 C 本阶段交付

- `application/plan.py` + `data_access/assignments_repo.py`
- `presentation/streamlit_app.py`（目标分解 + 空态/not_found）

## 验证

```powershell
$env:PYTHONPATH = (Get-Location)
pytest tests/test_plan.py tests/test_smoke.py -q
streamlit run presentation/streamlit_app.py
```
