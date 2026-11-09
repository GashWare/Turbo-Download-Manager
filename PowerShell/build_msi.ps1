# ==============================================================================
# Turbo Download Manager - Build MSI Installer (PowerShell)
# ==============================================================================

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   TURBO DOWNLOAD MANAGER - BUILD MSI INSTALLER       " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonDir = Join-Path $RootDir "Python"
$MsiDir = Join-Path $RootDir "MSI"
$VenvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
$Py312Py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"

if (Test-Path $VenvPy) {
    $PyBin = $VenvPy
} elseif (Test-Path $Py312Py) {
    $PyBin = $Py312Py
} else {
    $PyBin = "python"
}

Set-Location $PythonDir

# Ensure cx_Freeze is installed
Write-Host "[*] Checking cx_Freeze prerequisite using $PyBin..." -ForegroundColor Yellow
& "$PyBin" -m pip install cx_Freeze

Write-Host "[*] Compiling and packaging MSI installer..." -ForegroundColor Cyan
& "$PyBin" setup_msi.py bdist_msi

if ($LASTEXITCODE -eq 0) {
    if (-not (Test-Path $MsiDir)) {
        New-Item -ItemType Directory -Force -Path $MsiDir | Out-Null
    }
    Copy-Item "dist\*.msi" -Destination $MsiDir -Force
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host " [✓] MSI INSTALLER CREATED SUCCESSFULLY!              " -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "Location: $MsiDir" -ForegroundColor White
} else {
    Write-Host "[ERROR] Failed to build MSI installer." -ForegroundColor Red
}
