#!/usr/bin/env python3
"""Bootstrap pedestrian graph for an AOI bbox."""

from __future__ import annotations

import argparse
import sys

from umbrastride_geo.graph import bootstrap_aoi


def main() -> int:
    parser = argparse.ArgumentParser(description="Download OSM walk graph for bbox")
    parser.add_argument("--name", required=True, help="AOI id (e.g. demo)")
    parser.add_argument(
        "--bbox",
        required=True,
        help="west,south,east,north in WGS84 (e.g. 11.575,48.135,11.585,48.142)",
    )
    args = parser.parse_args()
    meta = bootstrap_aoi(args.name, args.bbox)
    print(f"Created AOI '{args.name}': {meta['nodes']} nodes, {meta['edges']} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
