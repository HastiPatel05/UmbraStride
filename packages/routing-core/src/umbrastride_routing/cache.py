# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from functools import lru_cache

import networkx as nx
import numpy as np
from umbrastride_geo.aoi import aoi_graph_path, resolve_data_dir
from umbrastride_geo.edge_index import ensure_edge_index, load_edge_index
from umbrastride_geo.graph import load_graph
from umbrastride_geo.sun import NIGHT_UNIFORM_SHADE

from umbrastride_routing.disk_cache import (
    RoutingCacheKey,
    load_routing_digraph,
    save_routing_digraph,
)
from umbrastride_routing.graph_build import build_routing_digraph
from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket

_graph_lock = threading.Lock()
_shade_lock = threading.Lock()
_build_lock = threading.Lock()


def _graph_mtime(aoi_id: str) -> float:
    path = aoi_graph_path(resolve_data_dir(), aoi_id)
    return path.stat().st_mtime if path.exists() else 0.0


def _shade_db_mtime(aoi_id: str) -> float:
    path = resolve_data_dir() / "shade-cache" / f"{aoi_id}.sqlite"
    # SQLite runs in WAL mode, so fresh shade writes may live in the sidecar
    # files before the main DB file is checkpointed. Include them in the cache
    # key so route graphs rebuild after external seed/precompute writes.
    paths = (path, path.with_name(f"{path.name}-wal"), path.with_name(f"{path.name}-shm"))
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


@lru_cache(maxsize=8)
def get_cached_graph(aoi_id: str, mtime: float) -> nx.MultiDiGraph:
    """Load street graph once per AOI until GraphML changes."""
    with _graph_lock:
        return load_graph(aoi_id)


def get_graph(aoi_id: str) -> nx.MultiDiGraph:
    return get_cached_graph(aoi_id, _graph_mtime(aoi_id))


@lru_cache(maxsize=8)
def _edge_index_cached(aoi_id: str, graph_mtime: float) -> tuple[list[str], dict[str, int]]:
    with _graph_lock:
        G = get_cached_graph(aoi_id, graph_mtime)
        loaded = load_edge_index(aoi_id)
        if loaded is not None:
            return loaded
        return ensure_edge_index(G, aoi_id)


@lru_cache(maxsize=32)
def _shade_array_cached(
    aoi_id: str,
    ts_bucket: str,
    db_mtime: float,
    graph_mtime: float,
) -> tuple[str, np.ndarray, bool]:
    """Load shade as a dense float32 array indexed by edge_key order."""
    with _shade_lock:
        _keys, key_to_index = _edge_index_cached(aoi_id, graph_mtime)
        store = ShadeStore(aoi_id)
        return store.resolve_bucket_array(ts_bucket, len(_keys), key_to_index)


def get_shade_map(aoi_id: str, ts_bucket: str) -> tuple[str, dict[str, float], bool]:
    """Return ``(resolved_bucket, shade_map, exact_match)`` (dict view for callers)."""
    gm = _graph_mtime(aoi_id)
    dm = _shade_db_mtime(aoi_id)
    resolved, arr, exact = _shade_array_cached(aoi_id, ts_bucket, dm, gm)
    _keys, _ = _edge_index_cached(aoi_id, gm)
    shade_map = {ek: float(arr[i]) for i, ek in enumerate(_keys) if i < len(arr)}
    return resolved, shade_map, exact


def _shade_array_for_routing(
    aoi_id: str,
    ts_bucket: str,
    graph_mtime: float,
    db_mtime: float,
    *,
    uniform_full_shade: bool,
) -> tuple[str, np.ndarray, bool]:
    resolved, arr, exact = _shade_array_cached(aoi_id, ts_bucket, db_mtime, graph_mtime)
    if uniform_full_shade:
        arr = np.full_like(arr, NIGHT_UNIFORM_SHADE, dtype=np.float32)
    return resolved, arr, exact


@lru_cache(maxsize=16)
def get_routing_digraph(
    aoi_id: str,
    ts_bucket: str,
    graph_mtime: float,
    db_mtime: float,
    alphas_key: tuple[float, ...],
    uniform_full_shade: bool,
) -> nx.DiGraph:
    """Cached collapsed DiGraph with precomputed weights for all requested alphas."""
    resolved_bucket, shade_array, _ = _shade_array_for_routing(
        aoi_id, ts_bucket, graph_mtime, db_mtime, uniform_full_shade=uniform_full_shade
    )
    cache_key = RoutingCacheKey(
        aoi_id=aoi_id,
        graph_mtime=graph_mtime,
        shade_mtime=db_mtime,
        resolved_bucket=resolved_bucket,
        alphas=alphas_key,
        uniform_full_shade=uniform_full_shade,
    )
    cached = load_routing_digraph(cache_key)
    if cached is not None:
        return cached

    with _build_lock:
        cached = load_routing_digraph(cache_key)
        if cached is not None:
            return cached
        G = get_cached_graph(aoi_id, graph_mtime)
        _keys, key_to_index = _edge_index_cached(aoi_id, graph_mtime)
        D = build_routing_digraph(
            G,
            shade_array,
            list(alphas_key),
            edge_key_to_index=key_to_index,
        )
        save_routing_digraph(cache_key, D)
        return D


def get_routing_graph_for_alphas(
    aoi_id: str,
    ts_bucket: str,
    alphas: list[float],
    *,
    uniform_full_shade: bool = False,
) -> tuple[nx.DiGraph, str, bool, bool]:
    """Return routing graph, shade bucket metadata, and whether night uniform shade was applied."""
    gm = _graph_mtime(aoi_id)
    dm = _shade_db_mtime(aoi_id)
    merged = tuple(sorted({0.0, 1.0, *[round(a, 4) for a in alphas]}))
    resolved_bucket, _, exact = _shade_array_for_routing(
        aoi_id, ts_bucket, gm, dm, uniform_full_shade=uniform_full_shade
    )
    D = get_routing_digraph(aoi_id, ts_bucket, gm, dm, merged, uniform_full_shade)
    return D, resolved_bucket, exact, uniform_full_shade


def warm_routing_cache(
    aoi_id: str,
    *,
    ts_buckets: list[str] | None = None,
    alphas: list[float] | None = None,
) -> dict:
    """
    Preload street graph, edge index, shade arrays, and routing DiGraph into RAM/disk cache.
    """
    alpha_list = alphas or [1.0, 0.0, 0.5]
    buckets = ts_buckets
    if buckets is None:
        now = datetime.now(timezone.utc)
        buckets = [floor_ts_bucket(now)]
        warm_hours = os.environ.get("ROUTING_WARM_HOURS", "").strip()
        if warm_hours:
            for part in warm_hours.split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    hour = int(part)
                    buckets.append(
                        floor_ts_bucket(now.replace(hour=hour, minute=0, second=0, microsecond=0))
                    )
                except ValueError:
                    continue
        buckets = list(dict.fromkeys(buckets))

    get_graph(aoi_id)
    gm = _graph_mtime(aoi_id)
    _edge_index_cached(aoi_id, gm)

    warmed: list[str] = []
    for tb in buckets:
        get_routing_graph_for_alphas(aoi_id, tb, alpha_list)
        warmed.append(tb)

    return {"aoi_id": aoi_id, "warmed_buckets": warmed, "alphas": alpha_list}


def clear_caches() -> None:
    get_cached_graph.cache_clear()
    _edge_index_cached.cache_clear()
    _shade_array_cached.cache_clear()
    get_routing_digraph.cache_clear()
