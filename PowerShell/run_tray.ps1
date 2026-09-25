$RootDir = Split-Path -Parent $PSScriptRoot
$VenvPyw = Join-Path $RootDir ".venv\Scripts\pythonw.exe"
$VenvPy = Join-Path $RootDir ".venv\Scripts\python.exe"
$MainPy = Join-Path $RootDir "Python\main.py"

if (Test-Path $VenvPyw) {
    Start-Process -FilePath $VenvPyw -ArgumentList "$MainPy --tray $($args -join ' ')"
} elseif (Test-Path $VenvPy) {
    Start-Process -FilePath $VenvPy -ArgumentList "$MainPy --tray $($args -join ' ')" -WindowStyle Hidden
} else {
    if (Get-Command pythonw -ErrorAction SilentlyContinue) {
        Start-Process -FilePath "pythonw" -ArgumentList "$MainPy --tray $($args -join ' ')"
    } else {
        Start-Process -FilePath "python" -ArgumentList "$MainPy --tray $($args -join ' ')" -WindowStyle Hidden
    }
}
