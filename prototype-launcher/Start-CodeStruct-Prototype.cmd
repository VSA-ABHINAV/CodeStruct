@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-CodeStruct-Prototype.ps1"
set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% neq 0 (
    echo.
    echo ============================================================
    echo [ERROR] Launcher failed with exit code %EXIT_CODE%.
    echo Please check the error messages above or the logs/ folder.
    echo ============================================================
    pause
)
exit /b %EXIT_CODE%
