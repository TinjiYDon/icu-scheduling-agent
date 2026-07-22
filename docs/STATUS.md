# 项目状态

> 更新：2026-07-22

## 数据检查点（已完成）

| 项 | 状态 |
|----|------|
| ETL staging | ✓ 94,458 stays |
| dump | ✓ 曾导出；schemas_only 不足支撑 PPO（见 `PARAM_STORY.md`） |
| 冒烟测试 | ✓ `run_data_pipeline.ps1` |

## 仿真阶段

| 项 | 状态 |
|----|------|
| SOFA + CP-SAT | B 主责（Issue #4） |
| L4 `plan` / Streamlit | ✅ C |
| Draft PR #3 lambda+PPO | 审查中 · **保持 Draft** · PPO 不合 main |
| MCP | P2+ |

## 成员 C 本阶段交付

- `plan` + `assignments_repo` + 目标分解 UI
- `docs/PARAM_STORY.md`
- PR #3 审查评论（拆合 lambda 可议）

## 验证

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py tests/test_smoke.py -q
streamlit run presentation/streamlit_app.py
```
