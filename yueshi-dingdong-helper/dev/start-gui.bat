@echo off
chcp 65001 >nul
rem Yueshi Dingdong helper - GUI launcher (dev mode).
rem Prefer start-gui.vbs (fully silent, no console flash at all).
rem Build venv lives in %LOCALAPPDATA%\YueshiDingdongHelper\build-venv.
cd /d %~dp0..
set "VENVPY=%LOCALAPPDATA%\YueshiDingdongHelper\build-venv\Scripts\pythonw.exe"
if exist "%VENVPY%" (
    start "" "%VENVPY%" src\gui.py
) else (
    start "" pythonw src\gui.py
)
