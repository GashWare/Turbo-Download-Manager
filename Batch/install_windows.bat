@echo off
setlocal enabledelayedexpansion
title Turbo Download Manager - Windows Installer

echo ======================================================
echo       TURBO DOWNLOAD MANAGER - WINDOWS INSTALLER
echo ======================================================
echo.

set "ROOT_DIR=%~dp0.."
set "VENV_DIR=%ROOT_DIR%\.venv"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is not found on your system PATH.
    echo [*] Attempting to install Python via Windows Package Manager (winget)...
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo [ERROR] Winget install failed or winget is not installed.
        echo Please install Python 3 manually from https://www.python.org/downloads/
        echo Make sure to check 'Add Python to PATH' during installation.
        pause
        exit /b 1
    )
    echo [✓] Python installed! Please restart this installer if path is not immediately refreshed.
)

:: Verify python again
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python is still not recognized. Please reopen this script or add Python to PATH.
    pause
    exit /b 1
)

:: Create Virtual Environment
echo.
echo [*] Creating isolated Python Virtual Environment at %VENV_DIR%...
if not exist "%VENV_DIR%" (
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [!] Failed to create venv. Using system Python directly.
    )
)

:: Choose Python & Pip executable
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PY_EXE=%VENV_DIR%\Scripts\python.exe"
    set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
) else (
    set "PY_EXE=python"
    set "PIP_EXE=pip"
)

:: Upgrade pip and install requirements
echo [*] Installing dependencies from Python\requirements.txt...
"%PIP_EXE%" install --upgrade pip
"%PIP_EXE%" install -r "%ROOT_DIR%\Python\requirements.txt"

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install some Python dependencies.
    pause
    exit /b 1
)

:: Create Desktop Shortcut (Optional VBScript)
set "SHORTCUT_SCRIPT=%TEMP%\create_shortcut.vbs"
set "DESKTOP_PATH=%USERPROFILE%\Desktop\Turbo Download Manager.lnk"
set "TARGET_PATH=%ROOT_DIR%\Batch\run_gui.bat"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%SHORTCUT_SCRIPT%"
echo sLinkFile = "%DESKTOP_PATH%" >> "%SHORTCUT_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%SHORTCUT_SCRIPT%"
echo oLink.TargetPath = "%TARGET_PATH%" >> "%SHORTCUT_SCRIPT%"
echo oLink.WorkingDirectory = "%ROOT_DIR%\Batch" >> "%SHORTCUT_SCRIPT%"
echo oLink.IconLocation = "%ROOT_DIR%\Python\gui\assets\app_icon.ico" >> "%SHORTCUT_SCRIPT%"
echo oLink.Description = "Turbo Download Manager" >> "%SHORTCUT_SCRIPT%"
echo oLink.Save >> "%SHORTCUT_SCRIPT%"
cscript //nologo "%SHORTCUT_SCRIPT%" >nul 2>&1

echo.
echo ======================================================
echo    TURBO DOWNLOAD MANAGER INSTALLED SUCCESSFULLY!
echo ======================================================
echo.
echo A desktop shortcut has been created: "%DESKTOP_PATH%"
echo You can also start the application using:
echo   - GUI: Batch\run_gui.bat
echo   - CLI: Batch\run_cli.bat add ^<URL^>
echo.
pause