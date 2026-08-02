# 本地学习 / 调参环境

> 更新：2026-08-02 · **Plotly Ops 台**（Ops / Accept）

| 工具 | 用途 | 入口 |
|------|------|------|
| Streamlit Ops | CP-SAT + 滚动占用 / 热力 | `.\.venv\Scripts\python.exe -m streamlit run presentation/streamlit_app.py` |
| MLflow UI | simulate KPI 历史 | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| dump | 20260802 full | [`DUMP_READY.md`](DUMP_READY.md) |

```powershell
cd d:\project\icu-scheduling-agent
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m streamlit run presentation/streamlit_app.py --server.port 8502
```

勿用裸 `streamlit`（需 venv）。下一步见 [`TOP_TIER_NEXT.md`](TOP_TIER_NEXT.md)。
