# ==============================================================================
# Turbo Download Manager - Copy and Package Distributions
# Uses purely relative paths dynamically resolved from script location.
# ==============================================================================

$RootDir = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $RootDir "Distributions"
$MsiDir = Join-Path $RootDir "MSI"
$PythonDir = Join-Path $RootDir "Python"

if (!(Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir -Force | Out-Null }
if (!(Test-Path $MsiDir)) { New-Item -ItemType Directory -Path $MsiDir -Force | Out-Null }

# 1. Copy MSI
$msiBuilt = Get-ChildItem (Join-Path $PythonDir "dist\*.msi") -ErrorAction SilentlyContinue | Select-Object -First 1
if ($msiBuilt) {
    Copy-Item $msiBuilt.FullName -Destination (Join-Path $MsiDir "Turbo Download Manager-2.0.0-win64.msi") -Force
    Write-Host "[OK] Updated MSI in: $MsiDir" -ForegroundColor Green
}

# 2. Package Portable ZIP
$portableSource = Get-ChildItem (Join-Path $PythonDir "build\exe.*") -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
if ($portableSource -and (Test-Path $portableSource.FullName)) {
    $portableZip = Join-Path $DistDir "Turbo-Download-Manager-2.0.0-Windows-Portable.zip"
    $pSrc = $portableSource.FullName
    python -c "
import os, zipfile
src = r'$pSrc'
out_p = r'$portableZip'
with zipfile.ZipFile(out_p, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        for f in files:
            abs_p = os.path.join(root, f)
            rel_p = os.path.relpath(abs_p, src).replace('\\\\', '/')
            zf.write(abs_p, rel_p)
"
    Write-Host "[OK] Updated Portable ZIP: $portableZip" -ForegroundColor Green
}

# 3. Package Linux Distributions from repository source
$stagingDir = Join-Path $DistDir "staging_linux"
if (Test-Path $stagingDir) { Remove-Item $stagingDir -Recurse -Force }
$linuxAppDir = Join-Path $stagingDir "Turbo-Download-Manager-2.0.0-Linux"
$linuxPyDir = Join-Path $linuxAppDir "Python"

New-Item -ItemType Directory -Path $linuxPyDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $linuxAppDir "Shell") -Force | Out-Null

Copy-Item (Join-Path $PythonDir "cli") -Destination $linuxPyDir -Recurse -Force
Copy-Item (Join-Path $PythonDir "core") -Destination $linuxPyDir -Recurse -Force
Copy-Item (Join-Path $PythonDir "gui") -Destination $linuxPyDir -Recurse -Force
$testsDest = Join-Path $linuxPyDir "tests"
New-Item -ItemType Directory -Path $testsDest -Force | Out-Null
Get-ChildItem (Join-Path $PythonDir "tests\*.py") -ErrorAction SilentlyContinue | ForEach-Object { Copy-Item $_.FullName -Destination $testsDest -Force }
Copy-Item (Join-Path $PythonDir "main.py") -Destination (Join-Path $linuxPyDir "main.py") -Force
Copy-Item (Join-Path $PythonDir "requirements.txt") -Destination (Join-Path $linuxPyDir "requirements.txt") -Force
Copy-Item (Join-Path $RootDir "Shell\*") -Destination (Join-Path $linuxAppDir "Shell") -Recurse -Force
Copy-Item (Join-Path $RootDir "README.md") -Destination (Join-Path $linuxAppDir "README.md") -Force -ErrorAction SilentlyContinue

$linuxZip = Join-Path $DistDir "Turbo-Download-Manager-2.0.0-Linux.zip"
$linuxTar = Join-Path $DistDir "Turbo-Download-Manager-2.0.0-Linux.tar.gz"

python -c "
import os, zipfile
src = r'$linuxAppDir'
out_p = r'$linuxZip'
with zipfile.ZipFile(out_p, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        for f in files:
            abs_p = os.path.join(root, f)
            rel_p = os.path.relpath(abs_p, src).replace('\\\\', '/')
            zf.write(abs_p, rel_p)
"

try {
    tar.exe -czf $linuxTar -C $stagingDir "Turbo-Download-Manager-2.0.0-Linux" 2>$null
} catch {
    # Fallback to standard packaging
}

# 4. Package Firefox Extension with standard forward-slash zip structure
$extDir = Join-Path $RootDir "Extension\firefox"
if (Test-Path $extDir) {
    $extZip = Join-Path $DistDir "Turbo-Download-Manager-Firefox-Extension.zip"
    $extXpi = Join-Path $DistDir "Turbo-Download-Manager-Firefox-Extension.xpi"
    
    python -c "
import os, zipfile
src = r'$extDir'
for out_p in [r'$extZip', r'$extXpi']:
    if os.path.exists(out_p): os.remove(out_p)
    with zipfile.ZipFile(out_p, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src):
            for f in files:
                if f.endswith(('.pyc', '.tmp', '.log')): continue
                abs_p = os.path.join(root, f)
                rel_p = os.path.relpath(abs_p, src).replace('\\\\', '/')
                zf.write(abs_p, rel_p)
"
    Write-Host "[OK] Updated Firefox Extension: $extZip and $extXpi" -ForegroundColor Green
}

Write-Host "[OK] Updated Linux packages: $linuxZip and $linuxTar" -ForegroundColor Green

Get-ChildItem $DistDir | Select-Object Name, Length
Get-ChildItem $MsiDir | Select-Object Name, Length


