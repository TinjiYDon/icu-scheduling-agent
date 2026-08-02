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

### 3. 仿真与演示（成员 C 骨架 ✅）

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
.\.venv\Scripts\python.exe -m streamlit run presentation/streamlit_app.py --server.port 8502
```

L4：`run_simulation_with_plan()` · `get_plan()` — Ops/Accept 监测台见 [`TUNING_LOCAL.md`](TUNING_LOCAL.md)

### 从已有 dump 恢复

```powershell
.\scripts\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-full_mimic_94458stays_20260802.dump
```

详见 [`DUMP_READY.md`](DUMP_READY.md)。

## 检查点一览

| 阶段 | 状态 |
|------|------|
| ETL + dump + 冒烟 | **已完成** |
| CP-SAT + Plotly Ops | ✅ |
| online PPO 轨迹 | ❌ 无 MIMIC 轨迹包 |

## dump 命名

当前交付：`icu_scheduling_P0-full_mimic_94458stays_20260802.dump`（`dumps/`，不入 Git）

## 注意

- 勿提交 dump、artifacts、本地配置
- 本仓库与其他 ICU 项目**无代码或数据依赖**
