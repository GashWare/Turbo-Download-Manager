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

Set-Location $PythonDir

# Ensure cx_Freeze is installed
Write-Host "[*] Checking cx_Freeze prerequisite..." -ForegroundColor Yellow
python -m pip install cx_Freeze

Write-Host "[*] Compiling and packaging MSI installer..." -ForegroundColor Cyan
python setup_msi.py bdist_msi

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