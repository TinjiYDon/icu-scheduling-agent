# 项目状态

> 更新：2026-07-26

## 数据检查点（已完成）

| 项 | 状态 |
|----|------|
| ETL staging | ✓ 94,458 stays |
| dump | ✓ 最新仍 **20260708**；`_local-data` 重复/legacy 已清 |
| 冒烟测试 | ✓ `run_data_pipeline.ps1` |

## 仿真阶段

| 项 | 状态 |
|----|------|
| SOFA + CP-SAT | B 主责（Issue #4）；Owner 可代跑 labs→sofa |
| L4 `plan` / Streamlit | ✅ C |
| MCP Tool `optimize_beds` | ✅ C 骨架（`presentation/mcp_server.py`） |
| Draft PR #3 lambda+PPO | 审查中 · **保持 Draft** · PPO 不合 main |
| calib/eval 骨架 | ✅ Wave1 · `eval_split` + simulate metrics |
| SOFA→feat + STATUS 数值 | ⏳ Wave2 · B |
| MCP（完整联调） | P2+ · 骨架已合 |
| Bugbot | ✅ 已开 |
| 路线图 | [`ROADMAP_EXEC.md`](ROADMAP_EXEC.md) |

## 成员 C 本阶段交付

- `plan` + `assignments_repo` + 目标分解 UI
- `docs/PARAM_STORY.md`
- PR #3 审查评论（拆合 lambda 可议）
- MCP `optimize_beds` 骨架

## 验证

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py tests/test_smoke.py tests/test_mcp_optimize.py -q
streamlit run presentation/streamlit_app.py
.\.venv\Scripts\pip.exe install "mcp>=1.0"
.\.venv\Scripts\python.exe -m presentation.mcp_server
```
