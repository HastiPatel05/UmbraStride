# API reference

HTTP API for UmbraStride. Default base URL: **http://127.0.0.1:8000**

Interactive docs (when API is running): **http://127.0.0.1:8000/docs**

For a friendly overview, see [User guide](user-guide.md) and [Architecture](architecture.md).

---

## Conventions

- **Coordinates:** `lng` (longitude), `lat` (latitude), WGS84.
- **Time:** ISO 8601 strings; UTC recommended (e.g. `2026-05-22T12:00:00Z`).
- **Errors:** JSON `{"detail": "message"}` with HTTP 4xx/5xx.
- **CORS:** Configured via `API_CORS_ORIGINS` in `.env`.

---

## Health

### `GET /health`

**Response:**

```json
{ "status": "ok" }
```

Use for uptime checks.

---

## Regions (Arizona)

### `GET /v1/regions`

List available region manifest ids.

### `GET /v1/regions/{region_id}`

Example: `GET /v1/regions/arizona`

Returns manifest from `data/regions/arizona.json` plus:

| Field | Description |
|-------|-------------|
| `presets` | Metro AOIs with bbox and names |
| `tiles` | Generated Arizona grid AOIs with bbox and names |
| `default_aoi` | Fallback AOI id |
| `default_center` | Map center `[lng, lat]` |
| `default_zoom` | Suggested zoom |
| `tile_count` | Approximate grid tile count |
| `bootstrapped_aois` | AOI ids with `data/graphs/{id}.graphml` present |

### `GET /v1/regions/{region_id}/resolve?lng=&lat=`

Pick an AOI for a single point. Metro presets are preferred; generated tile AOIs are used for on-demand Arizona coverage outside metro presets.

**Example:** `GET /v1/regions/arizona/resolve?lng=-112.07&lat=33.45`

**Response:**

```json
{ "aoi_id": "az-phoenix", "lng": -112.07, "lat": 33.45 }
```

### `POST /v1/regions/{region_id}/bootstrap-preset`

Download OSM graph for a named preset (long-running).

**Body:**

```json
{ "preset": "az-phoenix" }
```

**Response:** Bootstrap metadata (`nodes`, `edges`, `aoi_id`, …).

---

## AOIs (graphs on disk)

### `GET /v1/aoi`

List AOIs that have a GraphML file under `DATA_DIR/graphs/`.

**Response:**

```json
{
  "aois": [
    { "aoi_id": "az-phoenix", "bbox": [-112.22, 33.38, -111.92, 33.58] }
  ]
}
```

### `GET /v1/aoi/{aoi_id}/graph`

GeoJSON `FeatureCollection` of walk edges (for map overlay). Can be large.

**Errors:** `404` if graph not bootstrapped.

### `POST /v1/aoi/bootstrap`

Custom bbox bootstrap.

**Body:**

```json
{
  "aoi_id": "my-area",
  "bbox": "-112.12,33.42,-112.02,33.50"
}
```

Format: `west,south,east,north`.

---

## Shade cache

### `GET /v1/aoi/{aoi_id}/cache/coverage`

Optional query: `?ts_bucket=2026-05-22T12:00`

**Response:**

```json
{
  "aoi_id": "az-phoenix",
  "total_edges": 560496,
  "cached_edges": 139340,
  "coverage_ratio": 0.248,
  "ts_buckets": ["2026-05-22T10:00", "2026-05-22T11:00"],
  "ts_bucket": null
}
```

`coverage_ratio` = distinct cached edge keys / graph edges (approximate).

### `POST /v1/aoi/{aoi_id}/cache/warm`

Ping shade worker with a sample of edge midpoints (does not full precompute).

**Body:**

```json
{
  "datetime": "2026-05-22T12:00:00Z",
  "edge_keys": null,
  "persist_sample": false
}
```

| Field | Description |
|-------|-------------|
| `edge_keys` | Optional list to limit edges; `null` = sample up to 200 points |
| `persist_sample` | If `true`, write sampled edge shade rows to SQLite for this bucket |

**Response:**

```json
{
  "status": "worker_ok",
  "ts_bucket": "2026-05-22T12:00",
  "sampled_points": 200,
  "hint": "Run scripts/precompute_shade.py for full edge cache"
}
```

**Errors:** `502` if worker down; `404` if graph missing.

### `POST /v1/aoi/{aoi_id}/routing/warm`

Preload **street graph**, **shade arrays**, and **routing DiGraph** into memory and disk cache. Does not call ShadeMap.

Use after bootstrap/seed or before a demo to avoid a slow first `POST /v1/route`.

**Body (all fields optional):**

```json
{
  "datetime": "2026-05-22T12:00:00Z",
  "hours": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0, 1, 2],
  "alphas": [1.0, 0.0, 0.5]
}
```

| Field | Description |
|-------|-------------|
| `datetime` | Warm this specific time bucket (15-min floor) |
| `hours` | UTC hours on **today's date** to warm. Use `[5, 6, ..., 19]` for 5 AM-7 PM UTC, or `[12, 13, ..., 23, 0, 1, 2]` for 5 AM-7 PM Phoenix local (MST / UTC-7). |
| `alphas` | α values to include in cached routing graph (default `[1.0, 0.0, 0.5]`) |

