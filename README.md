# ICU 医疗资源动态调度智能体

仓库：[icu-scheduling-agent](https://github.com/TinjiYDon/icu-scheduling-agent) · 数据库：`icu_scheduling`

## 文档

**从 [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) 开始。**

## 当前阶段

数据检查点 ✓（ETL 94,458 + dump + 冒烟）· 下一步：CP-SAT 仿真

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1
python -m application.simulate
```

## 架构

```
Layer0 mimic → ETL → SOFA → CP-SAT/PPO → Streamlit
```

## Docker

```powershell
docker compose up -d   # PG 端口 5434
```
