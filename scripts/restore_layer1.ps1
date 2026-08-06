# Restore Layer1 dump into icu_scheduling
# Usage: .\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-etl_*.dump
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$PgPassword = "postgres"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $DumpFile)) { throw "Dump not found: $DumpFile" }

$db = "icu_scheduling"
$pgRestore = $null
# 1) Prefer pg_restore on PATH (user configured env, or standard install)
$cmdOnPath = Get-Command pg_restore -ErrorAction SilentlyContinue
if ($cmdOnPath) { $pgRestore = $cmdOnPath.Source }
# 2) Discover PostgreSQL installations from Windows registry
if (-not $pgRestore) {
    $regKeys = @(
        "HKLM:\SOFTWARE\PostgreSQL\Installations\*",
        "HKLM:\SOFTWARE\WOW6432Node\PostgreSQL\Installations\*"
    )
    foreach ($key in $regKeys) {
        $items = Get-ItemProperty $key -ErrorAction SilentlyContinue
        foreach ($item in $items) {
            if ($item.BaseDirectory) {
                $candidate = Join-Path $item.BaseDirectory "bin\pg_restore.exe"
                if (Test-Path $candidate) { $pgRestore = $candidate; break }
            }
        }
        if ($pgRestore) { break }
    }
}
# 3) Fallback: well-known default Program Files locations (PG 15/16/17)
if (-not $pgRestore) {
    $fallbacks = @(
        "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe",
        "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe",
        "C:\Program Files\PostgreSQL\15\bin\pg_restore.exe",
        "C:\Program Files (x86)\PostgreSQL\17\bin\pg_restore.exe",
        "C:\Program Files (x86)\PostgreSQL\16\bin\pg_restore.exe"
    )
    foreach ($candidate in $fallbacks) {
        if (Test-Path $candidate) { $pgRestore = $candidate; break }
    }
}
# 4) Last resort: bare "pg_restore" (will fail with clear error if not on PATH)
if (-not $pgRestore) { $pgRestore = "pg_restore" }

$env:PGPASSWORD = $PgPassword
Write-Host "Restoring $DumpFile -> $db on ${PgHost}:${PgPort}"
& $pgRestore -h $PgHost -p $PgPort -U $PgUser -d $db --clean --if-exists --no-owner --role=icu_dev $DumpFile
Write-Host "OK. Ensure configs/data.yaml has source: mimic"
Write-Host "Connection: icu_dev/icu_dev @ ${PgHost}:${PgPort}/$db"
