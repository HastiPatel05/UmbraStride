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
| **Shade worker** (optional) | Real ShadeMap batch profiling | 3001 |

You also download **street data** once per metro (**bootstrap**) and **shade data** (**seed**) before routing works correctly.

---

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| **Python** | 3.11+ | API, routing, scripts |
| **Node.js** | 20+ | Web app, optional worker |
| **Git** | any | Clone repo |
| **Internet** | — | OSM, map tiles, optional ShadeMap |
| **Disk** | ~2 GB+ | Phoenix metro graph + cache |

### Windows

- Python: [python.org/downloads](https://www.python.org/downloads/) — enable **Add to PATH**
- Node: [nodejs.org](https://nodejs.org/) LTS
- Use **PowerShell** or Git Bash

### Optional: ShadeMap API key

[shademap.app/about](https://shademap.app/about/) — for **live shadows** on the map and **real** shade precompute. **Not** required for demo routing with synthetic seed.

---

## 1. Get the code

### Linux / macOS

```bash
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout tanmay   # or your branch
git pull
```

### Windows (PowerShell)

```powershell
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout tanmay
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
SNAP_MAX_DIST_M=1200

# Performance (included in .env.example — recommended)
ROUTING_DISK_CACHE=1
ROUTING_WARM_ON_STARTUP=1
ROUTING_WARM_HOURS=10,11,12,13,14
ROUTING_PATH_ENGINE=rustworkx
ROUTING_USE_ASTAR=1
```

Full reference: [Configuration](configuration.md).

### Minimum `apps/web/.env`

```env
VITE_DEFAULT_AOI=az-phoenix
```

Add `VITE_SHADEMAP_API_KEY=...` for live building shadows.

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
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14 --date 2026-05-22
```

**Windows:** same commands with venv activated.

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
python scripts/seed_demo_cache.py --aoi az-phoenix-core --hours 10,11,12,13,14
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
python scripts/seed_demo_cache.py --aoi az-tucson --hours 10,11,12,13,14
```

Details: [Arizona coverage](arizona.md).

---

## 6. Run the app

Use **two terminals** (three with shade worker).

### Terminal 1 — API

```bash
cd UmbraStride
source .venv/bin/activate   # Linux/macOS
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

**Windows:**

```powershell
cd UmbraStride
.\.venv\Scripts\Activate.ps1
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

**On startup** (when `ROUTING_WARM_ON_STARTUP=1`): API preloads `DEFAULT_AOI_ID` graph and routing cache. First run after seed may take **minutes** while `data/routing-cache/` is populated.

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

### Terminal 3 — Shade doc worker (optional)

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
  -d '{"hours": [10, 11, 12, 13, 14]}' | python3 -m json.tool
```

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
- Add `VITE_SHADEMAP_API_KEY` and restart web for **live shadows**.

---

## 9. Optional: real ShadeMap precompute

```bash
# Terminals: API + worker running
source .venv/bin/activate
python scripts/precompute_shade.py --aoi az-phoenix --hours 10,11,12,13,14
```

Requires `SHADEMAP_API_KEY` in `.env`. See [Shade cache](shade-cache.md).

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
| `npm run dev:api` | API (alternative to uvicorn) |

---

## Scripts cheat sheet

| Command | Purpose |
|---------|---------|
| `python scripts/bootstrap_arizona.py --preset az-phoenix` | Download streets |
| `python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14` | Synthetic shade |
| `curl -X POST .../routing/warm` | Preload routing cache |
| `python scripts/bootstrap_arizona.py --list-presets` | List metros |

---

## More documentation

| Doc | Topic |
|-----|--------|
| [Documentation index](README.md) | All guides |
| [Routing performance](performance.md) | Caches, warm, disk artifacts |
| [User guide](user-guide.md) | Using the map |
| [Troubleshooting](troubleshooting.md) | Fixes |
| [Configuration](configuration.md) | Env vars |
| [API](api.md) | HTTP endpoints |
