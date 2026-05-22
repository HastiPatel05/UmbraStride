from __future__ import annotations

import networkx as nx

from umbrastride_geo.graph import edge_key, iter_edges
from umbrastride_routing.weights import edge_weight


def alpha_weight_key(alpha: float) -> str:
    return f"w_{round(alpha, 4)}"


def build_routing_digraph(
    G: nx.MultiDiGraph,
    shade_map: dict[str, float],
    alphas: list[float],
    *,
    default_shade: float = 0.5,
) -> nx.DiGraph:
    D = nx.DiGraph()
    D.add_nodes_from(G.nodes(data=True))
    wkeys = [alpha_weight_key(a) for a in alphas]

    for u, v, k, length, geom in iter_edges(G):
        ek = edge_key(u, v, k)
        sf = shade_map.get(ek, default_shade)
        weights = {wk: edge_weight(length, sf, a) for wk, a in zip(wkeys, alphas)}
        payload = {
            "length_m": length,
            "shade_fraction": sf,
            "edge_key": ek,
            "geometry": geom,
            **weights,
        }
        if D.has_edge(u, v):
            cur = D[u][v]
            for wk in wkeys:
                if weights[wk] < cur[wk]:
                    cur[wk] = weights[wk]
            if geom is not None and cur.get("geometry") is None:
                cur["geometry"] = geom
        else:
            D.add_edge(u, v, **payload)
    return D
