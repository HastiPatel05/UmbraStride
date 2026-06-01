# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
import pytest
from fastapi import HTTPException
from umbrastride_api.main import LngLat, RouteRequest, get_region, health, post_route
from umbrastride_geo.regions import load_region, point_in_bbox, tile_records


def _rural_tile_points():
    region = load_region("arizona")
    for tile in tile_records(region):
        w, s, _e, _n = tile["bbox"]
        p1 = (w + 0.05, s + 0.05)
        p2 = (w + 0.10, s + 0.10)
        if not any(
            point_in_bbox(p1[0], p1[1], preset["bbox"])
            or point_in_bbox(p2[0], p2[1], preset["bbox"])
            for preset in region["presets"]
        ):
            return tile, p1, p2
    raise AssertionError("no rural tile found")


def test_health():
    assert health()["status"] == "ok"


def test_region_response_includes_generated_tiles():
    result = get_region("arizona")
    assert result["presets"]
    assert result["tiles"]
    assert result["tiles"][0]["aoi_id"].startswith("az-tile-")
    assert result["tile_count"] == len(result["tiles"])


def test_route_honors_valid_preferred_aoi(monkeypatch):
    seen = {}

    def fake_compute_routes(aoi_id, *_args, **_kwargs):
        seen["aoi_id"] = aoi_id
        return {
            "aoi_id": aoi_id,
            "origin_node": 1,
            "dest_node": 2,
            "ts_bucket": "2026-05-22T12:00",
            "shade_ts_bucket": "2026-05-22T12:00",
            "shade_cache_exact": True,
            "routes": [
                {
                    "label": "shortest",
                    "alpha": 1.0,
                    "geometry": None,
                    "distance_m": 1.0,
                    "shade_fraction": 0.5,
                    "detour_ratio": 1.0,
                    "ts_bucket": "2026-05-22T12:00",
                }
            ],
        }

    monkeypatch.setattr("umbrastride_api.main.compute_routes", fake_compute_routes)
    monkeypatch.setattr(
        "umbrastride_api.main.ensure_synthetic_shade_bucket",
        lambda *_args, **_kwargs: {"seeded": False},
    )
    result = post_route(
        RouteRequest(
            aoi_id="az-phoenix-core",
            origin=LngLat(lng=-112.08, lat=33.45),
            destination=LngLat(lng=-112.05, lat=33.46),
            datetime="2026-05-22T12:00:00Z",
            alpha=0.35,
        )
    )

    assert seen["aoi_id"] == "az-phoenix-core"
    assert result["aoi_id"] == "az-phoenix-core"


def test_route_can_resolve_to_same_arizona_tile(monkeypatch):
    tile, origin, destination = _rural_tile_points()
    seen = {}

    def fake_compute_routes(aoi_id, *_args, **_kwargs):
        seen["aoi_id"] = aoi_id
        return {
            "aoi_id": aoi_id,
            "origin_node": 1,
            "dest_node": 2,
            "ts_bucket": "2026-05-22T12:00",
            "shade_ts_bucket": "2026-05-22T12:00",
            "shade_cache_exact": True,
            "routes": [
                {
                    "label": "shortest",
                    "alpha": 1.0,
                    "geometry": None,
                    "distance_m": 1.0,
                    "shade_fraction": 0.5,
                    "detour_ratio": 1.0,
                    "ts_bucket": "2026-05-22T12:00",
                }
            ],
        }

    monkeypatch.setattr("umbrastride_api.main.compute_routes", fake_compute_routes)
    monkeypatch.setattr(
        "umbrastride_api.main.ensure_synthetic_shade_bucket",
        lambda *_args, **_kwargs: {"seeded": False},
    )
    result = post_route(
        RouteRequest(
            origin=LngLat(lng=origin[0], lat=origin[1]),
            destination=LngLat(lng=destination[0], lat=destination[1]),
            datetime="2026-05-22T12:00:00Z",
            alpha=0.35,
        )
    )

    assert seen["aoi_id"] == tile["aoi_id"]
    assert result["aoi_id"] == tile["aoi_id"]


def test_route_rejects_points_outside_arizona():
    with pytest.raises(HTTPException) as exc:
        post_route(
            RouteRequest(
                origin=LngLat(lng=-82.3248, lat=29.6516),
                destination=LngLat(lng=-82.32, lat=29.65),
                datetime="2026-05-22T12:00:00Z",
                alpha=0.35,
            )
        )

    assert exc.value.status_code == 400
    assert "same Arizona tile" in str(exc.value.detail)


def test_route_syncs_selected_shade_bucket_before_compute(monkeypatch):
    calls = []

    def fake_compute_routes(aoi_id, *_args, **_kwargs):
        calls.append(("compute", aoi_id))
        return {
            "aoi_id": aoi_id,
            "origin_node": 1,
            "dest_node": 2,
            "ts_bucket": "2026-05-22T02:00",
            "shade_ts_bucket": "2026-05-22T02:00",
            "shade_cache_exact": True,
            "routes": [
                {
                    "label": "coolest",
                    "alpha": 0.0,
                    "geometry": None,
                    "distance_m": 1.0,
                    "shade_fraction": 0.8,
                    "detour_ratio": 1.0,
                    "ts_bucket": "2026-05-22T02:00",
                }
            ],
        }

    def fake_ensure(aoi_id, dt, *_args, **_kwargs):
        calls.append(("ensure", aoi_id, dt.hour))
        return {"seeded": True}

    monkeypatch.setattr("umbrastride_api.main.compute_routes", fake_compute_routes)
    monkeypatch.setattr("umbrastride_api.main.ensure_synthetic_shade_bucket", fake_ensure)
    result = post_route(
        RouteRequest(
            aoi_id="az-phoenix-core",
            origin=LngLat(lng=-112.08, lat=33.45),
            destination=LngLat(lng=-112.05, lat=33.46),
            datetime="2026-05-22T02:00:00Z",
            alpha=0.0,
        )
    )

    assert calls == [("ensure", "az-phoenix-core", 2), ("compute", "az-phoenix-core")]
    assert result["shade_cache_exact"] is True
