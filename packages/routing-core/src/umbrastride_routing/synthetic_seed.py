# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
"""Synthetic shade cache seeding (no ShadeMap) — used by API and seed_demo_cache.py."""

from __future__ import annotations

import math
import threading
from datetime import datetime, timezone
from typing import Any

from umbrastride_geo.edge_index import load_edge_index
from umbrastride_geo.graph import edge_key, iter_edges
from umbrastride_geo.sun import (
    NIGHT_UNIFORM_SHADE,
    ensure_utc,
    sun_altitude_deg,
    sun_azimuth_deg,
)

from umbrastride_routing.cache import clear_caches, get_graph
from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket

_seed_lock = threading.Lock()
_seed_in_progress: set[str] = set()
_seed_locks: dict[str, threading.Lock] = {}


def _bucket_lock(key: str) -> threading.Lock:
    with _seed_lock:
        lock = _seed_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _seed_locks[key] = lock
        return lock


def synthetic_shade_fraction(
    lng: float,
    lat: float,
    bearing_deg: float | None,
    *,
    dt: datetime,
) -> float:
    dt = ensure_utc(dt)
    altitude = sun_altitude_deg(dt, lat, lng)
    if altitude <= 0:
        return NIGHT_UNIFORM_SHADE

    sun_az = sun_azimuth_deg(dt, lat, lng)
    sun_rad = math.radians(sun_az)
    utc_hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    altitude_factor = 1.0 - min(max(altitude, 0.0), 75.0) / 75.0
    base = 0.18 + 0.22 * altitude_factor

    if bearing_deg is not None:
        seg = math.radians(bearing_deg)
        align = abs(math.cos(seg - sun_rad))
        street_factor = 0.42 * align
    else:
        street_factor = 0.18 * abs(math.sin(math.radians(lng * 1000 + lat * 1000)))

    corridor = 0.20 * math.sin((lng + 112.08) * 9500 + sun_rad * 1.7 + utc_hour * 0.03)
    cross_street = 0.16 * math.cos((lat - 33.45) * 11000 - sun_rad * 1.3)

    return max(0.04, min(0.96, base + street_factor + corridor + cross_street))


def _bucket_dt(dt: datetime) -> datetime:
    """Align to the 15-minute bucket used by routing."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    tb = floor_ts_bucket(dt)
    return datetime.fromisoformat(f"{tb}:00+00:00")


def _expected_edge_count(aoi_id: str) -> int:
    loaded = load_edge_index(aoi_id)
    if loaded is not None:
        keys, _ = loaded
        if keys:
            return len(keys)
    G = get_graph(aoi_id)
    return sum(1 for _ in iter_edges(G))


def bucket_coverage_fraction(aoi_id: str, ts_bucket: str) -> float:
    """Fraction of graph edges that have shade for ``ts_bucket`` (0–1)."""
    n_edges = _expected_edge_count(aoi_id)
    if n_edges == 0:
        return 0.0
    store = ShadeStore(aoi_id)
    cached = store.count_bucket_edges(ts_bucket)
    return cached / n_edges


def build_synthetic_rows_for_bucket(
    aoi_id: str,
    dt: datetime,
) -> tuple[str, list[tuple[str, str, float, int]]]:
    """Build bulk_set rows for one time bucket."""
    dt = _bucket_dt(dt)
    tb = floor_ts_bucket(dt)
    G = get_graph(aoi_id)
    rows: list[tuple[str, str, float, int]] = []

    for u, v, k, _length, geom in iter_edges(G):
        ek = edge_key(u, v, k)
        if geom is None:
            sf = 0.5
        else:
            mid = geom.interpolate(0.5, normalized=True)
            coords = list(geom.coords)
            if len(coords) >= 2:
                dx = coords[-1][0] - coords[0][0]
                dy = coords[-1][1] - coords[0][1]
                bearing = (math.degrees(math.atan2(dx, dy)) + 360) % 360
            else:
                bearing = None
            sf = synthetic_shade_fraction(mid.x, mid.y, bearing, dt=dt)
        rows.append((ek, tb, sf, 5))

    return tb, rows


def ensure_synthetic_shade_bucket(
    aoi_id: str,
    dt: datetime,
    *,
    force: bool = False,
    min_coverage: float = 0.9,
) -> dict[str, Any]:
    """
    Ensure synthetic shade exists for the routing time bucket.

    Skips work when coverage is already >= ``min_coverage`` unless ``force`` is True.
    """
    dt = _bucket_dt(dt)
    tb = floor_ts_bucket(dt)
    coverage = bucket_coverage_fraction(aoi_id, tb)
    if not force and coverage >= min_coverage:
        return {
            "aoi_id": aoi_id,
            "ts_bucket": tb,
            "seeded": False,
            "coverage": round(coverage, 3),
            "edge_rows": 0,
        }

    key = f"{aoi_id}:{tb}"
    with _bucket_lock(key):
        coverage = bucket_coverage_fraction(aoi_id, tb)
        if not force and coverage >= min_coverage:
            return {
                "aoi_id": aoi_id,
                "ts_bucket": tb,
                "seeded": False,
                "coverage": round(coverage, 3),
                "edge_rows": 0,
            }

        _tb, rows = build_synthetic_rows_for_bucket(aoi_id, dt)
        store = ShadeStore(aoi_id)
        store.bulk_set(rows)

    clear_caches()

    return {
        "aoi_id": aoi_id,
        "ts_bucket": tb,
        "seeded": True,
        "coverage": 1.0,
        "edge_rows": len(rows),
    }


def schedule_synthetic_shade_seed(aoi_id: str, dt: datetime) -> dict[str, Any]:
    """
    Non-blocking: return immediately; seed in a background thread if the bucket is missing.

    Routing should proceed without waiting for the seed to finish.
    """
    dt = _bucket_dt(dt)
    tb = floor_ts_bucket(dt)
    coverage = bucket_coverage_fraction(aoi_id, tb)
    if coverage >= 0.9:
        return {
            "aoi_id": aoi_id,
            "ts_bucket": tb,
            "scheduled": False,
            "coverage": round(coverage, 3),
        }

    key = f"{aoi_id}:{tb}"
    with _seed_lock:
        if key in _seed_in_progress:
            return {
                "aoi_id": aoi_id,
                "ts_bucket": tb,
                "scheduled": False,
                "coverage": round(coverage, 3),
                "status": "already_running",
            }
        _seed_in_progress.add(key)

    def _worker() -> None:
        try:
            ensure_synthetic_shade_bucket(aoi_id, dt)
        finally:
            with _seed_lock:
                _seed_in_progress.discard(key)

    threading.Thread(target=_worker, name=f"shade-seed-{key}", daemon=True).start()
    return {
        "aoi_id": aoi_id,
        "ts_bucket": tb,
        "scheduled": True,
        "coverage": round(coverage, 3),
    }
