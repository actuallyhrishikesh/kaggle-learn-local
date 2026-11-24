# Create .venv and install everything needed to run the courses (Windows PowerShell).
# Usage: .\scripts\setup.ps1 [extra ...]   extras: sql deep-learning geospatial explainability data-cleaning game-ai legacy all
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$py = $env:PYTHON
if (-not $py) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py -3.11" } else { $py = "python" }
}
Write-Host "Using $py"
if (-not (Test-Path .venv)) { Invoke-Expression "$py -m venv .venv" }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt
& .\.venv\Scripts\pip.exe install --no-build-isolation "git+https://github.com/Kaggle/learntools.git"
foreach ($extra in $args) {
    $f = "requirements\$extra.txt"
    if (-not (Test-Path $f)) { throw "Unknown extra '$extra' (see requirements\)" }
    & .\.venv\Scripts\pip.exe install -r $f
}
Write-Host ""
Write-Host "Done. Next:"
Write-Host "  .venv\Scripts\activate"
Write-Host "  python scripts\download_data.py --list"
Write-Host "  jupyter lab"
