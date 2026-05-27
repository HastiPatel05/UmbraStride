#!/usr/bin/env bash
# Bootstrap all Arizona metro presets and seed synthetic shade cache.
set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate 2>/dev/null || true

echo "=== Arizona metro graphs ==="
python scripts/bootstrap_arizona.py --preset all

echo "=== Shade cache (synthetic, per metro) ==="
for preset in az-phoenix-core az-phoenix az-tucson az-flagstaff az-prescott az-yuma az-lake-havasu az-sedona az-nogales az-show-low; do
  if [[ -f "data/graphs/${preset}.graphml" ]]; then
    echo "Seeding ${preset}..."
    python scripts/seed_demo_cache.py --aoi "$preset"
  fi
done

echo "Done. Default AOI: az-phoenix-core. Start API + web (see docs/setup.md)."
