# UmbraStride documentation

Welcome. This folder explains **what UmbraStride is**, **how to use it**, and **how it works**—whether you write code or just want cooler walking routes in Arizona.

---

## Start here (pick your path)

| I want to… | Read this |
|------------|-----------|
| **Use the web app** (click map, get routes) | [User guide](user-guide.md) |
| **Install and run** on my computer | [Setup guide](setup.md) |
| **Fix something broken** | [Troubleshooting](troubleshooting.md) |
| **Understand words** (AOI, alpha, shade cache…) | [Glossary](glossary.md) |
| **Change settings** (.env files) | [Configuration](configuration.md) |
| **Call the HTTP API** | [API reference](api.md) |
| **Learn how the code is organized** | [Architecture](architecture.md) |
| **Work with Arizona / Phoenix data** | [Arizona coverage](arizona.md) |
| **Understand shade storage & performance** | [Shade cache](shade-cache.md) |
| **See how this relates to the research paper** | [Paper mapping](paper-mapping.md) |

---

## What is UmbraStride? (30 seconds)

UmbraStride helps you plan **walking routes that balance shade and distance**. On a map you set **where you start** and **where you want to go**, pick **date and time** (sun position matters), and adjust a slider between **“stay in shade”** and **“shortest walk”**.

The app shows up to **three routes**:

- **Shortest** — fewest meters, shade ignored.
- **Coolest** — prefers shady sidewalks and streets.
- **Your route** — your slider choice in between.

Behind the scenes it uses **OpenStreetMap** street data, **estimated shade** along each street (cached per time of day), and a standard **shortest-path** algorithm with custom weights—not magic, but the same idea as the [*Walking in the Shade*](https://doi.org/10.1145/3678717.3691287) research paper (SIGSPATIAL 2024).

---

## What you need before routing works

Routing is **not** global by default. Your computer must have **prepared data** for the area you click:

1. A **street network** file (downloaded once per metro area).
2. A **shade cache** file (synthetic demo data is enough to start).

The [Setup guide](setup.md) walks through this for **Phoenix metro (wide)** — `az-phoenix` — which is the current default.

---

## Project layout (high level)

```
UmbraStride/
├── apps/web/          ← Browser map (React + MapLibre)
├── services/api/      ← Backend (Python FastAPI)
├── services/shade-worker/  ← Optional ShadeMap batch jobs
├── packages/geo-core/     ← OSM graphs
├── packages/routing-core/ ← Routing + shade SQLite
├── scripts/           ← Bootstrap & seed commands
├── data/              ← Graphs & cache (created by you)
└── docs/              ← You are here
```

---

## Keeping docs accurate

These docs match the **`tanmay`** branch features as of the latest release:

- **No metro dropdown** — area is chosen automatically from map clicks.
- **Default metro:** `az-phoenix` (wide Phoenix), not downtown-only.
- **Map:** [OpenFreeMap](https://openfreemap.org/) + 3D buildings ([MapLibre example](https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/)).
- **Optional:** live building shadows with a [ShadeMap](https://shademap.app/about/) API key.

If something in the app disagrees with the docs, open an issue or update the doc that was wrong.

---

## Quick links

- [Main README](../README.md)
- [Environment template](../.env.example)
- [Web app env template](../apps/web/.env.example)
- [Arizona region manifest](../data/regions/arizona.json)
