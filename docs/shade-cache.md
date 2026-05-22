# Shade cache

How UmbraStride stores **shade along streets**, how that affects **routing**, and how to **fill or refresh** the cache. Written for both users and developers.

---

## Plain-language summary

For each **street segment** and **time of day**, UmbraStride stores a number between 0 and 1:

- **0** — mostly in the sun  
- **1** — mostly in shade  

When you ask for a **coolest** route, the algorithm makes **sunny** segments “cost more” than **shady** ones. When you ask for **shortest**, shade is ignored.

That data lives in a **SQLite file per AOI** on disk. If the file is empty or missing your chosen time, every street looks “50% shady” and all routes collapse to the same shortest path.

---

## Hybrid cache model (design)

| Tier | Name | What happens |
|------|------|----------------|
| **L1 hot** | In-memory | After first API request: graph + shade map + routing graph cached in RAM |
| **L2 warm** | SQLite on disk | Pre-seeded or precomputed rows per `(aoi_id, edge_key, ts_bucket)` |
| **L3 cold** | On-demand | Shade worker profiles missing edges (optional; `cache/warm`, `precompute_shade.py`) |

---

## Keys and time buckets

| Field | Format | Example |
|-------|--------|---------|
| `aoi_id` | Metro id | `az-phoenix` |
| `edge_key` | Unique street segment id in graph | `41190548\|7093578437\|0` |
| `ts_bucket` | UTC, floored to **15 minutes** | `2026-05-22T12:00` |

Routing converts your request datetime to a bucket, loads all rows for that bucket in **one SQL query**, then builds edge weights.

### Time bucket matching

If **no rows** exist for the exact bucket:

1. API loads the **nearest cached hour** in SQLite.
2. Response includes `shade_cache_exact: false` and `shade_ts_bucket` (actual bucket used).
3. Web app may show a yellow hint in the sidebar.

**Fix for users:** Seed the hours you test:

```bash
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14 --date 2026-05-22
```

Use the **same calendar day** in the web datetime picker, or accept nearest-hour fallback.

---

## How shade is computed (per edge)

### Production path (ShadeMap + worker)

For each graph edge:

1. Sample `N = max(5, ceil(length_m / 10))` points along the street geometry.
2. Call ShadeMap shade profile at datetime `t` (via shade worker).
3. `shade_fraction = (points in shade) / N`.
4. Store in SQLite.

Command:

```bash
npm run dev:worker
python scripts/precompute_shade.py --aoi az-phoenix --hours 10,11,12,13,14
```

Requires `SHADEMAP_API_KEY` and worker running.

### Demo path (synthetic — no ShadeMap)

`scripts/seed_demo_cache.py` writes **fake** shade that varies by:

- Time of day (sun angle proxy)
- Street **bearing** vs simulated sun from the south

Good enough to see **different** shortest vs coolest routes. **Not** ground truth for a real walk.

```bash
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14
```

Parallel hours: `SHADE_SEED_WORKERS=0` uses all CPU cores.

---

## SQLite schema

Path: `{DATA_DIR}/shade-cache/{aoi_id}.sqlite`

```sql
CREATE TABLE edge_shade (
  aoi_id TEXT NOT NULL,
  edge_key TEXT NOT NULL,
  ts_bucket TEXT NOT NULL,
  shade_fraction REAL NOT NULL,
  sample_count INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (aoi_id, edge_key, ts_bucket)
);
```

Inspect (optional):

```bash
python3 -c "
from umbrastride_routing.shade_store import ShadeStore
s = ShadeStore('az-phoenix')
print(s.coverage())
print('buckets', s.list_buckets()[:5])
"
```

---

## How shade affects routing weights

For edge length `L`, shade `S`, preference `α`, sun penalty `β` (default 2):

```
L_sun   = L * (1 - S)
L_shade = L * S
weight  = α * L + (1 - α) * (L_sun * β + L_shade)
```

- **α = 1** → weight = `L` (shortest path).  
- **α = 0** → sunny length counts more (×β).  
- **α = 0.35** → blend (your slider).

Code: `packages/routing-core/src/umbrastride_routing/weights.py`.

Each request computes paths for **α ∈ {1.0, 0.0, your α}** in parallel (when `ROUTING_DIJKSTRA_WORKERS` > 0).

---

## Routing performance (API)

In-memory caches (per API process):

| Cache | Invalidation |
|-------|----------------|
| GraphML | File mtime change |
| Shade map | SQLite mtime + bucket resolve |
| Routing DiGraph | Graph + shade + α set |

Optimizations:

- **Bulk** SQLite load per bucket (not per edge query).
- **Vectorized** NumPy weight build.
- **Local subgraph** crop around origin/destination (`ROUTING_LOCAL_MARGIN_DEG`, default ~1.3 km).
- **Parallel** Dijkstra per α.

Typical timings (hardware-dependent):

| AOI | First request | Warm requests |
|-----|---------------|---------------|
| `az-phoenix-core` | ~5 s (load + build) | often &lt; 0.5 s |
| `az-phoenix` | ~10–20 s first time | ~0.3–2 s |

Restart API after changing routing code.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `UMBRASTIDE_CPU_WORKERS` | all cores | Global parallel default when `0` |
| `ROUTING_DIJKSTRA_WORKERS` | all cores | Parallel Dijkstra per α |
| `ROUTING_LOCAL_MARGIN_DEG` | `0.012` | Subgraph crop margin |
| `SHADE_SEED_WORKERS` | all cores | `seed_demo_cache.py` |
| `PRECOMPUTE_WORKERS` | all cores | `precompute_shade.py` parallel HTTP |
| `SUN_AVERSION_BETA` | `2.0` | Sun penalty strength |
| `SHADE_WORKER_URL` | `http://127.0.0.1:3001` | Worker for warm/precompute |

Full table: [Configuration](configuration.md).

---

## API: cache coverage and warm

**Coverage:**

```http
GET /v1/aoi/az-phoenix/cache/coverage
GET /v1/aoi/az-phoenix/cache/coverage?ts_bucket=2026-05-22T12:00
```

**Warm (sample):**

```http
POST /v1/aoi/az-phoenix/cache/warm
Content-Type: application/json

{"datetime": "2026-05-22T12:00:00Z", "edge_keys": null}
```

Does not replace full `precompute_shade.py` — pings worker with up to 200 sample points.

---

## Shade worker

`services/shade-worker` — Express service.

- **POST `/profile`** — body `{ "points": [{lng, lat}, ...], "datetime": "ISO" }`  
- Returns `{ "results": [{ "lng", "lat", "inShade" }, ...] }`  
- Implementation may use **mock** shade when Playwright/ShadeMap is not fully wired.

Start: `npm run dev:worker`

---

## Checklist: routing looks wrong

- [ ] `data/shade-cache/{aoi}.sqlite` exists  
- [ ] `seed_demo_cache` or `precompute` run for that AOI  
- [ ] Web datetime matches seeded `--hours` / `--date`  
- [ ] API restarted after seeding  
- [ ] Sidebar does not only say “nearest cached hour” with empty DB  
- [ ] Coolest and shortest differ on map (teal vs orange)

More: [Troubleshooting — identical routes](troubleshooting.md#all-three-routes-look-identical).

---

## See also

- [User guide](user-guide.md)
- [Architecture](architecture.md)
- [Paper mapping](paper-mapping.md)
