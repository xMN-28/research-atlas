$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 and its Windows launcher first.' }
    }
    & .venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Push-Location frontend
    try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } }
    finally { Pop-Location }
    Write-Host 'Dependencies installed. Existing models can be used without retraining.'
    Write-Host 'Launch: powershell -ExecutionPolicy Bypass -File scripts\start.ps1'
} finally { Pop-Location }
