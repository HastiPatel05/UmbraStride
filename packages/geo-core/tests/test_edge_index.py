import json
import pickle

import networkx as nx
from shapely.geometry import LineString

from umbrastride_geo.edges import edge_key, parse_edge_key
from umbrastride_geo.graph import geometry_for_edge_key
from umbrastride_geo.edge_index import build_edge_index, ensure_edge_index


def test_build_edge_index_order():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.0)
    G.add_edge(1, 2, 0, length=100.0)
    G.add_edge(1, 2, 1, length=120.0)
    keys, key_to_index = build_edge_index(G)
    assert keys == ["1|2|0", "1|2|1"]
    assert key_to_index["1|2|1"] == 1


def test_parse_edge_key_int_nodes():
    u, v, k = parse_edge_key("1|2|0")
    assert u == 1 and v == 2 and k == 0


def test_geometry_for_edge_key(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.0)
    geom = LineString([(0.0, 0.0), (0.001, 0.0)])
    G.add_edge(1, 2, 0, length=100.0, geometry=geom)
    resolved = geometry_for_edge_key(G, edge_key(1, 2, 0))
    assert resolved is not None
    assert resolved.length > 0


def test_ensure_edge_index_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=0.001, y=0.0)
    G.add_edge(1, 2, 0, length=100.0)
    keys, key_to_index = ensure_edge_index(G, "test-aoi")
    assert len(keys) == 1
    keys2, key_to_index2 = ensure_edge_index(G, "test-aoi")
    assert keys2 == keys
    assert key_to_index2 == key_to_index
