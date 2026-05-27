# Glossary

Plain-language definitions for terms used in UmbraStride docs and the app.

---

## A

**Alpha (α)** — A number from **0 to 1** on the preference slider. **0** means “optimize for shade (coolest walk).” **1** means “shortest distance only.” **0.35** is a typical middle value. The app also computes fixed routes at 0 and 1 for comparison.

**AOI (Area of Interest)** — A named geographic box where UmbraStride has (or will have) a street network and shade data. Examples: `az-phoenix` (wide Phoenix), `az-tucson`. You do not pick this from a menu anymore—the app **infers** it from your origin and destination.

**API** — The backend program that answers HTTP requests (routes, graphs, health). Runs on port **8000** by default. The web app talks to it automatically in development.

---

## B

**Bootstrap** — The one-time process of **downloading OpenStreetMap streets** for an AOI and saving them as a graph file on disk. Command: `python scripts/bootstrap_arizona.py --preset az-phoenix`. Can take minutes for large areas.

**Bbox (bounding box)** — Four numbers defining a rectangle on the map: west, south, east, north (longitude/latitude). Each Arizona metro preset has a bbox.

---

## C

**Cache (shade cache)** — A SQLite database file storing **how shady each street segment is** at different times of day. Without it, every street is treated as equally sunny/shady and coolest ≈ shortest.

**Coolest route** — The path that minimizes “discomfort in the sun,” not the shortest path. Shown in **teal** on the map.

**Custom route** — The path for **your slider** alpha value. Shown in **purple**.

---

## D

**Detour ratio** — How much longer a route is compared to the shortest route. **1.0** = same length. **1.15** = 15% longer. Cooler routes often have a higher detour ratio.

**Dijkstra** — A classic algorithm that finds a minimum-cost path on a network. UmbraStride uses it on the walk graph with different “costs” per shade preference.

---

## E

**Edge** — One street segment in the graph (between two intersections). Shade is stored **per edge**.

**Edge key** — Unique ID for one directed street segment, e.g. `123|456|0`. Used in shade SQLite and for geometry lookup on the final path.

**Edge index** — File `data/graphs/{aoi}.edge-index.json` listing all edge keys in order so shade loads as a fast numeric array.

---

## G

**Graph (street graph)** — Walkable streets and connections. Stored as GraphML; fast reload via `graph.pkl`.

---

## M

**MapLibre** — The open-source map library that draws the basemap, 3D buildings, and your routes in the browser.

**Metro preset** — A predefined AOI for a city region (Phoenix wide, Tucson, Flagstaff, …). Listed in `data/regions/arizona.json`.

---

## O

**OpenFreeMap** — Free vector map tiles used for the basemap and **3D building extrusions** in the web app.

**OpenStreetMap (OSM)** — Community-maintained map of the world; UmbraStride downloads **pedestrian** streets from OSM.

**Origin / Destination** — Green and red points you place on the map (start and end of the walk).

---

## P

**Pickle graph (`graph.pkl`)** — A binary copy of the street graph saved next to GraphML. The API loads this first because it is much faster than parsing XML.

**Preset** — Same idea as a metro AOI (e.g. `az-phoenix`). See [Arizona coverage](arizona.md).

---

## R

**Render height** — Building height from map tiles for 3D blocks and shadow simulation.

**Routing cache** — Files under `data/routing-cache/{aoi}/` storing a pre-built weighted street graph for a shade time bucket. Avoids rebuilding on every cold API start.

**Routing warm** — Preloading graph + shade + routing cache via API startup or `POST /v1/aoi/{id}/routing/warm`. See [Routing performance](performance.md).

**Route** — Path along streets from origin to destination with distance and shade statistics.

**rustworkx** — Fast graph library (Rust) used for shortest-path when `ROUTING_PATH_ENGINE=rustworkx`.

---

## S

**Seed (shade seed)** — Filling the shade cache with data. **Demo seed** uses synthetic shade. **Precompute** can use the shade worker in synthetic or building-aware mode.

**Shade fraction** — For one street segment, the fraction of sample points **in shade** at a given time (0 = full sun, 1 = full shade). **50% shade** means half the segment length is shady on average.

**Shade worker** — Optional Node service that profiles shade for many points using synthetic or building-aware logic.

**Shortest route** — Minimum distance path; shade ignored. Shown in **orange**.

**Snap** — Moving your clicked point to the **nearest walkable street** node so routing can start. If you click too far from any street, you get an error.

**Sun aversion (beta)** — Environment variable `SUN_AVERSION_BETA` (default **5**). Higher values make sunny street segments “cost” more when you prefer shade.

**Shade-bias curve** — Environment variable `SHADE_BIAS_CURVE` (default **3**). It keeps middle slider values from behaving like the extreme 100% shade setting.

**Sun below horizon** — When the sun has set at a location. If true at **both** route endpoints, UmbraStride uses **uniform full shade** (S = 1) so coolest and shortest paths match. API field: `sun_below_horizon`.

---

## T

**Tile (grid tile)** — Small fixed cells covering all of Arizona for advanced statewide coverage. Hundreds of tiles; bootstrap on demand. See [Arizona coverage](arizona.md).

**Time bucket (`ts_bucket`)** — Shade data is stored per **15-minute** UTC window, e.g. `2026-05-22T12:00`. When automatic local shade is enabled, route requests sync the selected bucket before computing and the API background sync refreshes roughly every 10 minutes.

---

## W

**Worker (shade worker)** — Optional Node service used by `precompute_shade.py`, not required for demo routing.

---

## Symbols on the map

| Color | Meaning |
|-------|---------|
| Green dot | Origin |
| Red dot | Destination |
| Orange line | Shortest route |
| Teal line | Coolest route |
| Purple line | Your preference route |
| Blue outline | Active metro area (AOI bbox) |
| Gray 3D blocks | Buildings (zoom 15+) |
| Dark overlay | Live shadows (zoom 15+) |
