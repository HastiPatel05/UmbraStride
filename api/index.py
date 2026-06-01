from __future__ import annotations

import json
import math
import os
import pickle
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import networkx as nx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from shapely.geometry import LineString, mapping

AOI_ID = os.environ.get("DEFAULT_AOI_ID", "az-phoenix-vercel")
REGION_ID = "arizona"
PHOENIX_UTC_OFFSET_HOURS = -7
NIGHT_UNIFORM_SHADE = 1.0
LOCAL_MARGIN_DEG = 0.02


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


SUN_AVERSION_BETA = _float_env("SUN_AVERSION_BETA", 5.0)
SHADE_DISTANCE_TIEBREAK = _float_env("SHADE_DISTANCE_TIEBREAK", 0.05)
SHADE_BIAS_CURVE = max(0.1, _float_env("SHADE_BIAS_CURVE", 0.65))
SNAP_MAX_DIST_M = _float_env("SNAP_MAX_DIST_M", 1200.0)


class LngLat(BaseModel):
    lng: float
    lat: float


class RouteRequest(BaseModel):
    aoi_id: str | None = Field(default=None)
    origin: LngLat
    destination: LngLat
    datetime: str
    alpha: float = Field(ge=0.0, le=1.0, default=0.5)


class ShadeSyncRequest(BaseModel):
    datetime: str | None = None
    force: bool = False


app = FastAPI(title="UmbraStride Vercel API", version="0.1.0")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _data_dir() -> Path:
    raw = os.environ.get("DATA_DIR", "data-vercel")
    path = Path(raw)
    if not path.is_absolute():
        path = _project_root() / path
    return path


def _region_path(region_id: str = REGION_ID) -> Path:
    return _data_dir() / "regions" / f"{region_id}.json"


def _graph_path(aoi_id: str = AOI_ID) -> Path:
    return _data_dir() / "graphs" / f"{aoi_id}.graph.pkl"


def _meta_path(aoi_id: str = AOI_ID) -> Path:
    return _data_dir() / "graphs" / f"{aoi_id}.meta.json"


@lru_cache(maxsize=1)
def _load_region(region_id: str = REGION_ID) -> dict[str, Any]:
    path = _region_path(region_id)
    if not path.exists():
        raise FileNotFoundError(f"Region manifest not found: {region_id}")
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def _load_graph(aoi_id: str = AOI_ID) -> nx.MultiDiGraph:
    path = _graph_path(aoi_id)
    if not path.exists():
        raise FileNotFoundError(f"Graph not packaged for aoi '{aoi_id}'")
    with path.open("rb") as fh:
        return pickle.load(fh)


@lru_cache(maxsize=1)
def _node_points(aoi_id: str = AOI_ID) -> list[tuple[Any, float, float]]:
    graph = _load_graph(aoi_id)
    return [
        (node, float(data["x"]), float(data["y"]))
        for node, data in graph.nodes(data=True)
        if data.get("x") is not None and data.get("y") is not None
    ]


