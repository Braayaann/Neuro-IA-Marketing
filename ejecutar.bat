@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno virtual. Consulta README.md para instalarlo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
