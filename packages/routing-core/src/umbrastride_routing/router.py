from __future__ import annotations

import math
import os
from datetime import datetime
from typing import Any

import networkx as nx
from shapely.geometry import LineString, mapping

from umbrastride_geo.graph import geometry_for_edge_key, snap_point_to_graph
from umbrastride_geo.sun import is_route_at_night
from umbrastride_routing.cache import get_graph, get_routing_graph_for_alphas
from umbrastride_routing.graph_build import alpha_weight_key as _alpha_weight_key
from umbrastride_routing.pathfind import corridor_subgraph, run_shortest_paths_batch
from umbrastride_routing.shade_store import floor_ts_bucket
from umbrastride_routing.weights import edge_weight  # noqa: F401 — re-exported via __init__

_LOCAL_MARGIN_DEG = float(os.environ.get("ROUTING_LOCAL_MARGIN_DEG", "0.012"))


def _edge_route_payload(data: dict[str, Any], weight_attr: str) -> dict[str, Any]:
    return data.get("route_payloads", {}).get(weight_attr, data)


def _append_path_coords(coords: list[tuple[float, float]], segment: list[tuple[float, float]]) -> None:
    """Append segment vertices, skipping duplicates at joins."""
    if not segment:
        return
    if not coords:
        coords.extend(segment)
        return
    last = coords[-1]
    for pt in segment:
        if abs(pt[0] - last[0]) > 1e-9 or abs(pt[1] - last[1]) > 1e-9:
            coords.append(pt)
            last = pt


def _orient_segment_toward(
    segment: list[tuple[float, float]],
    from_xy: tuple[float, float],
    to_xy: tuple[float, float],
) -> list[tuple[float, float]]:
    """Ensure segment runs from ``from_xy`` toward ``to_xy`` (graph edge direction)."""
    if len(segment) < 2:
        return segment
    d0_from = (segment[0][0] - from_xy[0]) ** 2 + (segment[0][1] - from_xy[1]) ** 2
    d1_from = (segment[-1][0] - from_xy[0]) ** 2 + (segment[-1][1] - from_xy[1]) ** 2
    if d1_from < d0_from:
        segment = list(reversed(segment))
    return segment


def _path_geometry_from_digraph(
    walk_graph: nx.MultiDiGraph,
    D: nx.DiGraph,
    path: list,
    weight_attr: str,
) -> dict[str, Any] | None:
    """Build a single LineString following path order (never drop disconnected segments)."""
    coords: list[tuple[float, float]] = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if not D.has_edge(u, v):
            continue
        data = _edge_route_payload(D[u][v], weight_attr)
        ek = data.get("edge_key")
        geom = geometry_for_edge_key(walk_graph, ek) if ek else None
        if geom is not None:
            ux, uy = float(walk_graph.nodes[u]["x"]), float(walk_graph.nodes[u]["y"])
            vx, vy = float(walk_graph.nodes[v]["x"]), float(walk_graph.nodes[v]["y"])
            segment = _orient_segment_toward(list(geom.coords), (ux, uy), (vx, vy))
        elif D.nodes[u].get("x") is not None and D.nodes[v].get("x") is not None:
            segment = [
                (float(D.nodes[u]["x"]), float(D.nodes[u]["y"])),
                (float(D.nodes[v]["x"]), float(D.nodes[v]["y"])),
            ]
        else:
            continue
        _append_path_coords(coords, segment)

    if len(coords) < 2:
        return None
    return mapping(LineString(coords))


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


<<<<<<< HEAD
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
    geom = _path_geometry_from_digraph(
        walk_graph,
        D,
        path,
        weight_attr,
    )
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
=======
def _great_circle_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    radius_m = 6_371_009.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    )
    return radius_m * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _heuristic_weight_floor(alpha: float) -> float:
    beta = float(os.environ.get("SUN_AVERSION_BETA", "2.0"))
    return min(1.0, alpha + (1.0 - alpha) * beta)


def _astar_path(H: nx.MultiDiGraph, origin, dest, alpha: float) -> list | None:
    dest_data = H.nodes[dest]
    dest_x = float(dest_data["x"])
    dest_y = float(dest_data["y"])
    weight_floor = _heuristic_weight_floor(alpha)

    def heuristic(node, _target) -> float:
        data = H.nodes[node]
        if data.get("x") is None or data.get("y") is None:
            return 0.0
        return (
            _great_circle_m(float(data["x"]), float(data["y"]), dest_x, dest_y)
            * weight_floor
        )

    try:
        return nx.astar_path(H, origin, dest, heuristic=heuristic, weight="weight")
    except nx.NetworkXNoPath:
        return None
>>>>>>> d56812eca50b80859697d402931616e3e63ba03c


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

    origin_node, origin_snap_dist_m = snap_point_to_graph(G, origin_lng, origin_lat, label="Origin")
    dest_node, dest_snap_dist_m = snap_point_to_graph(G, dest_lng, dest_lat, label="Destination")

    alphas = compare_alphas if compare_alphas is not None else [1.0, 0.0, alpha]
    seen: set[float] = set()
    alpha_list: list[float] = []
    for a in alphas:
        key = round(a, 3)
        if key not in seen:
            seen.add(key)
            alpha_list.append(a)

    sun_below_horizon = is_route_at_night(dt, origin_lat, origin_lng, dest_lat, dest_lng)

    D, shade_ts_bucket, shade_cache_exact, _ = get_routing_graph_for_alphas(
        aoi_id,
        ts_bucket,
        alpha_list,
        uniform_full_shade=sun_below_horizon,
    )
    D_local = corridor_subgraph(D, origin_node, dest_node, _LOCAL_MARGIN_DEG)
    paths_by_alpha = run_shortest_paths_batch(D_local, origin_node, dest_node, alpha_list)

    routes = []
    shortest_dist = None
    for a in alpha_list:
<<<<<<< HEAD
        path = paths_by_alpha.get(a)
=======
        H = _build_weighted_graph(G, store, ts_bucket, a)
        path = _astar_path(H, origin_node, dest_node, a)
>>>>>>> d56812eca50b80859697d402931616e3e63ba03c
        if path is None:
            continue
        route, shortest_dist = _build_route_result(
            a,
            path,
            G,
            D,
            ts_bucket,
            shortest_dist,
        )
        routes.append(route)

    origin_node_data = G.nodes[origin_node]
    dest_node_data = G.nodes[dest_node]

    return {
        "aoi_id": aoi_id,
        "origin_node": origin_node,
        "dest_node": dest_node,
        "origin_snapped": {
            "lng": float(origin_node_data["x"]),
            "lat": float(origin_node_data["y"]),
            "distance_m": round(origin_snap_dist_m, 1),
        },
        "destination_snapped": {
            "lng": float(dest_node_data["x"]),
            "lat": float(dest_node_data["y"]),
            "distance_m": round(dest_snap_dist_m, 1),
        },
        "ts_bucket": ts_bucket,
        "shade_ts_bucket": shade_ts_bucket,
        "shade_cache_exact": shade_cache_exact,
        "sun_below_horizon": sun_below_horizon,
        "routes": routes,
    }
