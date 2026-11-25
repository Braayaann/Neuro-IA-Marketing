param([string]$Python = '.\.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) { throw 'Primero crea .venv con Python 3.12 o pasa -Python con la ruta de tu intérprete.' }
function Run-Python { & $Python @args; if ($LASTEXITCODE -ne 0) { throw 'Falló un paso de preparación.' } }
Run-Python -m pip install -r backend/requirements.txt
Run-Python scripts/postgres_local.py install
Run-Python scripts/postgres_local.py start
Run-Python -m alembic upgrade head
Run-Python scripts/crear_acceso_local.py
if (Get-Command npm.cmd -ErrorAction SilentlyContinue) {
    Push-Location frontend
    try { npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'Falló npm ci.' }; npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Falló el build.' } } finally { Pop-Location }
} elseif (Test-Path '.tools/npm/package/bin/npm-cli.js') {
    node .tools/npm/package/bin/npm-cli.js ci --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'Falló npm ci.' }
    node .tools/npm/package/bin/npm-cli.js run build --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'Falló el build.' }
} else { throw 'Instala Node.js LTS (incluye npm) y vuelve a ejecutar este script.' }
Write-Host 'Listo. Revisa .local/acceso-inicial.txt y ejecuta .\iniciar_web.ps1'
