# ==============================================================================
# Turbo Download Manager - Windows PowerShell Installer & Bootloader
# ==============================================================================

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "      TURBO DOWNLOAD MANAGER - WINDOWS INSTALLER      " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RootDir ".venv"
$ReqFile = Join-Path $RootDir "Python\requirements.txt"

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[!] Python not found in system PATH. Attempting automated install via winget..." -ForegroundColor Yellow
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetCmd) {
        winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Host "[ERROR] Winget is not available. Please install Python from https://python.org" -ForegroundColor Red
        Exit 1
    }
}

$pyVer = python --version 2>&1
Write-Host "[*] Detected $pyVer" -ForegroundColor Green

# 2. Setup Virtual Environment
Write-Host "[*] Configuring Virtual Environment at $VenvDir..." -ForegroundColor Cyan
if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
}

$venvPython = Join-Path $VenvDir "Scripts\python.exe"
$venvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (Test-Path $venvPip) {
    Write-Host "[*] Upgrading pip and installing dependencies..." -ForegroundColor Cyan
    & $venvPip install --upgrade pip
    & $venvPip install -r $ReqFile
} else {
    Write-Host "[!] Using system pip fallback..." -ForegroundColor Yellow
    pip install -r $ReqFile
}

# 3. Create Desktop Shortcut
$desktopPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "Turbo Download Manager.lnk")
$targetPath = Join-Path $RootDir "PowerShell\run_gui.ps1"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($desktopPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$targetPath`""
$Shortcut.WorkingDirectory = $RootDir
$Shortcut.IconLocation = Join-Path $RootDir "Python\gui\assets\app_icon.ico"
$Shortcut.Description = "Turbo Download Manager"
$Shortcut.Save()

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "   TURBO DOWNLOAD MANAGER INSTALLED SUCCESSFULLY!     " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "Shortcut created on Desktop: $desktopPath" -ForegroundColor White
Write-Host "Launch with PowerShell\run_gui.ps1 or Batch\run_gui.bat" -ForegroundColor White