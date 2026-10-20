# Export Layer1 database icu_scheduling to dumps/ (do not commit dumps to GitHub)
# Usage: .\export_layer1.ps1 [-SchemasOnly] [-MimicSource mimic]
param(
    [switch]$SchemasOnly,
    [string]$OutDir = "",
    [string]$PgHost = "localhost",
    [int]$PgPort = 0,
    [string]$PgUser = "postgres",
    [string]$PgPassword = "postgres",
    [string]$MimicSource = "mimic",
    [string]$Phase = "P0",
    [string]$Database = "icu_scheduling"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "db_tools.ps1")
$PgDatabase = $Database

$PgPort = Resolve-PgPort -Port $PgPort -Root $root
$dumpsDir = Join-Path $root "dumps"
if (-not $OutDir) { $OutDir = $dumpsDir }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Schemas = @("staging", "feat", "sim", "sched", "app")

$pgDump = Get-PgTool -Name "pg_dump"
if (-not $pgDump) {
    throw "pg_dump not found (install PostgreSQL client tools) and container '$PgContainer' is not running. Try: docker compose -p icu_scheduling up -d"
}
$psql = Get-PgTool -Name "psql"

Write-Host "Target: $(Format-PgTarget -Tool $pgDump -DbHost $PgHost -DbPort $PgPort) (db=$PgDatabase)"
$env:PGPASSWORD = $PgPassword
$dateTag = Get-Date -Format "yyyyMMdd"
$version = Get-Date -Format "yyyyMMdd_HHmm"

$stayCount = 0
if ($psql) {
    if ($psql.Mode -eq "docker") {
        $n = & docker exec $PgContainer psql -U postgres -d $PgDatabase -t -A -c "SELECT COUNT(*) FROM staging.icustays;" 2>$null
    }
    else {
        $n = & $psql.Path -h $PgHost -p $PgPort -U $PgUser -d $PgDatabase -t -A -c "SELECT COUNT(*) FROM staging.icustays;" 2>$null
    }
    if ($LASTEXITCODE -eq 0 -and $n) { $stayCount = [int](($n | Out-String).Trim()) }
}

$kind = if ($SchemasOnly) { "etl" } else { "full" }
if ($stayCount -le 0 -and $SchemasOnly) { $kind = "schema-only" }
$fileName = "${PgDatabase}_${Phase}-${kind}_${MimicSource}_${stayCount}stays_${dateTag}.dump"
$out = Join-Path $OutDir $fileName

Write-Host "Exporting $PgDatabase -> $out"
if ($pgDump.Mode -eq "docker") {
    # Write inside the bind-mounted /dumps first, then move if a custom OutDir was given.
    $containerOut = "/dumps/$fileName"
    $pgArgs = @("exec", "-e", "PGOPTIONS=-c client_min_messages=warning", $PgContainer, "pg_dump", "-U", "postgres", "-Fc", "-f", $containerOut)
    if ($SchemasOnly) { foreach ($s in $Schemas) { $pgArgs += @("-n", $s) } }
    $pgArgs += $PgDatabase
    $code = Invoke-Native -FilePath "docker" -Arguments $pgArgs
    if ($code -ne 0) { throw "pg_dump failed for $PgDatabase (exit $code)" }
    $produced = Join-Path $dumpsDir $fileName
    if ((Resolve-Path $OutDir).Path -ne (Resolve-Path $dumpsDir).Path) {
        Move-Item $produced $out -Force
    }
}
else {
    $pgArgs = @("-h", $PgHost, "-p", "$PgPort", "-U", $PgUser, "-Fc", "-f", $out)
    if ($SchemasOnly) { foreach ($s in $Schemas) { $pgArgs += @("-n", $s) } }
    $pgArgs += $PgDatabase
    $code = Invoke-Native -FilePath $pgDump.Path -Arguments $pgArgs
    if ($code -ne 0) { throw "pg_dump failed for $PgDatabase (exit $code)" }
}

$meta = @{
    version      = $version
    database     = $PgDatabase
    phase        = $Phase
    mimic_source = $MimicSource
    stay_count   = $stayCount
    schemas_only = [bool]$SchemasOnly
    exported_at  = (Get-Date).ToString("o")
    file         = $out
}
$metaPath = Join-Path $OutDir "DATA_VERSION_${version}.json"
$meta | ConvertTo-Json -Depth 4 | Set-Content -Path $metaPath -Encoding UTF8

Write-Host ""
Write-Host "Done. Share dump offline if needed (not via GitHub):"
Write-Host "  $out"
Write-Host "  $metaPath"
