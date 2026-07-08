# 本地数据与 ETL（不入 GitHub）

## SSOT

```
d:\project\_local-data\mimic\
└── icu_scheduling_P0-etl_mimic_94458stays_20260708.dump
```

命名：`{db}_P0-etl_{layer0}_{N}stays_{yyyymmdd}.dump`

## 生产 dump

```powershell
$env:PYTHONPATH = (Get-Location)
.\scripts\run_data_pipeline.ps1
```

## 队友 restore

```powershell
.\scripts\restore_layer1.ps1 -Target scheduling `
  -DumpFile "d:\project\_local-data\mimic\icu_scheduling_P0-etl_mimic_94458stays_20260708.dump"
```

## 模型阶段（下一步）

```powershell
python -m application.simulate
python -m application.run_p0
```
