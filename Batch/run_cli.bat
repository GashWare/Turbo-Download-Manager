@echo off
title Turbo Download Manager - CLI
setlocal
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
set "PY312_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

cd /d "%~dp0..\Python"
if exist "%VENV_PY%" (
    "%VENV_PY%" main.py %*
) else if exist "%PY312_PY%" (
    "%PY312_PY%" main.py %*
) else (
    py -3.12 --version >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        py -3.12 main.py %*
    ) else (
        python main.py %*
    )
)
exit /b %ERRORLEVEL%
