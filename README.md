# UmbraStride

Shadow-oriented pedestrian navigation inspired by [*Walking in the Shade: Shadow-oriented Navigation for Pedestrians*](https://doi.org/10.1145/3678717.3691287) (Feng et al., SIGSPATIAL 2024).

UmbraStride builds a walkable street graph from OpenStreetMap, estimates edge shade using [ShadeMap](https://shademap.app/about/), and routes with Dijkstra while balancing **cooler (shadier)** vs **shorter** paths via a preference slider.

## Architecture

- **geo-core** — OSMnx pedestrian graphs, GraphML export, GeoJSON overrides
- **routing-core** — Alpha-weighted Dijkstra, route metrics
- **shade-engine** — Edge point sampling, cache keys, SQLite schema
- **shade-worker** — Headless ShadeMap batch profiling (Playwright)
- **api** — FastAPI REST (`/v1/route`, `/v1/graph`, `/v1/cache/warm`)
- **web** — React + MapLibre + ShadeMap overlay

## Quick start

**Full setup for Linux, macOS, and Windows:** [docs/setup.md](docs/setup.md)

### Prerequisites

- Python 3.11+
- Node.js 20+
- ShadeMap API key ([get one](https://shademap.app/about/))

### Setup (Linux / macOS)

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env
# Edit .env — SHADEMAP_API_KEY, DEFAULT_AOI_ID=az-phoenix-core

python3 -m venv .venv
source .venv/bin/activate
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"
npm install

python scripts/bootstrap_arizona.py --preset az-phoenix-core
python scripts/seed_demo_cache.py --aoi az-phoenix-core
```

### Setup (Windows — PowerShell)

```powershell
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"
npm install

python scripts/bootstrap_arizona.py --preset az-phoenix-core
python scripts/seed_demo_cache.py --aoi az-phoenix-core
# Or: .\scripts\seed_arizona.ps1 -Preset az-phoenix-core
```

### Run (all platforms)

**Terminal 1 — API** (activate venv first on Windows: `.\.venv\Scripts\Activate.ps1`)

```bash
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Web**

```bash
npm run dev:web
```

**Terminal 3 — Shade worker (optional)**

```bash
npm run dev:worker
```

Open **http://localhost:5173** — select **Phoenix downtown (fast)**, set origin/destination on the map, then **Find routes**.

### 2.5D building shadows

Set `VITE_SHADEMAP_API_KEY` in `apps/web/.env` (Windows: `apps\web\.env`), restart the web dev server, zoom to **15+**.

### Precompute shade (optional)

```bash
npm run dev:worker
python scripts/precompute_shade.py --aoi az-phoenix-core --hours 10,11,12,13,14
```

## Environment variables

See [.env.example](.env.example).

## Documentation

- **[Setup & run (Linux + Windows)](docs/setup.md)**
- [Paper mapping](docs/paper-mapping.md)
- [Arizona coverage](docs/arizona.md)
- [Shade cache](docs/shade-cache.md)
- [API](docs/api.md)

## License

MIT — see [LICENSE](LICENSE).

## Attribution

- Research: Yu Feng et al., SIGSPATIAL 2024
- Shadows: [ShadeMap](https://shademap.app/) / [mapbox-gl-shadow-simulator](https://www.npmjs.com/package/mapbox-gl-shadow-simulator)
- Streets: [OpenStreetMap](https://www.openstreetmap.org/) via [OSMnx](https://osmnx.readthedocs.io/)
