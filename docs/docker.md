# Docker deployment

Run UmbraStride as three containers: **shade-worker**, **API**, and **web** (nginx).

**Prerequisites:** Docker Compose v2, `./data` populated with at least one bootstrapped AOI and shade seed (see [Setup](setup.md)).

---

## Quick start

From repo root:

```bash
# Ensure data exists on host
python scripts/bootstrap_arizona.py --preset az-phoenix
python scripts/seed_demo_cache.py --aoi az-phoenix --hours 10,11,12,13,14

# Optional: copy .env for SHADEMAP_API_KEY (building-aware worker mode)
cp .env.example .env

docker compose build
docker compose up
```

| Service | URL |
|---------|-----|
| Web app | http://localhost:8080 |
| API | http://localhost:8000/health |
| Shade worker | http://localhost:3001/health |

The web container proxies `/api/*` to the API service.

---

## Environment

Pass through from host `.env` or shell:

| Variable | Service | Purpose |
|----------|---------|---------|
| `SHADEMAP_API_KEY` | shade-worker | Enables **building-aware** profiling (Overpass + sun) |
| `SHADE_WORKER_CONCURRENCY` | shade-worker | Parallel profile requests (default 2) |
| `DEFAULT_AOI_ID` | api, web build | Default metro |
| `ROUTING_WARM_ON_STARTUP` | api | Set `1` to warm routing on boot (slow first start) |

Example:

```bash
SHADEMAP_API_KEY=your_key docker compose up --build
```

---

## Volumes

`./data` is mounted read-write into the API container at `/data`:

- `data/graphs/` — street networks  
- `data/shade-cache/` — SQLite shade  
- `data/routing-cache/` — routing performance cache  

Bootstrap and seed on the **host** before `docker compose up`, or exec into the API container.

---

## Shade worker modes

| `SHADEMAP_API_KEY` | Mode | Description |
|--------------------|------|-------------|
| empty | `synthetic` | Demo shade (matches `seed_demo_cache.py` style) |
| set | `building-aware` | OSM buildings via Overpass + SunCalc sun position |

This is **not** full ShadeMap Playwright ray tracing; use `precompute_shade.py` with a running worker for batch cache fills.

---

## Production notes

- Set `ROUTING_WARM_ON_STARTUP=0` in compose unless you accept a long first boot.
- Build web with your public API URL:  
  `docker compose build --build-arg VITE_API_URL=https://api.example.com web`
- Add TLS termination in front of nginx (port 8080).
- Do not commit `.env` with real API keys.

---

## See also

- [Setup guide](setup.md)
- [Configuration](configuration.md)
- [Architecture](architecture.md)
