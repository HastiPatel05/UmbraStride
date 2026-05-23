# Configuration reference

UmbraStride uses two environment files. You copy the examples once, then edit values.

| File | Who reads it | Purpose |
|------|----------------|---------|
| [`.env`](../.env.example) | Python API, scripts | Data paths, routing, ShadeMap server key |
| [`apps/web/.env`](../apps/web/.env.example) | Web app (Vite) | Map API keys, default AOI hint |

**Rule:** After changing `.env` files, **restart** the API and web dev servers.

---

## Root `.env` (API and scripts)

Copy from [`.env.example`](../.env.example).

### Required for real ShadeMap server / precompute

| Variable | Example | Description |
|----------|---------|-------------|
| `SHADEMAP_API_KEY` | `eyJ...` | API key from [shademap.app/about](https://shademap.app/about/). Used by shade worker and server-side tools—not the browser key. |

### Data and server

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `./data` | Where graphs (`data/graphs/`) and shade cache (`data/shade-cache/`) are stored. |
| `API_HOST` | `0.0.0.0` | API bind address. |
| `API_PORT` | `8000` | API port. |
| `API_CORS_ORIGINS` | `http://localhost:5173,...` | Browser origins allowed to call the API. Add your LAN URL if testing from another device. |

### Shade worker

| Variable | Default | Description |
|----------|---------|-------------|
| `SHADE_WORKER_URL` | `http://127.0.0.1:3001` | URL of `services/shade-worker` for cache warm / precompute. |
| `SHADE_WORKER_CONCURRENCY` | `2` | Parallel in-flight `/profile` requests in shade-worker. |

### Routing behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_AOI_ID` | `az-phoenix` | Fallback AOI when resolution fails. Should match a **bootstrapped** preset. |
| `SUN_AVERSION_BETA` | `5.0` | How strongly sunny street length is penalized when α→0 (shade preference). Higher = stronger avoidance of sun. |
| `SNAP_MAX_DIST_M` | `1200` | Max distance (meters) to snap a click to the nearest walkable street node. |

### CPU parallelism (`0` = use all cores)

| Variable | Default | Used by |
|----------|---------|---------|
| `UMBRASTIDE_CPU_WORKERS` | `0` | Global default for parallel tasks |
| `ROUTING_DIJKSTRA_WORKERS` | `0` | Parallel shortest-path runs (one per α) |
| `ROUTING_BUILD_WORKERS` | `0` | Reserved; graph build uses NumPy |
| `SHADE_SEED_WORKERS` | `0` | `seed_demo_cache.py` |
| `PRECOMPUTE_WORKERS` | `0` | `precompute_shade.py` HTTP chunks |
| `BOOTSTRAP_WORKERS` | `0` | `bootstrap_arizona.py --preset all` (capped at 4 for OSM politeness) |

Set any to a positive integer to limit cores (e.g. `ROUTING_DIJKSTRA_WORKERS=4`).

### Routing performance (advanced)

| Variable | Default | Description |
|----------|---------|-------------|
| `ROUTING_LOCAL_MARGIN_DEG` | `0.012` | Corridor crop margin around origin/destination before shortest-path. |
| `ROUTING_CORRIDOR_SCALES` | `0.6,1.0,1.6,3.0` | Expand corridor until a path exists (multipliers on margin). |
| `ROUTING_DISK_CACHE` | `1` | Persist built routing DiGraph under `data/routing-cache/`. |
| `ROUTING_WARM_ON_STARTUP` | `1` | Preload `DEFAULT_AOI_ID` when API starts. |
| `ROUTING_WARM_HOURS` | empty | Comma hours (UTC) to warm on startup, e.g. `10,11,12,13,14`. |
| `ROUTING_PATH_ENGINE` | `rustworkx` | `rustworkx` or `networkx` for shortest-path. |
| `ROUTING_USE_ASTAR` | `1` | A* with geographic heuristic (disable if debugging). |

**On-disk artifacts (auto-created):**

| Path | Purpose |
|------|---------|
| `data/graphs/{aoi}.graph.pkl` | Fast street-graph reload (vs GraphML). |
| `data/graphs/{aoi}.edge-index.json` | Stable `edge_key` → index for vectorized shade. |
| `data/routing-cache/{aoi}/*.routing.pkl` | Cached weighted routing graph per shade bucket + α set. |

**API:** `POST /v1/aoi/{aoi_id}/routing/warm` preloads graph + routing cache without waiting for the first route click.

### Optional Mapbox (server)

| Variable | Default | Description |
|----------|---------|-------------|
| `MAPBOX_ACCESS_TOKEN` | empty | Optional; not required if using OpenFreeMap in the web app. |

---

## Web `apps/web/.env`

Copy from [`apps/web/.env.example`](../apps/web/.env.example).

| Variable | Required? | Description |
|----------|-------------|-------------|
| `VITE_SHADEMAP_API_KEY` | For live shadows | Browser ShadeMap key ([get one](https://shademap.app/about/)). **Separate** from root `SHADEMAP_API_KEY` in practice—use the same key value in both unless ShadeMap docs say otherwise. |
| `VITE_MAPBOX_ACCESS_TOKEN` | No | If set, uses Mapbox Streets as basemap instead of OpenFreeMap. 3D buildings still use OpenFreeMap tiles when extrusions are added. |
| `VITE_DEFAULT_AOI` | No | Initial AOI hint (`az-phoenix`). App **overrides** from map clicks when region data loads. |
| `VITE_API_URL` | No | Default `/api` (Vite proxy to port 8000 in dev). Set full URL if API is elsewhere. |

**Vite rule:** Only variables prefixed with `VITE_` are visible in the browser.

---

## Minimum working configuration (demo)

**Root `.env`:**

```env
DATA_DIR=./data
DEFAULT_AOI_ID=az-phoenix
SUN_AVERSION_BETA=5.0
```

**`apps/web/.env`:**

```env
VITE_DEFAULT_AOI=az-phoenix
```

ShadeMap keys can be empty for routing with **synthetic** seeded shade.

---

## Recommended production-like local setup

```env
# .env
SHADEMAP_API_KEY=your_key
DATA_DIR=./data
DEFAULT_AOI_ID=az-phoenix
SNAP_MAX_DIST_M=1200
```

```env
# apps/web/.env
VITE_SHADEMAP_API_KEY=your_key
VITE_DEFAULT_AOI=az-phoenix
```

Plus:

```bash
python scripts/bootstrap_arizona.py --preset az-phoenix
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14
```

---

## Security notes

- **Do not commit** `.env` or `apps/web/.env` to git (they are gitignored).
- API keys in `VITE_*` variables are **exposed to anyone** who can open your web app—restrict network access in production.
- Use separate keys or quotas for development vs production if ShadeMap offers them.

---

## See also

- [Setup guide](setup.md)
- [Shade cache](shade-cache.md)
- [Troubleshooting](troubleshooting.md)
