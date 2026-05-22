# Bootstrap Arizona metro graph(s) and seed synthetic shade cache.
# Usage:
#   .\scripts\seed_arizona.ps1
#   .\scripts\seed_arizona.ps1 -Preset az-phoenix-core
#   .\scripts\seed_arizona.ps1 -AllMetros
param(
    [string]$Preset = "az-phoenix-core",
    [switch]$AllMetros
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

if ($AllMetros) {
    Write-Host "=== Arizona metro graphs (all presets) ==="
    python scripts/bootstrap_arizona.py --preset all
    $presets = @(
        "az-phoenix-core", "az-phoenix", "az-tucson", "az-flagstaff",
        "az-prescott", "az-yuma", "az-lake-havasu", "az-sedona",
        "az-nogales", "az-show-low"
    )
} else {
    Write-Host "=== Bootstrap $Preset ==="
    python scripts/bootstrap_arizona.py --preset $Preset
    $presets = @($Preset)
}

Write-Host "=== Shade cache (synthetic) ==="
foreach ($p in $presets) {
    $graph = "data\graphs\$p.graphml"
    if (Test-Path $graph) {
        Write-Host "Seeding $p..."
        python scripts/seed_demo_cache.py --aoi $p
    }
}

Write-Host "Done. Default AOI: az-phoenix-core. Start API + web (see docs/setup.md)."
