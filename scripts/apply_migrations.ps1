param(
    [string]$PgHost = "localhost",
    [int]$PgPort = 0,
    [string]$PgUser = "postgres",
    [string]$PgPassword = "postgres",
    [string]$Database = "icu_scheduling"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "db_tools.ps1")
$PgDatabase = $Database

$PgPort = Resolve-PgPort -Port $PgPort -Root $root
$psql = Get-PgTool -Name "psql"
if (-not $psql) {
    throw "psql not found (install PostgreSQL client tools) and container '$PgContainer' is not running. Try: docker compose -p icu_scheduling up -d"
}
Write-Host "Target: $(Format-PgTarget -Tool $psql -DbHost $PgHost -DbPort $PgPort) (db=$PgDatabase)"

$env:PGPASSWORD = $PgPassword
Get-ChildItem (Join-Path $root "migrations\*.sql") | Sort-Object Name | ForEach-Object {
    Write-Host "Applying $($_.Name) ..."
    if ($psql.Mode -eq "docker") {
        $tmp = "/tmp/$($_.Name)"
        $code = Invoke-Native -FilePath "docker" -Arguments @("cp", $_.FullName, "${PgContainer}:$tmp")
        if ($code -ne 0) { throw "docker cp failed: $($_.Name)" }
        $code = Invoke-Native -FilePath "docker" -Arguments @(
            "exec", "-e", "PGOPTIONS=-c client_min_messages=warning", $PgContainer,
            "psql", "-U", "postgres", "-d", $PgDatabase, "-v", "ON_ERROR_STOP=1", "-q", "-f", $tmp
        )
    }
    else {
        $code = Invoke-Native -FilePath $psql.Path -Arguments @(
            "-h", $PgHost, "-p", "$PgPort", "-U", $PgUser, "-d", $PgDatabase, "-v", "ON_ERROR_STOP=1", "-f", $_.FullName
        )
    }
    if ($code -ne 0) { throw "migration failed: $($_.Name) (exit $code)" }
}
Write-Host "Applied all migrations to $PgDatabase"
