@echo off
title Turbo Download Manager - CLI
setlocal
set "VENV_PY=%~dp0..\.venv\Scripts\python.exe"
cd /d "%~dp0..\Python"
if exist "%VENV_PY%" (
    "%VENV_PY%" main.py %*
) else (
    python main.py %*
)