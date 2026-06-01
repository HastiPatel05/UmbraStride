# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from umbrastride_geo.aoi import resolve_data_dir


def regions_dir(data_dir: Path | None = None) -> Path:
    data_dir = data_dir or resolve_data_dir()
    return data_dir.parent / "regions" if (data_dir / "..").exists() else Path("data/regions")


def _repo_regions_dir() -> Path:
    """Region manifests shipped in repo under data/regions/."""
    root = Path(__file__).resolve().parents[4]
    return root / "data" / "regions"


def load_region(region_id: str) -> dict[str, Any]:
    for base in (_repo_regions_dir(), Path("data/regions"), resolve_data_dir().parent / "regions"):
        path = base / f"{region_id}.json"
        if path.exists():
            return json.loads(path.read_text())
    raise FileNotFoundError(f"Region manifest not found: {region_id}")


def list_regions() -> list[str]:
    found: list[str] = []
    for base in (_repo_regions_dir(), Path("data/regions")):
        if not base.exists():
            continue
        for p in sorted(base.glob("*.json")):
            if p.stem not in found:
                found.append(p.stem)
    return found


def get_preset(region: dict[str, Any], preset_id: str) -> dict[str, Any]:
    for p in region.get("presets", []):
        if p["aoi_id"] == preset_id:
            return p
    raise KeyError(f"Preset '{preset_id}' not in region {region.get('region_id')}")


def bbox_to_str(bbox: list[float]) -> str:
    west, south, east, north = bbox
    return f"{west},{south},{east},{north}"


def tile_id(west: float, south: float) -> str:
    return f"az-tile-{west:.2f}_{south:.2f}"


def iter_tile_bboxes(region: dict[str, Any]) -> list[tuple[str, list[float]]]:
    """Generate grid tile bboxes covering the region bbox."""
    grid = region.get("tile_grid") or {}
    step = float(grid.get("step_deg", 0.25))
    west, south, east, north = region["bbox"]
    tiles: list[tuple[str, list[float]]] = []
    y = south
    while y < north:
        x = west
        while x < east:
            tw, ts, te, tn = x, y, min(x + step, east), min(y + step, north)
            tid = tile_id(tw, ts)
            tiles.append((tid, [tw, ts, te, tn]))
            x += step
        y += step
    return tiles


def tile_records(region: dict[str, Any]) -> list[dict[str, Any]]:
    """Generated tile AOI records with the same public shape as metro presets."""
    records: list[dict[str, Any]] = []
    for tid, bbox in iter_tile_bboxes(region):
        west, south, east, north = bbox
        records.append(
            {
                "aoi_id": tid,
                "name": f"Arizona tile {west:.2f}, {south:.2f}",
                "bbox": bbox,
                "description": (
                    f"On-demand Arizona grid tile covering "
                    f"{west:.2f},{south:.2f} to {east:.2f},{north:.2f}"
                ),
            }
        )
    return records


def estimate_tile_count(region: dict[str, Any]) -> int:
    return len(iter_tile_bboxes(region))


def point_in_bbox(lng: float, lat: float, bbox: list[float]) -> bool:
    west, south, east, north = bbox
    return west <= lng <= east and south <= lat <= north


def _preset_area(bbox: list[float]) -> float:
    west, south, east, north = bbox
    return abs(east - west) * abs(north - south)


def presets_containing_both(
    lng1: float, lat1: float, lng2: float, lat2: float, region_id: str = "arizona"
) -> list[str]:
    """AOI ids whose bbox contains both points, largest area first (prefer wide metro)."""
    region = load_region(region_id)
    matches = []
    for p in region.get("presets", []):
        bbox = p["bbox"]
        if point_in_bbox(lng1, lat1, bbox) and point_in_bbox(lng2, lat2, bbox):
            matches.append((p["aoi_id"], _preset_area(bbox)))
    matches.sort(key=lambda x: x[1], reverse=True)
    return [aid for aid, _ in matches]


def tiles_containing_both(
    lng1: float, lat1: float, lng2: float, lat2: float, region_id: str = "arizona"
) -> list[str]:
    """Tile AOI ids whose bbox contains both points."""
    region = load_region(region_id)
    matches: list[str] = []
    for tid, bbox in iter_tile_bboxes(region):
        if point_in_bbox(lng1, lat1, bbox) and point_in_bbox(lng2, lat2, bbox):
            matches.append(tid)
    return matches


def routable_aois_containing_both(
    lng1: float, lat1: float, lng2: float, lat2: float, region_id: str = "arizona"
) -> list[str]:
    """Metro candidates first, then same-tile candidates."""
    presets = presets_containing_both(lng1, lat1, lng2, lat2, region_id)
    tiles = tiles_containing_both(lng1, lat1, lng2, lat2, region_id)
    return presets + [tid for tid in tiles if tid not in presets]


def resolve_aoi_for_route(
    origin_lng: float,
    origin_lat: float,
    dest_lng: float,
    dest_lat: float,
    *,
    preferred_aoi: str | None = None,
    region_id: str = "arizona",
) -> str:
    """Pick metro first, then same-tile AOI; prefer preferred_aoi if valid."""
    candidates = routable_aois_containing_both(
        origin_lng, origin_lat, dest_lng, dest_lat, region_id
    )
    if preferred_aoi and preferred_aoi in candidates:
        return preferred_aoi
    if candidates:
        return candidates[0]
    if preferred_aoi:
        return preferred_aoi
    return resolve_aoi_for_point(origin_lng, origin_lat, region_id) or load_region(region_id)[
        "default_aoi"
    ]


def resolve_aoi_for_point(
    lng: float, lat: float, region_id: str = "arizona"
) -> str | None:
    """Pick widest metro preset containing the point, else nearest preset centroid."""
    region = load_region(region_id)
    containing: list[tuple[dict, float]] = []
    for p in region.get("presets", []):
        if point_in_bbox(lng, lat, p["bbox"]):
            containing.append((p, _preset_area(p["bbox"])))
    if containing:
        containing.sort(key=lambda x: x[1], reverse=True)
        return containing[0][0]["aoi_id"]
    # nearest preset by bbox center distance
    best_id = region["default_aoi"]
    best_d = math.inf
    for p in region.get("presets", []):
        w, s, e, n = p["bbox"]
        cx, cy = (w + e) / 2, (s + n) / 2
        d = (lng - cx) ** 2 + (lat - cy) ** 2
        if d < best_d:
            best_d = d
            best_id = p["aoi_id"]
    return best_id
