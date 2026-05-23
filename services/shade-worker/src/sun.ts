import SunCalc from "suncalc";

/** Match geo-core NIGHT_UNIFORM_SHADE */
export const NIGHT_UNIFORM_SHADE = 1.0;

export function isSunBelowHorizon(datetime: string | Date, lat: number, lng: number): boolean {
  const date = typeof datetime === "string" ? new Date(datetime) : datetime;
  const pos = SunCalc.getPosition(date, lat, lng);
  return pos.altitude <= 0;
}
