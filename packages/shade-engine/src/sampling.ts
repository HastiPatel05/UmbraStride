// Copyright (c) 2026 Tanmay Godse and Hasti Pareshbhai Patel. All Rights Reserved.
import * as turf from "@turf/turf";
import type { Feature, LineString } from "geojson";

export type SamplePoint = { lng: number; lat: number; edgeKey: string; index: number };

export function sampleCountForLength(lengthM: number): number {
  return Math.max(5, Math.ceil(lengthM / 10));
}

export function sampleEdge(
  edgeKey: string,
  coordinates: [number, number][],
  lengthM: number
): SamplePoint[] {
  const line = turf.lineString(coordinates);
  const n = sampleCountForLength(lengthM);
  const points: SamplePoint[] = [];
  for (let i = 0; i < n; i++) {
    const distKm = (lengthM / 1000) * (n === 1 ? 0 : i / (n - 1));
    const pt = turf.along(line, distKm, { units: "kilometers" });
    const [lng, lat] = pt.geometry.coordinates;
    points.push({ lng, lat, edgeKey, index: i });
  }
  return points;
}

export function aggregateShadeFraction(
  samples: { index: number; inShade: boolean }[],
  total: number
): number {
  const shade = samples.filter((s) => s.inShade).length;
  return total > 0 ? shade / total : 0.5;
}

/** Group points into screen batches (simplified: fixed chunk size). */
export function chunkPoints<T>(items: T[], chunkSize: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += chunkSize) {
    chunks.push(items.slice(i, i + chunkSize));
  }
  return chunks;
}
