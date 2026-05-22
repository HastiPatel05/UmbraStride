# Bootstrap one AOI and seed shade cache (legacy helper).
# Usage: .\scripts\seed_demo.ps1
#        .\scripts\seed_demo.ps1 -Preset az-phoenix-core
param(
    [string]$Preset = "az-phoenix-core"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

$graph = "data\graphs\$Preset.graphml"
if (-not (Test-Path $graph)) {
    Write-Host "Bootstrapping $Preset..."
    python scripts/bootstrap_arizona.py --preset $Preset
}

Write-Host "Seeding shade cache for $Preset..."
python scripts/seed_demo_cache.py --aoi $Preset
Write-Host "Done."
