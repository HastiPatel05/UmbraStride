from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import networkx as nx
import numpy as np
import rustworkx as rx

from umbrastride_routing.cpu import worker_count
from umbrastride_routing.graph_build import alpha_weight_key
from umbrastride_routing.weights import shade_bias_for_alpha


def _path_engine() -> str:
    return os.environ.get("ROUTING_PATH_ENGINE", "rustworkx").strip().lower()


def _use_astar() -> bool:
    return os.environ.get("ROUTING_USE_ASTAR", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _dijkstra_workers() -> int:
    if os.environ.get("ROUTING_DIJKSTRA_WORKERS", "").strip() not in ("", "0"):
        return worker_count("ROUTING_DIJKSTRA_WORKERS", minimum=1)
    return worker_count("UMBRASTIDE_CPU_WORKERS", minimum=1, cap=32)


def _node_xy(D: nx.DiGraph, node: Any) -> tuple[float, float]:
    data = D.nodes[node]
    return float(data["x"]), float(data["y"])


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Approximate great-circle distance in meters (WGS84 mean radius)."""
    r = 6_371_000.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return float(2 * r * np.arcsin(np.sqrt(a)))


def _alpha_from_weight_attr(weight_attr: str) -> float | None:
    if not weight_attr.startswith("w_"):
        return None
    try:
        return max(0.0, min(1.0, float(weight_attr[2:])))
    except ValueError:
        return None


def _formula_min_ratio(weight_attr: str) -> float | None:
    alpha = _alpha_from_weight_attr(weight_attr)
    if alpha is None:
        return None
    beta = float(os.environ.get("SUN_AVERSION_BETA", "5.0"))
    shade_tiebreak = float(os.environ.get("SHADE_DISTANCE_TIEBREAK", "0.001"))
    shade_bias = shade_bias_for_alpha(alpha)
    distance_bias = 1.0 - shade_bias
    return distance_bias + shade_bias * min(beta, shade_tiebreak)


def _heuristic_scale(D: nx.DiGraph, weight_attr: str) -> float:
    """Scale straight-line distance so A* heuristic stays admissible for positive weights."""
    samples: list[float] = []
    for _u, _v, data in D.edges(data=True):
        length = float(data.get("length_m", data.get("length", 0)) or 0)
        weight = float(data.get(weight_attr, length) or 0)
        if length > 0 and weight > 0:
            samples.append(weight / length)
        if len(samples) >= 256:
            break
    if not samples:
        return _formula_min_ratio(weight_attr) or 1.0
    scale = float(min(samples))
    formula_min = _formula_min_ratio(weight_attr)
    return min(scale, formula_min) if formula_min is not None else scale


def _build_rx_index(D: nx.DiGraph) -> tuple[rx.PyDiGraph, dict[Any, int], list[Any]]:
    index: dict[Any, int] = {}
    nodes: list[Any] = []
    for node in D.nodes:
        index[node] = len(nodes)
        nodes.append(node)
    graph = rx.PyDiGraph()
    for node in nodes:
        attrs = dict(D.nodes[node])
        attrs["label"] = node
        graph.add_node(attrs)
    for u, v, data in D.edges(data=True):
        graph.add_edge(index[u], index[v], data)
    return graph, index, nodes


def shortest_path(
    D: nx.DiGraph,
    origin: Any,
    dest: Any,
    weight_attr: str,
) -> list[Any] | None:
    if origin not in D or dest not in D:
        return None
    if _path_engine() == "networkx":
        try:
            return nx.shortest_path(D, origin, dest, weight=weight_attr)
        except nx.NetworkXNoPath:
            return None

    rx_graph, index, nodes = _build_rx_index(D)
    oi, di = index[origin], index[dest]
    dest_xy = _node_xy(D, dest)
    scale = _heuristic_scale(D, weight_attr) if _use_astar() else 0.0

    def edge_cost(edge_obj: dict) -> float:
        return float(edge_obj.get(weight_attr, edge_obj.get("length_m", 1.0)))

    try:
        if _use_astar() and scale > 0:

            def goal_fn(node_data: dict) -> bool:
                return node_data.get("label") == dest

            def estimate_fn(node_data: dict) -> float:
                if node_data.get("x") is None:
                    return 0.0
                x, y = float(node_data["x"]), float(node_data["y"])
                return _haversine_m(x, y, dest_xy[0], dest_xy[1]) * scale

            path_idx = list(
                rx.digraph_astar_shortest_path(
                    rx_graph,
                    oi,
                    goal_fn,
                    edge_cost,
                    estimate_fn,
                )
            )
        else:
            paths = rx.digraph_dijkstra_shortest_paths(
                rx_graph,
                oi,
                target=di,
                weight_fn=edge_cost,
            )
            if di not in paths:
                return None
            path_idx = list(paths[di])
    except rx.NoPathFound:
        return None

    if not path_idx:
        return None
    return [nodes[i] for i in path_idx]


def corridor_subgraph(
    D: nx.DiGraph,
    origin: Any,
    dest: Any,
    margin_deg: float,
) -> nx.DiGraph:
    """Crop to an origin–destination corridor; expand margin until a path exists."""
    if origin not in D or dest not in D:
        return D

    scales_env = os.environ.get("ROUTING_CORRIDOR_SCALES", "0.6,1.0,1.6,3.0")
    try:
        scales = [float(s.strip()) for s in scales_env.split(",") if s.strip()]
    except ValueError:
        scales = [0.6, 1.0, 1.6, 3.0]
    if not scales:
        scales = [1.0]

    ox, oy = _node_xy(D, origin)
    dx, dy = _node_xy(D, dest)
    seg_len = max(_haversine_m(ox, oy, dx, dy), 1.0)

    for scale in scales:
        margin = margin_deg * scale
        west = min(ox, dx) - margin
        east = max(ox, dx) + margin
        south = min(oy, dy) - margin
        north = max(oy, dy) + margin
        # Perpendicular corridor: nodes near the OD segment or inside the bbox
        keep: list[Any] = []
        for n, data in D.nodes(data=True):
            if data.get("x") is None:
                continue
            x, y = float(data["x"]), float(data["y"])
            if not (west <= x <= east and south <= y <= north):
                continue
            # Distance from point to segment in degree space (cheap proxy)
            vx, vy = dx - ox, dy - oy
            wx, wy = x - ox, y - oy
            seg_sq = vx * vx + vy * vy
            t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_sq)) if seg_sq else 0.0
            proj_x, proj_y = ox + t * vx, oy + t * vy
            along_m = _haversine_m(ox, oy, proj_x, proj_y)
            cross_m = _haversine_m(x, y, proj_x, proj_y)
            cross_limit = max(margin * 111_000.0 * 0.85, seg_len * 0.35 * scale)
            if cross_m <= cross_limit or along_m <= seg_len * 0.05:
                keep.append(n)

        if origin not in keep:
            keep.append(origin)
        if dest not in keep:
            keep.append(dest)
        sub = D.subgraph(keep).copy()
        try:
            nx.has_path(sub, origin, dest)
            if nx.has_path(sub, origin, dest):
                return sub
        except nx.NetworkXError:
            continue

    return D


def run_shortest_paths_batch(
    D: nx.DiGraph,
    origin: Any,
    dest: Any,
    alpha_list: list[float],
) -> dict[float, list[Any] | None]:
    workers = min(_dijkstra_workers(), len(alpha_list))

    def one(alpha: float) -> tuple[float, list[Any] | None]:
        wkey = alpha_weight_key(alpha)
        return alpha, shortest_path(D, origin, dest, wkey)

    if len(alpha_list) <= 1 or workers <= 1:
        return dict(one(a) for a in alpha_list)

    out: dict[float, list[Any] | None] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, a): a for a in alpha_list}
        for fut in as_completed(futures):
            alpha, path = fut.result()
            out[alpha] = path
    return out
