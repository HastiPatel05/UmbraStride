# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from umbrastride_routing.graph_build import build_routing_digraph, alpha_weight_key
from umbrastride_routing.router import edge_weight
import networkx as nx


def test_build_routing_digraph_single_pass():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.0)
    from shapely.geometry import LineString

    G.add_edge(1, 2, 0, length=100.0, geometry=LineString([(0, 0), (0.001, 0)]))
    shade = {"1|2|0": 0.8}
    D = build_routing_digraph(G, shade, [0.0, 1.0])
    assert D.has_edge(1, 2)
    assert alpha_weight_key(0.0) in D[1][2]
    assert D[1][2][alpha_weight_key(1.0)] == 100.0


def test_parallel_edges_keep_alpha_specific_route_payloads():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.0)
    from shapely.geometry import LineString

    G.add_edge(1, 2, 0, length=100.0, geometry=LineString([(0, 0), (0.001, 0)]))
    G.add_edge(1, 2, 1, length=120.0, geometry=LineString([(0, 0), (0.001, 0.0001)]))
    shade = {"1|2|0": 0.0, "1|2|1": 1.0}

    D = build_routing_digraph(G, shade, [0.0, 1.0])

    shortest_payload = D[1][2]["route_payloads"][alpha_weight_key(1.0)]
    coolest_payload = D[1][2]["route_payloads"][alpha_weight_key(0.0)]
    assert shortest_payload["edge_key"] == "1|2|0"
    assert shortest_payload["length_m"] == 100.0
    assert coolest_payload["edge_key"] == "1|2|1"
    assert coolest_payload["length_m"] == 120.0
    assert coolest_payload["shade_fraction"] == 1.0
