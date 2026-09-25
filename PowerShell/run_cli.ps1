$RootDir = Split-Path -Parent $PSScriptRoot
$VenvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
$MainPy = Join-Path $RootDir "Python\main.py"

if (Test-Path $VenvPy) {
    & $VenvPy $MainPy $args
} else {
    python $MainPy $args
}