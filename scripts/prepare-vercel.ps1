$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$destination = Join-Path $projectRoot 'backend/runtime-data'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
foreach ($filename in @('analysis.json', 'research.sqlite')) {
    Copy-Item -LiteralPath (Join-Path $projectRoot "artifacts/$filename") -Destination $destination -Force
}
Write-Host 'Prepared saved analysis and read-only database for Vercel. No training or API keys required.'
