from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from umbrastride_geo.aoi import aoi_edge_index_path, resolve_data_dir
from umbrastride_geo.edges import edge_key, iter_edges


def build_edge_index(G: nx.MultiDiGraph) -> tuple[list[str], dict[str, int]]:
    """Stable edge_key → dense index mapping for vectorized shade lookup."""
    keys: list[str] = []
    key_to_index: dict[str, int] = {}
    for u, v, k, _length, _geom in iter_edges(G):
        ek = edge_key(u, v, k)
        if ek in key_to_index:
            continue
        key_to_index[ek] = len(keys)
        keys.append(ek)
    return keys, key_to_index


def save_edge_index(
    aoi_id: str,
    keys: list[str],
    key_to_index: dict[str, int],
    *,
    data_dir: Path | None = None,
) -> Path:
    data_dir = data_dir or resolve_data_dir()
    path = aoi_edge_index_path(data_dir, aoi_id)
    payload = {"aoi_id": aoi_id, "edge_keys": keys, "count": len(keys)}
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_edge_index(
    aoi_id: str, *, data_dir: Path | None = None
) -> tuple[list[str], dict[str, int]] | None:
    data_dir = data_dir or resolve_data_dir()
    path = aoi_edge_index_path(data_dir, aoi_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    keys = payload.get("edge_keys") or []
    return keys, {ek: i for i, ek in enumerate(keys)}


def ensure_edge_index(
    G: nx.MultiDiGraph, aoi_id: str, *, data_dir: Path | None = None
) -> tuple[list[str], dict[str, int]]:
    data_dir = data_dir or resolve_data_dir()
    path = aoi_edge_index_path(data_dir, aoi_id)
    graphml = data_dir / "graphs" / f"{aoi_id}.graphml"
    if path.exists() and graphml.exists() and path.stat().st_mtime >= graphml.stat().st_mtime:
        loaded = load_edge_index(aoi_id, data_dir=data_dir)
        if loaded is not None:
            return loaded
    keys, key_to_index = build_edge_index(G)
    save_edge_index(aoi_id, keys, key_to_index, data_dir=data_dir)
    return keys, key_to_index
