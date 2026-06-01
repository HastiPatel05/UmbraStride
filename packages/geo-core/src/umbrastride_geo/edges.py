# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

from typing import Any, Iterator

import networkx as nx
from shapely.geometry import LineString


def edge_key(u: int | str, v: int | str, k: int = 0) -> str:
    return f"{u}|{v}|{k}"


def parse_edge_key(ek: str) -> tuple[Any, Any, int]:
    parts = ek.split("|")
    if len(parts) != 3:
        raise ValueError(f"invalid edge_key: {ek!r}")
    u, v, k_str = parts
    try:
        u = int(u)
        v = int(v)
    except ValueError:
        try:
            u = float(u)
            v = float(v)
        except ValueError:
            pass
    return u, v, int(k_str)


def iter_edges(G: nx.MultiDiGraph) -> Iterator[tuple[Any, Any, int, float, Any]]:
    for u, v, k, data in G.edges(keys=True, data=True):
        length = float(data.get("length", 1.0))
        geom = None
        if "geometry" in data:
            geom = data["geometry"]
        elif G.nodes[u].get("x") is not None:
            geom = LineString(
                [
                    (G.nodes[u]["x"], G.nodes[u]["y"]),
                    (G.nodes[v]["x"], G.nodes[v]["y"]),
                ]
            )
        yield u, v, k, length, geom
