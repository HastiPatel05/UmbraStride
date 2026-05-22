from __future__ import annotations

from typing import Any

import networkx as nx
import numpy as np

from umbrastride_geo.graph import edge_key, iter_edges


def alpha_weight_key(alpha: float) -> str:
    return f"w_{round(alpha, 4)}"


def _beta() -> float:
    import os

    return float(os.environ.get("SUN_AVERSION_BETA", "5.0"))


def _weight_matrix(lengths: np.ndarray, shade: np.ndarray, alphas: list[float]) -> dict[str, np.ndarray]:
    """Vectorized edge weights for all alphas (uses NumPy/BLAS — multi-core on large graphs)."""
    beta = _beta()
    a = np.asarray(alphas, dtype=np.float64)
    l = lengths.astype(np.float64, copy=False)
    s = shade.astype(np.float64, copy=False)
    a = np.clip(a, 0.0, 1.0)
    sun = l * (1.0 - s)
    shade_len = l * s
    # (n_edges, n_alphas)
    w = a * l[:, None] + (1.0 - a) * (sun[:, None] * beta + shade_len[:, None])
    return {alpha_weight_key(al): w[:, i] for i, al in enumerate(alphas)}


def build_routing_digraph(
    G: nx.MultiDiGraph,
    shade_map: dict[str, float],
    alphas: list[float],
    *,
    default_shade: float = 0.5,
) -> nx.DiGraph:
    """Collapse parallel edges; compute all alpha weights (vectorized NumPy/BLAS)."""
    D = nx.DiGraph()
    D.add_nodes_from(G.nodes(data=True))
    wkeys = [alpha_weight_key(a) for a in alphas]

    rows: list[tuple[Any, Any, float, Any, str, float]] = []
    for u, v, k, length, geom in iter_edges(G):
        ek = edge_key(u, v, k)
        sf = shade_map.get(ek, default_shade)
        rows.append((u, v, length, geom, ek, sf))

    if not rows:
        return D

    lengths = np.fromiter((r[2] for r in rows), dtype=np.float64, count=len(rows))
    shade = np.fromiter((r[5] for r in rows), dtype=np.float64, count=len(rows))
    w_by_key = _weight_matrix(lengths, shade, alphas)

    for i, (u, v, length, geom, ek, sf) in enumerate(rows):
        route_payload: dict[str, Any] = {
            "length_m": length,
            "shade_fraction": sf,
            "edge_key": ek,
            "geometry": geom,
        }
        payload: dict[str, Any] = {
            **route_payload,
            "route_payloads": {},
        }
        for wk in wkeys:
            payload[wk] = float(w_by_key[wk][i])
            payload["route_payloads"][wk] = route_payload
        if D.has_edge(u, v):
            cur = D[u][v]
            for wk in wkeys:
                if payload[wk] < cur[wk]:
                    cur[wk] = payload[wk]
                    cur.setdefault("route_payloads", {})[wk] = route_payload
            if geom is not None and cur.get("geometry") is None:
                cur["geometry"] = geom
        else:
            D.add_edge(u, v, **payload)
    return D
