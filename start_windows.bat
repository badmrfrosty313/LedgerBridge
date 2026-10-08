@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 -m ledgerbridge.server
) else (
  python -m ledgerbridge.server
)
pause
