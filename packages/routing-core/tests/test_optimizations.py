# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
import networkx as nx
import numpy as np
from umbrastride_routing.disk_cache import (
    RoutingCacheKey,
    load_routing_digraph,
    save_routing_digraph,
)
from umbrastride_routing.graph_build import alpha_weight_key, build_routing_digraph
from umbrastride_routing.pathfind import _heuristic_scale, corridor_subgraph, shortest_path


def test_build_routing_digraph_with_shade_array():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.0)
    G.add_edge(1, 2, 0, length=100.0)
    shade = np.array([0.8], dtype=np.float32)
    key_to_index = {"1|2|0": 0}
    D = build_routing_digraph(G, shade, [0.0, 1.0], edge_key_to_index=key_to_index)
    assert D[1][2][alpha_weight_key(1.0)] == 100.0


def test_astar_heuristic_scale_respects_shade_tiebreak(monkeypatch):
    monkeypatch.setenv("SHADE_DISTANCE_TIEBREAK", "0.001")
    D = nx.DiGraph()
    D.add_node(1, x=0.0, y=0.0)
    D.add_node(2, x=0.001, y=0.0)
    D.add_edge(1, 2, **{alpha_weight_key(0.0): 100.0, "length_m": 100.0})

    assert _heuristic_scale(D, alpha_weight_key(0.0)) == 0.001


def test_disk_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    D = nx.DiGraph()
    D.add_node(1, x=0.0, y=0.0)
    D.add_node(2, x=0.001, y=0.0)
    D.add_edge(1, 2, **{"w_1.0": 10.0, "length_m": 10.0})
    key = RoutingCacheKey(
        aoi_id="test",
        graph_mtime=1.0,
        shade_mtime=2.0,
        resolved_bucket="2026-05-22T12:00",
        alphas=(0.0, 1.0),
    )
    save_routing_digraph(key, D)
    loaded = load_routing_digraph(key)
    assert loaded is not None
    assert loaded[1][2]["w_1.0"] == 10.0


def test_shortest_path_rustworkx():
    D = nx.DiGraph()
    D.add_node("a", x=0.0, y=0.0)
    D.add_node("b", x=0.001, y=0.0)
    D.add_node("c", x=0.002, y=0.0)
    # length_m matches geographic distance (OSM-like) so A* heuristic stays admissible
    D.add_edge("a", "b", **{"w_1.0": 111.0, "length_m": 111.0})
    D.add_edge("b", "c", **{"w_1.0": 111.0, "length_m": 111.0})
    D.add_edge("a", "c", **{"w_1.0": 500.0, "length_m": 222.0})
    path = shortest_path(D, "a", "c", "w_1.0")
    assert path == ["a", "b", "c"]


def test_corridor_subgraph_expands_until_path():
    D = nx.DiGraph()
    for i in range(5):
        D.add_node(i, x=float(i) * 0.01, y=0.0)
    for i in range(4):
        D.add_edge(i, i + 1, **{"w_1.0": 1.0, "length_m": 1.0})
    sub = corridor_subgraph(D, 0, 4, margin_deg=0.001)
    path = shortest_path(sub, 0, 4, "w_1.0")
    assert path == [0, 1, 2, 3, 4]
