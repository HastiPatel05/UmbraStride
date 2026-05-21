# API

Base URL: `http://localhost:8000`

## `GET /health`

Returns `{ "status": "ok" }`.

## `GET /v1/aoi`

List AOIs with graph on disk.

## `GET /v1/aoi/{aoi_id}/graph`

GeoJSON FeatureCollection of walk edges.

## `GET /v1/aoi/{aoi_id}/cache/coverage`

```json
{
  "aoi_id": "demo",
  "total_edges": 1200,
  "cached_edges": 800,
  "coverage_ratio": 0.67,
  "ts_buckets": ["2026-05-21T10:00", "2026-05-21T11:00"]
}
```

## `POST /v1/aoi/{aoi_id}/cache/warm`

Body:

```json
{
  "datetime": "2026-05-21T12:00:00Z",
  "edge_keys": null
}
```

Triggers shade-worker for cache misses (best-effort).

## `POST /v1/route`

Body:

```json
{
  "aoi_id": "demo",
  "origin": { "lng": 11.58, "lat": 48.137 },
  "destination": { "lng": 11.582, "lat": 48.14 },
  "datetime": "2026-05-21T12:00:00Z",
  "alpha": 0.3
}
```

Response:

```json
{
  "routes": [
    {
      "label": "shortest",
      "alpha": 1.0,
      "geometry": { "type": "LineString", "coordinates": [] },
      "distance_m": 420,
      "shade_fraction": 0.35,
      "detour_ratio": 1.0
    },
    {
      "label": "coolest",
      "alpha": 0.0,
      "geometry": { "type": "LineString", "coordinates": [] },
      "distance_m": 510,
      "shade_fraction": 0.62,
      "detour_ratio": 1.21
    }
  ]
}
```
