@echo off
title Turbo Download Manager - Background Tray
setlocal
set "VENV_PYW=%~dp0..\.venv\Scripts\pythonw.exe"
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"

cd /d "%~dp0..\Python"
if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" main.py --tray %*
) else if exist "%VENV_PY%" (
    start "" "%VENV_PY%" main.py --tray %*
) else (
    where pythonw >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        start "" pythonw main.py --tray %*
    ) else (
        start "" python main.py --tray %*
    )
)
exit /b 0
