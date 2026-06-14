# 项目一 · 状态摘要

> 团队总览：[`../PROJECT_STATUS.md`](../PROJECT_STATUS.md)

## P0 进度（Demo）

| 项 | 状态 |
|----|------|
| ETL staging | ✓ 140 stays |
| SOFA（24h  lab 简化） | ✓ |
| CP-SAT 床位分配 | ✓ 20/140 分配 |
| Layer1 dump | ✓ `../dumps/icu_scheduling_layer1_schemas_*.dump` |

## 一键跑通

```powershell
.\scripts\apply_migrations.ps1
python -m application.run_p0
```

## 分步

```powershell
python -m application.etl_pipeline
python -m application.simulate
```
