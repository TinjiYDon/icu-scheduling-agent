# ICU 调度智能体 · 项目指南

面向所有克隆本仓库的开发者：按下列步骤即可复现数据检查点，无需其他 ICU 项目。

## 架构

```
Layer0 (MIMIC) → ETL → SOFA → CP-SAT / PPO → Streamlit
PostgreSQL: icu_scheduling
```

## 前置条件

| 项 | 说明 |
|----|------|
| PostgreSQL 16 | 本机 `localhost:5432` 或 Docker `5434` |
| Python 3.11+ | 建议 venv + `pip install -e ".[dev]"` |
| Layer0 数据 | `mimic_iv_demo` 或自建 `mimic` 全量库 |
| 本地配置 | 从 `configs/*.example` 复制，**勿提交** |

> 脚本端口解析顺序：`-PgPort` > `$env:PG_PORT` > `configs/database.yaml` > `5432`；Docker 用户把 `database.yaml` 的端口写成 `5434` 即可。
> 未安装宿主 `psql` / `pg_dump` / `pg_restore` 时，`scripts/*.ps1` 自动回退到 `docker exec`（容器名可用 `$env:PG_CONTAINER` 覆盖）。

## 推荐流程

### 1. 初始化

```powershell
copy configs\database.yaml.example configs\database.yaml
copy configs\data.yaml.example configs\data.yaml
.\scripts\apply_migrations.ps1
```

### 2. 数据检查点（当前阶段终点）

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1
```

### 3. 仿真与演示

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
.\.venv\Scripts\python.exe -m streamlit run presentation/streamlit_app.py --server.port 8502
```

L4：`run_simulation_with_plan()` · `get_plan()` — Ops/Accept 监测台见 [`TUNING_LOCAL.md`](TUNING_LOCAL.md)

### 从已有 dump 恢复

```powershell
.\scripts\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-full_*.dump
```

宿主没有 `pg_restore` 时自动走 `docker exec`；目标库可用 `-Database` 指定。详见 [`DUMP_READY.md`](DUMP_READY.md)。

## 命令入口

| 用途 | 命令 |
|------|------|
| ETL 检查点 | `python -m application.run_etl_stage` |
| ETL + 仿真 | `python -m application.run_p0` |
| 滚动仿真 | `python -m application.simulate` |
| 策略选择（cp_sat / ppo） | `python -m application.optimize` |
| GBDT 优先级 | `python -m application.train_priority` |
| PPO 训练 / 推理 / 对照评估 | `python -m application.train_ppo` · `run_ppo` · `evaluate_ppo` |
| MCP | `python -m presentation.mcp_server` |
| Ops 台 | `.\scripts\run_console.ps1` |

## PPO 模块契约

- 环境每次决策一个患者：动作 `0..n_beds-1` 选床，`n_beds` 表示继续等待。
- 调用方构造固定 episode 的 `Patient` / `Bed`；`ICUEnv` 本身不查库。
- 训练与推理都必须使用 `action_masks()`，不能只依赖非法动作惩罚。
- 默认策略仍是 `cp_sat`；PPO 仅作对照，`artifacts/ppo_icu.zip` 不入库。

## dump 命名

`dumps/icu_scheduling_P0-full_<mimic_source>_<stays>stays_<yyyymmdd>.dump`（**不入 Git**）。

## 注意

- 勿提交 dump、artifacts、本地配置
- 本仓库与其他 ICU 项目**无代码或数据依赖**
