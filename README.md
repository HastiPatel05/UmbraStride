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

### Prerequisites

- Python 3.11+
- Node.js 20+
- ShadeMap API key ([get one](https://shademap.app/about/))

### Setup

```bash
cp .env.example .env
# Edit .env — set SHADEMAP_API_KEY (and optionally MAPBOX_ACCESS_TOKEN)

# Python packages
python3 -m venv .venv
source .venv/bin/activate
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"

# Node packages
npm install

# Bootstrap Arizona (Phoenix metro by default)
python scripts/bootstrap_arizona.py --preset az-phoenix

# Or all Arizona metros + shade cache
./scripts/seed_arizona.sh

# Seed mock shade cache for one metro
python scripts/seed_demo_cache.py --aoi az-phoenix
```

### Run

```bash
# Terminal 1 — API
source .venv/bin/activate
uvicorn umbrastride_api.main:app --reload --port 8000

# Terminal 2 — Web
npm run dev:web

# Optional — shade worker (real ShadeMap profiling)
npm run dev:worker
```

Open http://localhost:5173 — pick origin/destination on the map, set datetime and alpha, then **Find routes**.

### 2.5D building shadows on the map (like shademap.app)

```bash
cp apps/web/.env.example apps/web/.env
# Set VITE_SHADEMAP_API_KEY from https://shademap.app/about/
npm run dev:web
```

At zoom **15+**, the map loads OSM building footprints (Overpass) with heights and renders ShadeMap shadows for the selected date/time. Optional `VITE_MAPBOX_ACCESS_TOKEN` improves building heights where Mapbox data is available.

### Precompute shade (requires SHADEMAP_API_KEY + worker)

```bash
npm run dev:worker
python scripts/precompute_shade.py --aoi az-phoenix --hours 10,11,12,13,14
```

## Environment variables

See [.env.example](.env.example).

## Documentation

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
