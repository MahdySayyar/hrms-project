# Launch locally through the Windows process-management service so the app can
# remain open after the chat's command runner closes. No startup task is created.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$workerPath = Join-Path $PSScriptRoot 'start-background.ps1'

try {
    $existingInstance = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/instance' -TimeoutSec 2
    if ($existingInstance.instance -eq 'hrms-local-1') {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3
        if ($health.status -eq 'ok') {
            Write-Output 'HRMS is already running: http://127.0.0.1:8000/login'
            exit 0
        }
    }
} catch { }
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8000 is occupied. Inspect the existing process before starting HRMS.'
}

$powerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$startupInfo = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
$launchResult = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = ('"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}"' -f $powerShellExe, $workerPath)
    CurrentDirectory = $projectRoot
    ProcessStartupInformation = $startupInfo
}
if ($launchResult.ReturnValue -ne 0) { throw "Windows could not launch HRMS (code $($launchResult.ReturnValue))." }
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
        if ($health.status -eq 'ok') {
            Write-Output 'HRMS is ready: http://127.0.0.1:8000/login'
            exit 0
        }
    } catch { }
    Start-Sleep -Milliseconds 500
}
throw 'HRMS did not become ready. Inspect artifacts\background-start.log and web.stderr.log.'
