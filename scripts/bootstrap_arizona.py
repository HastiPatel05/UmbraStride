#!/usr/bin/env python3
"""Bootstrap pedestrian graphs for Arizona (metros or grid tiles)."""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from umbrastride_geo.graph import bootstrap_aoi
from umbrastride_routing.cpu import available_cores, worker_count
from umbrastride_geo.regions import (
    bbox_to_str,
    estimate_tile_count,
    get_preset,
    iter_tile_bboxes,
    load_region,
)


def _bootstrap_one(item: tuple[str, str]) -> tuple[str, dict]:
    aoi_id, bbox = item
    meta = bootstrap_aoi(aoi_id, bbox, network_type="walk")
    return aoi_id, meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Arizona walk graphs")
    parser.add_argument("--region", default="arizona", help="Region manifest id")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--preset",
        help="Metro preset aoi_id (e.g. az-phoenix) or 'all' for every preset",
    )
    group.add_argument("--tile", help="Tile aoi_id (e.g. az-tile--112.00_33.25)")
    group.add_argument(
        "--list-presets",
        action="store_true",
        help="List metro presets and exit",
    )
    group.add_argument(
        "--list-tiles",
        action="store_true",
        help="List grid tile ids (full state coverage) and exit",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="parallel metros when --preset all (0 = min(cores, 4) for OSM politeness)",
    )
    args = parser.parse_args()

    region = load_region(args.region)

    if args.list_presets:
        for p in region["presets"]:
            print(f"  {p['aoi_id']:20} {p['name']:28} {bbox_to_str(p['bbox'])}")
        return 0

    if args.list_tiles:
        tiles = iter_tile_bboxes(region)
        print(f"Tiles: {len(tiles)} (step {region['tile_grid']['step_deg']}°)")
        for tid, bbox in tiles[:20]:
            print(f"  {tid}  {bbox_to_str(bbox)}")
        if len(tiles) > 20:
            print(f"  ... and {len(tiles) - 20} more")
        return 0

    if args.preset:
        if args.preset == "all":
            targets = [(p["aoi_id"], p["bbox"]) for p in region["presets"]]
        else:
            p = get_preset(region, args.preset)
            targets = [(p["aoi_id"], p["bbox"])]
    elif args.tile:
        tiles = {tid: bbox for tid, bbox in iter_tile_bboxes(region)}
        if args.tile not in tiles:
            print(f"Unknown tile '{args.tile}'. Use --list-tiles", file=sys.stderr)
            return 1
        targets = [(args.tile, tiles[args.tile])]
    else:
        default = region["default_aoi"]
        p = get_preset(region, default)
        targets = [(p["aoi_id"], p["bbox"])]
        print(f"No --preset/--tile given; bootstrapping default {default}")

    if args.workers > 0:
        os.environ["BOOTSTRAP_WORKERS"] = str(args.workers)

    n_workers = worker_count("BOOTSTRAP_WORKERS", default=min(available_cores(), 4), minimum=1)
    parallel = len(targets) > 1 and n_workers > 1

    if parallel:
        print(f"Bootstrapping {len(targets)} AOIs with {n_workers} workers ...")
        with ProcessPoolExecutor(max_workers=min(n_workers, len(targets))) as pool:
            futures = {pool.submit(_bootstrap_one, t): t[0] for t in targets}
            for fut in as_completed(futures):
                aoi_id, meta = fut.result()
                print(f"  {aoi_id}: {meta['nodes']} nodes, {meta['edges']} edges")
    else:
        for aoi_id, bbox in targets:
            print(f"Bootstrapping {aoi_id} ...")
            meta = bootstrap_aoi(aoi_id, bbox, network_type="walk")
            print(f"  -> {meta['nodes']} nodes, {meta['edges']} edges")

    if args.preset == "all":
        print(f"\nDone. {len(targets)} metro graphs. Full state grid has ~{estimate_tile_count(region)} tiles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
