# ICU 调度智能体 · 项目指南

## 架构

```
Layer0 mimic → ETL → SOFA → CP-SAT → Streamlit / 滚动仿真
PostgreSQL: icu_scheduling
```

## 数据与 dump（不入 GitHub）

| 资源 | 路径 |
|------|------|
| 最新 dump | `d:\project\_local-data\mimic\icu_scheduling_P0-etl_mimic_94458stays_20260708.dump` |
| 本地配置 | `configs/database.yaml` `configs/data.yaml` |

## 常用命令

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1      # ✅ 数据检查点
python -m application.simulate       # ⏸ 模型阶段
python -m application.run_p0
```

## 检查点

| 阶段 | 状态 |
|------|------|
| ETL + dump + 冒烟 | **当前终点** |
| CP-SAT / PPO | 下一步 |

## 待完成

| 项 | 文件 |
|----|------|
| Streamlit | `presentation/streamlit_app.py` |
| PPO | `domain/optimizer/` |
| MCP | `docs/INNOVATION_ROADMAP.md` |

## GitHub

`TinjiYDon/icu-scheduling-agent`

## 注意

- dump / artifacts 勿提交
- `mimic_source`: demo \| full \| mimic
