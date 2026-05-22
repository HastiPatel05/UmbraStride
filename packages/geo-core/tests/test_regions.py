from umbrastride_geo.regions import (
    estimate_tile_count,
    load_region,
    resolve_aoi_for_point,
)


def test_load_arizona():
    r = load_region("arizona")
    assert r["region_id"] == "arizona"
    assert len(r["presets"]) >= 5
    assert r["default_aoi"] == "az-phoenix"


def test_resolve_phoenix_point():
    aoi = resolve_aoi_for_point(-112.07, 33.45, "arizona")
    assert aoi == "az-phoenix"


def test_tile_count_reasonable():
    r = load_region("arizona")
    n = estimate_tile_count(r)
    assert 200 < n < 800
