# Arizona coverage

UmbraStride is configured for **Arizona, USA** instead of a single city hardcoded in the app. This page explains **what areas exist**, **how the app picks one automatically**, and **how to prepare data**.

For everyday use, see the [User guide](user-guide.md). For commands, see [Setup](setup.md).

---

## Why not one graph for the entire state?

Arizona is roughly **295,000 km²**. A single statewide pedestrian graph would be:

- **Millions** of street segments
- **Gigabytes** on disk
- **Very slow** routing and shade precompute

So UmbraStride splits work into **AOIs** (areas of interest)—boxes you prepare one at a time.

---

## Two ways to cover geography

### 1. Metro presets (recommended)

Ten urban regions defined in [`data/regions/arizona.json`](../data/regions/arizona.json):

| AOI id | Name | Approx. coverage |
|--------|------|------------------|
| `az-phoenix` | Phoenix metro (wide) | Phoenix, Tempe, Scottsdale — **default** |
| `az-phoenix-core` | Phoenix downtown (fast) | Central Phoenix ~5 km — quick dev/tests |
| `az-tucson` | Tucson metro | Tucson area |
| `az-flagstaff` | Flagstaff | Flagstaff urban |
| `az-prescott` | Prescott area | Prescott / Prescott Valley |
| `az-yuma` | Yuma | Southwest corner |
| `az-lake-havasu` | Lake Havasu City | Colorado River |
| `az-sedona` | Sedona / Verde Valley | Sedona region |
| `az-nogales` | Nogales | Border area |
| `az-show-low` | Show Low / White Mountains | Eastern high country |

Each preset has:

- `bbox`: `[west, south, east, north]` in degrees
- `name`: Human-readable label in the app sidebar

### 2. Grid tiles (advanced)

The manifest includes a **0.25° grid** over the state bbox (~460 tiles). Tile IDs look like `az-tile--112.00_33.25`. Use for rural or statewide expansion **on demand**—not for first-time setup.

```bash
python scripts/bootstrap_arizona.py --list-tiles
python scripts/bootstrap_arizona.py --tile az-tile--112.00_33.25
```

---

## How the app chooses an AOI (no dropdown)

When you place **origin** and **destination** on the map:

1. Find all presets whose **blue box** contains **both** points.
2. Prefer the **largest** matching preset (wide Phoenix over downtown core when both fit).
3. Prefer a preset that is **bootstrapped** (graph file exists on disk).
4. If no metro preset contains both points, find a generated tile that contains both points.
5. Prefer a bootstrapped tile when one is available.
6. Show the name under **Active area:** in the sidebar.

The API uses the same logic when you call `POST /v1/route` without `aoi_id`.

**Example:** Clicks in downtown Phoenix → usually `az-phoenix` if that graph exists; otherwise falls back to `az-phoenix-core` if only that was bootstrapped.

**Tile example:** Rural Arizona clicks inside one `az-tile-*` cell can route after bootstrapping that tile:

```bash
python scripts/bootstrap_arizona.py --tile az-tile--112.00_33.25
python scripts/seed_demo_cache.py --aoi az-tile--112.00_33.25 --hours 10,11,12,13,14
```

Routes across multiple tiles are not supported as one route yet.

Implementation: `packages/geo-core/src/umbrastride_geo/regions.py` and `apps/web/src/resolveAoi.ts`.

---

## Preparing data for a metro

### Step 1 — Bootstrap (streets)

Downloads OSM **walk** network inside the preset bbox.

```bash
source .venv/bin/activate
python scripts/bootstrap_arizona.py --preset az-phoenix
```

Creates:

- `data/graphs/az-phoenix.graphml`
- `data/graphs/az-phoenix.meta.json`
- `data/graphs/az-phoenix.graph.pkl` (fast reload)
- `data/graphs/az-phoenix.edge-index.json` (shade vectorization)

**Time / size:** `az-phoenix-core` ≈ minutes / tens of MB; `az-phoenix` ≈ longer / larger.

### Step 2 — Seed shade (routing quality)

```bash
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14
```

Creates `data/shade-cache/az-phoenix.sqlite`.

### Step 3 — Warm routing cache (recommended)

After API is running:

```bash
curl -X POST http://127.0.0.1:8000/v1/aoi/az-phoenix/routing/warm \
  -H "Content-Type: application/json" \
  -d '{"hours": [10, 11, 12, 13, 14]}'
```

Or set `ROUTING_WARM_ON_STARTUP=1` in `.env` so the API warms on boot.  
Creates `data/routing-cache/az-phoenix/*.routing.pkl`.

See [Routing performance](performance.md).

### One-command helpers

**Linux / macOS:**

```bash
./scripts/seed_arizona.sh
```

**Windows:**

```powershell
.\scripts\seed_arizona.ps1 -Preset az-phoenix
.\scripts\seed_arizona.ps1 -AllMetros
```

---

## Phoenix: downtown vs wide

| | `az-phoenix-core` | `az-phoenix` |
|---|-------------------|--------------|
| **Use case** | Fast laptop demo, CI | Realistic metro trips |
| **Area** | ~5 km core | ~25 km multi-city |
| **Graph edges** | ~140k (order of magnitude) | ~560k |
| **Bootstrap time** | Shorter | Longer |
| **Default in repo** | Older default | **Current default** |

**“Whole Phoenix” in the app** means **`az-phoenix`**, not the entire Valley at county scale. A larger bbox would need a new preset in `arizona.json` and a new bootstrap.

---

## API endpoints for regions

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/regions` | List region ids |
| `GET /v1/regions/arizona` | Full manifest + generated `tiles` + `bootstrapped_aois` |
| `GET /v1/regions/arizona/resolve?lng=&lat=` | AOI for one point |
| `POST /v1/regions/arizona/bootstrap-preset` | Body `{"preset":"az-phoenix"}` — bootstrap via API |

`POST /v1/route` with optional `aoi_id` — auto-resolves from origin/destination.

Details: [API reference](api.md).

---

## Web map defaults

From `data/regions/arizona.json`:

- **Center:** `[-112.07, 33.48]` (Phoenix area)
- **Zoom:** 13 (see wide metro)
- **State outline:** Arizona bbox on map
- **Metro outline:** Active preset bbox (blue)

Override initial hint with `VITE_DEFAULT_AOI` in `apps/web/.env` (map clicks still win after load).

---

## Adding a new preset (technical)

1. Edit `data/regions/arizona.json` — add entry with `aoi_id`, `name`, `bbox`, `description`.
2. `python scripts/bootstrap_arizona.py --preset your_id`
3. `python scripts/seed_demo_cache.py --aoi your_id`
4. Restart API; refresh web — clicks inside bbox resolve to new AOI.

---

## See also

- [Setup guide](setup.md)
- [Shade cache](shade-cache.md)
- [Glossary — AOI, preset, bootstrap](glossary.md)
