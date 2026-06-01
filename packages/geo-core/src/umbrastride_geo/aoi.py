# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

import json
import os
from pathlib import Path


def resolve_data_dir() -> Path:
    raw = os.environ.get("DATA_DIR", "./data")
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    for sub in ("raw", "graphs", "shade-cache", "overrides", "routing-cache"):
        (path / sub).mkdir(parents=True, exist_ok=True)
    return path


def aoi_graph_path(data_dir: Path, aoi_id: str) -> Path:
    return data_dir / "graphs" / f"{aoi_id}.graphml"


def aoi_graph_pickle_path(data_dir: Path, aoi_id: str) -> Path:
    return data_dir / "graphs" / f"{aoi_id}.graph.pkl"


def aoi_edge_index_path(data_dir: Path, aoi_id: str) -> Path:
    return data_dir / "graphs" / f"{aoi_id}.edge-index.json"


def routing_cache_dir(data_dir: Path, aoi_id: str) -> Path:
    path = data_dir / "routing-cache" / aoi_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def aoi_meta_path(data_dir: Path, aoi_id: str) -> Path:
    return data_dir / "graphs" / f"{aoi_id}.meta.json"


def override_path(data_dir: Path, aoi_id: str) -> Path:
    return data_dir / "overrides" / f"{aoi_id}.geojson"


def list_aois(data_dir: Path | None = None) -> list[dict]:
    data_dir = data_dir or resolve_data_dir()
    graphs_dir = data_dir / "graphs"
    if not graphs_dir.exists():
        return []
    aois = []
    for p in sorted(graphs_dir.glob("*.graphml")):
        aoi_id = p.stem
        meta = {}
        meta_path = aoi_meta_path(data_dir, aoi_id)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        aois.append(
            {
                "aoi_id": aoi_id,
                "nodes": meta.get("nodes"),
                "edges": meta.get("edges"),
                "bbox": meta.get("bbox"),
            }
        )
    return aois
