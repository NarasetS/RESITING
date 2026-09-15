@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_resiting.ps1"
if errorlevel 1 (
    echo.
    echo RESITING setup stopped with an error.
    echo Check the message above, then press any key to close.
    pause >nul
)
