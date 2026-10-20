# 本地实验查看

| 工具 | 用途 | 入口 |
|------|------|------|
| MLflow UI | `run_simulation_with_plan` 的 KPI 历史 | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| λ 网格搜索 | 生成 `reports/lambda_tuning_*.csv|json` | `python scripts/tune_lambda.py --split calib` |
| dump | restore / 导出 | [`DUMP_READY.md`](DUMP_READY.md) |

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
.\.venv\Scripts\python.exe -m mlflow ui --backend-store-uri sqlite:///./mlflow.db
```

仿真 KPI 由 `application/plan.py` 写入 MLflow（不可用时会在返回 JSON 的 `mlflow_error` 里说明，不中断仿真）。
