import type { LngLat, ShadeProfilePoint } from "@umbrastride/shared-types";

/**
 * Mock sun/shade profile (deterministic). Replace with Playwright+ShadeMap when SHADEMAP_API_KEY is set.
 */
export function mockShadeProfile(points: LngLat[], datetime: string): ShadeProfilePoint[] {
  const hour = new Date(datetime).getUTCHours();
  const sunAz = ((hour - 12) * 15 * Math.PI) / 180;
  return points.map((p) => {
    const latFactor = Math.sin(p.lat * 120);
    const lngFactor = Math.cos(p.lng * 80 + sunAz);
    const shadeScore = 0.5 + 0.35 * latFactor + 0.25 * lngFactor;
    return { lng: p.lng, lat: p.lat, inShade: shadeScore > 0.55 };
  });
}
