$ErrorActionPreference = 'Stop'
$hrmsRoot = Split-Path -Parent $PSScriptRoot
$hrmsCompose = Join-Path $hrmsRoot 'deployments/compose.yaml'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install and start Docker Desktop with Linux containers, then try again.'
}

docker compose -f $hrmsCompose --profile tools run --rm --no-deps init-secrets
if ($LASTEXITCODE -ne 0) { throw 'Docker secret initialization failed. Start Docker and check the error above.' }

docker compose -f $hrmsCompose up --build -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed. Check the error above.' }

$hrmsPort = if ($env:HRMS_HTTP_PORT) { $env:HRMS_HTTP_PORT } else { '8001' }
Write-Host "HRMS is ready: http://localhost:$hrmsPort/login"
Write-Host 'Username: hradmin'
Write-Host ('Password file: ' + (Join-Path $hrmsRoot '.runtime/docker-hrms-secrets/admin_password'))
