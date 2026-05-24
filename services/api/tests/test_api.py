from umbrastride_api.main import LngLat, RouteRequest, health, post_route


def test_health():
    assert health()["status"] == "ok"


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
