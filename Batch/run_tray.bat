@echo off
title Turbo Download Manager - Background Tray
setlocal
set "VENV_PYW=%~dp0..\.venv\Scripts\pythonw.exe"
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
set "PY312_PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
set "PY312_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

cd /d "%~dp0..\Python"
if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" main.py --tray %*
) else if exist "%VENV_PY%" (
    start "" "%VENV_PY%" main.py --tray %*
) else if exist "%PY312_PYW%" (
    start "" "%PY312_PYW%" main.py --tray %*
) else if exist "%PY312_PY%" (
    start "" "%PY312_PY%" main.py --tray %*
) else (
    pyw -3.12 --version >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        start "" pyw -3.12 main.py --tray %*
    ) else (
        where pythonw >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            start "" pythonw main.py --tray %*
        ) else (
            start "" python main.py --tray %*
        )
    )
)
exit /b 0
