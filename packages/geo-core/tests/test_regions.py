# Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
from umbrastride_geo.regions import (
    estimate_tile_count,
    load_region,
    point_in_bbox,
    routable_aois_containing_both,
    resolve_aoi_for_point,
    resolve_aoi_for_route,
    tile_records,
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


def _rural_tile_points():
    r = load_region("arizona")
    presets = r["presets"]
    for tile in tile_records(r):
        w, s, e, n = tile["bbox"]
        p1 = (w + 0.05, s + 0.05)
        p2 = (w + 0.10, s + 0.10)
        if not any(
            point_in_bbox(p1[0], p1[1], preset["bbox"])
            or point_in_bbox(p2[0], p2[1], preset["bbox"])
            for preset in presets
        ):
            return tile, p1, p2
    raise AssertionError("no rural tile found")


def test_region_tiles_have_public_aoi_shape():
    r = load_region("arizona")
    tiles = tile_records(r)
    assert len(tiles) == estimate_tile_count(r)
    assert tiles[0]["aoi_id"].startswith("az-tile-")
    assert {"aoi_id", "name", "bbox", "description"} <= set(tiles[0])


def test_routable_candidates_prefer_metro_over_tile():
    candidates = routable_aois_containing_both(-112.08, 33.45, -112.05, 33.46)
    assert candidates[0] == "az-phoenix"


def test_route_resolves_to_same_tile_outside_metros():
    tile, p1, p2 = _rural_tile_points()
    assert resolve_aoi_for_route(p1[0], p1[1], p2[0], p2[1]) == tile["aoi_id"]
