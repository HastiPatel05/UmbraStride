# Setup and run guide

Complete instructions to install UmbraStride on your machine and run the map app. Commands are given for **Linux / macOS (bash)** and **Windows (PowerShell)**.

**Not technical?** After setup, read the [User guide](user-guide.md) for how to use the map.  
**Stuck?** See [Troubleshooting](troubleshooting.md).

---

## What you are installing

UmbraStride is not a single “app installer.” It is three small programs that work together:

| Part | What it does | Port |
|------|----------------|------|
| **Web** | Map in your browser | 5173 |
| **API** | Computes routes | 8000 |
| **Shade worker** (optional) | Fills real shade data via ShadeMap | 3001 |

You also download **street data** once per city region (“bootstrap”) and **shade data** (“seed”) before routing works.

---

## Prerequisites

| Tool | Version | Why you need it |
|------|---------|-----------------|
| **Python** | 3.11+ | API, routing, bootstrap scripts |
| **Node.js** | 20+ | Web app and optional shade worker |
| **Git** | any | Clone the repository |
| **Internet** | — | OSM download, map tiles, optional ShadeMap |

### Windows installs

- Python: [python.org/downloads](https://www.python.org/downloads/) — enable **“Add python.exe to PATH.”**
- Node: [nodejs.org](https://nodejs.org/) LTS installer.
- Use **PowerShell** (recommended) or Git Bash.

### Optional: ShadeMap API key

- Free key: [shademap.app/about](https://shademap.app/about/)
- Needed for **live shadow overlay** on the map and for **real** shade precompute—not for demo routing with synthetic seed.

---

## 1. Get the code

### Linux / macOS

```bash
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout tanmay   # or your branch
```

### Windows (PowerShell)

```powershell
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout tanmay
```

---

## 2. Configure environment files

You need **two** env files (copy examples, then edit).

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

### Minimum `.env` (repo root)

```env
DATA_DIR=./data
DEFAULT_AOI_ID=az-phoenix
SUN_AVERSION_BETA=2.0
SNAP_MAX_DIST_M=1200
```

Add `SHADEMAP_API_KEY=...` if you use the shade worker or precompute.

Full list: [Configuration reference](configuration.md).

### Minimum `apps/web/.env`

```env
VITE_DEFAULT_AOI=az-phoenix
```

Add `VITE_SHADEMAP_API_KEY=...` for live building shadows on the map.

---

## 3. Python environment

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Install packages:

```powershell
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"
```

**Tip:** Your shell prompt should show `(.venv)` when active.

---

## 4. Node.js dependencies

From repo root (all platforms):

```bash
npm install
```

---

## 5. Bootstrap Arizona data

**Bootstrap** = download walkable streets from OpenStreetMap and save a graph file.

**Seed** = fill shade database so coolest ≠ shortest routes.

### Recommended: Phoenix metro (wide)

Covers Phoenix, Tempe, Scottsdale (~25 km). Larger download than downtown-only; matches current app default.

**Linux / macOS** (venv active):

```bash
python scripts/bootstrap_arizona.py --preset az-phoenix
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14
```

**Windows** (venv active):

```powershell
python scripts/bootstrap_arizona.py --preset az-phoenix
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14
```

Or:

```powershell
.\scripts\seed_arizona.ps1 -Preset az-phoenix
```

**Expect:** Bootstrap may take **several minutes** and hundreds of MB disk for `az-phoenix`. Downtown-only `az-phoenix-core` is faster for quick tests:

```bash
python scripts/bootstrap_arizona.py --preset az-phoenix-core
python scripts/seed_demo_cache.py --aoi az-phoenix-core
```

### Verify files exist

```bash
ls data/graphs/az-phoenix.graphml
ls data/shade-cache/az-phoenix.sqlite
```

### Other metros

```bash
python scripts/bootstrap_arizona.py --list-presets
python scripts/bootstrap_arizona.py --preset az-tucson
python scripts/seed_demo_cache.py --aoi az-tucson --hours 10,11,12,13,14
```

### All metros (long)

```bash
./scripts/seed_arizona.sh          # Linux/macOS
.\scripts\seed_arizona.ps1 -AllMetros   # Windows
```

Details: [Arizona coverage](arizona.md).

---

## 6. Run the app

Use **two terminals** minimum (three if using shade worker).

### Terminal 1 — API

**Linux / macOS:**

```bash
cd UmbraStride
source .venv/bin/activate
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

**Windows:**

```powershell
cd UmbraStride
.\.venv\Scripts\Activate.ps1
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

Leave running. Test: open `http://127.0.0.1:8000/health` → `{"status":"ok"}`.

### Terminal 2 — Web

```bash
cd UmbraStride
npm run dev:web
```

Open **http://localhost:5173**

### Terminal 3 — Shade worker (optional)

Only for `precompute_shade.py` or API cache warm—not required for demo seed.

```bash
npm run dev:worker
```

---

## 7. Use the app

The UI **no longer has a metro dropdown**. The active area is chosen from your map clicks.

1. Click **Origin**, then click the map (green dot).
2. Click **Destination**, then click the map (red dot).
3. Confirm sidebar shows **Active area: Phoenix metro (wide)** (or another bootstrapped metro).
4. Set **date & time** (use hours you seeded, e.g. noon).
5. Adjust **shade ↔ short** slider.
6. Click **Find routes**.

Full walkthrough: [User guide](user-guide.md).

### Map tips

- Zoom **15+** for 3D buildings ([OpenFreeMap](https://openfreemap.org/) + [MapLibre 3D example](https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/)).
- Add `VITE_SHADEMAP_API_KEY` and restart web for **live shadows**.

---

## 8. Optional: real ShadeMap precompute

```bash
# Terminals: API, worker, then:
source .venv/bin/activate
python scripts/precompute_shade.py --aoi az-phoenix --hours 10,11,12,13,14
```

Requires `SHADEMAP_API_KEY` in `.env` and worker running. See [Shade cache](shade-cache.md).

---

## 9. Run tests (developers)

```bash
source .venv/bin/activate
python -m pytest packages/geo-core/tests packages/routing-core/tests -q
cd apps/web && npm run lint
```

---

## Quick reference — npm scripts

| Command | Purpose |
|---------|---------|
| `npm run dev:web` | Start Vite dev server (port 5173) |
| `npm run dev:worker` | Start shade worker (port 3001) |
| `npm run dev:api` | Start API (alternative to uvicorn command) |

---

## Environment variables

See [Configuration reference](configuration.md) and [`.env.example`](../.env.example).

---

## More documentation

| Doc | Topic |
|-----|--------|
| [Documentation index](README.md) | All guides |
| [User guide](user-guide.md) | Using the map |
| [Troubleshooting](troubleshooting.md) | Fixes |
| [Glossary](glossary.md) | Terms |
| [API](api.md) | HTTP endpoints |
| [Architecture](architecture.md) | Code structure |

---

## Platform-specific issues

See [Troubleshooting — Windows](troubleshooting.md#windows-specific) and the tables in [Troubleshooting](troubleshooting.md).
