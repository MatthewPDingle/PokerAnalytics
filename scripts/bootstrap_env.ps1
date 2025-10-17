param(
    [string]$PythonBin = "python",
    [string]$VenvDir = ".venv"
)

if (!(Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment in $VenvDir"
    & $PythonBin -m venv $VenvDir
}

$activateScript = Join-Path $VenvDir "Scripts" "Activate.ps1"
. $activateScript

python -m pip install --upgrade pip
pip install -e ".[dev]"

Write-Host "Environment ready. Activate with: `n    . $activateScript"
