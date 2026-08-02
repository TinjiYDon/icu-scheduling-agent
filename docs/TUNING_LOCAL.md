# 本地学习 / 调参环境

> 更新：2026-08-02 · Streamlit 交互台（仿真 / 时间线 / 验收）+ MLflow

## 人读摘要

| 工具 | 用途 | 入口 |
|------|------|------|
| Streamlit | CP-SAT + 滚动占用时间线 + 验收 | `streamlit run presentation/streamlit_app.py` |
| MLflow UI | simulate KPI 历史 | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| dump | 20260802 full | [`DUMP_READY.md`](DUMP_READY.md) |
| yaml | 权威配置 | `configs/optimizer.yaml` |

```powershell
cd d:\project\icu-scheduling-agent
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\pip.exe install mlflow streamlit
streamlit run presentation/streamlit_app.py
.\.venv\Scripts\python.exe -m mlflow ui --backend-store-uri sqlite:///./mlflow.db
```

`mlflow.db` / `mlruns/` 已 gitignore。顶尖下一步见工作区 `docs/TOP_TIER_NEXT.md`。
