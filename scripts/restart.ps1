$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $projectRoot '.runtime\web.pid'
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    $recordedId = if (Test-Path -LiteralPath $pidPath) { [int](Get-Content -LiteralPath $pidPath -Raw).Trim() } else { 0 }
    if ($owner.CommandLine -notlike '*uvicorn app.main:app*' -or ($owner.ProcessId -ne $recordedId -and $owner.ParentProcessId -ne $recordedId)) {
        throw 'Port 8000 belongs to an unrecognized process; no process was stopped.'
    }
    Stop-Process -Id $owner.ProcessId
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 100
    }
}
& (Join-Path $PSScriptRoot 'launch.ps1')
