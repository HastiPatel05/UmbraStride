# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
import networkx as nx

from umbrastride_geo.graph import edge_key, iter_edges


def test_edge_key_stable():
    assert edge_key(1, 2, 0) == "1|2|0"


def test_iter_edges_synthetic():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.0)
    from shapely.geometry import LineString

    geom = LineString([(0.0, 0.0), (0.001, 0.0)])
    G.add_edge(1, 2, 0, length=100.0, geometry=geom)
    edges = list(iter_edges(G))
    assert len(edges) == 1
    assert edges[0][3] == 100.0
