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

## Mock mode

`scripts/seed_demo_cache.py` writes synthetic shade (higher on north-south streets) so routing works without ShadeMap credentials.

## Worker

`services/shade-worker` runs Playwright + MapLibre + ShadeMap. POST `/profile` with `{ points, datetime }` returns `{ results: [{ lng, lat, inShade }] }`.
