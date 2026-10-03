@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop-CodeStruct-Prototype.ps1"
set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% neq 0 (
    echo.
    echo ============================================================
    echo [ERROR] Stop script failed with exit code %EXIT_CODE%.
    echo ============================================================
    pause
)
exit /b %EXIT_CODE%
