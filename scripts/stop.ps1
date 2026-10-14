$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$statePath = Join-Path $projectRoot '.runtime\processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Host 'No saved service processes.'; exit 0 }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($processId in @($state.backend, $state.frontend)) {
    $serviceProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    if ($serviceProcess) {
        $expected = (($serviceProcess.CommandLine -like '*uvicorn backend.main:app*') -and ($serviceProcess.ExecutablePath -eq (Join-Path $projectRoot '.venv\Scripts\python.exe'))) -or ($serviceProcess.CommandLine -like ('*' + $projectRoot + '*node_modules*next*'))
        if (-not $expected) { throw "Process $processId does not match a project service; refusing to stop it." }
        Stop-Process -Id $processId -Force
        Write-Host "Stopped service process $processId"
    }
}
Remove-Item -LiteralPath $statePath
