# Restore Layer1 dump into icu_scheduling
# Usage: .\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-etl_*.dump
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,
    [string]$PgHost = "localhost",
    [int]$PgPort = 0,
    [string]$PgUser = "postgres",
    [string]$PgPassword = "postgres"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

# Port precedence: -PgPort > $env:PG_PORT > configs/database.yaml > 5432
if ($PgPort -le 0) {
    if ($env:PG_PORT) {
        $PgPort = [int]$env:PG_PORT
    }
    elseif (Test-Path (Join-Path $root "configs\database.yaml")) {
        $m = Select-String -Path (Join-Path $root "configs\database.yaml") -Pattern 'localhost:(\d+)' -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($m) { $PgPort = [int]$m.Matches[0].Groups[1].Value }
    }
    if ($PgPort -le 0) { $PgPort = 5432 }
}

if (-not (Test-Path $DumpFile)) { throw "Dump not found: $DumpFile" }

$db = "icu_scheduling"
$pgRestore = "pg_restore"
if (Test-Path "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe") {
    $pgRestore = "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe"
}

$env:PGPASSWORD = $PgPassword
Write-Host "Restoring $DumpFile -> $db on ${PgHost}:${PgPort}"
& $pgRestore -h $PgHost -p $PgPort -U $PgUser -d $db --clean --if-exists --no-owner --role=icu_dev $DumpFile
Write-Host "OK. Ensure configs/data.yaml has source: mimic"
Write-Host "Connection: icu_dev/icu_dev @ ${PgHost}:${PgPort}/$db"
