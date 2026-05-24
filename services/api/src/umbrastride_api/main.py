from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from umbrastride_geo import (
    bootstrap_aoi,
    graph_to_geojson,
    list_aois,
    list_regions,
    load_graph,
    load_region,
    resolve_aoi_for_point,
    resolve_aoi_for_route,
    presets_containing_both,
)
from umbrastride_geo.regions import bbox_to_str, estimate_tile_count, get_preset, iter_tile_bboxes
from umbrastride_routing import ShadeStore, compute_routes, ensure_synthetic_shade_bucket, warm_routing_cache
from umbrastride_routing.shade_store import floor_ts_bucket

load_dotenv()

SHADE_AUTO_SYNC_SEC = int(os.environ.get("SHADE_AUTO_SYNC_SEC", "600"))
AUTO_SHADE_SEED = os.environ.get("AUTO_SHADE_SEED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)


def _auto_shade_enabled() -> bool:
    return AUTO_SHADE_SEED


async def _shade_auto_sync_loop() -> None:
    """Background: refresh synthetic shade for the current hour on bootstrapped AOIs."""
    while True:
        await asyncio.sleep(SHADE_AUTO_SYNC_SEC)
        if not _auto_shade_enabled():
            continue
        now = datetime.now(timezone.utc)
        for aoi in list_aois():
            aoi_id = aoi.get("aoi_id", "")
            if not aoi_id.startswith("az-"):
                continue
            try:
                await asyncio.to_thread(
                    ensure_synthetic_shade_bucket,
                    aoi_id,
                    now,
                    force=False,
                )
            except FileNotFoundError:
                continue
            except Exception:
                pass


def _startup_warm_routing() -> None:
    if os.environ.get("ROUTING_WARM_ON_STARTUP", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return
    aoi_id = os.environ.get("DEFAULT_AOI_ID", "az-phoenix").strip()
    if not aoi_id:
        return
    try:
        warm_routing_cache(aoi_id)
    except FileNotFoundError:
        pass
    except Exception:
        # Warm is best-effort; routing still works on first request.
        pass


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _startup_warm_routing()
    sync_task = asyncio.create_task(_shade_auto_sync_loop())
    try:
        yield
    finally:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="UmbraStride API", version="0.1.0", lifespan=_lifespan)

_origins = os.environ.get(
    "API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LngLat(BaseModel):
    lng: float
    lat: float


class RouteRequest(BaseModel):
    aoi_id: str | None = Field(
        default=None,
        description="AOI id (e.g. az-phoenix). Auto-resolved from origin if omitted.",
    )
    origin: LngLat
    destination: LngLat
    datetime: str
    alpha: float = Field(ge=0.0, le=1.0, default=0.5)


class CacheWarmRequest(BaseModel):
    datetime: str
    edge_keys: list[str] | None = None
    persist_sample: bool = Field(
        default=False,
        description="If true, write sampled edge shade fractions to SQLite for this bucket",
    )


class RoutingWarmRequest(BaseModel):
    datetime: str | None = None
    hours: list[int] | None = None
    alphas: list[float] | None = None


class ShadeSyncRequest(BaseModel):
    datetime: str | None = Field(
        default=None,
        description="ISO datetime for the shade bucket (default: now UTC)",
    )
    force: bool = Field(
        default=False,
        description="Re-seed even when the bucket already has coverage",
    )


class BootstrapRequest(BaseModel):
    aoi_id: str
    bbox: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/regions")
def get_regions():
    return {"regions": list_regions()}


@app.get("/v1/regions/{region_id}")
def get_region(region_id: str):
    try:
        region = load_region(region_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return {
        **region,
        "tile_count": estimate_tile_count(region),
        "bootstrapped_aois": [a["aoi_id"] for a in list_aois() if a["aoi_id"].startswith("az-")],
    }


@app.get("/v1/regions/{region_id}/resolve")
def resolve_region_aoi(region_id: str, lng: float, lat: float):
    try:
        aoi_id = resolve_aoi_for_point(lng, lat, region_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return {"aoi_id": aoi_id, "lng": lng, "lat": lat}


@app.get("/v1/aoi")
def get_aois():
    return {"aois": list_aois()}


@app.get("/v1/aoi/{aoi_id}/graph")
def get_graph(aoi_id: str):
    try:
        G = load_graph(aoi_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return graph_to_geojson(G)


@app.get("/v1/aoi/{aoi_id}/cache/coverage")
def cache_coverage(aoi_id: str, ts_bucket: str | None = None):
    store = ShadeStore(aoi_id)
    cov = store.coverage(ts_bucket)
    try:
        G = load_graph(aoi_id)
        total_edges = G.number_of_edges()
    except FileNotFoundError:
        total_edges = 0
    cached = cov["cached_edges"]
    return {
        "aoi_id": aoi_id,
        "total_edges": total_edges,
        "cached_edges": cached,
        "coverage_ratio": round(cached / total_edges, 3) if total_edges else 0.0,
        "ts_buckets": cov["ts_buckets"],
        "ts_bucket": ts_bucket,
    }


@app.post("/v1/aoi/{aoi_id}/cache/warm")
async def cache_warm(aoi_id: str, body: CacheWarmRequest):
    """Trigger shade-worker for a datetime bucket (best-effort)."""
    worker = os.environ.get("SHADE_WORKER_URL", "http://127.0.0.1:3001")
    try:
        G = load_graph(aoi_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e

    dt = datetime.fromisoformat(body.datetime.replace("Z", "+00:00"))
    ts_bucket = floor_ts_bucket(dt)

    from umbrastride_geo.graph import edge_key, iter_edges

    edge_points: list[tuple[str, dict]] = []
    for u, v, k, length, geom in iter_edges(G):
        ek = edge_key(u, v, k)
        if body.edge_keys and ek not in body.edge_keys:
            continue
        if geom is None:
            continue
        mid = geom.interpolate(0.5, normalized=True)
        edge_points.append((ek, {"lng": mid.x, "lat": mid.y}))

    if not edge_points:
        return {"status": "no_points", "ts_bucket": ts_bucket}

    sample_pairs = edge_points[: min(200, len(edge_points))]
    sample = [p for _ek, p in sample_pairs]
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{worker}/profile",
                json={"points": sample, "datetime": body.datetime},
            )
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(502, f"shade-worker unavailable: {e}") from e

    persisted_edges = 0
    if body.persist_sample:
        store = ShadeStore(aoi_id)
        rows = []
        results = payload.get("results") or []
        for i, (ek, _pt) in enumerate(sample_pairs):
            if i >= len(results):
                break
            sf = 0.85 if results[i].get("inShade") else 0.15
            rows.append((ek, ts_bucket, sf, 1))
        if rows:
            store.bulk_set(rows)
            persisted_edges = len(rows)

    return {
        "status": "worker_ok",
        "ts_bucket": ts_bucket,
        "sampled_points": len(sample),
        "worker_mode": payload.get("mode"),
        "persisted_edges": persisted_edges,
        "hint": "Run scripts/precompute_shade.py for full edge cache",
    }


@app.post("/v1/aoi/{aoi_id}/routing/warm")
def routing_warm(aoi_id: str, body: RoutingWarmRequest | None = None):
    """Preload street graph, shade arrays, and routing DiGraph into memory/disk cache."""
    from datetime import timezone

    body = body or RoutingWarmRequest()
    buckets: list[str] = []
    if body.datetime:
        dt = datetime.fromisoformat(body.datetime.replace("Z", "+00:00"))
        buckets.append(floor_ts_bucket(dt))
    if body.hours:
        now = datetime.now(timezone.utc)
        for hour in body.hours:
            buckets.append(
                floor_ts_bucket(now.replace(hour=hour, minute=0, second=0, microsecond=0))
            )
    buckets = list(dict.fromkeys(buckets)) or None

    try:
        result = warm_routing_cache(
            aoi_id,
            ts_buckets=buckets,
            alphas=body.alphas,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e

    return {"status": "warmed", **result}


@app.post("/v1/aoi/{aoi_id}/shade/sync")
def shade_sync(aoi_id: str, body: ShadeSyncRequest | None = None):
    """Ensure synthetic shade exists for the requested time bucket (auto-seed)."""
    body = body or ShadeSyncRequest()
    if body.datetime:
        try:
            dt = datetime.fromisoformat(body.datetime.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(400, f"invalid datetime: {e}") from e
    else:
        dt = datetime.now(timezone.utc)

    try:
        result = ensure_synthetic_shade_bucket(aoi_id, dt, force=body.force)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    return {"status": "ok", **result}


@app.post("/v1/route")
def post_route(body: RouteRequest):
    try:
        dt = datetime.fromisoformat(body.datetime.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(400, f"invalid datetime: {e}") from e

    aoi_id = resolve_aoi_for_route(
        body.origin.lng,
        body.origin.lat,
        body.destination.lng,
        body.destination.lat,
        preferred_aoi=body.aoi_id,
        region_id="arizona",
    )

    candidates = presets_containing_both(
        body.origin.lng,
        body.origin.lat,
        body.destination.lng,
        body.destination.lat,
        "arizona",
    )
    if body.aoi_id and body.aoi_id not in candidates and not candidates:
        raise HTTPException(
            400,
            f"Origin and destination are outside the '{body.aoi_id}' metro bounds. "
            "Move both points inside the same metro area or select a different metro.",
        )

    try:
        if _auto_shade_enabled():
            ensure_synthetic_shade_bucket(aoi_id, dt)
        result = compute_routes(
            aoi_id,
            body.origin.lng,
            body.origin.lat,
            body.destination.lng,
            body.destination.lat,
            dt,
            body.alpha,
            compare_alphas=[1.0, 0.0, body.alpha],
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if not result["routes"]:
        raise HTTPException(404, "no route found between origin and destination")

    result["aoi_id"] = aoi_id
    return result


class BootstrapPresetRequest(BaseModel):
    preset: str = "az-phoenix"


@app.post("/v1/regions/{region_id}/bootstrap-preset")
def bootstrap_region_preset(region_id: str, body: BootstrapPresetRequest):
    try:
        region = load_region(region_id)
        preset = get_preset(region, body.preset)
        meta = bootstrap_aoi(preset["aoi_id"], bbox_to_str(preset["bbox"]))
        return meta
    except (FileNotFoundError, KeyError) as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.post("/v1/aoi/bootstrap")
def post_bootstrap(body: BootstrapRequest):
    try:
        meta = bootstrap_aoi(body.aoi_id, body.bbox)
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return meta
