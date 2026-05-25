import type { ArizonaPreset, ArizonaRegion } from "./api";

export function pointInBbox(lng: number, lat: number, bbox: number[]): boolean {
  const [west, south, east, north] = bbox;
  return lng >= west && lng <= east && lat >= south && lat <= north;
}

function presetArea(bbox: number[]): number {
  const [west, south, east, north] = bbox;
  return Math.abs(east - west) * Math.abs(north - south);
}

function nearestPreset(
  lng: number,
  lat: number,
  presets: ArizonaPreset[]
): ArizonaPreset {
  let best = presets[0];
  let bestD = Infinity;
  for (const p of presets) {
    const [w, s, e, n] = p.bbox;
    const cx = (w + e) / 2;
    const cy = (s + n) / 2;
    const d = (lng - cx) ** 2 + (lat - cy) ** 2;
    if (d < bestD) {
      bestD = d;
      best = p;
    }
  }
  return best;
}

function presetsContainingPoint(
  lng: number,
  lat: number,
  region: ArizonaRegion
): ArizonaPreset[] {
  return region.presets
    .filter((p) => pointInBbox(lng, lat, p.bbox))
    .sort((a, b) => presetArea(b.bbox) - presetArea(a.bbox));
}

function tilesContainingPoint(
  lng: number,
  lat: number,
  region: ArizonaRegion
): ArizonaPreset[] {
  return (region.tiles ?? []).filter((p) => pointInBbox(lng, lat, p.bbox));
}

function allAois(region: ArizonaRegion): ArizonaPreset[] {
  return [...region.presets, ...(region.tiles ?? [])];
}

function firstBootstrapped(
  candidates: ArizonaPreset[],
  bootstrapped?: Set<string>
): ArizonaPreset | null {
  if (!bootstrapped) return null;
  return candidates.find((p) => bootstrapped.has(p.aoi_id)) ?? null;
}

/** Widest metro preset first, then same Arizona tile for statewide coverage. */
export function resolvePresetForPoint(
  lng: number,
  lat: number,
  region: ArizonaRegion,
  bootstrapped?: Set<string>
): ArizonaPreset {
  const metroContaining = presetsContainingPoint(lng, lat, region);
  const tileContaining = tilesContainingPoint(lng, lat, region);
  return (
    firstBootstrapped(metroContaining, bootstrapped) ??
    firstBootstrapped(tileContaining, bootstrapped) ??
    metroContaining[0] ??
    tileContaining[0] ??
    nearestPreset(lng, lat, allAois(region))
  );
}

/**
 * Pick widest metro preset that contains both points, then same Arizona tile.
 * Prefers bootstrapped graphs when available.
 */
export function resolveAoiForRoute(
  origin: [number, number],
  destination: [number, number],
  region: ArizonaRegion,
  bootstrapped: Set<string>
): { aoiId: string; preset: ArizonaPreset } {
  const containingMetro = region.presets
    .filter(
      (p) =>
        pointInBbox(origin[0], origin[1], p.bbox) &&
        pointInBbox(destination[0], destination[1], p.bbox)
    )
    .sort((a, b) => presetArea(b.bbox) - presetArea(a.bbox));
  const containingTiles = (region.tiles ?? []).filter(
    (p) =>
      pointInBbox(origin[0], origin[1], p.bbox) &&
      pointInBbox(destination[0], destination[1], p.bbox)
  );

  const bootstrappedMetro = firstBootstrapped(containingMetro, bootstrapped);
  if (bootstrappedMetro) {
    return { aoiId: bootstrappedMetro.aoi_id, preset: bootstrappedMetro };
  }
  const bootstrappedTile = firstBootstrapped(containingTiles, bootstrapped);
  if (bootstrappedTile) {
    return { aoiId: bootstrappedTile.aoi_id, preset: bootstrappedTile };
  }
  if (containingMetro.length > 0) {
    return { aoiId: containingMetro[0].aoi_id, preset: containingMetro[0] };
  }
  if (containingTiles.length > 0) {
    return { aoiId: containingTiles[0].aoi_id, preset: containingTiles[0] };
  }

  const fallback = resolvePresetForPoint(origin[0], origin[1], region, bootstrapped);
  return { aoiId: fallback.aoi_id, preset: fallback };
}
