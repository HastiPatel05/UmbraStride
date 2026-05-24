# Research paper mapping

UmbraStride is **inspired by** peer-reviewed work on shadow-aware pedestrian navigation. This page connects the paper to what the software actually does today—useful for students, researchers, and curious users.

**Citation:** Yu Feng, Yingqiao Zhang, Yuxin Xue, Jingyi Chen, Song Gao, [*Walking in the Shade: Shadow-oriented Navigation for Pedestrians*](https://doi.org/10.1145/3678717.3691287), ACM SIGSPATIAL 2024.

---

## What the paper proposes (simple summary)

On hot sunny days, the **shortest walk** may expose you to more sun. The paper builds a **pedestrian street network**, estimates **which parts of each street are shady** at a given time (using detailed 3D city models and shadow simulation), then finds paths that trade off **walking distance** vs **staying in shade** based on user preference.

---

## Paper vs UmbraStride v1

| Paper (Munich-focused) | UmbraStride (Arizona-focused) |
|------------------------|-------------------------------|
| Manually corrected OSM pedestrian network | OSMnx automatic `network_type=walk` + optional GeoJSON overrides |
| LoD2 3D city models | OSM / OpenFreeMap building heights |
| Ray-tracing-style shadow simulation | Local geometric shadows + **cached** edge shade fractions |
| User preference cooler ↔ shorter | **Alpha slider** 0 (shade) → 1 (short) |
| 3D scene verification | MapLibre 2D/2.5D map + optional live shadow layer |
| Single study area workflow | **Metro presets** + optional statewide grid tiles |

UmbraStride is **not** a reproduction of the Munich pipeline. It is a **practical open-source stack** with similar routing mathematics and a different data pipeline.

---

## Routing weight model (shared idea)

For each street segment with length `L` and shade fraction `S` (0 = sunny, 1 = full shade):

```
L_sun   = L × (1 - S)
L_shade = L × S
b       = (1 - α) ^ γ
weight  = (1 - b) × L + b × (L_sun × β + L_shade × ε)
```

| Symbol | Meaning | Default in UmbraStride |
|--------|---------|------------------------|
| `α` | User preference | Slider 0–1; also fixed routes at 0 and 1 |
| `β` | Sun aversion | `SUN_AVERSION_BETA=5` in `.env` |
| `ε` | Shaded-distance tie-break | `SHADE_DISTANCE_TIEBREAK=0.001` in `.env` |
| `γ` | Shade-bias curve | `SHADE_BIAS_CURVE=3` in `.env` |
| `S` | Shade fraction along edge | From SQLite cache or 0.5 default |

**Shortest path:** `α = 1` → weight = `L`.  
**Most shade-friendly:** `α = 0` → minimize sunny distance first; shaded distance only breaks ties.
Middle slider values use the curve so they remain visibly between shortest and most-shaded instead of saturating too early.

Algorithm: **Dijkstra** on a directed graph minimizing sum of edge weights.

Implementation: `packages/routing-core/src/umbrastride_routing/weights.py`.

---

## Shade data: paper vs app

| Aspect | Paper | UmbraStride |
|--------|-------|-------------|
| Geometry | High-detail building models | OSM footprints + heights (tiles / Overpass) |
| Simulation | Custom ray tracing | Local SunCalc + geometric projection |
| Storage | Paper-specific | SQLite per AOI + time bucket |
| Demo without 3D | N/A | `seed_demo_cache.py` synthetic shade |

For scientific comparison with the paper, treat **building-aware precomputed cache** as the closest mode; treat **demo seed** as a functional placeholder only.

---

## What UmbraStride adds for practitioners

- **OpenStreetMap** global street ingest (OSMnx).
- **Arizona metro presets** and automatic AOI resolution from map clicks.
- **REST API** + web UI for non-programmers (after setup).
- **Performance** caches, parallel Dijkstra, local subgraph cropping—see [Shade cache](shade-cache.md).

---

## What we do not claim

- UmbraStride routes are **not certified** for medical heat exposure.
- Shade fractions are **approximate** unless properly precomputed.
- **Not validated** against the paper’s Munich experiments.

---

## Further reading in this repo

- [Architecture](architecture.md) — software design  
- [Shade cache](shade-cache.md) — data pipeline  
- [User guide](user-guide.md) — using the slider and reading routes  

---

## Citing UmbraStride

If you use this software in academic work, cite the **original paper** for the shadow-routing concept and describe UmbraStride as an open implementation with OSM building footprints and local solar geometry. Check the repo LICENSE (MIT) for code attribution.
