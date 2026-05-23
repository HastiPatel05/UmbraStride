from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import networkx as nx
from shapely.geometry import LineString, mapping
from shapely.ops import linemerge

from umbrastride_geo.graph import geometry_for_edge_key, snap_point_to_graph
from umbrastride_routing.cache import get_graph, get_routing_graph_for_alphas
from umbrastride_routing.graph_build import alpha_weight_key as _alpha_weight_key
from umbrastride_routing.pathfind import corridor_subgraph, run_shortest_paths_batch
from umbrastride_routing.shade_store import floor_ts_bucket
from umbrastride_routing.weights import edge_weight  # noqa: F401 — re-exported via __init__

_LOCAL_MARGIN_DEG = float(os.environ.get("ROUTING_LOCAL_MARGIN_DEG", "0.012"))


def _edge_route_payload(data: dict[str, Any], weight_attr: str) -> dict[str, Any]:
    return data.get("route_payloads", {}).get(weight_attr, data)


def _path_geometry_from_digraph(
    walk_graph: nx.MultiDiGraph,
    D: nx.DiGraph,
    path: list,
    weight_attr: str,
) -> dict[str, Any] | None:
    lines = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if not D.has_edge(u, v):
            continue
        data = _edge_route_payload(D[u][v], weight_attr)
        ek = data.get("edge_key")
        geom = geometry_for_edge_key(walk_graph, ek) if ek else None
        if geom is not None:
            lines.append(geom)
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


def _route_metrics_digraph(D: nx.DiGraph, path: list, weight_attr: str) -> dict:
    dist = 0.0
    shade_len = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if not D.has_edge(u, v):
            continue
        data = _edge_route_payload(D[u][v], weight_attr)
        length = float(data.get("length_m", 0))
        sf = float(data.get("shade_fraction", 0.5))
        dist += length
        shade_len += length * sf
    shade_fraction = shade_len / dist if dist > 0 else 0.0
    return {"distance_m": round(dist, 1), "shade_fraction": round(shade_fraction, 3)}


def _build_route_result(
    a: float,
    path: list,
    walk_graph: nx.MultiDiGraph,
    D: nx.DiGraph,
    ts_bucket: str,
    shortest_dist: float | None,
) -> tuple[dict, float | None]:
    weight_attr = _alpha_weight_key(a)
    metrics = _route_metrics_digraph(D, path, weight_attr)
    geom = _path_geometry_from_digraph(walk_graph, D, path, weight_attr)
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
    D_local = corridor_subgraph(D, origin_node, dest_node, _LOCAL_MARGIN_DEG)
    paths_by_alpha = run_shortest_paths_batch(D_local, origin_node, dest_node, alpha_list)

    routes = []
    shortest_dist = None
    for a in alpha_list:
        path = paths_by_alpha.get(a)
        if path is None:
            continue
        route, shortest_dist = _build_route_result(a, path, G, D, ts_bucket, shortest_dist)
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
