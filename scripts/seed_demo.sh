#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

AOI="${1:-demo}"
BBOX="${2:-11.570,48.130,11.590,48.145}"

if [ ! -f "data/graphs/${AOI}.graphml" ]; then
  echo "Bootstrapping AOI ${AOI}..."
  python scripts/bootstrap_aoi.py --name "$AOI" --bbox "$BBOX"
fi

echo "Seeding shade cache for ${AOI}..."
python scripts/seed_demo_cache.py --aoi "$AOI"
echo "Done. Start API and web."
