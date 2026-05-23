import networkx as nx
from datetime import datetime, timezone

from umbrastride_routing.router import compute_routes
from umbrastride_routing.shade_store import ShadeStore, floor_ts_bucket
from umbrastride_geo.graph import edge_key


def _synthetic_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from shapely.geometry import LineString
    import json
    from umbrastride_geo.aoi import aoi_graph_path, aoi_meta_path, resolve_data_dir
    import osmnx as ox

    G = nx.MultiDiGraph()
    G.graph["crs"] = "epsg:4326"
    for n, (x, y) in enumerate([(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.001)]):
        G.add_node(n, x=x, y=y)
    G.add_edge(0, 1, 0, length=100, geometry=LineString([(0, 0), (0.001, 0)]))
    G.add_edge(1, 2, 0, length=100, geometry=LineString([(0.001, 0), (0.001, 0.001)]))
    G.add_edge(2, 3, 0, length=100, geometry=LineString([(0.001, 0.001), (0, 0.001)]))
    G.add_edge(0, 3, 0, length=141, geometry=LineString([(0, 0), (0, 0.001)]))
    data_dir = resolve_data_dir()
    ox.save_graphml(G, aoi_graph_path(data_dir, "test"))
    aoi_meta_path(data_dir, "test").write_text(
        json.dumps({"aoi_id": "test", "bbox": [0, 0, 0.001, 0.001], "nodes": 4, "edges": 4})
    )
    store = ShadeStore("test")
    tb = floor_ts_bucket(datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc))
    store.set_fraction(edge_key(0, 3, 0), tb, 0.9, 5)
    store.set_fraction(edge_key(0, 1, 0), tb, 0.1, 5)
    store.set_fraction(edge_key(1, 2, 0), tb, 0.1, 5)
    store.set_fraction(edge_key(2, 3, 0), tb, 0.1, 5)
    return G, tb


def test_compute_routes_prefers_shade_at_alpha_zero(tmp_path, monkeypatch):
    _synthetic_graph(tmp_path, monkeypatch)
    result = compute_routes(
        "test",
        0.0001,
        0.0001,
        0.0001,
        0.0009,
        datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        0.0,
        compare_alphas=[1.0, 0.0],
    )
    assert len(result["routes"]) == 2
    coolest = next(r for r in result["routes"] if r["label"] == "coolest")
    shortest = next(r for r in result["routes"] if r["label"] == "shortest")
    assert coolest["shade_fraction"] >= shortest["shade_fraction"]


def test_compute_routes_shortest_equals_coolest_at_night(tmp_path, monkeypatch):
    """When sun is below horizon, uniform shade => same path for shortest and coolest."""
    _synthetic_graph(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "umbrastride_routing.router.is_route_at_night",
        lambda *_args, **_kwargs: True,
    )
    night = datetime(2026, 6, 21, 8, 0, tzinfo=timezone.utc)
    result = compute_routes(
        "test",
        0.0001,
        0.0001,
        0.0001,
        0.0009,
        night,
        0.0,
        compare_alphas=[1.0, 0.0],
    )
    assert result["sun_below_horizon"] is True
    shortest = next(r for r in result["routes"] if r["label"] == "shortest")
    coolest = next(r for r in result["routes"] if r["label"] == "coolest")
    assert shortest["distance_m"] == coolest["distance_m"]
    assert shortest["geometry"] == coolest["geometry"]
