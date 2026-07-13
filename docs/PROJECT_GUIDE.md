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
python -m application.simulate
python -m application.run_p0
streamlit run presentation/streamlit_app.py
```

L4：`run_simulation_with_plan()` · `get_plan()` — 见 [`docs/TODO_OWNER.md`](TODO_OWNER.md)

### 从已有 dump 恢复

```powershell
.\scripts\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-etl_mimic_94458stays_20260708.dump
.\scripts\bootstrap_from_dump.ps1 -SkipEtl
```

## 检查点一览

| 阶段 | 状态 |
|------|------|
| ETL + dump + 冒烟 | **已完成** |
| CP-SAT + Streamlit | C 骨架 ✅ · B 指标待完善 |

## dump 命名

`icu_scheduling_P0-etl_{layer0}_{N}stays_{yyyymmdd}.dump` → 存放于 `dumps/`

## 待完成

| 项 | 位置 |
|----|------|
| CP-SAT 指标 / 目标分解 | B · `domain/optimizer/` |
| PPO | `domain/optimizer/` |
| MCP Tool | `docs/INNOVATION_ROADMAP.md` |

## 注意

- 勿提交 dump、artifacts、本地配置
- 本仓库与其他 ICU 项目**无代码或数据依赖**
