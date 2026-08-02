# 本地学习 / 调参环境

> 更新：2026-08-02 · **演示台 v4**（项目 / 运行 / 验收）

| 工具 | 用途 | 入口 |
|------|------|------|
| Streamlit Ops | CP-SAT + 滚动占用 / 热力 / 可解释 | `.\scripts\run_console.ps1` |
| MLflow UI | simulate KPI 历史 | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| dump | 20260802 full | [`DUMP_READY.md`](DUMP_READY.md) |
| 答辩口播 | [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) |

```powershell
cd d:\project\icu-scheduling-agent
.\scripts\run_console.ps1
# 默认 http://localhost:8502
```

勿用裸 `streamlit`（需 venv）。下一步见 [`TOP_TIER_NEXT.md`](TOP_TIER_NEXT.md)。
