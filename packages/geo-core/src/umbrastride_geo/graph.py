# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

import json
import os
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, Polygon, mapping

from umbrastride_geo.aoi import (
    aoi_graph_path,
    aoi_graph_pickle_path,
    aoi_meta_path,
    override_path,
    resolve_data_dir,
)
from umbrastride_geo.edge_index import ensure_edge_index
from umbrastride_geo.edges import edge_key, iter_edges, parse_edge_key


def _parse_bbox(bbox_str: str) -> tuple[float, float, float, float]:
    parts = [float(x.strip()) for x in bbox_str.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be west,south,east,north")
    west, south, east, north = parts
    if west >= east or south >= north:
        raise ValueError("invalid bbox: west < east and south < north required")
    return west, south, east, north


def _apply_overrides(G: nx.MultiDiGraph, data_dir: Path, aoi_id: str) -> nx.MultiDiGraph:
    path = override_path(data_dir, aoi_id)
    if not path.exists():
        return G
    fc = json.loads(path.read_text())
    exclude_uuids: set[str] = set()
    for feat in fc.get("features", []):
        props = feat.get("properties") or {}
        if props.get("action") == "exclude_way" and props.get("osmid"):
            exclude_uuids.add(str(props["osmid"]))
    if not exclude_uuids:
        return G
    to_remove = []
    for u, v, k, data in G.edges(keys=True, data=True):
        osmid = data.get("osmid")
        if osmid is None:
            continue
        ids = osmid if isinstance(osmid, list) else [osmid]
        if any(str(i) in exclude_uuids for i in ids):
            to_remove.append((u, v, k))
    for edge in to_remove:
        if G.has_edge(*edge):
            G.remove_edge(*edge)
    return G


def bootstrap_aoi(
    aoi_id: str,
    bbox: str | tuple[float, float, float, float],
    *,
    data_dir: Path | None = None,
    network_type: str = "walk",
) -> dict[str, Any]:
    """Download OSM walk graph for bbox and persist GraphML + metadata."""
    data_dir = data_dir or resolve_data_dir()
    if isinstance(bbox, str):
        west, south, east, north = _parse_bbox(bbox)
    else:
        west, south, east, north = bbox

    polygon = Polygon(
        [
            (west, south),
            (east, south),
            (east, north),
            (west, north),
            (west, south),
        ]
    )
    G = ox.graph_from_polygon(polygon, network_type=network_type, simplify=True)
    G = _apply_overrides(G, data_dir, aoi_id)

    # Largest weakly connected component
    if not nx.is_weakly_connected(G):
        largest = max(nx.weakly_connected_components(G), key=len)
        G = G.subgraph(largest).copy()

    graph_path = aoi_graph_path(data_dir, aoi_id)
    ox.save_graphml(G, graph_path)
    _save_graph_pickle(G, aoi_id, data_dir)
    ensure_edge_index(G, aoi_id, data_dir=data_dir)

    meta = {
        "aoi_id": aoi_id,
        "bbox": [west, south, east, north],
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "network_type": network_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "region": "arizona" if aoi_id.startswith("az-") else None,
    }
    aoi_meta_path(data_dir, aoi_id).write_text(json.dumps(meta, indent=2))
    return meta


def _save_graph_pickle(G: nx.MultiDiGraph, aoi_id: str, data_dir: Path) -> Path:
    path = aoi_graph_pickle_path(data_dir, aoi_id)
    with path.open("wb") as fh:
        pickle.dump(G, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_graph(aoi_id: str, *, data_dir: Path | None = None) -> nx.MultiDiGraph:
    """Load street graph — prefers pickle when present and up to date vs GraphML."""
    data_dir = data_dir or resolve_data_dir()
    graphml_path = aoi_graph_path(data_dir, aoi_id)
    pickle_path = aoi_graph_pickle_path(data_dir, aoi_id)
    if not graphml_path.exists() and not pickle_path.exists():
        raise FileNotFoundError(f"Graph not found for aoi '{aoi_id}': {graphml_path}")

    if pickle_path.exists() and (
        not graphml_path.exists()
        or pickle_path.stat().st_mtime >= graphml_path.stat().st_mtime
    ):
        with pickle_path.open("rb") as fh:
            return pickle.load(fh)

    G = ox.load_graphml(graphml_path)
    _save_graph_pickle(G, aoi_id, data_dir)
    ensure_edge_index(G, aoi_id, data_dir=data_dir)
    return G


def geometry_for_edge_key(G: nx.MultiDiGraph, ek: str) -> LineString | None:
    """Resolve edge geometry from the walk graph using a stable edge_key."""
    u, v, k = parse_edge_key(ek)
    if not G.has_edge(u, v, k):
        return None
    data = G[u][v][k]
    if data.get("geometry") is not None:
        return data["geometry"]
    if G.nodes[u].get("x") is not None and G.nodes[v].get("x") is not None:
        return LineString(
            [
                (G.nodes[u]["x"], G.nodes[u]["y"]),
                (G.nodes[v]["x"], G.nodes[v]["y"]),
            ]
        )
    return None


def graph_to_geojson(G: nx.MultiDiGraph) -> dict[str, Any]:
    features = []
    for u, v, k, length, geom in iter_edges(G):
        if geom is None:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "u": u,
                    "v": v,
                    "key": k,
                    "edge_key": edge_key(u, v, k),
                    "length_m": length,
                },
                "geometry": mapping(geom),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def snap_point_to_graph(
    G: nx.MultiDiGraph,
    lng: float,
    lat: float,
    *,
    max_dist_m: float | None = None,
    label: str = "point",
) -> tuple[Any, float]:
    """Return nearest pedestrian network node and distance in meters."""
    import osmnx as ox

    if max_dist_m is None:
        max_dist_m = float(os.environ.get("SNAP_MAX_DIST_M", "1200"))

    x, y = lng, lat
    node, dist = ox.distance.nearest_nodes(G, x, y, return_dist=True)
    dist = float(dist)
    if dist > max_dist_m:
        raise ValueError(
            f"{label}: no walk network within {max_dist_m:.0f}m of ({lng:.5f}, {lat:.5f}) "
            f"(nearest sidewalk ~{dist:.0f}m away). Click closer to a street or choose a metro "
            f"that covers this area."
        )
    return node, dist