def _parse_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(400, f"invalid datetime: {exc}") from exc
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _floor_ts_bucket(dt: datetime, minutes: int = 15) -> str:
    dt = dt.astimezone(timezone.utc)
    minute = (dt.minute // minutes) * minutes
    floored = dt.replace(minute=minute, second=0, microsecond=0)
    return floored.strftime("%Y-%m-%dT%H:%M")


def _point_in_bbox(lng: float, lat: float, bbox: list[float]) -> bool:
    west, south, east, north = bbox
    return west <= lng <= east and south <= lat <= north


def _resolve_aoi_for_route(body: RouteRequest) -> str:
    region = _load_region(REGION_ID)
    for preset in region.get("presets", []):
        bbox = preset.get("bbox") or []
        if (
            len(bbox) == 4
            and _point_in_bbox(body.origin.lng, body.origin.lat, bbox)
            and _point_in_bbox(body.destination.lng, body.destination.lat, bbox)
        ):
            return str(preset["aoi_id"])
    raise HTTPException(
        400,
        "Origin and destination must be inside the Phoenix Vercel demo area.",
    )


def _distance_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    lat = math.radians((lat1 + lat2) / 2.0)
    dx = (lng2 - lng1) * 111_320.0 * math.cos(lat)
    dy = (lat2 - lat1) * 110_540.0
    return math.hypot(dx, dy)


def _snap_point(graph: nx.MultiDiGraph, lng: float, lat: float, label: str) -> tuple[Any, float]:
    best_node: Any | None = None
    best_dist = float("inf")
    for node, node_lng, node_lat in _node_points(AOI_ID):
        dist = _distance_m(lng, lat, node_lng, node_lat)
        if dist < best_dist:
            best_dist = dist
            best_node = node
    if best_node is None or best_dist > SNAP_MAX_DIST_M:
        raise HTTPException(
            400,
            f"{label}: no walk network within {SNAP_MAX_DIST_M:.0f}m of "
            f"({lng:.5f}, {lat:.5f}). Click inside the Phoenix demo area.",
        )
    return best_node, best_dist


def _local_hour(dt: datetime) -> float:
    utc = dt.astimezone(timezone.utc)
    hour = (utc.hour + PHOENIX_UTC_OFFSET_HOURS) % 24
    return hour + utc.minute / 60.0 + utc.second / 3600.0


def _is_night(dt: datetime) -> bool:
    hour = _local_hour(dt)
    return hour < 5.5 or hour > 19.5


def _edge_key(u: Any, v: Any, k: int = 0) -> str:
    return f"{u}|{v}|{k}"


def _edge_coords(graph: nx.MultiDiGraph, u: Any, v: Any, data: dict[str, Any]) -> list[tuple[float, float]]:
    geom = data.get("geometry")
    if geom is not None:
        return [(float(x), float(y)) for x, y in geom.coords]
    return [
        (float(graph.nodes[u]["x"]), float(graph.nodes[u]["y"])),
        (float(graph.nodes[v]["x"]), float(graph.nodes[v]["y"])),
    ]


def _bearing_deg(coords: list[tuple[float, float]]) -> float | None:
    if len(coords) < 2:
        return None
    dx = coords[-1][0] - coords[0][0]
    dy = coords[-1][1] - coords[0][1]
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _synthetic_shade_fraction(lng: float, lat: float, bearing_deg: float | None, dt: datetime) -> float:
    if _is_night(dt):
        return NIGHT_UNIFORM_SHADE

    local_hour = _local_hour(dt)
    daylight_pos = max(0.0, min(1.0, (local_hour - 5.5) / 14.0))
    altitude_proxy = math.sin(math.pi * daylight_pos)
    altitude_factor = 1.0 - max(0.0, altitude_proxy)
    base = 0.18 + 0.22 * altitude_factor
    sun_azimuth = math.radians(80.0 + 200.0 * daylight_pos)

    if bearing_deg is not None:
        street_factor = 0.42 * abs(math.cos(math.radians(bearing_deg) - sun_azimuth))
    else:
        street_factor = 0.18 * abs(math.sin(math.radians(lng * 1000.0 + lat * 1000.0)))

    corridor = 0.20 * math.sin((lng + 112.08) * 9500.0 + sun_azimuth * 1.7 + local_hour * 0.03)
    cross_street = 0.16 * math.cos((lat - 33.45) * 11000.0 - sun_azimuth * 1.3)
    return max(0.04, min(0.96, base + street_factor + corridor + cross_street))


def _shade_bias_for_alpha(alpha: float) -> float:
    alpha = max(0.0, min(1.0, alpha))
    return (1.0 - alpha) ** SHADE_BIAS_CURVE


def _edge_weight(length_m: float, shade_fraction: float, alpha: float) -> float:
    shade_bias = _shade_bias_for_alpha(alpha)
    distance_bias = 1.0 - shade_bias
    l_sun = length_m * (1.0 - shade_fraction)
    l_shade = length_m * shade_fraction
    shade_cost = l_sun * SUN_AVERSION_BETA + l_shade * SHADE_DISTANCE_TIEBREAK
    return distance_bias * length_m + shade_bias * shade_cost


def _alpha_key(alpha: float) -> str:
    return f"w_{round(alpha, 4):.4f}"


def _corridor_nodes(
    graph: nx.MultiDiGraph,
    origin_node: Any,
    dest_node: Any,
    margin_deg: float = LOCAL_MARGIN_DEG,
) -> set[Any]:
    ox = float(graph.nodes[origin_node]["x"])
    oy = float(graph.nodes[origin_node]["y"])
    dx = float(graph.nodes[dest_node]["x"])
    dy = float(graph.nodes[dest_node]["y"])
    west, east = sorted((ox, dx))
    south, north = sorted((oy, dy))
    return {
        node
        for node, data in graph.nodes(data=True)
        if west - margin_deg <= float(data.get("x", 999.0)) <= east + margin_deg
        and south - margin_deg <= float(data.get("y", 999.0)) <= north + margin_deg
    }


@lru_cache(maxsize=32)
def _routing_graph(aoi_id: str, ts_bucket: str, alpha_key: tuple[float, ...]) -> nx.DiGraph:
    graph = _load_graph(aoi_id)
    dt = _parse_datetime(f"{ts_bucket}:00+00:00")
    digraph = nx.DiGraph()
    digraph.add_nodes_from(graph.nodes(data=True))

    for u, v, k, data in graph.edges(keys=True, data=True):
        length = float(data.get("length", 1.0))
        coords = _edge_coords(graph, u, v, data)
        midpoint = coords[len(coords) // 2] if coords else (
            float(graph.nodes[u]["x"]),
            float(graph.nodes[u]["y"]),
        )
        shade = _synthetic_shade_fraction(midpoint[0], midpoint[1], _bearing_deg(coords), dt)
        route_payload = {
            "edge_key": _edge_key(u, v, k),
            "length_m": length,
            "shade_fraction": shade,
            "coordinates": coords,
        }
        payload: dict[str, Any] = {"route_payloads": {}}
        for alpha in alpha_key:
            weight_key = _alpha_key(alpha)
            payload[weight_key] = _edge_weight(length, shade, alpha)
            payload["route_payloads"][weight_key] = route_payload

        if digraph.has_edge(u, v):
            current = digraph[u][v]
            for alpha in alpha_key:
                weight_key = _alpha_key(alpha)
                if payload[weight_key] < current[weight_key]:
                    current[weight_key] = payload[weight_key]
                    current.setdefault("route_payloads", {})[weight_key] = route_payload
        else:
            digraph.add_edge(u, v, **payload)
    return digraph


def _route_payload(edge_data: dict[str, Any], weight_key: str) -> dict[str, Any]:
    return edge_data.get("route_payloads", {}).get(weight_key, edge_data)


def _orient_segment(
    coords: list[tuple[float, float]],
    start: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    if not coords:
        return []
    forward = _distance_m(coords[0][0], coords[0][1], start[0], start[1]) + _distance_m(
        coords[-1][0], coords[-1][1], end[0], end[1]
    )
    backward = _distance_m(coords[-1][0], coords[-1][1], start[0], start[1]) + _distance_m(
        coords[0][0], coords[0][1], end[0], end[1]
    )
    return coords if forward <= backward else list(reversed(coords))


def _append_coords(target: list[tuple[float, float]], segment: list[tuple[float, float]]) -> None:
    for coord in segment:
        if target and target[-1] == coord:
            continue
        target.append(coord)


def _route_geometry(
    graph: nx.MultiDiGraph,
    digraph: nx.DiGraph,
    path: list[Any],
    weight_key: str,
) -> dict[str, Any] | None:
    coords: list[tuple[float, float]] = []
    for start_node, end_node in zip(path, path[1:]):
        payload = _route_payload(digraph[start_node][end_node], weight_key)
        segment = payload.get("coordinates") or [
            (float(graph.nodes[start_node]["x"]), float(graph.nodes[start_node]["y"])),
            (float(graph.nodes[end_node]["x"]), float(graph.nodes[end_node]["y"])),
        ]
        start = (float(graph.nodes[start_node]["x"]), float(graph.nodes[start_node]["y"]))
        end = (float(graph.nodes[end_node]["x"]), float(graph.nodes[end_node]["y"]))
        _append_coords(coords, _orient_segment(segment, start, end))
    if len(coords) < 2:
        return None
    return mapping(LineString(coords))


def _route_metrics(digraph: nx.DiGraph, path: list[Any], weight_key: str) -> dict[str, float]:
    total_length = 0.0
    shade_weighted = 0.0
    for start_node, end_node in zip(path, path[1:]):
        payload = _route_payload(digraph[start_node][end_node], weight_key)
        length = float(payload.get("length_m", 0.0))
        shade = float(payload.get("shade_fraction", 0.5))
        total_length += length
        shade_weighted += shade * length
    return {
        "distance_m": round(total_length, 1),
        "shade_fraction": round(shade_weighted / total_length, 3) if total_length else 0.0,
    }


def _label_for_alpha(alpha: float) -> str:
    if alpha >= 0.999:
        return "shortest"
    if alpha <= 0.001:
        return "coolest"
    return "custom"


def _compute_routes(body: RouteRequest, aoi_id: str, dt: datetime) -> dict[str, Any]:
    graph = _load_graph(aoi_id)
    origin_node, origin_snap = _snap_point(graph, body.origin.lng, body.origin.lat, "Origin")
    dest_node, dest_snap = _snap_point(graph, body.destination.lng, body.destination.lat, "Destination")
    ts_bucket = _floor_ts_bucket(dt)

    alpha_list: list[float] = []
    for alpha in (1.0, 0.0, body.alpha):
        rounded = round(alpha, 4)
        if rounded not in alpha_list:
            alpha_list.append(rounded)

    digraph = _routing_graph(aoi_id, ts_bucket, tuple(sorted(alpha_list)))
    corridor = _corridor_nodes(graph, origin_node, dest_node)
    if origin_node in corridor and dest_node in corridor and len(corridor) > 2:
        route_graph = digraph.subgraph(corridor).copy()
    else:
        route_graph = digraph

    routes: list[dict[str, Any]] = []
    shortest_dist: float | None = None
    for alpha in alpha_list:
        weight_key = _alpha_key(alpha)
        try:
            path = nx.shortest_path(route_graph, origin_node, dest_node, weight=weight_key)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            try:
                path = nx.shortest_path(digraph, origin_node, dest_node, weight=weight_key)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

        metrics = _route_metrics(digraph, path, weight_key)
        label = _label_for_alpha(alpha)
        if label == "shortest":
            shortest_dist = metrics["distance_m"]
        detour = metrics["distance_m"] / shortest_dist if shortest_dist else 1.0
        routes.append(
            {
                "label": label,
                "alpha": alpha,
                "geometry": _route_geometry(graph, digraph, path, weight_key),
                "distance_m": metrics["distance_m"],
                "shade_fraction": metrics["shade_fraction"],
                "detour_ratio": round(detour, 3),
                "ts_bucket": ts_bucket,
            }
        )

    if not routes:
        raise HTTPException(404, "no route found between origin and destination")

    origin_data = graph.nodes[origin_node]
    dest_data = graph.nodes[dest_node]
    return {
        "aoi_id": aoi_id,
        "origin_node": origin_node,
        "dest_node": dest_node,
        "origin_snapped": {
            "lng": float(origin_data["x"]),
            "lat": float(origin_data["y"]),
            "distance_m": round(origin_snap, 1),
        },
        "destination_snapped": {
            "lng": float(dest_data["x"]),
            "lat": float(dest_data["y"]),
            "distance_m": round(dest_snap, 1),
        },
        "ts_bucket": ts_bucket,
        "shade_ts_bucket": ts_bucket,
        "shade_cache_exact": True,
        "sun_below_horizon": _is_night(dt),
        "routes": routes,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/regions")
def get_regions() -> dict[str, list[dict[str, str]]]:
    return {"regions": [{"region_id": REGION_ID, "name": _load_region(REGION_ID)["name"]}]}


@app.get("/api/v1/regions/{region_id}")
def get_region(region_id: str) -> dict[str, Any]:
    try:
        region = _load_region(region_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        **region,
        "bootstrapped_aois": [AOI_ID] if _graph_path(AOI_ID).exists() else [],
    }


@app.get("/api/v1/aoi")
def get_aois() -> dict[str, list[dict[str, Any]]]:
    try:
        meta = json.loads(_meta_path(AOI_ID).read_text())
    except FileNotFoundError:
        meta = {"aoi_id": AOI_ID, "bbox": _load_region(REGION_ID)["bbox"]}
    return {"aois": [meta]}


@app.post("/api/v1/route")
def post_route(body: RouteRequest) -> dict[str, Any]:
    dt = _parse_datetime(body.datetime)
    aoi_id = _resolve_aoi_for_route(body)
    try:
        return _compute_routes(body, aoi_id, dt)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/v1/aoi/{aoi_id}/shade/sync")
def shade_sync(aoi_id: str, body: ShadeSyncRequest | None = None) -> dict[str, Any]:
    if aoi_id != AOI_ID:
        raise HTTPException(404, f"Graph not packaged for aoi '{aoi_id}'")
    request = body or ShadeSyncRequest()
    dt = _parse_datetime(request.datetime) if request.datetime else datetime.now(timezone.utc)
    return {"status": "ok", "seeded": False, "ts_bucket": _floor_ts_bucket(dt)}


@app.get("/api/v1/aoi/{aoi_id}/graph")
def get_graph(aoi_id: str) -> dict[str, Any]:
    if aoi_id != AOI_ID:
        raise HTTPException(404, f"Graph not packaged for aoi '{aoi_id}'")
    raise HTTPException(
        501,
        "Full graph GeoJSON is disabled on the Vercel demo to keep responses small.",
    )


@app.post("/api/v1/aoi/{aoi_id}/cache/warm")
@app.post("/api/v1/aoi/{aoi_id}/routing/warm")
@app.post("/api/v1/regions/{region_id}/bootstrap-preset")
@app.post("/api/v1/aoi/bootstrap")
def unsupported_write_endpoints() -> None:
    raise HTTPException(501, "This Vercel demo is read-only; bootstrap and cache warm jobs are disabled.")
