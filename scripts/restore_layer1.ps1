# Restore Layer1 dump into icu_scheduling
# Usage: .\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-full_*.dump
# Runs as a superuser (-PgUser, default postgres); the dump's GRANTs give icu_dev access.
# Falls back to `docker exec` when host pg_restore is not installed.
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,
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
if (-not (Test-Path $DumpFile)) { throw "Dump not found: $DumpFile" }

$pgRestore = Get-PgTool -Name "pg_restore"
if (-not $pgRestore) {
    throw "pg_restore not found (install PostgreSQL client tools) and container '$PgContainer' is not running. Try: docker compose -p icu_scheduling up -d"
}
Write-Host "Restoring $DumpFile -> $PgDatabase on $(Format-PgTarget -Tool $pgRestore -DbHost $PgHost -DbPort $PgPort)"

$env:PGPASSWORD = $PgPassword
if ($pgRestore.Mode -eq "docker") {
    # dumps/ is bind-mounted at /dumps; other paths are copied into the container.
    $resolved = (Resolve-Path $DumpFile).Path
    $dumpsDir = (Join-Path $root "dumps")
    if ($resolved.StartsWith($dumpsDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        $rel = $resolved.Substring($dumpsDir.Length).TrimStart([char[]]@('\', '/')).Replace('\', '/')
        $containerPath = "/dumps/$rel"
    }
    else {
        $containerPath = "/tmp/restore.dump"
        $copyCode = Invoke-Native -FilePath "docker" -Arguments @("cp", $resolved, "${PgContainer}:$containerPath")
        if ($copyCode -ne 0) { throw "docker cp failed: $resolved" }
    }
    $code = Invoke-Native -FilePath "docker" -Arguments @(
        "exec", "-e", "PGOPTIONS=-c client_min_messages=warning", $PgContainer,
        "pg_restore", "-U", "postgres", "-d", $PgDatabase, "--clean", "--if-exists", "--no-owner", $containerPath
    )
}
else {
    $code = Invoke-Native -FilePath $pgRestore.Path -Arguments @(
        "-h", $PgHost, "-p", "$PgPort", "-U", $PgUser, "-d", $PgDatabase, "--clean", "--if-exists", "--no-owner", $DumpFile
    )
}
if ($code -ne 0) { throw "pg_restore failed (exit $code)" }

Write-Host "OK. Ensure configs/data.yaml has source: mimic"
Write-Host "Connection: icu_dev/icu_dev @ ${PgHost}:${PgPort}/$PgDatabase"
