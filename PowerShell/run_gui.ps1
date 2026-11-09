$RootDir = Split-Path -Parent $PSScriptRoot
$VenvPyw = Join-Path $RootDir ".venv\Scripts\pythonw.exe"
$VenvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
$Py312Pyw = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\pythonw.exe"
$Py312Py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
$MainPy = Join-Path $RootDir "Python\main.py"

if (Test-Path $VenvPyw) {
    Start-Process -FilePath $VenvPyw -ArgumentList "$MainPy --gui $($args -join ' ')"
} elseif (Test-Path $VenvPy) {
    Start-Process -FilePath $VenvPy -ArgumentList "$MainPy --gui $($args -join ' ')" -WindowStyle Hidden
} elseif (Test-Path $Py312Pyw) {
    Start-Process -FilePath $Py312Pyw -ArgumentList "$MainPy --gui $($args -join ' ')"
} elseif (Test-Path $Py312Py) {
    Start-Process -FilePath $Py312Py -ArgumentList "$MainPy --gui $($args -join ' ')" -WindowStyle Hidden
} else {
    if (Get-Command pyw -ErrorAction SilentlyContinue) {
        Start-Process -FilePath "pyw" -ArgumentList "-3.12 $MainPy --gui $($args -join ' ')"
    } elseif (Get-Command pythonw -ErrorAction SilentlyContinue) {
        Start-Process -FilePath "pythonw" -ArgumentList "$MainPy --gui $($args -join ' ')"
    } else {
        Start-Process -FilePath "python" -ArgumentList "$MainPy --gui $($args -join ' ')" -WindowStyle Hidden
    }
}
