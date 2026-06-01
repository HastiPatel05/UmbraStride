# Setup and run guide

Complete instructions to install UmbraStride, prepare Arizona data, **warm performance caches**, and run the map app.

Commands are given for **Linux / macOS (bash)** and **Windows (PowerShell)**.

**Not technical?** After setup, read the [User guide](user-guide.md).  
**Stuck?** See [Troubleshooting](troubleshooting.md).  
**Slow routing?** See [Routing performance](performance.md).

---

## What you are installing

| Part | What it does | Port |
|------|----------------|------|
| **Web** | Map in your browser | 5173 |
| **API** | Computes routes, warms caches on startup | 8000 |
| **Shade worker** (optional) | Batch shade profiling | 3001 |

You also download **street data** once per metro (**bootstrap**) and **shade data** (**seed**) before routing works correctly.

---

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| **Python** | 3.11+ | API, routing, scripts |
| **Node.js** | 20+ | Web app, optional worker |
| **Git** | any | Clone repo |
| **Internet** | — | OSM, map tiles, optional Overpass |
| **Disk** | ~2 GB+ | Phoenix metro graph + cache |

### Windows

- Python: [python.org/downloads](https://www.python.org/downloads/) — enable **Add to PATH**
- Node: [nodejs.org](https://nodejs.org/) LTS
- Use **PowerShell** or Git Bash

### Optional: building-aware precompute

Set `SHADE_PROFILE_MODE=building-aware` if you want worker precompute to use OSM building footprints from Overpass + SunCalc. Live map shadows do not need an API key.

---

## 1. Get the code

### Linux / macOS

```bash
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout main
git pull
```

### Windows (PowerShell)

```powershell
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout main
git pull
```

---

## 2. Configure environment files

Two env files (copy examples, then edit).

### Linux / macOS

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env
```

### Windows (PowerShell)

```powershell
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env
notepad .env
notepad apps\web\.env
```

### Minimum root `.env`

```env
DATA_DIR=./data
DEFAULT_AOI_ID=az-phoenix
SUN_AVERSION_BETA=5.0
SHADE_DISTANCE_TIEBREAK=0.001
SHADE_BIAS_CURVE=3.0
SNAP_MAX_DIST_M=1200

# Performance (included in .env.example — recommended)
ROUTING_DISK_CACHE=1
ROUTING_WARM_ON_STARTUP=1
# Phoenix local 5 AM-7 PM, expressed as UTC buckets
ROUTING_WARM_HOURS=12,13,14,15,16,17,18,19,20,21,22,23,0,1,2
ROUTING_PATH_ENGINE=rustworkx
ROUTING_USE_ASTAR=1
```

Full reference: [Configuration](configuration.md).

### Minimum `apps/web/.env`

```env
VITE_DEFAULT_AOI=az-phoenix
```

Live building shadows use local SunCalc and building footprints; no browser shadow key is needed.

---

## 3. Python environment

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"
```

This installs **rustworkx** (fast shortest-path). If you see import errors later: `pip install rustworkx`.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Prompt should show `(.venv)`.

---

## 4. Node.js dependencies

From repo root:

```bash
npm install
```

---

## 5. Bootstrap Arizona data

**Bootstrap** = download walkable OSM streets and save graph files.  
**Seed** = fill shade SQLite so coolest ≠ shortest routes.

### Recommended: Phoenix metro (wide)

Covers Phoenix, Tempe, Scottsdale. Matches app default `az-phoenix`.

```bash
source .venv/bin/activate   # if not already
python scripts/bootstrap_arizona.py --preset az-phoenix
# 5 AM-7 PM UTC
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 5,6,7,8,9,10,11,12,13,14,15,16,17,18,19
# 5 AM-7 PM Phoenix local (MST / UTC-7)
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 12,13,14,15,16,17,18,19,20,21,22,23,0,1,2
```

**Windows:** same commands with venv activated.

`--date` defaults to today's UTC date, and `--hours` is always UTC. For a pinned Phoenix-local date with `--date YYYY-MM-DD`, seed `12..23` on the local date and `0..2` on the next UTC date if you need exact date alignment.

**Creates:**

| File | Purpose |
|------|---------|
| `data/graphs/az-phoenix.graphml` | Street network (source) |
| `data/graphs/az-phoenix.graph.pkl` | Fast reload cache |
| `data/graphs/az-phoenix.edge-index.json` | Shade vectorization index |
| `data/graphs/az-phoenix.meta.json` | Metadata |
| `data/shade-cache/az-phoenix.sqlite` | Shade per street × hour |

Bootstrap may take **several minutes** and hundreds of MB.

### Quick dev: downtown only

```bash
python scripts/bootstrap_arizona.py --preset az-phoenix-core
python scripts/seed_demo_cache.py --aoi az-phoenix-core --hours 12,13,14,15,16,17,18,19,20,21,22,23,0,1,2
```

Set `DEFAULT_AOI_ID=az-phoenix-core` and `VITE_DEFAULT_AOI=az-phoenix-core` if you use this as default.

### Verify bootstrap + seed

```bash
ls data/graphs/az-phoenix.graphml
ls data/graphs/az-phoenix.graph.pkl
ls data/shade-cache/az-phoenix.sqlite
```

### Other metros

```bash
python scripts/bootstrap_arizona.py --list-presets
python scripts/bootstrap_arizona.py --preset az-tucson
python scripts/seed_demo_cache.py --aoi az-tucson --hours 12,13,14,15,16,17,18,19,20,21,22,23,0,1,2
```

Details: [Arizona coverage](arizona.md).

### Night shade buckets

If you already have Phoenix streets and day shade, pull the latest code, ensure **astral** is installed (used for sun-below-horizon in the seed script), then add **night hours** to the same SQLite file:

```bash
git pull origin main
source .venv/bin/activate
pip install -e packages/geo-core   # pulls in astral
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 20,21,22,23,0,1,2,3,4,5
```

Restart the API (or call `POST /v1/aoi/az-phoenix/routing/warm` with those hours) so in-memory caches pick up the new buckets. See [Day vs night routing](README.md#day-vs-night-routing-important).

---

## 6. Run the app

Use **two terminals** (three with shade worker).

### Terminal 1 — API

```bash
cd UmbraStride
npm run dev:api
```

This starts Uvicorn from the repo `.venv` on **http://127.0.0.1:8000**. For local development it defaults `ROUTING_WARM_ON_STARTUP=0`, so the API can answer `/health` immediately instead of blocking while routing caches warm.

To change the port, use `API_PORT=8001 npm run dev:api` and start the web app with `VITE_API_URL=http://127.0.0.1:8001 npm run dev:web`.

**On startup** (when `ROUTING_WARM_ON_STARTUP=1`): API preloads `DEFAULT_AOI_ID` graph and routing cache. First run after seed may take **minutes** while `data/routing-cache/` is populated. Keep it off for normal UI work and warm manually before demos.

Test:

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok"}
```

### Terminal 2 — Web

```bash
cd UmbraStride
npm run dev:web
```

Open **http://localhost:5173**

If the Vite terminal prints `http proxy error: /v1/regions/arizona` with `ECONNREFUSED 127.0.0.1:8000`, Terminal 1 is not running or is on a different port. Start `npm run dev:api`, confirm `curl http://127.0.0.1:8000/health`, then refresh the page.

### Terminal 3 — Shade worker (optional)

Only for `precompute_shade.py` or shade `cache/warm` — not required for demo seed.

```bash
npm run dev:worker
```

---

## 7. Warm routing cache (recommended before demo)

After API is up, optionally warm explicit hours:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/aoi/az-phoenix/routing/warm \
  -H "Content-Type: application/json" \
  -d '{"hours": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0, 1, 2]}' | python3 -m json.tool
```

For 5 AM-7 PM UTC instead, use `[5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]`.

Verify routing cache files:

```bash
ls data/routing-cache/az-phoenix/
```

Deep dive: [Routing performance](performance.md).

---

## 8. Use the app

No metro dropdown — area is chosen from map clicks.

1. Click **Origin**, then the map (green).
2. Click **Destination**, then the map (red).
3. Sidebar shows **Active area** (e.g. Phoenix metro wide).
4. Set **date & time** to a **seeded hour** (e.g. 12:00 on your seed date).
5. Adjust **shade ↔ short** slider.
6. Click **Find routes**.

Walkthrough: [User guide](user-guide.md).

### Map tips

- Zoom **15+** for 3D buildings ([OpenFreeMap](https://openfreemap.org/)).
- Pick a daytime morning or late-afternoon time for longer **live shadows**.

---

## 9. Optional: building-aware precompute

```bash
# Terminals: API + worker running
source .venv/bin/activate
python scripts/precompute_shade.py --aoi az-phoenix --hours 12,13,14,15,16,17,18,19,20,21,22,23,0,1,2
```

Set `SHADE_PROFILE_MODE=building-aware` in `.env` for Overpass + SunCalc precompute. See [Shade cache](shade-cache.md).

---

## 10. Run tests (developers)

```bash
source .venv/bin/activate
python -m pytest packages/geo-core/tests packages/routing-core/tests services/api/tests -q
cd apps/web && npm run lint
```

---

## End-to-end checklist

Use this to confirm a working install:

- [ ] `.venv` active; packages installed (including rustworkx)
- [ ] `.env` and `apps/web/.env` copied and edited
- [ ] `data/graphs/az-phoenix.graphml` exists
- [ ] `data/shade-cache/az-phoenix.sqlite` exists
- [ ] API `/health` returns ok
- [ ] Web opens at :5173
- [ ] `data/routing-cache/az-phoenix/` has `.routing.pkl` after warm or first route
- [ ] Three routes differ (orange / teal / purple) at seeded datetime

---

## Quick reference — npm scripts

| Command | Purpose |
|---------|---------|
| `npm run dev:web` | Web :5173 |
| `npm run dev:worker` | Worker :3001 |
| `npm run dev:api` | API :8000, using repo `.venv` |

---

## Scripts cheat sheet

| Command | Purpose |
|---------|---------|
| `python scripts/bootstrap_arizona.py --preset az-phoenix` | Download streets |
| `python scripts/seed_demo_cache.py --aoi az-phoenix --hours 5,6,7,8,9,10,11,12,13,14,15,16,17,18,19` | Synthetic shade, 5 AM-7 PM UTC |
| `python scripts/seed_demo_cache.py --aoi az-phoenix --hours 12,13,14,15,16,17,18,19,20,21,22,23,0,1,2` | Synthetic shade, 5 AM-7 PM Phoenix local |
| [Night shade update](setup.md#night-shade-buckets) | `git pull origin main` + `pip install -e packages/geo-core` + night seed |
| `curl -X POST .../routing/warm` | Preload routing cache |
| `docker compose up` | API + worker + web on :8080 — [Docker](docker.md) |
| `python scripts/bootstrap_arizona.py --list-presets` | List metros |

---

## Optional: Docker Compose

```bash
docker compose build
docker compose up
```

Open http://localhost:8080 — full guide: [Docker](docker.md).

---

## More documentation

| Doc | Topic |
|-----|--------|
| [Documentation index](README.md) | All guides |
| [Routing performance](performance.md) | Caches, warm, disk artifacts |
| [Docker guide](docker.md) | Container deployment |
| [User guide](user-guide.md) | Using the map |
| [Troubleshooting](troubleshooting.md) | Fixes |
| [Configuration](configuration.md) | Env vars |
| [API](api.md) | HTTP endpoints |
