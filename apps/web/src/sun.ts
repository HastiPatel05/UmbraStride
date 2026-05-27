/**
 * Sun position for map shadows (browser).
 * Backend routing uses Python `astral` in umbrastride_geo.sun — same astronomy, different library.
 */
import SunCalc from "suncalc";

export type SunPosition = {
  altitudeRad: number;
  azimuthRad: number;
  altitudeDeg: number;
  belowHorizon: boolean;
};

/** Solar position at a point. SunCalc azimuth: 0 = south, π/2 = west. */
export function getSunPosition(datetime: string | Date, lat: number, lng: number): SunPosition {
  const date = typeof datetime === "string" ? new Date(datetime) : datetime;
  const pos = SunCalc.getPosition(date, lat, lng);
  const altitudeDeg = (pos.altitude * 180) / Math.PI;
  return {
    altitudeRad: pos.altitude,
    azimuthRad: pos.azimuth,
    altitudeDeg,
    belowHorizon: pos.altitude <= 0,
  };
}

export function isSunBelowHorizon(datetime: string | Date, lat: number, lng: number): boolean {
  return getSunPosition(datetime, lat, lng).belowHorizon;
}

/** Meters per degree at latitude (approx WGS84). */
export function metersPerDegree(lat: number): { lng: number; lat: number } {
  const latM = 111_320;
  return { lat: latM, lng: latM * Math.cos((lat * Math.PI) / 180) };
}

/** Shadow cast direction in meters (east, north) from building height and sun position. */
export function shadowOffsetMeters(
  heightM: number,
  altitudeRad: number,
  azimuthRad: number
): { east: number; north: number; lengthM: number } {
  if (altitudeRad <= 0.02 || heightM <= 0) {
    return { east: 0, north: 0, lengthM: 0 };
  }
  const lengthM = heightM / Math.tan(altitudeRad);
  // SunCalc azimuth uses 0=south and positive toward west. In east/north
  // meters, the ground shadow vector is [sin(azimuth), cos(azimuth)].
  const east = lengthM * Math.sin(azimuthRad);
  const north = lengthM * Math.cos(azimuthRad);
  return { east, north, lengthM };
}
