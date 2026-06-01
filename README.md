# UmbraStride Vercel Demo

Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.

This branch, `vercel-deploy`, contains the bounded Vercel Hobby deployment for UmbraStride. It is intentionally not the full Arizona deployment.

## What This Branch Is

- **Frontend:** Vite app from `apps/web`, served by Vercel.
- **API:** Same-origin FastAPI function in [`api/index.py`](api/index.py), exposed under `/api`.
- **Runtime data:** Compact [`data-vercel/`](data-vercel/) graph artifacts only.
- **Demo AOI:** `az-phoenix-vercel`.
- **Demo bbox:** `[-112.09, 33.465, -112.045, 33.505]`.

The map displays the demo boundary and blocks clicks outside it. The API also rejects route requests outside the packaged bbox. This keeps the demo inside Vercel Hobby limits for bundle size, memory, execution time, response size, and filesystem behavior.

## What This Branch Is Not

This branch does not carry the full project documentation or full Arizona runtime setup. For full Phoenix, statewide Arizona tiles, Docker Compose, shade-worker, bootstrap jobs, and persistent cache deployment, use the `main` branch:

- [Main branch README](https://github.com/HastiPatel05/UmbraStride/blob/main/README.md)
- [Full setup guide](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/setup.md)
- [Arizona coverage](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/arizona.md)
- [Docker deployment](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/docker.md)
- [Routing performance](https://github.com/HastiPatel05/UmbraStride/blob/main/docs/performance.md)

Do not remove the bbox guard from this branch unless the Vercel runtime data is also expanded and the deployment target can handle the extra compute and storage.

## Vercel Settings

Use the repo root as the Vercel project root.

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

## Branch Docs

- [docs/vercel-hobby.md](docs/vercel-hobby.md) - Vercel Hobby deployment details.
- [docs/README.md](docs/README.md) - Short deploy-branch docs index.

## License

- **Code and documentation:** [CC BY-NC 4.0](LICENSE) - non-commercial use only.
- **Commercial use:** Not permitted without prior written permission from the copyright holders.
