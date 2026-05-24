# Troubleshooting

Symptoms, likely causes, and fixes. Start with the [User guide](user-guide.md) if you are unsure how the app is supposed to work.

---

## Installation and startup

### `python` or `pip` not found

**Cause:** Python not installed or not on PATH (common on Windows).

**Fix:**

- Install Python 3.11+ from [python.org](https://www.python.org/downloads/) and check **“Add to PATH.”**
- On Windows try `py -3.12` instead of `python`.
- Activate the venv before `pip` or `uvicorn` (see [Setup](setup.md)).

### `Activate.ps1` cannot be loaded (Windows)

**Cause:** PowerShell execution policy.

**Fix:**

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### `uvicorn` not found

**Cause:** Virtual environment not activated or API package not installed.

**Fix:**

```bash
source .venv/bin/activate   # Linux/macOS
pip install -e "services/api[dev]"
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

### Web opens but API errors / “Failed to fetch”

**Cause:** API not running or wrong port; CORS/proxy mismatch.

**Fix:**

1. Confirm API: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`.
2. Run `npm run dev:web` from repo root (Vite proxies `/api` → 8000).
3. Check `API_CORS_ORIGINS` in `.env` includes your browser URL.

---

## Map and UI

### Clicking the map does nothing

**Cause:** Clicks hit an overlay, or pick mode not set.

**Fix:**

1. Click **Origin** or **Destination** in the sidebar first (button should look active).
2. Click the **map canvas**, not the hint text at the bottom.
3. Hard-refresh the page (Ctrl+Shift+R).

### Map is black or blank after clicking

**Cause:** (Older bug) map recreated on state change; or style failed to load.

**Fix:** Refresh page. Ensure network can reach `tiles.openfreemap.org`. Check browser console for errors.

### No 3D buildings

**Cause:** Zoom too low; or style failed.

**Fix:**

- Zoom to **15+** (16+ for full building height).
- Tilt the map (right-drag) to see extrusions.
- OpenFreeMap requires network access; check ad blockers.

### No live shadows (but buildings show)

**Cause:** Zoom &lt; 15, the sun is down, building tiles are still loading, or the selected time has very short midday shadows.

**Fix:**

1. Zoom to **15+**.
2. Pick a daytime morning or late-afternoon time.
3. Wait for the **Geometric shadows** banner, or pan slightly to load fresh building tiles.

### Map shows wrong area / keeps jumping

**Cause:** Auto AOI resolution recenters when metro **changes**.

**Fix:** Expected when origin/destination move to a different metro. Pan manually after placement; same-metro clicks should not recenter.

---

## Routing errors

### “No graph for this area” / graph not loaded

**Cause:** `data/graphs/{aoi_id}.graphml` missing.

**Fix:**

```bash
source .venv/bin/activate
python scripts/bootstrap_arizona.py --preset az-phoenix
# or the preset shown in the error message
```

Wait until bootstrap finishes (wide Phoenix can take several minutes).

### “No street network for this area”

**Cause:** Active AOI not in `bootstrapped_aois` list (no GraphML on disk).

**Fix:** Same as above—bootstrap the preset name shown in the sidebar.

### “No graph node within … m” / snap failed

**Cause:** Click too far from any walkable street in the graph.

**Fix:**

- Move origin/destination closer to a visible street.
- Increase `SNAP_MAX_DIST_M` in `.env` (default 1200 m)—temporary workaround.
- Ensure you are inside the prepared metro, not desert with no OSM paths.

### Origin and destination outside metro bounds

**Cause:** Points in different metros or outside Arizona preset boxes.

**Fix:** Place both points inside the **blue outline** (active area). For cross-metro trips, bootstrap a larger AOI or two separate requests (not supported as one route today).

### “No route found between origin and destination”

**Cause:** Disconnected walk graph (rare) or nodes not connected in subgraph.

**Fix:** Try points closer together; verify graph integrity; check API logs for `NetworkXNoPath`.

### Shortest and coolest differ at night (expected: same)

**Expected:** When the sun is below the horizon at **both** origin and destination, shortest and coolest should be **identical**. Sidebar should mention night / full shade.

**If they still differ at night:**

1. Confirm datetime is truly night at **both** points (not dusk with one point still in daylight).
2. Pull latest code, install `geo-core` (for **astral**), and re-seed night hours — full steps in [Setup — Night shade buckets](setup.md#night-shade-buckets-after-pulling-tanmay):

   ```bash
   git pull origin tanmay
   source .venv/bin/activate
   pip install -e packages/geo-core   # pulls in astral
   python scripts/seed_demo_cache.py --aoi az-phoenix --hours 20,21,22,23,0,1,2,3,4,5
   ```

3. Restart API (clears in-memory cache) or call `POST .../routing/warm`.
4. Check API response: `sun_below_horizon` should be `true`.

### All three routes look identical (daytime)

**Cause:** **Shade cache miss** — all edges use default shade 0.5, so only distance matters.

**Fix:**

1. Seed cache for your AOI and **date/hour**:

   ```bash
   python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14 --date 2026-05-22
   ```

2. Make sure `AUTO_SHADE_SEED=1` is enabled, or match the web app **datetime** to seeded hours.
3. Restart API after seeding.

### Routes very slow first time, then OK

**Cause:** Cold load — GraphML parse, shade load, routing graph build, or first-time write to `data/routing-cache/`.

**Fix:**

1. Enable warm in `.env`:
   ```env
   ROUTING_WARM_ON_STARTUP=1
   ROUTING_WARM_HOURS=10,11,12,13,14
   ROUTING_DISK_CACHE=1
   ```
2. After API starts, run manual warm:
   ```bash
   curl -X POST http://127.0.0.1:8000/v1/aoi/az-phoenix/routing/warm \
     -H "Content-Type: application/json" \
     -d '{"hours": [10, 11, 12, 13, 14]}'
   ```
3. Verify: `ls data/routing-cache/az-phoenix/` should show `*.routing.pkl`.
4. Keep API running between clicks (RAM cache). Dev `--reload` restarts process and clears RAM.

Full guide: [Routing performance](performance.md).

### API startup seems to hang

**Cause:** Startup warm building routing cache for `az-phoenix` (large graph).

**Fix:** Wait for first warm to finish, or temporarily set `ROUTING_WARM_ON_STARTUP=0`, start API, then call `POST .../routing/warm` manually. Use `az-phoenix-core` for faster dev.

### ImportError: rustworkx

**Cause:** Routing package dependency not installed.

**Fix:**
```bash
source .venv/bin/activate
pip install rustworkx
# or reinstall routing-core
pip install -e "packages/routing-core[dev]"
```

Or set `ROUTING_PATH_ENGINE=networkx` in `.env` (slower).

### Shade note: “nearest cached hour”

**Cause:** No SQLite rows for exact 15-minute bucket.

**Fix:** Enable `AUTO_SHADE_SEED=1`, seed that hour, or accept nearest-hour fallback (documented in [Shade cache](shade-cache.md)).

---

## Data and scripts

### Bootstrap hangs or Overpass timeout

**Cause:** Large bbox or Overpass rate limits.

**Fix:**

- Start with `az-phoenix-core` for testing.
- Retry later; use smaller preset.
- Check internet connection.

### `seed_demo_cache.py` very slow

**Cause:** Large graph × many hours.

**Fix:** Reduce `--hours`; use `SHADE_SEED_WORKERS=0` for all cores; seed one AOI at a time.

### Wrong AOI selected automatically

**Cause:** Resolution picks **widest** preset containing both points.

**Fix:** If you only bootstrapped `az-phoenix-core`, app falls back to it when wide metro missing. Bootstrap `az-phoenix` for full metro behavior.

---

## Windows-specific

| Issue | Fix |
|-------|-----|
| Path separators | Use `apps\web\.env` or forward slashes in PowerShell |
| Long paths | Clone near drive root (e.g. `C:\dev\UmbraStride`) |
| Firewall | Allow Python and Node on private networks for localhost |

---

## Still stuck?

1. Note **exact error text** from sidebar or browser dev tools (F12 → Network/Console).
2. Check `GET http://127.0.0.1:8000/v1/regions/arizona` — does `bootstrapped_aois` include your AOI?
3. Check files exist: `data/graphs/az-phoenix.graphml`, `data/shade-cache/az-phoenix.sqlite`.
4. Read [Glossary](glossary.md) and [Setup](setup.md).

---

## Diagnostic commands (technical)

```bash
# API health
curl http://127.0.0.1:8000/health

# Arizona manifest + bootstrapped list
curl http://127.0.0.1:8000/v1/regions/arizona | python3 -m json.tool

# Cache coverage
curl "http://127.0.0.1:8000/v1/aoi/az-phoenix/cache/coverage"

# Warm routing cache
curl -X POST http://127.0.0.1:8000/v1/aoi/az-phoenix/routing/warm \
  -H "Content-Type: application/json" \
  -d '{"hours": [10, 11, 12, 13, 14]}'

# List graphs and caches on disk
ls -la data/graphs/
ls -la data/routing-cache/az-phoenix/ 2>/dev/null || echo "routing cache not built yet"
```
