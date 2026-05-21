#!/usr/bin/env python3
"""Precompute edge shade fractions via shade-worker and SQLite cache."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

from umbrastride_geo.graph import edge_key, graph_to_geojson, iter_edges, load_graph
from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket


def _worker_profile(points: list[dict], dt_iso: str) -> list[dict]:
    url = os.environ.get("SHADE_WORKER_URL", "http://127.0.0.1:3001") + "/profile"
    payload = json.dumps({"points": points, "datetime": dt_iso}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["results"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", default="demo")
    parser.add_argument("--hours", default="10,11,12,13,14")
    parser.add_argument("--date", default=None)
    parser.add_argument("--chunk", type=int, default=50, help="points per worker request")
    args = parser.parse_args()

    G = load_graph(args.aoi)
    store = ShadeStore(args.aoi)
    day = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hours = [int(h) for h in args.hours.split(",")]

    for hour in hours:
        dt = datetime.fromisoformat(f"{day}T{hour:02d}:00:00+00:00")
        tb = floor_ts_bucket(dt)
        dt_iso = dt.isoformat().replace("+00:00", "Z")

        edge_samples: dict[str, list[tuple[float, float, int]]] = {}
        for u, v, k, length, geom in iter_edges(G):
            ek = edge_key(u, v, k)
            if geom is None:
                continue
            coords = list(geom.coords)
            n = max(5, int(length // 10) + 1)
            samples = []
            for i in range(n):
                t = i / (n - 1) if n > 1 else 0
                idx = min(int(t * (len(coords) - 1)), len(coords) - 2)
                frac = t * (len(coords) - 1) - idx
                lng = coords[idx][0] + frac * (coords[idx + 1][0] - coords[idx][0])
                lat = coords[idx][1] + frac * (coords[idx + 1][1] - coords[idx][1])
                samples.append((lng, lat, i))
            edge_samples[ek] = samples

        all_points = []
        point_meta = []
        for ek, samples in edge_samples.items():
            for lng, lat, idx in samples:
                all_points.append({"lng": lng, "lat": lat})
                point_meta.append((ek, idx))

        shade_by_edge: dict[str, list[bool]] = {ek: [] for ek in edge_samples}
        for i in range(0, len(all_points), args.chunk):
            chunk_pts = all_points[i : i + args.chunk]
            results = _worker_profile(chunk_pts, dt_iso)
            for j, r in enumerate(results):
                ek, _idx = point_meta[i + j]
                shade_by_edge[ek].append(r.get("inShade", False))

        rows = []
        for ek, flags in shade_by_edge.items():
            total = len(edge_samples[ek])
            sf = sum(flags) / total if total else 0.5
            rows.append((ek, tb, sf, total))
        store.bulk_set(rows)
        print(f"Cached {len(rows)} edges for {tb}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
