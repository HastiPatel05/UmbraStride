from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import networkx as nx
from shapely.geometry import LineString, mapping
from shapely.ops import linemerge

from umbrastride_geo.graph import snap_point_to_graph
from umbrastride_routing.cache import get_graph, get_routing_graph_for_alphas
from umbrastride_routing.cpu import worker_count
from umbrastride_routing.graph_build import alpha_weight_key as _alpha_weight_key
from umbrastride_routing.shade_store import floor_ts_bucket
from umbrastride_routing.weights import edge_weight  # noqa: F401 — re-exported via __init__

_LOCAL_MARGIN_DEG = float(os.environ.get("ROUTING_LOCAL_MARGIN_DEG", "0.012"))


def _dijkstra_workers() -> int:
    if os.environ.get("ROUTING_DIJKSTRA_WORKERS", "").strip() not in ("", "0"):
        return worker_count("ROUTING_DIJKSTRA_WORKERS", minimum=1)
    return worker_count("UMBRASTIDE_CPU_WORKERS", minimum=1, cap=32)


def _path_geometry(G: nx.MultiDiGraph, path: list) -> dict[str, Any] | None:
    lines = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if not G.has_edge(u, v):
            continue
        edges = G[u][v]
        data = edges[min(edges.keys())]
        if data.get("geometry") is not None:
            lines.append(data["geometry"])
        elif G.nodes[u].get("x") is not None:
            lines.append(
                LineString(
                    [
                        (G.nodes[u]["x"], G.nodes[u]["y"]),
                        (G.nodes[v]["x"], G.nodes[v]["y"]),
                    ]
                )
            )
    if not lines:
        return None
    merged = linemerge(lines)
    if merged.geom_type == "LineString":
        return mapping(merged)
    if merged.geom_type == "MultiLineString":
        longest = max(merged.geoms, key=lambda g: g.length)
        return mapping(longest)
    return None


def _path_geometry_from_digraph(D: nx.DiGraph, path: list) -> dict[str, Any] | None:
    lines = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if not D.has_edge(u, v):
            continue
        data = D[u][v]
        if data.get("geometry") is not None:
            lines.append(data["geometry"])
        elif D.nodes[u].get("x") is not None:
            lines.append(
                LineString(
                    [
                        (D.nodes[u]["x"], D.nodes[u]["y"]),
                        (D.nodes[v]["x"], D.nodes[v]["y"]),
                    ]
                )
            )
    if not lines:
        return None
    merged = linemerge(lines)
    if merged.geom_type == "LineString":
        return mapping(merged)
    if merged.geom_type == "MultiLineString":
        longest = max(merged.geoms, key=lambda g: g.length)
        return mapping(longest)
    return None


def _route_metrics_digraph(D: nx.DiGraph, path: list) -> dict:
    dist = 0.0
    shade_len = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if not D.has_edge(u, v):
            continue
        data = D[u][v]
        length = float(data.get("length_m", 0))
        sf = float(data.get("shade_fraction", 0.5))
        dist += length
        shade_len += length * sf
    shade_fraction = shade_len / dist if dist > 0 else 0.0
    return {"distance_m": round(dist, 1), "shade_fraction": round(shade_fraction, 3)}


def _local_subgraph(D: nx.DiGraph, origin, dest, margin_deg: float) -> nx.DiGraph:
    if origin not in D or dest not in D:
        return D
    ox, oy = float(D.nodes[origin]["x"]), float(D.nodes[origin]["y"])
    dx, dy = float(D.nodes[dest]["x"]), float(D.nodes[dest]["y"])
    west = min(ox, dx) - margin_deg
    east = max(ox, dx) + margin_deg
    south = min(oy, dy) - margin_deg
    north = max(oy, dy) + margin_deg
    keep = [
        n
        for n, data in D.nodes(data=True)
        if data.get("x") is not None
        and west <= float(data["x"]) <= east
        and south <= float(data["y"]) <= north
    ]
    if origin not in keep:
        keep.append(origin)
    if dest not in keep:
        keep.append(dest)
    return D.subgraph(keep).copy()


