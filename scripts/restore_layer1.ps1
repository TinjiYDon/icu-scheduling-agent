# Restore Layer1 dump into icu_scheduling
# Usage: .\restore_layer1.ps1 -DumpFile .\dumps\icu_scheduling_P0-etl_*.dump
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$PgPassword = "postgres",
    [string]$Database = "icu_scheduling",
    [string]$AppRole = "icu_dev",
    [bool]$RecreateDb = $true
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $DumpFile)) { throw "Dump not found: $DumpFile" }

$pgBin = "C:\Program Files\PostgreSQL\16\bin"
$pgRestore = if (Test-Path "$pgBin\pg_restore.exe") { "$pgBin\pg_restore.exe" } else { "pg_restore" }
$psql = if (Test-Path "$pgBin\psql.exe") { "$pgBin\psql.exe" } else { "psql" }
$dropdb = if (Test-Path "$pgBin\dropdb.exe") { "$pgBin\dropdb.exe" } else { "dropdb" }
$createdb = if (Test-Path "$pgBin\createdb.exe") { "$pgBin\createdb.exe" } else { "createdb" }

$env:PGPASSWORD = $PgPassword

function Invoke-PsqlFile {
    param([string]$Db, [string]$Sql)
    $tmp = [System.IO.Path]::GetTempFileName() + ".sql"
    try {
        Set-Content -Path $tmp -Value $Sql -Encoding UTF8
        & $psql -h $PgHost -p $PgPort -U $PgUser -d $Db -v ON_ERROR_STOP=1 -f $tmp
        if ($LASTEXITCODE -ne 0) { throw "psql failed on $Db (exit $LASTEXITCODE)" }
    }
    finally {
        Remove-Item -Force $tmp -ErrorAction SilentlyContinue
    }
}

if ($RecreateDb) {
    Write-Host "Recreating database $Database (terminate sessions + drop + create)..."
    $termSql = @"
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$Database' AND pid <> pg_backend_pid();
"@
    Invoke-PsqlFile -Db "postgres" -Sql $termSql
    & $dropdb -h $PgHost -p $PgPort -U $PgUser --if-exists $Database
    & $createdb -h $PgHost -p $PgPort -U $PgUser -O $PgUser $Database
    $roleSql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$AppRole') THEN
    CREATE ROLE $AppRole LOGIN PASSWORD 'icu_dev';
  END IF;
END
`$`$;
ALTER ROLE $AppRole WITH LOGIN PASSWORD 'icu_dev';
GRANT CONNECT ON DATABASE $Database TO $AppRole;
GRANT CREATE ON DATABASE $Database TO $AppRole;
"@
    Invoke-PsqlFile -Db $Database -Sql $roleSql
}

Write-Host "Restoring $DumpFile -> $Database on ${PgHost}:${PgPort} as $PgUser"
# Own objects as postgres, then grant to app role (avoids owner fights with --role=icu_dev).
& $pgRestore -h $PgHost -p $PgPort -U $PgUser -d $Database --clean --if-exists --no-owner --no-acl $DumpFile
$restoreCode = $LASTEXITCODE
if ($restoreCode -ne 0) {
    Write-Warning "pg_restore exit code $restoreCode (some warnings may be OK); checking row counts..."
}

$grantSql = @"
GRANT USAGE ON SCHEMA staging, feat, sched, sim, mock, app TO $AppRole;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA staging, feat, sched, sim, mock, app TO $AppRole;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA staging, feat, sched, sim, mock, app TO $AppRole;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging, feat, sched, sim, mock, app
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $AppRole;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging, feat, sched, sim, mock, app
  GRANT USAGE, SELECT ON SEQUENCES TO $AppRole;
SELECT
  (SELECT COUNT(*) FROM staging.icustays) AS stays,
  (SELECT COUNT(*) FROM feat.sofa_timeseries) AS sofa;
"@
Invoke-PsqlFile -Db $Database -Sql $grantSql

Write-Host "OK. Ensure configs use DATABASE_URL with ${AppRole}@$Database"
Write-Host "Connection: ${AppRole}/icu_dev @ ${PgHost}:${PgPort}/$Database"
