# 本地数据说明

**数据文件不入 GitHub。** 默认使用仓库内 `dumps/` 目录。

## 目录约定

```
icu-scheduling-agent/
├── dumps/
│   └── icu_scheduling_P0-etl_*.dump
└── configs/database.yaml, data.yaml   ← 本地创建
```

## Layer0 配置

`configs/database.yaml`：

```yaml
layer0:
  mimic_source: mimic
  mimic_dsn: "postgresql+psycopg://icu_dev:icu_dev@localhost:5432/mimic"
```

## 导出 dump

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1
```

## 从 dump 恢复

```powershell
.\scripts\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-etl_mimic_94458stays_20260708.dump
```

## 下一阶段

```powershell
python -m application.simulate
python -m application.run_p0
```
