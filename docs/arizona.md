# Arizona coverage

UmbraStride targets **Arizona, USA** instead of a single Munich bbox.

## Why not one graph for the whole state?

Arizona is ~295,000 km². A single OSM pedestrian graph would be millions of edges and gigabytes on disk. Routing and shade precompute are done **per AOI** (area of interest).

## Coverage model

1. **Metro presets** — 10 urban areas including `az-phoenix-core` (small, fast) and `az-phoenix` (wide). Best for demos and routing.
2. **Grid tiles** — 0.25° cells over the state bbox (~460 tiles). For rural / statewide coverage, bootstrap tiles on demand.

Manifest: [`data/regions/arizona.json`](../data/regions/arizona.json)

## Bootstrap

**Linux / macOS**

```bash
python scripts/bootstrap_arizona.py --preset az-phoenix-core   # recommended
python scripts/bootstrap_arizona.py --preset all
python scripts/bootstrap_arizona.py --list-presets
python scripts/bootstrap_arizona.py --list-tiles
python scripts/bootstrap_arizona.py --tile az-tile--112.00_33.25
```

**Windows (PowerShell)** — activate `.venv` first

```powershell
python scripts/bootstrap_arizona.py --preset az-phoenix-core
python scripts/bootstrap_arizona.py --list-presets
```

## Shade cache

**Linux / macOS**

```bash
./scripts/seed_arizona.sh
python scripts/seed_demo_cache.py --aoi az-phoenix-core
```

**Windows (PowerShell)**

```powershell
.\scripts\seed_arizona.ps1 -Preset az-phoenix-core
.\scripts\seed_arizona.ps1 -AllMetros
python scripts/seed_demo_cache.py --aoi az-phoenix-core
```

## API

- `GET /v1/regions/arizona` — manifest + bootstrapped AOIs
- `GET /v1/regions/arizona/resolve?lng=&lat=` — pick metro for a point
- `POST /v1/route` — `aoi_id` optional; resolved from origin in Arizona

## Web defaults

- Map center: Phoenix (`33.448, -112.074`)
- Default AOI: `az-phoenix-core` (`VITE_DEFAULT_AOI` / `DEFAULT_AOI_ID`)
