# icu-scheduling-agent — AGENTS.md

> 资源动态调度 · SOFA + CP-SAT · 成员 C=集成

## 一句话

ICU stays → SOFA/优先级 → CP-SAT 分床 → `sched.assignments` → Streamlit。

## 角色

| 成员 | 职责 |
|------|------|
| A | ETL / dump |
| B | SOFA / CP-SAT /（预研 PPO） |
| C | L4 `plan` + Streamlit |

## 命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py tests/test_smoke.py tests/test_mcp_optimize.py -q
streamlit run presentation/streamlit_app.py
.\.venv\Scripts\pip.exe install "mcp>=1.0"
.\.venv\Scripts\python.exe -m presentation.mcp_server
```

## 关键契约

- L4：`run_simulation_with_plan()` / `get_plan()`
- MCP：`optimize_beds(run_id?)` → 同上（`presentation/mcp_tools.py`）
- 参数故事：`docs/PARAM_STORY.md`
- Bugbot：`docs/BUGBOT.md`
- 默认策略：`cp_sat`；Draft PR #3 的 PPO **不进 main** 直至数据与审查通过

## 分层

UI → L4 → data_access；SQL 在 `data_access/`。

## 数据

schemas_only dump + 缺轨迹表 → 不能宣称真实 PPO 训练成功。
