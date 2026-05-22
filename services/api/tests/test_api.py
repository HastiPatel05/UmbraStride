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
