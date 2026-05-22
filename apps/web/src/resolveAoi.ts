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

/** Widest metro preset containing the point (e.g. Phoenix metro over downtown core). */
export function resolvePresetForPoint(
  lng: number,
  lat: number,
  region: ArizonaRegion,
  bootstrapped?: Set<string>
): ArizonaPreset {
  const containing = presetsContainingPoint(lng, lat, region);
  if (bootstrapped) {
    for (const p of containing) {
      if (bootstrapped.has(p.aoi_id)) return p;
    }
  }
  if (containing.length > 0) return containing[0];
  return nearestPreset(lng, lat, region.presets);
}

/**
 * Pick widest metro preset that contains both points (Phoenix metro over downtown).
 * Prefers bootstrapped graphs when available.
 */
export function resolveAoiForRoute(
  origin: [number, number],
  destination: [number, number],
  region: ArizonaRegion,
  bootstrapped: Set<string>
): { aoiId: string; preset: ArizonaPreset } {
  const containing = region.presets
    .filter(
      (p) =>
        pointInBbox(origin[0], origin[1], p.bbox) &&
        pointInBbox(destination[0], destination[1], p.bbox)
    )
    .sort((a, b) => presetArea(b.bbox) - presetArea(a.bbox));

  for (const p of containing) {
    if (bootstrapped.has(p.aoi_id)) {
      return { aoiId: p.aoi_id, preset: p };
    }
  }
  if (containing.length > 0) {
    return { aoiId: containing[0].aoi_id, preset: containing[0] };
  }

  const fallback = resolvePresetForPoint(origin[0], origin[1], region, bootstrapped);
  return { aoiId: fallback.aoi_id, preset: fallback };
}
