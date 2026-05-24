import SunCalc from "suncalc";
import type { LngLat, ShadeProfilePoint } from "@umbrastride/shared-types";
import { fetchBuildingsInBbox, type BuildingFootprint } from "./buildings.js";
import { syntheticShadeFraction } from "./synthetic.js";

function pointInRing(lng: number, lat: number, ring: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect =
      yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-12) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function rayHitsBuilding(
  lng: number,
  lat: number,
  sunAzimuth: number,
  sunAltitude: number,
  buildings: BuildingFootprint[]
): boolean {
  if (sunAltitude <= 0) return true;

  const sunDx = Math.sin(sunAzimuth);
  const sunDy = Math.cos(sunAzimuth);
  const maxDistDeg = 0.003;
  const steps = 8;

  for (let s = 1; s <= steps; s++) {
    const t = (s / steps) * maxDistDeg;
    const sx = lng + sunDx * t;
    const sy = lat + sunDy * t;

    for (const b of buildings) {
      if (!pointInRing(sx, sy, b.ring)) continue;
      const horizDist = t * 111_000;
      const requiredAlt = Math.atan2(b.heightM, Math.max(horizDist, 1));
      if (sunAltitude < requiredAlt) {
        return true;
      }
    }
  }
  return false;
}

let buildingCache: { key: string; buildings: BuildingFootprint[] } | null = null;

function cacheKey(points: LngLat[]): string {
  const west = Math.min(...points.map((p) => p.lng));
  const east = Math.max(...points.map((p) => p.lng));
  const south = Math.min(...points.map((p) => p.lat));
  const north = Math.max(...points.map((p) => p.lat));
  return `${west.toFixed(4)},${south.toFixed(4)},${east.toFixed(4)},${north.toFixed(4)}`;
}

async function getBuildings(points: LngLat[]): Promise<BuildingFootprint[]> {
  const key = cacheKey(points);
  if (buildingCache?.key === key) return buildingCache.buildings;
  const buildings = await fetchBuildingsInBbox(points);
  buildingCache = { key, buildings };
  return buildings;
}

/**
 * Building-aware shade using OSM footprints + sun position (Overpass + SunCalc).
 * More realistic than pure synthetic, with no ShadeMap API dependency.
 */
export async function buildingAwareShadeProfile(
  points: LngLat[],
  datetime: string
): Promise<ShadeProfilePoint[]> {
  const date = new Date(datetime);
  const hour = date.getUTCHours();
  const buildings = await getBuildings(points);

  return points.map((p) => {
    const sun = SunCalc.getPosition(date, p.lat, p.lng);
    const altitude = sun.altitude;
    const azimuth = sun.azimuth + Math.PI;

    let inShade: boolean;
    if (altitude <= 0) {
      inShade = true;
    } else if (buildings.length === 0) {
      const sf = syntheticShadeFraction(p.lng, p.lat, hour, null, datetime);
      inShade = sf > 0.5;
    } else {
      inShade = rayHitsBuilding(p.lng, p.lat, azimuth, altitude, buildings);
    }

    return { lng: p.lng, lat: p.lat, inShade };
  });
}
