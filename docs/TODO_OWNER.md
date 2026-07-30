# 成员 C · 集成负责人待办

## 已完成（本阶段）

| 任务 | 文件 | 状态 |
|------|------|------|
| L4 方案查询 | `application/plan.py` + `data_access/assignments_repo.py` | ✅ SQL 下沉 |
| Streamlit 演示 | `presentation/streamlit_app.py` | ✅ 目标分解 + 空态 |
| 测试 | `tests/test_plan.py` | ✅ smoke |

## 待完成

| 任务 | 说明 |
|------|------|
| MCP `optimize_beds` | ✅ 骨架 · `python -m presentation.mcp_server` |
| PPO 进阶 | S4 · B 主责 · Draft PR #3 |
| Bugbot | ✅ 已开 2026-07-22 · `docs/BUGBOT.md` |

## 验证

```powershell
$env:PYTHONPATH = (Get-Location)
python -m application.simulate
python -m application.run_p0
streamlit run presentation/streamlit_app.py
pytest tests/test_plan.py -q
```
