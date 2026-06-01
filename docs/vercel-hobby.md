# Vercel Hobby Demo Deployment

This page documents the `vercel-deploy` branch. It is a constrained Vercel Hobby deployment, not the full Arizona deployment.

For the full project deployment, use the `main` branch docs:

- [Setup guide](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/setup.md)
- [Arizona coverage](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/arizona.md)
- [Docker guide](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/docker.md)
- [Routing performance](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/performance.md)

## What This Branch Deploys

| Part | Vercel demo behavior |
|------|----------------------|
| Web app | Vite frontend from `apps/web` |
| API | Same-origin FastAPI function in `api/index.py` |
| API base URL | `/api` |
| Default AOI | `az-phoenix-vercel` |
| Runtime data | Small committed artifacts under `data-vercel/` |
| Full `data/` volume | Not included |
| Shade worker | Not included |
| Bootstrap/warm jobs | Disabled or unsupported |

The Vercel branch exists to show a real Phoenix route demo without requiring a VPS, Docker Compose, or a large persistent data volume.

## Why The Map Has A Bounding Box

The live demo only packages this AOI:

```txt
az-phoenix-vercel
[-112.09, 33.465, -112.045, 33.505]
```

That bbox is intentionally small because Vercel Hobby is a serverless target with limited compute, memory, duration, bundle size, response payload size, and no normal persistent writable filesystem. A full Phoenix or statewide Arizona graph requires much larger street-network data, shade cache data, routing cache data, and background work.

Because only this bbox is packaged:

- The map displays an outlined demo boundary.
- Map clicks outside the outlined boundary are blocked.
- Place search is constrained to the demo bbox.
- `POST /api/v1/route` rejects origin/destination points outside the bbox.
- The API returns routes only for `az-phoenix-vercel`.

This prevents users from selecting points that the Vercel runtime cannot route.

## Why This Is Different From `main`

The `main` branch is the source of truth for the complete deployment model:

- Full FastAPI service under `services/api`
- Shade worker under `services/shade-worker`
- Bootstrap scripts for Arizona presets and tiles
- Persistent `data/` volume
- Graph, shade-cache, and routing-cache artifacts
- Docker Compose deployment docs
- Statewide Arizona tile documentation

This `vercel-deploy` branch keeps only enough runtime data and code to make the Vercel Hobby demo reliable.

## Vercel Settings

Use the repo root as the Vercel project root because the deployment needs both `apps/web` and `api/index.py`.

| Setting | Value |
|---------|-------|
| Framework preset | Vite |
| Root directory | Repo root |
| Install command | `npm install` |
| Build command | `npm run build -w @umbrastride/web` |
| Output directory | `apps/web/dist` |
| Production branch | `vercel-deploy` |

Environment variables:

```env
VITE_API_URL=/api
VITE_DEFAULT_AOI=az-phoenix-vercel
DEFAULT_AOI_ID=az-phoenix-vercel
DATA_DIR=./data-vercel
AUTO_SHADE_SEED=0
ROUTING_DISK_CACHE=0
ROUTING_WARM_ON_STARTUP=0
```

## Operational Rule

Keep `data-vercel/` compact. Do not commit the full `data/` directory, routing-cache files, or shade SQLite databases to this branch. If the demo bbox expands, re-check Vercel bundle size, function memory, function duration, and route response payload size before deploying.
