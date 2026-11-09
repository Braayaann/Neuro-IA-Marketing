param([string]$Python = '.\.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Falta el entorno de Python. Sigue la preparación en docs/APLICACION_WEB.md.'
}
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
    throw 'Falta compilar React. Ejecuta preparar_web.ps1.'
}
Write-Host 'Iniciando PostgreSQL local...'
& $Python -B -u scripts/postgres_local.py start
if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar PostgreSQL.' }
Write-Host 'Iniciando el portal web...'
& $Python -B -u servidor.py
if ($LASTEXITCODE -ne 0) { throw 'El servidor web terminó con un error.' }
