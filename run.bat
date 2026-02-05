@echo off
mode con: cols=148 lines=46
chcp 65001
cd /d "%~dp0"
set "WORK_DIR=%CD%"

:: 1. Check if Windows Terminal (wt.exe) is installed
where wt >nul 2>nul
if %errorlevel%==0 (
    :: Launch WT with PowerShell executing our helper script
    start "" wt -d "%WORK_DIR%" powershell -ExecutionPolicy Bypass -File "launch.ps1"
    exit
)

:: 2. Fallback: Standard PowerShell
echo [INFO] Launching in PowerShell...
:: Run directly in this window
powershell -ExecutionPolicy Bypass -File "launch.ps1"
if %errorlevel% neq 0 (
    echo [ERROR] PowerShell script failed.
    pause
)
:: Final pause removed to allow auto-close on success