def _dijkstra(D: nx.DiGraph, origin, dest, weight_attr: str) -> list | None:
    try:
        return nx.shortest_path(D, origin, dest, weight=weight_attr)
    except nx.NetworkXNoPath:
        return None


def _run_dijkstra_batch(
    D: nx.DiGraph,
    origin_node,
    dest_node,
    alpha_list: list[float],
) -> dict[float, list | None]:
    workers = min(_dijkstra_workers(), len(alpha_list))

    def one(alpha: float) -> tuple[float, list | None]:
        wkey = _alpha_weight_key(alpha)
        return alpha, _dijkstra(D, origin_node, dest_node, wkey)

    if len(alpha_list) <= 1 or workers <= 1:
        return dict(one(a) for a in alpha_list)

    out: dict[float, list | None] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, a): a for a in alpha_list}
        for fut in as_completed(futures):
            alpha, path = fut.result()
            out[alpha] = path
    return out


def _build_route_result(
    a: float,
    path: list,
    D: nx.DiGraph,
    ts_bucket: str,
    shortest_dist: float | None,
) -> tuple[dict, float | None]:
    metrics = _route_metrics_digraph(D, path)
    geom = _path_geometry_from_digraph(D, path)
    label = "custom"
    if a >= 0.999:
        label = "shortest"
    elif a <= 0.001:
        label = "coolest"
    new_shortest = shortest_dist
    if label == "shortest":
        new_shortest = metrics["distance_m"]
    detour = (
        metrics["distance_m"] / new_shortest
        if new_shortest and new_shortest > 0
        else 1.0
    )
    route = {
        "label": label,
        "alpha": a,
        "geometry": geom,
        "distance_m": metrics["distance_m"],
        "shade_fraction": metrics["shade_fraction"],
        "detour_ratio": round(detour, 3),
        "ts_bucket": ts_bucket,
    }
    return route, new_shortest


def compute_routes(
    aoi_id: str,
    origin_lng: float,
    origin_lat: float,
    dest_lng: float,
    dest_lat: float,
    dt: datetime,
    alpha: float,
    *,
    compare_alphas: list[float] | None = None,
) -> dict[str, Any]:
    ts_bucket = floor_ts_bucket(dt)

    G = get_graph(aoi_id)

    origin_node, _ = snap_point_to_graph(G, origin_lng, origin_lat, label="Origin")
    dest_node, _ = snap_point_to_graph(G, dest_lng, dest_lat, label="Destination")

    alphas = compare_alphas if compare_alphas is not None else [1.0, 0.0, alpha]
    seen: set[float] = set()
    alpha_list: list[float] = []
    for a in alphas:
        key = round(a, 3)
        if key not in seen:
            seen.add(key)
            alpha_list.append(a)

    D, shade_ts_bucket, shade_cache_exact = get_routing_graph_for_alphas(
        aoi_id, ts_bucket, alpha_list
    )
    D_local = _local_subgraph(D, origin_node, dest_node, _LOCAL_MARGIN_DEG)
    paths_by_alpha = _run_dijkstra_batch(D_local, origin_node, dest_node, alpha_list)

    routes = []
    shortest_dist = None
    for a in alpha_list:
        path = paths_by_alpha.get(a)
        if path is None:
            continue
        route, shortest_dist = _build_route_result(a, path, D, ts_bucket, shortest_dist)
        routes.append(route)

    return {
        "aoi_id": aoi_id,
        "origin_node": origin_node,
        "dest_node": dest_node,
        "ts_bucket": ts_bucket,
        "shade_ts_bucket": shade_ts_bucket,
        "shade_cache_exact": shade_cache_exact,
        "routes": routes,
    }
