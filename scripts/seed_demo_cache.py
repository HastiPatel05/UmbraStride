#!/usr/bin/env python3
"""Seed synthetic shade cache for an AOI (no ShadeMap required)."""

from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime, timedelta, timezone

from umbrastride_geo.graph import edge_key, iter_edges, load_graph
from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket


def _synthetic_shade(lng: float, lat: float, hour: int) -> float:
    # Higher shade on streets aligned E-W (mock building shadows from south)
    sun_az = (hour - 12) * 15.0
    base = 0.35 + 0.25 * math.cos(math.radians(sun_az))
    street_factor = 0.2 * abs(math.sin(math.radians(lng * 1e5)))
    return max(0.05, min(0.95, base + street_factor))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", default="demo")
    parser.add_argument("--hours", default="10,11,12,13,14")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD UTC (default today)")
    args = parser.parse_args()

    G = load_graph(args.aoi)
    store = ShadeStore(args.aoi)
    day = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hours = [int(h) for h in args.hours.split(",")]

    rows = []
    for hour in hours:
        dt = datetime.fromisoformat(f"{day}T{hour:02d}:00:00+00:00")
        tb = floor_ts_bucket(dt)
        for u, v, k, _length, geom in iter_edges(G):
            ek = edge_key(u, v, k)
            if geom is None:
                sf = 0.5
            else:
                mid = geom.interpolate(0.5, normalized=True)
                sf = _synthetic_shade(mid.x, mid.y, hour)
            rows.append((ek, tb, sf, 5))

    store.bulk_set(rows)
    print(f"Seeded {len(rows)} edge shade records for aoi '{args.aoi}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
