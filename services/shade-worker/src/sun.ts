// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
import SunCalc from "suncalc";

/** Match geo-core NIGHT_UNIFORM_SHADE */
export const NIGHT_UNIFORM_SHADE = 1.0;

export type SunPosition = {
  altitudeDeg: number;
  azimuthDeg: number;
};

export function getSunPosition(datetime: string | Date, lat: number, lng: number): SunPosition {
  const date = typeof datetime === "string" ? new Date(datetime) : datetime;
  const pos = SunCalc.getPosition(date, lat, lng);
  return {
    altitudeDeg: (pos.altitude * 180) / Math.PI,
    azimuthDeg: (180 + (pos.azimuth * 180) / Math.PI + 360) % 360,
  };
}

export function isSunBelowHorizon(datetime: string | Date, lat: number, lng: number): boolean {
  return getSunPosition(datetime, lat, lng).altitudeDeg <= 0;
}
