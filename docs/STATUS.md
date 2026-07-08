# 项目状态

> 更新：2026-07-08

## 数据检查点（已完成）

| 项 | 状态 |
|----|------|
| ETL staging | ✓ 94,458 stays |
| dump | ✓ `dumps/icu_scheduling_P0-etl_mimic_94458stays_20260708.dump` |
| 冒烟测试 | ✓ `run_data_pipeline.ps1` |

## 仿真阶段（下一步）

| 项 | 状态 |
|----|------|
| SOFA + CP-SAT | 待 `application.simulate` |
| Streamlit | 占位 |

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1
python -m application.simulate
```
