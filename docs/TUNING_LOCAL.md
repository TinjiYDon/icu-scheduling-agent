# 本地学习 / 调参环境

> 更新：2026-07-27 · Streamlit + 可选 MLflow（SQLite）

## 人读摘要

| 工具 | 用途 | 入口 |
|------|------|------|
| Streamlit | 交互预测 / 仿真 / 改 candidate_cap | `streamlit run presentation/streamlit_app.py` |
| MLflow UI | 看 auc / simulate 指标历史 | `mlflow ui --backend-store-uri sqlite:///./mlflow.db` |
| PROGRESS | 数据处理看板 | `d:\project\_local-data\mimic\PROGRESS.md` |
| yaml | 权威配置 | `configs/*.yaml` |

## 安装（各仓 .venv）

```powershell
.\.venv\Scripts\pip.exe install mlflow streamlit
```

`mlflow.db` / `mlruns/` 已 gitignore，勿提交。

## Decision

```powershell
cd d:\project\icu-decision-agent
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.train
streamlit run presentation/streamlit_app.py
.\.venv\Scripts\python.exe -m mlflow ui --backend-store-uri sqlite:///./mlflow.db
```

## Scheduling

```powershell
cd d:\project\icu-scheduling-agent
$env:PYTHONPATH = (Get-Location)
streamlit run presentation/streamlit_app.py
.\.venv\Scripts\python.exe -m application.simulate
.\.venv\Scripts\python.exe -m mlflow ui --backend-store-uri sqlite:///./mlflow.db
```

## 注意

- 改 `candidate_cap` **不**减少 labs/SOFA/feat 行数
- PPO 合成 smoke 见 `PPO_SMOKE.md`，与 MLflow 实验台独立
