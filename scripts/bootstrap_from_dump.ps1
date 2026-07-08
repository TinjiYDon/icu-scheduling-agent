# 从 _local-data/mimic 的 Layer1 dump 恢复 → 跑 ETL（dump/ETL 数据均不入 GitHub）
param(
    [string]$DumpFile = "d:\project\_local-data\mimic\icu_scheduling_P0-etl_mimic_94458stays_20260708.dump",
    [ValidateSet("demo", "full", "mimic")]
    [string]$MimicSource = "demo",
    [switch]$SkipRestore,
    [switch]$SkipEtl,
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

if (-not $SkipRestore) {
    & (Join-Path $PSScriptRoot "restore_layer1.ps1") `
        -Target scheduling `
        -DumpFile $DumpFile `
        -PgHost $PgHost `
        -PgPort $PgPort
}

$dataYaml = Join-Path $root "configs\data.yaml"
if (-not (Test-Path $dataYaml)) {
    Copy-Item (Join-Path $root "configs\data.yaml.example") $dataYaml
}

if (-not $SkipEtl) {
    $env:PYTHONPATH = $root
    Write-Host "Running ETL (mimic_source=$MimicSource)..."
    & $py -m application.etl_pipeline
}

Write-Host "Done. Next: python -m application.run_p0"
