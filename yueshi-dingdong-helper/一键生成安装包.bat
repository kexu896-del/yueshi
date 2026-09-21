@echo off
rem ============================================================
rem Yueshi Dingdong Helper - one-click installer builder
rem This window closes immediately; a progress WINDOW pops up
rem and shows the whole build with a progress bar.
rem ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on this computer.
    echo         Install Python 3.11+ from https://www.python.org
    echo         IMPORTANT: tick "Add python.exe to PATH" during setup,
    echo         then double-click this file again.
    echo.
    pause
    exit /b 1
)

start "" pythonw build\builder_ui.py
exit
