import type { LngLat } from "@umbrastride/shared-types";

export type BuildingFootprint = {
  ring: [number, number][];
  heightM: number;
};

function parseHeightM(tags: Record<string, string> | undefined): number {
  if (!tags) return 3;
  const render = tags.render_height ?? tags.height ?? tags["building:height"];
  if (render) {
    const n = parseFloat(String(render).replace(/m$/i, "").trim());
    if (!Number.isNaN(n) && n > 0) return n > 50 ? n / 10 : n;
  }
  const levels = tags["building:levels"] ?? tags.levels;
  if (levels) {
    const n = parseInt(String(levels), 10);
    if (!Number.isNaN(n)) return n * 3;
  }
  return 3;
}

function bboxOfPoints(points: LngLat[], padDeg = 0.002): [number, number, number, number] {
  let west = points[0].lng;
  let east = points[0].lng;
  let south = points[0].lat;
  let north = points[0].lat;
  for (const p of points) {
    west = Math.min(west, p.lng);
    east = Math.max(east, p.lng);
    south = Math.min(south, p.lat);
    north = Math.max(north, p.lat);
  }
  return [west - padDeg, south - padDeg, east + padDeg, north + padDeg];
}

/**
 * Fetch OSM building footprints in bbox via Overpass.
 */
export async function fetchBuildingsInBbox(
  points: LngLat[]
): Promise<BuildingFootprint[]> {
  if (!points.length) return [];
  const [west, south, east, north] = bboxOfPoints(points);
  const query = `
[out:json][timeout:60];
way["building"](${south},${west},${north},${east});
out geom;
`;
  const url = "https://overpass-api.de/api/interpreter";
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `data=${encodeURIComponent(query)}`,
  });
  if (!resp.ok) {
    throw new Error(`Overpass HTTP ${resp.status}`);
  }
  const data = (await resp.json()) as {
    elements: Array<{
      type: string;
      tags?: Record<string, string>;
      geometry?: Array<{ lat: number; lon: number }>;
    }>;
  };

  const footprints: BuildingFootprint[] = [];
  for (const el of data.elements) {
    if (el.type !== "way" || !el.geometry?.length) continue;
    const ring: [number, number][] = el.geometry.map((g) => [g.lon, g.lat]);
    if (ring.length < 3) continue;
    footprints.push({
      ring,
      heightM: parseHeightM(el.tags),
    });
  }
  return footprints;
}
