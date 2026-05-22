from __future__ import annotations

import threading
from functools import lru_cache

import networkx as nx

from umbrastride_geo.aoi import aoi_graph_path, resolve_data_dir
from umbrastride_geo.graph import load_graph
from umbrastride_routing.graph_build import build_routing_digraph
from umbrastride_routing.shade_store import ShadeStore


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
def _shade_map_cached(
    aoi_id: str, ts_bucket: str, db_mtime: float
) -> tuple[str, dict[str, float], bool]:
    """Load shade map; may resolve to nearest cached bucket."""
    with _shade_lock:
        store = ShadeStore(aoi_id)
        return store.resolve_bucket(ts_bucket)


def get_shade_map(aoi_id: str, ts_bucket: str) -> tuple[str, dict[str, float], bool]:
    """Return ``(resolved_bucket, shade_map, exact_match)``."""
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
    resolved_bucket, shade_map, _ = _shade_map_cached(aoi_id, ts_bucket, db_mtime)
    return build_routing_digraph(G, shade_map, list(alphas_key))


def get_routing_graph_for_alphas(
    aoi_id: str, ts_bucket: str, alphas: list[float]
) -> tuple[nx.DiGraph, str, bool]:
    """Return routing graph plus resolved shade bucket metadata."""
    gm = _graph_mtime(aoi_id)
    dm = _shade_db_mtime(aoi_id)
    merged = tuple(sorted({0.0, 1.0, *[round(a, 4) for a in alphas]}))
    resolved_bucket, _, exact = _shade_map_cached(aoi_id, ts_bucket, dm)
    D = get_routing_digraph(aoi_id, ts_bucket, gm, dm, merged)
    return D, resolved_bucket, exact


def clear_caches() -> None:
    get_cached_graph.cache_clear()
    _shade_map_cached.cache_clear()
    get_routing_digraph.cache_clear()
