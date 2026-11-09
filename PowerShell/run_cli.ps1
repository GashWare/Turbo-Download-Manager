$RootDir = Split-Path -Parent $PSScriptRoot
$VenvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
$Py312Py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
$MainPy = Join-Path $RootDir "Python\main.py"

if (Test-Path $VenvPy) {
    & "$VenvPy" "$MainPy" @args
} elseif (Test-Path $Py312Py) {
    & "$Py312Py" "$MainPy" @args
} else {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & "py" "-3.12" "$MainPy" @args
    } else {
        & "python" "$MainPy" @args
    }
}
