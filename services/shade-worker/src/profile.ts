// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
import type { LngLat, ShadeProfilePoint } from "@umbrastride/shared-types";
import { buildingAwareShadeProfile } from "./building-shade.js";
import { syntheticShadeProfile } from "./synthetic.js";

export type ProfileMode = "synthetic" | "building-aware";

export function resolveProfileMode(): ProfileMode {
  const mode = process.env.SHADE_PROFILE_MODE?.trim().toLowerCase();
  if (mode === "building-aware" || mode === "buildings" || mode === "osm") {
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
