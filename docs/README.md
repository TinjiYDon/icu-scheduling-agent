# 文档索引

| 文档 | 内容 |
|------|------|
| [PROJECT_GUIDE.md](PROJECT_GUIDE.md) | **主入口** |
| [DATA_LOCAL.md](DATA_LOCAL.md) | MIMIC / dump 本地配置 |
| [STATUS.md](STATUS.md) | 当前进度 |
| [INNOVATION_ROADMAP.md](INNOVATION_ROADMAP.md) | 里程碑 P0–P4 |

## 数据检查点

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1
```

## dump 命名

`icu_scheduling_P0-etl_{layer0}_{N}stays_{yyyymmdd}.dump` → `dumps/`
