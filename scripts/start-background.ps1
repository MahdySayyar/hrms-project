# This worker is launched outside the chat command's temporary process tree.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Path (Join-Path $projectRoot 'artifacts') -Force | Out-Null
& (Join-Path $PSScriptRoot 'setup-postgres.ps1') -Action start
if ($LASTEXITCODE -ne 0) { throw 'Could not start the project database.' }
$webProcess = Start-Process -FilePath (Join-Path $projectRoot '.venv\Scripts\python.exe') -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'artifacts\web.stdout.log') -RedirectStandardError (Join-Path $projectRoot 'artifacts\web.stderr.log') -PassThru
$webProcess.Id | Set-Content -LiteralPath (Join-Path $projectRoot '.runtime\web.pid') -Encoding ascii
$webProcess.WaitForExit()
if ($webProcess.ExitCode -ne 0) { throw 'Web process exited; inspect artifacts\web.stderr.log.' }
