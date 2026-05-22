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
