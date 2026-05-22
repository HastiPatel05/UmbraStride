from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import networkx as nx
from shapely.geometry import LineString, mapping
from shapely.ops import linemerge

from umbrastride_geo.graph import edge_key, iter_edges, load_graph, snap_point_to_graph
from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket


def edge_weight(
    length_m: float,
    shade_fraction: float,
    alpha: float,
    *,
    beta: float | None = None,
) -> float:
    beta = beta if beta is not None else float(os.environ.get("SUN_AVERSION_BETA", "2.0"))
    alpha = max(0.0, min(1.0, alpha))
    l_sun = length_m * (1.0 - shade_fraction)
    l_shade = length_m * shade_fraction
    return alpha * length_m + (1.0 - alpha) * (l_sun * beta + l_shade)


def _build_weighted_graph(
    G: nx.MultiDiGraph,
    store: ShadeStore,
    ts_bucket: str,
    alpha: float,
) -> nx.MultiDiGraph:
    H = nx.MultiDiGraph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, k, length, _geom in iter_edges(G):
        ek = edge_key(u, v, k)
        sf = store.get_fraction(ek, ts_bucket)
        w = edge_weight(length, sf, alpha)
        H.add_edge(u, v, k, weight=w, length_m=length, shade_fraction=sf, edge_key=ek)
    return H


def _path_geometry(G: nx.MultiDiGraph, path: list) -> dict[str, Any] | None:
    lines = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        data = None
        if G.has_edge(u, v):
            # pick lowest weight edge if multi
            edges = G[u][v]
            data = edges[min(edges.keys())]
        if data and data.get("geometry") is not None:
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
        # use longest part
        longest = max(merged.geoms, key=lambda g: g.length)
        return mapping(longest)
    return None


def _route_metrics(G: nx.MultiDiGraph, path: list, ts_bucket: str, store: ShadeStore) -> dict:
    dist = 0.0
    shade_len = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if not G.has_edge(u, v):
            continue
        edges = G[u][v]
        k = min(edges.keys())
        d = edges[k]
        length = float(d.get("length", 0))
        ek = edge_key(u, v, k)
        sf = store.get_fraction(ek, ts_bucket)
        dist += length
        shade_len += length * sf
    shade_fraction = shade_len / dist if dist > 0 else 0.0
    return {"distance_m": round(dist, 1), "shade_fraction": round(shade_fraction, 3)}


def _dijkstra_path(H: nx.MultiDiGraph, origin, dest) -> list | None:
    try:
        return nx.shortest_path(H, origin, dest, weight="weight")
    except nx.NetworkXNoPath:
        return None


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
    G = load_graph(aoi_id)
    store = ShadeStore(aoi_id)
    ts_bucket = floor_ts_bucket(dt)

    origin_node, _ = snap_point_to_graph(G, origin_lng, origin_lat, label="Origin")
    dest_node, _ = snap_point_to_graph(G, dest_lng, dest_lat, label="Destination")

    alphas = compare_alphas if compare_alphas is not None else [1.0, 0.0, alpha]
    # unique preserving order
    seen = set()
    alpha_list = []
    for a in alphas:
        key = round(a, 3)
        if key not in seen:
            seen.add(key)
            alpha_list.append(a)

    routes = []
    shortest_dist = None

    for a in alpha_list:
        H = _build_weighted_graph(G, store, ts_bucket, a)
        path = _dijkstra_path(H, origin_node, dest_node)
        if path is None:
            continue
        metrics = _route_metrics(G, path, ts_bucket, store)
        geom = _path_geometry(G, path)
        label = "custom"
        if a >= 0.999:
            label = "shortest"
        elif a <= 0.001:
            label = "coolest"
        if shortest_dist is None and label == "shortest":
            shortest_dist = metrics["distance_m"]
        detour = (
            metrics["distance_m"] / shortest_dist
            if shortest_dist and shortest_dist > 0
            else 1.0
        )
        routes.append(
            {
                "label": label,
                "alpha": a,
                "geometry": geom,
                "distance_m": metrics["distance_m"],
                "shade_fraction": metrics["shade_fraction"],
                "detour_ratio": round(detour, 3),
                "ts_bucket": ts_bucket,
            }
        )

    return {
        "aoi_id": aoi_id,
        "origin_node": origin_node,
        "dest_node": dest_node,
        "ts_bucket": ts_bucket,
        "routes": routes,
    }