If both `datetime` and `hours` omitted, warms **current UTC** bucket only.

**Response:**

```json
{
  "status": "warmed",
  "aoi_id": "az-phoenix",
  "warmed_buckets": ["2026-05-22T12:00", "2026-05-22T10:00"],
  "alphas": [1.0, 0.0, 0.5]
}
```

**Errors:** `404` if graph not bootstrapped.

**Startup equivalent:** set `ROUTING_WARM_ON_STARTUP=1` and `ROUTING_WARM_HOURS=12,13,14,15,16,17,18,19,20,21,22,23,0,1,2` in `.env` for 5 AM-7 PM Phoenix local, or `5,6,7,8,9,10,11,12,13,14,15,16,17,18,19` for UTC. See [Routing performance](performance.md).

---

## Routing (main endpoint)

### `POST /v1/route`

Compute up to three routes: **shortest** (α=1), **coolest** (α=0), and **custom** (your α).

When automatic local shade is enabled, this endpoint first ensures the requested 15-minute shade bucket exists for the resolved AOI. That write uses the shade-cache SQLite database, so concurrent shade sync/precompute work for the same AOI may briefly make the route wait.

**Body:**

```json
{
  "aoi_id": null,
  "origin": { "lng": -112.08, "lat": 33.45 },
  "destination": { "lng": -112.05, "lat": 33.46 },
  "datetime": "2026-05-22T12:00:00Z",
  "alpha": 0.35
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `origin` | yes | Start point |
| `destination` | yes | End point |
| `datetime` | yes | Sun/shade time context |
| `alpha` | no (default 0.5) | Your preference 0–1 |
| `aoi_id` | no | If omitted, **auto-resolved** from points in Arizona |

**Success response:**

```json
{
  "aoi_id": "az-phoenix",
  "origin_node": 12345,
  "dest_node": 67890,
  "ts_bucket": "2026-05-22T12:00",
  "shade_ts_bucket": "2026-05-22T12:00",
  "shade_cache_exact": true,
  "sun_below_horizon": false,
  "routes": [
    {
      "label": "shortest",
      "alpha": 1.0,
      "geometry": { "type": "LineString", "coordinates": [[...]] },
      "distance_m": 2863.9,
      "shade_fraction": 0.683,
      "detour_ratio": 1.0,
      "ts_bucket": "2026-05-22T12:00"
    },
    {
      "label": "coolest",
      "alpha": 0.0,
      "geometry": { "type": "LineString", "coordinates": [[...]] },
      "distance_m": 2903.3,
      "shade_fraction": 0.73,
      "detour_ratio": 1.014,
      "ts_bucket": "2026-05-22T12:00"
    },
    {
      "label": "custom",
      "alpha": 0.35,
      "geometry": { "type": "LineString", "coordinates": [[...]] },
      "distance_m": 2874.1,
      "shade_fraction": 0.715,
      "detour_ratio": 1.004,
      "ts_bucket": "2026-05-22T12:00"
    }
  ]
}
```

| Route field | Meaning |
|-------------|---------|
| `geometry` | GeoJSON LineString along streets |
| `distance_m` | Path length (meters) |
| `shade_fraction` | Length-weighted average shade along path |
| `detour_ratio` | Distance / shortest distance |

| `sun_below_horizon` | When `true`, sun is down at both endpoints; coolest and shortest use uniform full shade (same path) |

**Errors:**

| Code | Typical cause |
|------|----------------|
| `400` | Invalid datetime; points outside requested AOI |
| `404` | No graph; no path between points |
| `500` | Unexpected server error; if logs show `database is locked`, restart on the latest code and avoid concurrent shade precompute for the same AOI |

---

## Example: curl

```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/v1/route \
  -H "Content-Type: application/json" \
  -d '{
    "origin": {"lng": -112.08, "lat": 33.45},
    "destination": {"lng": -112.05, "lat": 33.46},
    "datetime": "2026-05-22T12:00:00Z",
    "alpha": 0.35
  }' | python3 -m json.tool
```

---

## Web app proxy

In development, Vite serves the web app on port **5173** and proxies `/api` → `http://127.0.0.1:8000`. The browser calls `/api/v1/route`, not port 8000 directly.

Start the API first:

```bash
npm run dev:api
curl http://127.0.0.1:8000/health
npm run dev:web
```

If the Vite terminal logs `http proxy error` or `ECONNREFUSED 127.0.0.1:8000`, the API is not listening on port 8000 yet.

Set `VITE_API_URL` if the API is hosted elsewhere:

```bash
API_PORT=8001 npm run dev:api
VITE_API_URL=http://127.0.0.1:8001 npm run dev:web
```

---

## See also

- [Shade cache](shade-cache.md)
- [Configuration](configuration.md)
- [Arizona coverage](arizona.md)
