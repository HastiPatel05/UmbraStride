# Paper mapping

Reference: [Walking in the Shade: Shadow-oriented Navigation for Pedestrians](https://doi.org/10.1145/3678717.3691287) (Feng, Zhang, Xue, Chen, Meng — SIGSPATIAL 2024).

## Paper vs UmbraStride v1

| Paper component | UmbraStride |
|-----------------|-------------|
| Manually corrected OSM pedestrian network | OSMnx `network_type=walk` + optional `data/overrides/{aoi_id}.geojson` |
| LoD2 3D city models (Munich) | OSM building footprints + heights via ShadeMap / Overpass |
| Ray tracing shadow simulation | ShadeMap browser simulator + cached edge shade fractions |
| Cooler vs shorter user preference | `alpha` slider: 0 = max shade, 1 = shortest distance |
| 3D scene verification | 2D MapLibre map + live shadow layer (3D deferred) |

UmbraStride is **inspired by** the paper, not a reproduction of the Munich LoD2 pipeline.

## Routing weight model

For edge length `l` and shade fraction `S ∈ [0,1]`:

- `l_sun = l * (1 - S)`
- `l_shade = l * S`
- `weight = alpha * l + (1 - alpha) * (l_sun * beta + l_shade)` with `beta = SUN_AVERSION_BETA` (default 2)

Dijkstra minimizes total weight → paths favor shade when `alpha` is low.
