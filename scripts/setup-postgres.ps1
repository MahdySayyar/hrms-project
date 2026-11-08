param([ValidateSet('setup','start','stop','status')][string]$Action = 'setup')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pgBin = Join-Path $runtimeRoot 'postgresql\bin'
$dataPath = Join-Path $runtimeRoot 'pgdata'
$secretPath = Join-Path $runtimeRoot 'postgres-superuser.secret'
$logPath = Join-Path $runtimeRoot 'postgresql.log'

function Run-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Executable" }
}

if ($Action -eq 'setup') {
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install requirements first.' }
    New-Item -ItemType Directory -Path (Join-Path $runtimeRoot 'downloads') -Force | Out-Null
    Run-Checked $pythonExe @((Join-Path $PSScriptRoot 'configure_env.py'))
    if (-not (Test-Path -LiteralPath (Join-Path $pgBin 'initdb.exe'))) {
        $archive = Join-Path $runtimeRoot 'downloads\postgresql-17.6-1-windows-x64-binaries.zip'
        if (-not (Test-Path -LiteralPath $archive)) {
            $partialArchive = "$archive.partial"
            Run-Checked 'curl.exe' @('-L','--fail','--retry','2','--output',$partialArchive,'https://get.enterprisedb.com/postgresql/postgresql-17.6-1-windows-x64-binaries.zip')
            Move-Item -LiteralPath $partialArchive -Destination $archive
        }
        Run-Checked $pythonExe @((Join-Path $PSScriptRoot 'extract_postgres.py'))
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dataPath 'PG_VERSION'))) {
        if ((Test-Path -LiteralPath $dataPath) -and (Get-ChildItem -LiteralPath $dataPath -Force | Select-Object -First 1)) {
            throw 'pgdata is nonempty without PG_VERSION; inspect it before proceeding.'
        }
        if (-not (Test-Path -LiteralPath $secretPath)) {
            Run-Checked $pythonExe @('-c', "import pathlib,secrets,sys; pathlib.Path(sys.argv[1]).write_text(secrets.token_urlsafe(32), encoding='utf-8')", $secretPath)
        }
        Run-Checked (Join-Path $pgBin 'initdb.exe') @('-D',$dataPath,'-U','postgres',"--pwfile=$secretPath",'--encoding=UTF8','--locale=C','--auth=scram-sha-256')
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $dataPath 'PG_VERSION'))) { throw 'Run setup first.' }
$pgCtl = Join-Path $pgBin 'pg_ctl.exe'
& $pgCtl status -D $dataPath *> $null
$isRunning = $LASTEXITCODE -eq 0
if ($Action -eq 'stop') {
    if ($isRunning) { Run-Checked $pgCtl @('stop','-D',$dataPath,'-m','fast','-w') }
    else { Write-Output 'PostgreSQL is already stopped.' }
    exit 0
}
if ($Action -eq 'status') { if ($isRunning) { Write-Output 'PostgreSQL is running on 127.0.0.1:55432.' } else { Write-Output 'PostgreSQL is stopped.' }; exit 0 }
if (-not $isRunning) { Run-Checked $pgCtl @('start','-D',$dataPath,'-l',$logPath,'-o','-h 127.0.0.1 -p 55432','-w') }
if ($Action -eq 'setup') { Run-Checked $pythonExe @((Join-Path $PSScriptRoot 'create_database.py')) }
Write-Output 'Project-local PostgreSQL is ready on 127.0.0.1:55432.'
