# 本地学习 / 调参环境

> 更新：2026-10-09 · 演示台（项目 / 运行 / **多目标** / **对照** / 方法 / 验收）

| 工具 | 用途 | 入口 |
|------|------|------|
| Streamlit Ops | CP-SAT + 滚动 + MOO + H3 对照 | `.\scripts\run_console.ps1` |
| MLflow UI | simulate KPI 历史 | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| dump | 20260802 full（旁路目录） | [`DUMP_READY.md`](DUMP_READY.md) |
| 答辩口播 | [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) · [`TEACHER_INNOVATION.md`](TEACHER_INNOVATION.md) |

```powershell
cd "C:\Users\lenovo\Desktop\decision shcedule\icu-scheduling-agent"
.\scripts\run_console.ps1
# 默认 http://localhost:8502
```

勿用裸 `streamlit`（需 venv）。下一步见 [`TOP_TIER_NEXT.md`](TOP_TIER_NEXT.md)。
