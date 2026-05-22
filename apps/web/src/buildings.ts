import type maplibregl from "maplibre-gl";
import osmtogeojson from "osmtogeojson";

const MIN_ZOOM = 15;
const DEFAULT_HEIGHT_M = 3;
const LEVEL_HEIGHT_M = 3;

export type BuildingFeature = GeoJSON.Feature<
  GeoJSON.Polygon | GeoJSON.MultiPolygon,
  Record<string, unknown>
>;

function parseHeightMeters(props: Record<string, unknown>): number {
  const h = props.height ?? props["building:height"];
  if (typeof h === "string") {
    const n = parseFloat(h.replace(/m$/i, "").trim());
    if (!Number.isNaN(n)) return n;
  }
  if (typeof h === "number") return h;

  const render = props.render_height;
  if (typeof render === "number") return render;
  if (typeof render === "string") {
    const n = parseFloat(render);
    if (!Number.isNaN(n)) return n;
  }

  const levels = props["building:levels"] ?? props.levels;
  if (typeof levels === "string" || typeof levels === "number") {
    const n = parseInt(String(levels), 10);
    if (!Number.isNaN(n)) return n * LEVEL_HEIGHT_M;
  }

  return DEFAULT_HEIGHT_M;
}

function normalizeBuildingFeatures(features: GeoJSON.Feature[]): BuildingFeature[] {
  const out: BuildingFeature[] = [];
  for (const f of features) {
    if (!f.geometry) continue;
    if (f.geometry.type !== "Polygon" && f.geometry.type !== "MultiPolygon") continue;
    const props = { ...(f.properties ?? {}) };
    const height = parseHeightMeters(props);
    props.height = height;
    props.render_height = height;
    out.push({
      type: "Feature",
      geometry: f.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon,
      properties: props,
    });
  }
  return out;
}

/** Fetch OSM buildings in viewport via Overpass (free, global). */
export async function fetchOverpassBuildings(
  map: maplibregl.Map
): Promise<BuildingFeature[]> {
  if (map.getZoom() < MIN_ZOOM) return [];

  const bounds = map.getBounds();
  const south = bounds.getSouth();
  const west = bounds.getWest();
  const north = bounds.getNorth();
  const east = bounds.getEast();

  const query = `
[out:json][timeout:25];
(
  way["building"](${south},${west},${north},${east});
);
out body;
>;
out skel qt;
`;

  const url = `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Overpass error: ${res.status}`);
  const osmJson = await res.json();
  const geojson = osmtogeojson(osmJson) as GeoJSON.FeatureCollection;
  return normalizeBuildingFeatures(geojson.features);
}

/** Mapbox vector building footprints (needs style with composite/building layer). */
export async function fetchMapboxBuildings(
  map: maplibregl.Map
): Promise<BuildingFeature[]> {
  if (map.getZoom() < MIN_ZOOM) return [];

  await new Promise<void>((resolve) => {
    if (map.isStyleLoaded()) resolve();
    else map.once("idle", () => resolve());
  });

  const features = map.querySourceFeatures("composite", {
    sourceLayer: "building",
  });

  const normalized: BuildingFeature[] = [];
  for (const f of features) {
    if (!f.geometry || f.properties?.underground === "true") continue;
    if (f.geometry.type !== "Polygon" && f.geometry.type !== "MultiPolygon") continue;
    const props = { ...f.properties } as Record<string, unknown>;
    const height = parseHeightMeters(props);
    props.height = height;
    props.render_height = height;
    normalized.push({
      type: "Feature",
      geometry: f.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon,
      properties: props,
    });
  }
  return normalized;
}

export async function fetchBuildingsForMap(
  map: maplibregl.Map,
  mapboxToken?: string
): Promise<BuildingFeature[]> {
  if (map.getZoom() < MIN_ZOOM) return [];

  if (mapboxToken && map.getSource("composite")) {
    try {
      const fromMapbox = await fetchMapboxBuildings(map);
      if (fromMapbox.length > 0) return fromMapbox;
    } catch {
      // fall through to Overpass
    }
  }

  return fetchOverpassBuildings(map);
}

export const SHADE_MIN_ZOOM = MIN_ZOOM;
