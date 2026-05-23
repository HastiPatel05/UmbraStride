#!/usr/bin/env python3
"""Seed synthetic shade cache for an AOI (no ShadeMap required)."""

from __future__ import annotations

import argparse
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone

from umbrastride_geo.graph import edge_key, iter_edges, load_graph
from umbrastride_geo.sun import NIGHT_UNIFORM_SHADE, is_sun_below_horizon
from umbrastride_routing.cpu import worker_count
from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket


def _synthetic_shade(
    lng: float, lat: float, hour: int, bearing_deg: float | None, *, dt: datetime
) -> float:
    """Mock shade with directional and corridor variation for visible demo routes."""
    if is_sun_below_horizon(dt, lat, lng):
        return NIGHT_UNIFORM_SHADE

    sun_az = 180.0 + (hour - 12) * 15.0
    sun_rad = math.radians(sun_az)
    base = 0.28 + 0.10 * math.cos(math.radians((hour - 12) * 20))

    if bearing_deg is not None:
        seg = math.radians(bearing_deg)
        align = abs(math.cos(seg - sun_rad))
        street_factor = 0.42 * align
    else:
        street_factor = 0.18 * abs(math.sin(math.radians(lng * 1000 + lat * 1000)))

    corridor = 0.22 * math.sin((lng + 112.08) * 9500 + hour * 0.7)
    cross_street = 0.18 * math.cos((lat - 33.45) * 11000 - hour * 0.4)

    return max(0.04, min(0.96, base + street_factor + corridor + cross_street))


def _serialize_edges(G) -> list[tuple]:
    rows = []
    for u, v, k, _length, geom in iter_edges(G):
        ek = edge_key(u, v, k)
        if geom is None:
            rows.append((ek, None, None, None))
        else:
            mid = geom.interpolate(0.5, normalized=True)
            coords = list(geom.coords)
            if len(coords) >= 2:
                dx = coords[-1][0] - coords[0][0]
                dy = coords[-1][1] - coords[0][1]
                bearing = (math.degrees(math.atan2(dx, dy)) + 360) % 360
            else:
                bearing = None
            rows.append((ek, mid.x, mid.y, bearing))
    return rows


def _hour_rows(args: tuple) -> list[tuple]:
    """Worker: build shade rows for one hour bucket."""
    hour, day, edge_rows = args
    dt = datetime.fromisoformat(f"{day}T{hour:02d}:00:00+00:00")
    tb = floor_ts_bucket(dt)
    out = []
    for ek, lng, lat, bearing in edge_rows:
        if lng is None:
            sf = 0.5
        else:
            sf = _synthetic_shade(lng, lat, hour, bearing, dt=dt)
        out.append((ek, tb, sf, 5))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", default="demo")
    parser.add_argument("--hours", default="10,11,12,13,14")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD UTC (default today)")
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="parallel hour workers (0 = all CPU cores)",
    )
    args = parser.parse_args()

    if args.workers > 0:
        os.environ["SHADE_SEED_WORKERS"] = str(args.workers)

    G = load_graph(args.aoi)
    store = ShadeStore(args.aoi)
    day = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hours = [int(h) for h in args.hours.split(",")]

    edge_rows = _serialize_edges(G)
    n_workers = worker_count("SHADE_SEED_WORKERS", minimum=1)
    n_workers = min(n_workers, len(hours)) if hours else 1

    rows: list[tuple] = []
    tasks = [(h, day, edge_rows) for h in hours]
    if n_workers <= 1:
        for t in tasks:
            rows.extend(_hour_rows(t))
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(_hour_rows, t) for t in tasks]
            for fut in as_completed(futures):
                rows.extend(fut.result())

    store.bulk_set(rows)
    print(
        f"Seeded {len(rows)} edge shade records for aoi '{args.aoi}' "
        f"({len(hours)} hours, {n_workers} workers)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
