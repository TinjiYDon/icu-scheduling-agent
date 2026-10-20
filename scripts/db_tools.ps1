# Shared PostgreSQL helpers for scripts/*.ps1 (dot-source this file).
# Prefers host client tools (psql / pg_dump / pg_restore); when they are absent it
# falls back to `docker exec` on the compose Postgres container (dumps/ -> /dumps).

$PgContainer = if ($env:PG_CONTAINER) { $env:PG_CONTAINER } else { "icu_scheduling_pg16" }
$PgBinDir = "C:\Program Files\PostgreSQL\16\bin"
if (-not $PgDatabase) { $PgDatabase = "icu_scheduling" }

function Resolve-PgPort {
    param([int]$Port = 0, [string]$Root = ".")

    if ($Port -gt 0) { return $Port }
    if ($env:PG_PORT) { return [int]$env:PG_PORT }

    $yaml = Join-Path $Root "configs\database.yaml"
    if (Test-Path $yaml) {
        $m = Select-String -Path $yaml -Pattern 'localhost:(\d+)' -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($m) { return [int]$m.Matches[0].Groups[1].Value }
    }
    return 5432
}

function Test-DbContainer {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $state = & docker inspect -f "{{.State.Running}}" $PgContainer 2>$null
        return ($LASTEXITCODE -eq 0 -and (($state | Out-String).Trim()) -eq "true")
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

function Get-PgTool {
    param([Parameter(Mandatory = $true)][string]$Name)

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return @{ Mode = "host"; Path = $cmd.Source } }

    $local = Join-Path $PgBinDir "$Name.exe"
    if (Test-Path $local) { return @{ Mode = "host"; Path = $local } }

    if (Test-DbContainer) { return @{ Mode = "docker"; Path = $null } }
    return $null
}

function Format-PgTarget {
    param([Parameter(Mandatory = $true)]$Tool, [string]$DbHost = "localhost", [int]$DbPort = 0)

    if ($Tool.Mode -eq "docker") { return "docker:$PgContainer" }
    return "$($Tool.Path) -> ${DbHost}:${DbPort}"
}

function Invoke-Native {
    # Runs a native command without letting stderr NOTICEs trip $ErrorActionPreference=Stop.
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @Arguments
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
}
