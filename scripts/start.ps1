param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendPath = Join-Path $projectRoot 'frontend'
$runtimePath = Join-Path $projectRoot '.runtime'
$nodePath = (Get-Command node -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts\setup.ps1 first.' }
foreach ($servicePort in @(8000, 3000)) {
    if (Get-NetTCPConnection -LocalPort $servicePort -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $servicePort is already in use. Stop the existing server or use scripts\stop.ps1 before launching."
    }
}
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'artifacts\analysis.json'))) {
        & $pythonPath train.py
        if ($LASTEXITCODE -ne 0) { throw 'Training failed.' }
    }
    if ($Rebuild -or -not (Test-Path -LiteralPath (Join-Path $frontendPath '.next\BUILD_ID'))) {
        Push-Location $frontendPath
        try { & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
        finally { Pop-Location }
    }
    New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'backend.log') -RedirectStandardError (Join-Path $runtimePath 'backend.error.log')
    $nextEntry = Join-Path $frontendPath 'node_modules\next\dist\bin\next'
    $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $nextEntry + '"'),'start','--hostname','127.0.0.1','--port','3000') -WorkingDirectory $frontendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'frontend.log') -RedirectStandardError (Join-Path $runtimePath 'frontend.error.log')
    @{ backend = $backendProcess.Id; frontend = $frontendProcess.Id; project = $projectRoot } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimePath 'processes.json') -Encoding UTF8
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
            $response = Invoke-WebRequest 'http://127.0.0.1:3000' -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ready' -and $response.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        $backendProcess.Refresh(); $frontendProcess.Refresh()
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) { break }
    }
    if (-not $ready) { throw "A service failed to become ready. Inspect logs in $runtimePath; run scripts\stop.ps1 before retrying." }
    Write-Host 'Research Atlas is running at http://127.0.0.1:3000'
    Write-Host 'API documentation: http://127.0.0.1:8000/docs'
    Write-Host 'Stop with: powershell -ExecutionPolicy Bypass -File scripts\stop.ps1'
} finally { Pop-Location }
