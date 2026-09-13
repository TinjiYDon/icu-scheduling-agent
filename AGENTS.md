# icu-scheduling-agent — AGENTS.md

> 资源动态调度 · SOFA + CP-SAT + 滚动 · 仓内 RL 深化 · 成员 C=集成  
> **独立项目**：不读取 `icu-decision-agent` 风险分。

## 一句话

ICU stays → 仓内 SOFA/GBDT 优先级 → CP-SAT 多目标分床（滚动）→ 可选 PPO 对照 → Streamlit。

## 角色

| 成员 | 职责 |
|------|------|
| A | ETL / dump |
| B | SOFA / CP-SAT / 轨迹 / RL |
| C | L4 `plan` + Streamlit |

## 先读

1. `docs/ROADMAP.md`（Wave S-LIT / S0–S3 / S-FLY）
2. `docs/SOTA_SURVEY.md`（**先对标再创新**；无 LIT 不宣称 SOTA）
3. `docs/DATA_FLYWHEEL.md`
4. `docs/PARAM_STORY.md`
5. `docs/STATUS.md`
6. `docs/DUMP_READY.md` · `docs/TUNING_LOCAL.md` · `docs/PPO_SMOKE.md` · `docs/TRAJECTORY_PROTOCOL.md`

## 命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m pytest tests/test_plan.py tests/test_smoke.py tests/test_mcp_optimize.py tests/test_simulate_metrics.py -q
streamlit run presentation/streamlit_app.py
.\.venv\Scripts\pip.exe install "mcp>=1.0"
.\.venv\Scripts\python.exe -m presentation.mcp_server
```

## 关键契约

- L4：`run_simulation_with_plan()` / `get_plan()`
- 评估：calib/eval（`domain.optimizer.eval_split`）· **不是** train/val/test
- MCP：`optimize_beds(run_id?)` → 同上（`presentation/mcp_tools.py`）——**本仓接口**
- 参数故事：`docs/PARAM_STORY.md`
- Bugbot：`docs/BUGBOT.md`
- 默认策略：`cp_sat`；PPO 代码在 main，默认未切；**无轨迹协议则不宣称 online MIMIC-PPO**
- **禁止**硬耦合 decision `risk_score` API

## 分层

UI → L4 → data_access；SQL 在 `data_access/`。

## 数据

dump/artifacts/trajectories **不入 Git**。
