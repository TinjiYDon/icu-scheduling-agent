# ICU 医疗资源动态调度智能体

独立开源项目 · 3 人协作 · 仓库 [icu-scheduling-agent](https://github.com/TinjiYDon/icu-scheduling-agent)

**协作入口**：[`docs/COLLABORATION.md`](docs/COLLABORATION.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/BACKLOG.md`](docs/BACKLOG.md)

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
copy configs\database.yaml.example configs\database.yaml
copy configs\data.yaml.example configs\data.yaml
.\scripts\apply_migrations.ps1
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1   # 数据检查点：ETL + dump + 冒烟
```

## 文档

| 文档 | 说明 |
|------|------|
| [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) | 架构、流程、命令 |
| [docs/DUMP_READY.md](docs/DUMP_READY.md) | **线下 dump 单发 / restore** |
| [docs/TUNING_LOCAL.md](docs/TUNING_LOCAL.md) | Plotly Ops 台启动 |
| [docs/STATUS.md](docs/STATUS.md) | 当前进度 |
| [docs/README.md](docs/README.md) | 文档索引 |

## 架构

```
MIMIC (Layer0) → ETL → SOFA → CP-SAT（滚动） → Streamlit Ops
```

## Docker（可选）

```powershell
docker compose up -d   # PostgreSQL 端口 5434
```

## 仿真与演示（Plotly Ops）

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
.\.venv\Scripts\python.exe -m streamlit run presentation/streamlit_app.py --server.port 8502
```

线下 dump：**不入 Git**，见 [`docs/DUMP_READY.md`](docs/DUMP_READY.md)。页面：Ops / Accept。默认策略 `cp_sat`（无 MIMIC PPO 轨迹时勿宣称 online RL）。
