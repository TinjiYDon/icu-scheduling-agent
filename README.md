# ICU 医疗资源动态调度智能体

独立开源项目 · 3 人协作 · 仓库 [icu-scheduling-agent](https://github.com/TinjiYDon/icu-scheduling-agent)

**总目标 · 总内容（一条主线）**：[`docs/MASTER_NARRATIVE.md`](docs/MASTER_NARRATIVE.md)  
**完整汇报稿（面面俱到）**：[`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md)  
→ 可审计 · 可对照 · 可滚动的 ICU 床位动态调度（默认 CP-SAT；不接 decision 风险分）

**协作入口**：[`docs/COLLABORATION.md`](docs/COLLABORATION.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`docs/BACKLOG.md`](docs/BACKLOG.md)

**本次变更交接**：[`README_HANDOFF.md`](README_HANDOFF.md)（部署、复现、验证结果与后续任务）

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

## 测试

普通测试不依赖 PostgreSQL，CI 运行同一套完整单测：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

真实数据库测试必须显式启用。以下三项只读检查连接、数据和 CP-SAT 可行性：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_db.py tests/test_cp_sat_quick.py --run-db -q
```

`tests/test_etl.py::test_etl_smoke` 也属于数据库集成测试，会运行 ETL、写入特征表；仅在准备好相应数据库时单独执行。

## 文档导航

| 文档 | 说明 |
|------|------|
| [docs/MASTER_NARRATIVE.md](docs/MASTER_NARRATIVE.md) | **总目标 / 总内容 / 创新如何挂链** |
| [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) | 架构、流程、命令 |
| [docs/DUMP_READY.md](docs/DUMP_READY.md) | **线下 dump 单发 / restore** |
| [docs/TUNING_LOCAL.md](docs/TUNING_LOCAL.md) | Plotly Ops 台启动 |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | **答辩演示口播** |
| [docs/STATUS.md](docs/STATUS.md) | 当前进度与仿真 |
| [docs/TEAM_DIRECTION.md](docs/TEAM_DIRECTION.md) | **组员方向同步（必读）** |
| [docs/PROGRESS.md](docs/PROGRESS.md) | 里程碑完成度 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 本仓变更 / Release |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 下一版本 |
| [docs/README.md](docs/README.md) | 文档索引 |

**边界**：默认 `cp_sat`；预测层用仓内病情参数，**不接** decision 风险分。

## 答辩演示

```powershell
.\scripts\run_console.ps1
```

口播步骤见 [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)：项目总览 → 运行（自动仿真 + 可解释）→ 验收。

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
.\scripts\run_console.ps1
```

线下 dump：**不入 Git**，见 [`docs/DUMP_READY.md`](docs/DUMP_READY.md)。页面：项目 / 运行 / 验收。默认策略 `cp_sat`（无 MIMIC PPO 轨迹时勿宣称 online RL）。
