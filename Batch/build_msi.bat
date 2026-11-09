@echo off
setlocal
title Turbo Download Manager - Build MSI Installer
echo ======================================================
echo    TURBO DOWNLOAD MANAGER - BUILD MSI INSTALLER
echo ======================================================
echo.

set "ROOT_DIR=%~dp0.."
set "PY312_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PY_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
) else if exist "%PY312_PY%" (
    set "PY_BIN=%PY312_PY%"
) else (
    set "PY_BIN=python"
)

cd /d "%ROOT_DIR%\Python"

:: Ensure cx_Freeze is installed
"%PY_BIN%" -m pip install cx_Freeze

echo [*] Compiling and generating Windows MSI Installer...
"%PY_BIN%" setup_msi.py bdist_msi

if %errorlevel% equ 0 (
    if not exist "%ROOT_DIR%\MSI" mkdir "%ROOT_DIR%\MSI"
    copy /y dist\*.msi "%ROOT_DIR%\MSI\" >nul
    echo.
    echo ======================================================
    echo  [✓] MSI INSTALLER CREATED SUCCESSFULLY!
    echo ======================================================
    echo Location: %ROOT_DIR%\MSI\
) else (
    echo [ERROR] Failed to compile MSI package.
)

pause
