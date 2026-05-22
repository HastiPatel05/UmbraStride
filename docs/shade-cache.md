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
| `UMBRASTIDE_CPU_WORKERS` | all cores | Global default when task-specific vars are `0` |
| `ROUTING_DIJKSTRA_WORKERS` | all cores | Parallel Dijkstra (one process per α profile) |
| `ROUTING_BUILD_WORKERS` | (reserved) | Graph build uses vectorized NumPy/BLAS across cores |
| `ROUTING_LOCAL_MARGIN_DEG` | `0.012` | Crop graph around O/D before search (~1.3 km) |
| `SHADE_SEED_WORKERS` | all cores | `seed_demo_cache.py` — parallel hours |
| `PRECOMPUTE_WORKERS` | all cores | `precompute_shade.py` — parallel HTTP chunks |
| `BOOTSTRAP_WORKERS` | `min(cores, 4)` | `bootstrap_arizona.py --preset all` (OSM rate limits) |

Set any of these to a positive integer to cap workers (e.g. `ROUTING_BUILD_WORKERS=8`).

After the first request for an AOI + time bucket, typical route requests are **under ~0.5 s** on `az-phoenix-core`. The first request still pays GraphML load + graph build (~5 s).

Restart the API after changing routing code: `uvicorn umbrastride_api.main:app --reload`

## Time bucket matching

Routing floors the request datetime to a 15-minute UTC bucket (e.g. `2026-05-21T12:00`). If that bucket is missing in SQLite, the API **uses the nearest cached hour** and sets `shade_cache_exact: false` in the response.

Seed cache for the hours you test with:

```bash
python scripts/seed_demo_cache.py --aoi az-phoenix-core --hours 10,11,12,13,14
```

Use the same calendar day as the web app datetime picker, or expect a sidebar hint about the nearest bucket.

## Mock mode

`scripts/seed_demo_cache.py` writes synthetic shade (varies by street bearing vs sun) so routing works without ShadeMap credentials.

## Worker

`services/shade-worker` runs Playwright + MapLibre + ShadeMap. POST `/profile` with `{ points, datetime }` returns `{ results: [{ lng, lat, inShade }] }`.
