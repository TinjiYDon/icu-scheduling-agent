# ICU 医疗资源动态调度智能体

独立开源项目 · 3 人协作 · 仓库 [icu-scheduling-agent](https://github.com/TinjiYDon/icu-scheduling-agent)

**协作入口**：[`CONTRIBUTING.md`](CONTRIBUTING.md)

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
| [docs/DATA_LOCAL.md](docs/DATA_LOCAL.md) | 本地库配置、dump 导出与恢复 |
| [docs/DUMP_READY.md](docs/DUMP_READY.md) | **线下 dump 单发 / restore** |
| [docs/TUNING_LOCAL.md](docs/TUNING_LOCAL.md) | MLflow 本地查看 |
| [docs/PARAM_STORY.md](docs/PARAM_STORY.md) | SOFA / 优先级 / λ 参数语义 |
| [docs/LAMBDA_TUNING.md](docs/LAMBDA_TUNING.md) | λ 调参方法 |
| [docs/README.md](docs/README.md) | 文档索引 |

**边界**：默认 `cp_sat`；预测层用仓内病情参数，**不接** decision 风险分。

## 架构

```
MIMIC (Layer0) → ETL → SOFA → CP-SAT（滚动）
```

## Docker（可选）

```powershell
# 仓库路径含中文时 compose 推导不出 project name，需显式指定
docker compose -p icu_scheduling up -d   # PostgreSQL 端口 5434
```

脚本端口解析顺序：`-PgPort` > `$env:PG_PORT` > `configs/database.yaml` > `5432`。
未安装宿主 `psql` / `pg_dump` / `pg_restore` 时，`scripts/*` 自动回退到 `docker exec`（容器名可用 `$env:PG_CONTAINER` 覆盖）。

## 仿真

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
```

线下 dump：**不入 Git**，见 [`docs/DUMP_READY.md`](docs/DUMP_READY.md)。默认策略 `cp_sat`（无 MIMIC PPO 轨迹时勿宣称 online RL）。
