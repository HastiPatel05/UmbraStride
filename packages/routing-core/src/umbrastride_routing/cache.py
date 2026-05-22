from __future__ import annotations

import os
import sqlite3
import threading
from functools import lru_cache
from typing import Any

import networkx as nx

from umbrastride_geo.aoi import aoi_graph_path, resolve_data_dir
from umbrastride_geo.graph import load_graph
from umbrastride_routing.graph_build import build_routing_digraph


_graph_lock = threading.Lock()
_shade_lock = threading.Lock()


def _graph_mtime(aoi_id: str) -> float:
    path = aoi_graph_path(resolve_data_dir(), aoi_id)
    return path.stat().st_mtime if path.exists() else 0.0


@lru_cache(maxsize=8)
def get_cached_graph(aoi_id: str, mtime: float) -> nx.MultiDiGraph:
    """Load GraphML once per AOI until the file changes."""
    with _graph_lock:
        return load_graph(aoi_id)


def get_graph(aoi_id: str) -> nx.MultiDiGraph:
    return get_cached_graph(aoi_id, _graph_mtime(aoi_id))


@lru_cache(maxsize=32)
def _shade_map_cached(aoi_id: str, ts_bucket: str, db_mtime: float) -> dict[str, float]:
    path = resolve_data_dir() / "shade-cache" / f"{aoi_id}.sqlite"
    if not path.exists():
        return {}
    with _shade_lock:
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                """
                SELECT edge_key, shade_fraction FROM edge_shade
                WHERE aoi_id = ? AND ts_bucket = ?
                """,
                (aoi_id, ts_bucket),
            ).fetchall()
    return {ek: float(sf) for ek, sf in rows}


def get_shade_map(aoi_id: str, ts_bucket: str) -> dict[str, float]:
    path = resolve_data_dir() / "shade-cache" / f"{aoi_id}.sqlite"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _shade_map_cached(aoi_id, ts_bucket, mtime)


def _shade_db_mtime(aoi_id: str) -> float:
    path = resolve_data_dir() / "shade-cache" / f"{aoi_id}.sqlite"
    return path.stat().st_mtime if path.exists() else 0.0


@lru_cache(maxsize=16)
def get_routing_digraph(
    aoi_id: str,
    ts_bucket: str,
    graph_mtime: float,
    db_mtime: float,
    alphas_key: tuple[float, ...],
) -> nx.DiGraph:
    """Cached collapsed DiGraph with precomputed weights for all requested alphas."""
    G = get_cached_graph(aoi_id, graph_mtime)
    shade_map = _shade_map_cached(aoi_id, ts_bucket, db_mtime)
    return build_routing_digraph(G, shade_map, list(alphas_key))


def get_routing_graph_for_alphas(aoi_id: str, ts_bucket: str, alphas: list[float]) -> nx.DiGraph:
    gm = _graph_mtime(aoi_id)
    dm = _shade_db_mtime(aoi_id)
    # Always include 0 and 1 so cache hits across requests
    merged = tuple(sorted({0.0, 1.0, *[round(a, 4) for a in alphas]}))
    return get_routing_digraph(aoi_id, ts_bucket, gm, dm, merged)


def clear_caches() -> None:
    get_cached_graph.cache_clear()
    _shade_map_cached.cache_clear()
    get_routing_digraph.cache_clear()
