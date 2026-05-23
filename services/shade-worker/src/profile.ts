import type { LngLat, ShadeProfilePoint } from "@umbrastride/shared-types";
import { buildingAwareShadeProfile } from "./building-shade.js";
import { syntheticShadeProfile } from "./synthetic.js";

export type ProfileMode = "synthetic" | "building-aware";

export function resolveProfileMode(): ProfileMode {
  if (process.env.SHADEMAP_API_KEY?.trim()) {
    return "building-aware";
  }
  return "synthetic";
}

/**
 * Profile shade for a batch of points at a datetime.
 */
export async function profileShade(
  points: LngLat[],
  datetime: string
): Promise<{ results: ShadeProfilePoint[]; mode: ProfileMode }> {
  const mode = resolveProfileMode();
  if (mode === "building-aware") {
    const results = await buildingAwareShadeProfile(points, datetime);
    return { results, mode };
  }
  return { results: syntheticShadeProfile(points, datetime), mode: "synthetic" };
}

/** @deprecated use profileShade */
export function mockShadeProfile(points: LngLat[], datetime: string): ShadeProfilePoint[] {
  return syntheticShadeProfile(points, datetime);
}
