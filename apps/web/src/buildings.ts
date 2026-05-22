import type maplibregl from "maplibre-gl";
import osmtogeojson from "osmtogeojson";
import { OPENFREEMAP_SOURCE_ID } from "./mapStyle";

/** Match MapLibre 3D buildings example minzoom. */
export const SHADE_MIN_ZOOM = 15;

const MIN_ZOOM = SHADE_MIN_ZOOM;
const DEFAULT_HEIGHT_M = 3;
const LEVEL_HEIGHT_M = 3;

export type BuildingFeature = GeoJSON.Feature<
  GeoJSON.Polygon | GeoJSON.MultiPolygon,
  Record<string, unknown>
>;

function parseHeightMeters(props: Record<string, unknown>): number {
  const render = props.render_height;
  if (typeof render === "number" && render > 0) return render;
  if (typeof render === "string") {
    const n = parseFloat(render);
    if (!Number.isNaN(n) && n > 0) return n;
  }

  const h = props.height ?? props["building:height"];
  if (typeof h === "string") {
    const n = parseFloat(h.replace(/m$/i, "").trim());
    if (!Number.isNaN(n)) return n > 50 ? n / 10 : n;
  }
  if (typeof h === "number") {
    return h > 50 ? h / 10 : h;
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

/** Wait until MapLibre has loaded vector tiles (needed for querySourceFeatures). */
export async function waitForMapLoaded(map: maplibregl.Map): Promise<void> {
  if (map.loaded()) return;
  await new Promise<void>((resolve) => {
    const onRender = () => {
      if (!map.loaded()) return;
      map.off("render", onRender);
      resolve();
    };
    map.on("render", onRender);
    onRender();
  });
}

/** OpenFreeMap planet building layer (same as MapLibre 3D example). */
export async function fetchOpenFreeMapBuildings(
  map: maplibregl.Map
): Promise<BuildingFeature[]> {
  if (map.getZoom() < MIN_ZOOM) return [];
  if (!map.getSource(OPENFREEMAP_SOURCE_ID)) return [];

  await waitForMapLoaded(map);

  const raw = map.querySourceFeatures(OPENFREEMAP_SOURCE_ID, {
    sourceLayer: "building",
  });

  const features: GeoJSON.Feature[] = [];
  const seen = new Set<string>();

  for (const f of raw) {
    if (!f.geometry || f.properties?.underground === "true") continue;
    if (f.properties?.hide_3d === true) continue;
    if (f.geometry.type !== "Polygon" && f.geometry.type !== "MultiPolygon") continue;

    const props = f.properties as Record<string, unknown> | null;
    if (!props?.render_height && !props?.height) continue;

    const id = String(f.id ?? props.id ?? features.length);
    if (seen.has(id)) continue;
    seen.add(id);

    const heightM = parseHeightMeters(props);
    features.push({
      type: "Feature",
      geometry: f.geometry,
      properties: { ...props, height: heightM, render_height: heightM },
    });
  }

  features.sort((a, b) => {
    const ha = parseHeightMeters((a.properties ?? {}) as Record<string, unknown>);
    const hb = parseHeightMeters((b.properties ?? {}) as Record<string, unknown>);
    return ha - hb;
  });

  return normalizeBuildingFeatures(features);
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

  await waitForMapLoaded(map);

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

  if (map.getSource(OPENFREEMAP_SOURCE_ID)) {
    const fromOfm = await fetchOpenFreeMapBuildings(map);
    if (fromOfm.length > 0) return fromOfm;
  }

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
