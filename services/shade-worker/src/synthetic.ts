import type { LngLat, ShadeProfilePoint } from "@umbrastride/shared-types";
import { isSunBelowHorizon, NIGHT_UNIFORM_SHADE } from "./sun.js";

/**
 * Synthetic shade aligned with scripts/seed_demo_cache.py (_synthetic_shade).
 * Deterministic demo data — not measured building shadows.
 */
export function syntheticShadeFraction(
  lng: number,
  lat: number,
  hour: number,
  bearingDeg: number | null,
  datetime: string
): number {
  if (isSunBelowHorizon(datetime, lat, lng)) {
    return NIGHT_UNIFORM_SHADE;
  }

  const sunAz = 180.0 + (hour - 12) * 15.0;
  const sunRad = (sunAz * Math.PI) / 180;
  let base = 0.28 + 0.1 * Math.cos(((hour - 12) * 20 * Math.PI) / 180);

  let streetFactor: number;
  if (bearingDeg !== null) {
    const seg = (bearingDeg * Math.PI) / 180;
    const align = Math.abs(Math.cos(seg - sunRad));
    streetFactor = 0.42 * align;
  } else {
    streetFactor = 0.18 * Math.abs(Math.sin(lng * 1000 + lat * 1000));
  }

  const corridor = 0.22 * Math.sin((lng + 112.08) * 9500 + hour * 0.7);
  const crossStreet = 0.18 * Math.cos((lat - 33.45) * 11000 - hour * 0.4);

  return Math.max(0.04, Math.min(0.96, base + streetFactor + corridor + crossStreet));
}

export function syntheticShadeProfile(
  points: LngLat[],
  datetime: string
): ShadeProfilePoint[] {
  const hour = new Date(datetime).getUTCHours();
  return points.map((p) => {
    const sf = syntheticShadeFraction(p.lng, p.lat, hour, null, datetime);
    return { lng: p.lng, lat: p.lat, inShade: sf > 0.5 };
  });
}
