# Shade cache (hybrid)

## Keys

| Layer | Key | Granularity |
|-------|-----|-------------|
| L1 hot | `(aoi_id, edge_key, ts_bucket)` | 15-minute UTC buckets |
| L2 warm | same schema | 1-hour buckets from nightly precompute |
| L3 miss | on-demand | shade-worker fills missing rows |

`ts_bucket` format: `YYYY-MM-DDTHH:MM` (UTC, floored to 15 min).

## Edge sampling

For each graph edge:

1. Sample `N = max(5, ceil(length_m / 10))` points along the geometry.
2. ShadeMap `_generateShadeProfile` returns sun/shade per point at datetime `t`.
3. `shade_fraction = shade_points / N`.

## Storage

SQLite at `{DATA_DIR}/shade-cache/{aoi_id}.sqlite`:

```sql
CREATE TABLE edge_shade (
  aoi_id TEXT,
  edge_key TEXT,
  ts_bucket TEXT,
  shade_fraction REAL,
  sample_count INTEGER,
  PRIMARY KEY (aoi_id, edge_key, ts_bucket)
);
```

## Routing performance

The API caches in memory (per process):

- OSM **GraphML** (reload only when the file changes)
- **Shade SQLite** rows for the requested time bucket (one bulk query, not per edge)
- **Routing DiGraph** with weights for α = 0, 1, and your custom α

Optional env vars (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ROUTING_DIJKSTRA_WORKERS` | `3` | Parallel Dijkstra for shortest / coolest / custom |
| `ROUTING_LOCAL_MARGIN_DEG` | `0.012` | Crop graph around O/D before search (~1.3 km) |

After the first request for an AOI + time bucket, typical route requests are **under ~0.5 s** on `az-phoenix-core`. The first request still pays GraphML load + graph build (~5 s).

Restart the API after changing routing code: `uvicorn umbrastride_api.main:app --reload`

## Mock mode

`scripts/seed_demo_cache.py` writes synthetic shade (higher on north-south streets) so routing works without ShadeMap credentials.

## Worker

`services/shade-worker` runs Playwright + MapLibre + ShadeMap. POST `/profile` with `{ points, datetime }` returns `{ results: [{ lng, lat, inShade }] }`.
