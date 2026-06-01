// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
/**
 * Geometric building shadow projection on flat ground (no ShadeMap).
 *
 * Each footprint is swept from its base to the projected roof footprint with a
 * fast convex hull. That avoids expensive browser-side polygon unions.
 */
import type { BuildingFeature } from "./buildings";
import { parseHeightMeters } from "./buildings";
import { metersPerDegree, shadowOffsetMeters, type SunPosition } from "./sun";

type LngLat = [number, number];
type Ring = LngLat[];
type PolyClipPolygon = Ring[];
type PolyClipMultiPolygon = PolyClipPolygon[];

const MIN_SHADOW_LENGTH_M = 0.25;
const MIN_ALTITUDE_RAD = 0.02;
const MAX_RING_POINTS = 36;

function openRing(ring: number[][]): Ring {
  if (ring.length === 0) return [];
  const out = ring.map(([lng, lat]) => [lng, lat] as LngLat);
  const first = out[0];
  const last = out[out.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) out.pop();
  return out;
}

function closeRing(ring: Ring): Ring {
  if (ring.length === 0) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return ring;
  return [...ring, first];
}

function ringCentroid(ring: Ring): LngLat {
  let lng = 0;
  let lat = 0;
  for (const [x, y] of ring) {
    lng += x;
    lat += y;
  }
  return [lng / ring.length, lat / ring.length];
}

function projectRing(ring: Ring, dLng: number, dLat: number): Ring {
  return ring.map(([lng, lat]) => [lng + dLng, lat + dLat] as LngLat);
}

function multiPolyToGeoJSON(
  mp: PolyClipMultiPolygon
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  if (mp.length === 0) return null;
  if (mp.length === 1) {
    return { type: "Polygon", coordinates: mp[0] };
  }
  return { type: "MultiPolygon", coordinates: mp };
}

function pointKey([lng, lat]: LngLat): string {
  return `${lng.toFixed(8)},${lat.toFixed(8)}`;
}

function cross(o: LngLat, a: LngLat, b: LngLat): number {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
}

function simplifyRing(ring: Ring, maxPoints = MAX_RING_POINTS): Ring {
  if (ring.length <= maxPoints) return ring;
  const step = ring.length / maxPoints;
  const simplified: Ring = [];
  for (let i = 0; i < maxPoints; i++) {
    simplified.push(ring[Math.floor(i * step)]);
  }
  return simplified;
}

function convexHull(points: Ring): Ring {
  const byKey = new Map<string, LngLat>();
  for (const p of points) byKey.set(pointKey(p), p);
  const sorted = [...byKey.values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (sorted.length < 3) return [];

  const lower: Ring = [];
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
      lower.pop();
    }
    lower.push(p);
  }

  const upper: Ring = [];
  for (let i = sorted.length - 1; i >= 0; i--) {
    const p = sorted[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
      upper.pop();
    }
    upper.push(p);
  }

  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

/** Fast swept footprint approximation for one ring → ground shadow polygon. */
export function shadowMultiPolygonForRing(
  ring: number[][],
  heightM: number,
  centerLat: number,
  sun: SunPosition
): PolyClipMultiPolygon | null {
  if (sun.belowHorizon || sun.altitudeRad <= MIN_ALTITUDE_RAD || heightM <= 0) {
    return null;
  }

  const base = openRing(ring);
  if (base.length < 3) return null;

  const { east, north, lengthM } = shadowOffsetMeters(
    heightM,
    sun.altitudeRad,
    sun.azimuthRad
  );
  if (lengthM < MIN_SHADOW_LENGTH_M) return null;

  const scale = metersPerDegree(centerLat);
  const dLng = east / scale.lng;
  const dLat = north / scale.lat;
  const simplifiedBase = simplifyRing(base);
  const roof = projectRing(simplifiedBase, dLng, dLat);
  const hull = convexHull([...simplifiedBase, ...roof]);

  return hull.length >= 3 ? [[closeRing(hull)]] : null;
}

function shadowGeometryForPolygon(
  coordinates: number[][][],
  heightM: number,
  sun: SunPosition
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  const outer = coordinates[0];
  if (!outer) return null;
  const base = openRing(outer);
  if (base.length < 3) return null;
  const [, cLat] = ringCentroid(base);
  const part = shadowMultiPolygonForRing(outer, heightM, cLat, sun);
  return part ? multiPolyToGeoJSON(part) : null;
}

function shadowGeometryForBuilding(
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon,
  heightM: number,
  sun: SunPosition
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  if (geometry.type === "Polygon") {
    return shadowGeometryForPolygon(geometry.coordinates, heightM, sun);
  }

  const polygons: PolyClipMultiPolygon = [];
  for (const poly of geometry.coordinates) {
    const part = shadowGeometryForPolygon(poly, heightM, sun);
    if (!part) continue;
    if (part.type === "Polygon") {
      polygons.push(part.coordinates as PolyClipPolygon);
    } else {
      polygons.push(...(part.coordinates as PolyClipMultiPolygon));
    }
  }

  return multiPolyToGeoJSON(polygons);
}

/** Project building footprints into ground shadow polygons (no external API). */
export function buildingShadowsGeoJSON(
  buildings: BuildingFeature[],
  sun: SunPosition
): GeoJSON.FeatureCollection {
  if (sun.belowHorizon) {
    return { type: "FeatureCollection", features: [] };
  }

  const features: GeoJSON.Feature[] = [];

  for (const b of buildings) {
    if (!b.geometry) continue;
    const props = (b.properties ?? {}) as Record<string, unknown>;
    const heightM = parseHeightMeters(props);

    try {
      const geometry = shadowGeometryForBuilding(b.geometry, heightM, sun);
      if (!geometry) continue;

      const { lengthM } = shadowOffsetMeters(heightM, sun.altitudeRad, sun.azimuthRad);

      features.push({
        type: "Feature",
        properties: { height_m: heightM, shadow_length_m: lengthM },
        geometry,
      });
    } catch (e) {
      console.debug("Skip building shadow:", e);
    }
  }

  return { type: "FeatureCollection", features };
}
