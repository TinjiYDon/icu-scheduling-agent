param(
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
Write-Host "Target: ${PgHost}:${PgPort} (db=icu_scheduling)"

$migrations = Join-Path $root "migrations"
$psql = if (Test-Path "C:\Program Files\PostgreSQL\16\bin\psql.exe") {
    "C:\Program Files\PostgreSQL\16\bin\psql.exe"
} else { "psql" }
$env:PGPASSWORD = $PgPassword
Get-ChildItem (Join-Path $migrations "*.sql") | Sort-Object Name | ForEach-Object {
    Write-Host "Applying $($_.Name) ..."
    & $psql -h $PgHost -p $PgPort -U $PgUser -d icu_scheduling -f $_.FullName
}
Write-Host "Applied all migrations to icu_scheduling"
