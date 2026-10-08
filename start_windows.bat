@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 -m ledgerbridge.server --local-demo
) else (
  python -m ledgerbridge.server --local-demo
)
pause
