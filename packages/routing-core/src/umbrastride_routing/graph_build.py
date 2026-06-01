# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

from typing import Any

import networkx as nx
import numpy as np
from umbrastride_geo.edges import edge_key, iter_edges

from umbrastride_routing.weights import SHADE_BIAS_CURVE, SHADE_DISTANCE_TIEBREAK


def alpha_weight_key(alpha: float) -> str:
    return f"w_{round(alpha, 4)}"


def _beta() -> float:
    import os

    return float(os.environ.get("SUN_AVERSION_BETA", "5.0"))


def _shade_distance_tiebreak() -> float:
    import os

    return float(os.environ.get("SHADE_DISTANCE_TIEBREAK", str(SHADE_DISTANCE_TIEBREAK)))


def _shade_bias_curve() -> float:
    import os

    return max(0.1, float(os.environ.get("SHADE_BIAS_CURVE", str(SHADE_BIAS_CURVE))))


def _weight_matrix(
    lengths: np.ndarray,
    shade: np.ndarray,
    alphas: list[float],
) -> dict[str, np.ndarray]:
    """Vectorized edge weights for all alphas (uses NumPy/BLAS — multi-core on large graphs)."""
    beta = _beta()
    shade_tiebreak = _shade_distance_tiebreak()
    shade_curve = _shade_bias_curve()
    a = np.asarray(alphas, dtype=np.float64)
    length_vals = lengths.astype(np.float64, copy=False)
    s = shade.astype(np.float64, copy=False)
    a = np.clip(a, 0.0, 1.0)
    shade_bias = np.power(1.0 - a, shade_curve)
    distance_bias = 1.0 - shade_bias
    sun = length_vals * (1.0 - s)
    shade_len = length_vals * s
    shade_cost = sun[:, None] * beta + shade_len[:, None] * shade_tiebreak
    w = distance_bias * length_vals[:, None] + shade_bias * shade_cost
    return {alpha_weight_key(al): w[:, i] for i, al in enumerate(alphas)}


def _shade_value(
    ek: str,
    edge_index: int | None,
    shade_map: dict[str, float] | None,
    shade_array: np.ndarray | None,
    default_shade: float,
) -> float:
    if shade_array is not None and edge_index is not None and 0 <= edge_index < len(shade_array):
        return float(shade_array[edge_index])
    if shade_map is not None:
        return float(shade_map.get(ek, default_shade))
    return default_shade


def build_routing_digraph(
    G: nx.MultiDiGraph,
    shade: dict[str, float] | np.ndarray,
    alphas: list[float],
    *,
    edge_key_to_index: dict[str, int] | None = None,
    default_shade: float = 0.5,
) -> nx.DiGraph:
    """
    Collapse parallel edges; compute all alpha weights (vectorized NumPy/BLAS).

    Geometry is omitted from edge payloads. Resolve it via ``geometry_for_edge_key``
    on the walk graph.
    """
    D = nx.DiGraph()
    D.add_nodes_from(G.nodes(data=True))
    wkeys = [alpha_weight_key(a) for a in alphas]

    shade_map: dict[str, float] | None
    shade_array: np.ndarray | None
    if isinstance(shade, np.ndarray):
        shade_array = shade
        shade_map = None
    else:
        shade_array = None
        shade_map = shade

    rows: list[tuple[Any, Any, float, str, int | None, float]] = []
    for u, v, k, length, _geom in iter_edges(G):
        ek = edge_key(u, v, k)
        idx = edge_key_to_index.get(ek) if edge_key_to_index else None
        sf = _shade_value(ek, idx, shade_map, shade_array, default_shade)
        rows.append((u, v, length, ek, idx, sf))

    if not rows:
        return D

    lengths = np.fromiter((r[2] for r in rows), dtype=np.float64, count=len(rows))
    shade_vals = np.fromiter((r[5] for r in rows), dtype=np.float64, count=len(rows))
    w_by_key = _weight_matrix(lengths, shade_vals, alphas)

    for i, (u, v, length, ek, _idx, sf) in enumerate(rows):
        route_payload: dict[str, Any] = {
            "length_m": length,
            "shade_fraction": sf,
            "edge_key": ek,
        }
        payload: dict[str, Any] = {"route_payloads": {}}
        for wk in wkeys:
            payload[wk] = float(w_by_key[wk][i])
            payload["route_payloads"][wk] = route_payload
        if D.has_edge(u, v):
            cur = D[u][v]
            for wk in wkeys:
                if payload[wk] < cur[wk]:
                    cur[wk] = payload[wk]
                    cur.setdefault("route_payloads", {})[wk] = route_payload
        else:
            D.add_edge(u, v, **payload)
    return D
