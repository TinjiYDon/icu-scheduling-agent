# 成员 C · 集成负责人待办

## 已完成（本阶段）

| 任务 | 文件 | 状态 |
|------|------|------|
| L4 方案查询 | `application/plan.py` | ✅ `get_plan` / `run_simulation_with_plan` |
| Streamlit 演示 | `presentation/streamlit_app.py` | ✅ 仿真 → 分配表 |
| 测试 | `tests/test_plan.py` | ✅ smoke |

## 待完成

| 任务 | 说明 |
|------|------|
| MCP `optimize_beds` | S4 · P2 |
| PPO 进阶 | S4 · B 主责 |

## 验证

```powershell
$env:PYTHONPATH = (Get-Location)
python -m application.simulate
python -m application.run_p0
streamlit run presentation/streamlit_app.py
pytest tests/test_plan.py -q
```
