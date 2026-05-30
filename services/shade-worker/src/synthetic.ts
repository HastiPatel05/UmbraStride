import type { LngLat, ShadeProfilePoint } from "@umbrastride/shared-types";
import { getSunPosition, NIGHT_UNIFORM_SHADE } from "./sun.js";

/**
 * Synthetic shade aligned with scripts/seed_demo_cache.py (_synthetic_shade).
 * Deterministic demo data — not measured building shadows.
 */
export function syntheticShadeFraction(
  lng: number,
  lat: number,
  bearingDeg: number | null,
  datetime: string
): number {
  const sun = getSunPosition(datetime, lat, lng);
  if (sun.altitudeDeg <= 0) {
    return NIGHT_UNIFORM_SHADE;
  }

  const date = new Date(datetime);
  const utcHour =
    date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
  const sunRad = (sun.azimuthDeg * Math.PI) / 180;
  const altitudeFactor = 1 - Math.min(Math.max(sun.altitudeDeg, 0), 75) / 75;
  const base = 0.18 + 0.22 * altitudeFactor;

  let streetFactor: number;
  if (bearingDeg !== null) {
    const seg = (bearingDeg * Math.PI) / 180;
    const align = Math.abs(Math.cos(seg - sunRad));
    streetFactor = 0.42 * align;
  } else {
    streetFactor = 0.18 * Math.abs(Math.sin(lng * 1000 + lat * 1000));
  }

  const corridor = 0.2 * Math.sin((lng + 112.08) * 9500 + sunRad * 1.7 + utcHour * 0.03);
  const crossStreet = 0.16 * Math.cos((lat - 33.45) * 11000 - sunRad * 1.3);

  return Math.max(0.04, Math.min(0.96, base + streetFactor + corridor + crossStreet));
}

export function syntheticShadeProfile(
  points: LngLat[],
  datetime: string
): ShadeProfilePoint[] {
  return points.map((p) => {
    const sf = syntheticShadeFraction(p.lng, p.lat, null, datetime);
    return { lng: p.lng, lat: p.lat, inShade: sf > 0.5 };
  });
}
