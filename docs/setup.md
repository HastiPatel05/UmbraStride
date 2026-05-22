# Setup and run guide

Commands for **Linux / macOS** (bash) and **Windows** (PowerShell). Run all steps from the repo root (`UmbraStride`).

## Prerequisites

| Tool | Version | Windows install |
|------|---------|-----------------|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) — check **“Add python.exe to PATH”** |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) LTS |
| Git | any | [git-scm.com](https://git-scm.com/download/win) (optional; includes Git Bash) |
| ShadeMap API key | — | [shademap.app/about](https://shademap.app/about/) |

On Windows, use **PowerShell** (recommended) or **Git Bash** for bash-style commands.

---

## 1. Clone and configure

### Linux / macOS

```bash
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout tanmay   # or your branch

cp .env.example .env
cp apps/web/.env.example apps/web/.env
# Edit .env and apps/web/.env — set SHADEMAP_API_KEY / VITE_SHADEMAP_API_KEY
```

### Windows (PowerShell)

```powershell
git clone https://github.com/HastiPatel05/UmbraStride.git
cd UmbraStride
git checkout tanmay

Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env
# Edit with Notepad: notepad .env; notepad apps\web\.env
```

**`.env` (repo root)** — minimum:

```env
SHADEMAP_API_KEY=your_key_here
DEFAULT_AOI_ID=az-phoenix-core
DATA_DIR=./data
```

**`apps\web\.env`** — minimum:

```env
VITE_SHADEMAP_API_KEY=your_key_here
VITE_DEFAULT_AOI=az-phoenix-core
```

---

## 2. Python environment

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

Then install packages:

```powershell
pip install -e "packages/geo-core[dev]" -e "packages/routing-core[dev]" -e "services/api[dev]"
```

---

## 3. Node.js dependencies

Same on all platforms:

```bash
npm install
```

---

## 4. Bootstrap Arizona data

You need a pedestrian graph and shade cache before routing works.

### Quick path — Phoenix downtown (recommended)

**Linux / macOS**

```bash
source .venv/bin/activate
python scripts/bootstrap_arizona.py --preset az-phoenix-core
python scripts/seed_demo_cache.py --aoi az-phoenix-core
```

**Windows (PowerShell)** — with venv activated:

```powershell
python scripts/bootstrap_arizona.py --preset az-phoenix-core
python scripts/seed_demo_cache.py --aoi az-phoenix-core
```

Or use the helper script:

```powershell
.\scripts\seed_arizona.ps1 -Preset az-phoenix-core
```

### All Arizona metros (slow, large download)

**Linux / macOS**

```bash
./scripts/seed_arizona.sh
```

**Windows (PowerShell)**

```powershell
.\scripts\seed_arizona.ps1
# All metros: .\scripts\seed_arizona.ps1 -AllMetros
```

### List available metros

```bash
python scripts/bootstrap_arizona.py --list-presets
```

---

## 5. Run the app

Use **three terminals** (or run API + worker in background).

### Linux / macOS

**Terminal 1 — API**

```bash
cd UmbraStride
source .venv/bin/activate
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Web**

```bash
cd UmbraStride
npm run dev:web
```

**Terminal 3 — Shade worker (optional)**

```bash
cd UmbraStride
npm run dev:worker
```

### Windows (PowerShell)

**Terminal 1 — API**

```powershell
cd UmbraStride
.\.venv\Scripts\Activate.ps1
uvicorn umbrastride_api.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Web**

```powershell
cd UmbraStride
npm run dev:web
```

**Terminal 3 — Shade worker (optional)**

```powershell
cd UmbraStride
npm run dev:worker
```

### Open the app

Browser: **http://localhost:5173**

1. Select **Phoenix downtown (fast)** / `az-phoenix-core` in the sidebar.
2. Click **Origin** or **Destination**, then click the **map** to place points (inside the blue metro box).
3. Set date/time and the cooler ↔ shorter slider.
4. Click **Find routes**.

First route request may take ~5 s (loads graph); later requests are much faster if the API stayed running.

---

## 6. Map shadows (2.5D buildings)

Set `VITE_SHADEMAP_API_KEY` in `apps\web\.env`, restart `npm run dev:web`, zoom to **level 15+**.

---

## 7. Troubleshooting (Windows)

| Issue | Fix |
|-------|-----|
| `python` not found | Reinstall Python with “Add to PATH”, or use `py -3.12` instead of `python` |
| `Activate.ps1` disabled | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `uvicorn` not found | Activate venv first; `pip install uvicorn[standard]` |
| Routing error / no graph | Run bootstrap + seed for `az-phoenix-core`; avoid AOI `demo` in Arizona |
| Map click does nothing | Use sidebar **Origin** / **Destination** buttons, then click the map (not the hint label) |
| API CORS errors | Ensure API runs on port 8000; web proxies `/api` in dev |
| Firewall prompt | Allow Python and Node on private networks for localhost |

---

## Environment variables

See [.env.example](../.env.example) and [shade-cache.md](shade-cache.md) for routing performance options (`ROUTING_DIJKSTRA_WORKERS`, etc.).

---

## More docs

- [Arizona coverage](arizona.md)
- [API](api.md)
- [Paper mapping](paper-mapping.md)
