# ICU 医疗资源动态调度智能体 · CP-SAT 核心

独立开源项目 · 仓库 [icu-scheduling-agent](https://github.com/TinjiYDon/icu-scheduling-agent)

保留范围:**L1 基础设施 + L2 数据访问 + L3 CP-SAT(含 SOFA 评分)**。RL/PPO、L4 数据入口、文档与运维脚本已移除。

## 结构

```
infra/          L1  配置、数据库连接、MLflow
data_access/    L2  仓储(MIMIC 停留记录 / 分床结果)
domain/
  optimizer/    L3  CP-SAT 分床、calib/eval 划分、可解释输出、λ 调参
  scoring/      L3  SOFA 评分
  rolling/      L3  滚动时域调度引擎
  etl/          L3  ETL 流水线(保留库代码,暂无入口)
application/    L4  simulate / plan / optimize
configs/        配置模板与优化器参数
migrations/     PostgreSQL schema
tests/          CP-SAT / λ / DB 相关测试
```

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
copy configs\database.yaml.example configs\database.yaml
copy configs\data.yaml.example configs\data.yaml
```

数据库(可选 Docker):

```powershell
docker compose -p icu_scheduling up -d   # PostgreSQL 端口 5434
```

建表(按顺序执行 `migrations/` 下的 SQL,或使用任意迁移工具):

```powershell
psql -h localhost -p 5434 -U postgres -d icu_scheduling -f migrations\001_layer1_schemas.sql
psql -h localhost -p 5434 -U postgres -d icu_scheduling -f migrations\002_staging_icustays.sql
psql -h localhost -p 5434 -U postgres -d icu_scheduling -f migrations\003_sequence_grants.sql
```

## 入口

```powershell
$env:PYTHONPATH = (Get-Location)
.\.venv\Scripts\python.exe -m application.simulate
```

| 用途 | 入口 |
|------|------|
| 滚动仿真(CLI) | `python -m application.simulate` |
| 读取分床方案 | `from application.plan import get_plan, run_simulation_with_plan` |
| 策略入口 | `from application.optimize import optimize` |

## 关键契约

- 评估划分为 **calib / eval**,不是 train/val/test
- 唯一调度策略:`cp_sat`
- CP-SAT 只通过 `domain.optimizer.cp_sat.run_assignment()` 进入
- SQL 只出现在 `data_access/` 与 `migrations/`
