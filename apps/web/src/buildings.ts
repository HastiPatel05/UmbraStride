import type maplibregl from "maplibre-gl";
import osmtogeojson from "osmtogeojson";
import { BUILDINGS_3D_LAYER_ID, OPENFREEMAP_SOURCE_ID } from "./mapStyle";

/** Match MapLibre 3D buildings example minzoom. */
export const SHADE_MIN_ZOOM = 15;

const MIN_ZOOM = SHADE_MIN_ZOOM;
const DEFAULT_HEIGHT_M = 3;
const LEVEL_HEIGHT_M = 3;

export type BuildingFeature = GeoJSON.Feature<
  GeoJSON.Polygon | GeoJSON.MultiPolygon,
  Record<string, unknown>
>;

export function parseHeightMeters(props: Record<string, unknown>): number {
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

/** Normalize footprints for deterministic local shadow projection. */
export function toShadowBuildingFeatures(features: BuildingFeature[]): BuildingFeature[] {
  const sorted = [...features].sort(
    (a, b) =>
      parseHeightMeters((a.properties ?? {}) as Record<string, unknown>) -
      parseHeightMeters((b.properties ?? {}) as Record<string, unknown>)
  );
  return sorted.map((f) => {
    const props = { ...(f.properties ?? {}) };
    const height = parseHeightMeters(props);
    props.height = height;
    props.render_height = height;
    return { ...f, properties: props };
  });
}

/** Wait until the style object can accept/query layers. */
export async function waitForMapStyleReady(map: maplibregl.Map): Promise<void> {
  if (map.isStyleLoaded()) return;
  await new Promise<void>((resolve) => {
    const cleanup = () => {
      map.off("load", check);
      map.off("styledata", check);
      map.off("idle", check);
    };
    const check = () => {
      if (map.isStyleLoaded()) {
        cleanup();
        resolve();
      }
    };
    map.on("load", check);
    map.on("styledata", check);
    map.on("idle", check);
    check();
  });
}

/** Wait until MapLibre has finished loading/rendering (needed for queryRenderedFeatures). */
export async function waitForMapLoaded(
  map: maplibregl.Map,
  maxWaitMs = 3500
): Promise<void> {
  await waitForMapStyleReady(map);
  if (map.loaded()) return;

  await new Promise<void>((resolve) => {
    let done = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const cleanup = () => {
      map.off("idle", finish);
      map.off("load", checkLoaded);
      map.off("render", checkLoaded);
      map.off("sourcedata", checkLoaded);
      if (timeoutId) clearTimeout(timeoutId);
    };
    const finish = () => {
      if (done) return;
      done = true;
      cleanup();
      resolve();
    };
    const checkLoaded = () => {
      if (map.loaded()) finish();
    };

    timeoutId = setTimeout(finish, maxWaitMs);
    map.on("idle", finish);
    map.on("load", checkLoaded);
    map.on("render", checkLoaded);
    map.on("sourcedata", checkLoaded);
    map.triggerRepaint();
    checkLoaded();
  });
}

function featureCentroid(f: GeoJSON.Feature): [number, number] | null {
  const g = f.geometry;
  if (!g) return null;
  if (g.type === "Point") return g.coordinates as [number, number];
  if (g.type === "Polygon") {
    const ring = g.coordinates[0];
    if (!ring?.length) return null;
    let lng = 0;
    let lat = 0;
    const n = ring.length > 1 ? ring.length - 1 : ring.length;
    for (let i = 0; i < n; i++) {
      lng += ring[i][0];
      lat += ring[i][1];
    }
    return [lng / n, lat / n];
  }
  if (g.type === "MultiPolygon") {
    const ring = g.coordinates[0]?.[0];
    if (!ring?.length) return null;
    return [ring[0][0], ring[0][1]];
  }
  return null;
}

function featureKey(f: BuildingFeature): string {
  const props = (f.properties ?? {}) as Record<string, unknown>;
  const explicitId = f.id ?? props.id ?? props.osm_id;
  if (explicitId) return String(explicitId);

  const c = featureCentroid(f);
  const height = parseHeightMeters(props).toFixed(1);
  if (c) return `${f.geometry.type}:${c[0].toFixed(6)},${c[1].toFixed(6)}:${height}`;

  const ring =
    f.geometry.type === "Polygon"
      ? f.geometry.coordinates[0]
      : f.geometry.coordinates[0]?.[0];
  const first = ring?.[0];
  return first
    ? `${f.geometry.type}:${first[0].toFixed(6)},${first[1].toFixed(6)}:${height}`
    : `${f.geometry.type}:${height}`;
}

function featureInMapBounds(map: maplibregl.Map, f: GeoJSON.Feature): boolean {
  const c = featureCentroid(f);
  if (!c) return false;
  const b = map.getBounds();
  return (
    c[1] >= b.getSouth() &&
    c[1] <= b.getNorth() &&
    c[0] >= b.getWest() &&
    c[0] <= b.getEast()
  );
}

function buildingSourceId(map: maplibregl.Map): string | null {
  if (map.getSource(OPENFREEMAP_SOURCE_ID)) return OPENFREEMAP_SOURCE_ID;
  const layer = map.getLayer(BUILDINGS_3D_LAYER_ID);
  if (layer && "source" in layer && typeof layer.source === "string") {
    return layer.source;
  }
  return null;
}

/** Buildings currently drawn on screen (best match for visible 3D extrusions). */
export async function fetchRendered3dBuildings(
  map: maplibregl.Map
): Promise<BuildingFeature[]> {
  if (map.getZoom() < MIN_ZOOM) return [];
  if (!map.getLayer(BUILDINGS_3D_LAYER_ID)) return [];

  await waitForMapLoaded(map);

  const raw = map.queryRenderedFeatures(undefined, {
    layers: [BUILDINGS_3D_LAYER_ID],
  });

  const features: GeoJSON.Feature[] = [];
  const seen = new Set<string>();

  for (const f of raw) {
    if (!f.geometry) continue;
    if (f.geometry.type !== "Polygon" && f.geometry.type !== "MultiPolygon") continue;
    if (f.properties?.underground === "true" || f.properties?.hide_3d === true) continue;

    const props = (f.properties ?? {}) as Record<string, unknown>;
    const id = String(f.id ?? props.id ?? `${features.length}`);
    if (seen.has(id)) continue;
    seen.add(id);

    features.push({
      type: "Feature",
      geometry: f.geometry,
      properties: { ...props },
    });
  }

  return normalizeBuildingFeatures(features);
}

/** OpenFreeMap planet building layer (vector tile query). */
export async function fetchOpenFreeMapBuildings(
  map: maplibregl.Map
): Promise<BuildingFeature[]> {
  if (map.getZoom() < MIN_ZOOM) return [];
  const sourceId = buildingSourceId(map);
  if (!sourceId) return [];

  await waitForMapLoaded(map);

  const raw = map.querySourceFeatures(sourceId, {
    sourceLayer: "building",
  });

  const features: GeoJSON.Feature[] = [];
  const seen = new Set<string>();

  for (const f of raw) {
    if (!f.geometry || f.properties?.underground === "true") continue;
    if (f.properties?.hide_3d === true) continue;
    if (f.geometry.type !== "Polygon" && f.geometry.type !== "MultiPolygon") continue;
    if (!featureInMapBounds(map, f as GeoJSON.Feature)) continue;

    const props = (f.properties ?? {}) as Record<string, unknown>;
    const id = String(f.id ?? props.id ?? features.length);
    if (seen.has(id)) continue;
    seen.add(id);

    features.push({
      type: "Feature",
      geometry: f.geometry,
      properties: { ...props },
    });
  }

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

  const endpoints = [
    `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`,
    `https://overpass.kumi.systems/api/interpreter?data=${encodeURIComponent(query)}`,
  ];

  let lastErr: Error | null = null;
  for (const url of endpoints) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    try {
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) throw new Error(`Overpass error: ${res.status}`);
      const osmJson = await res.json();
      const geojson = osmtogeojson(osmJson) as GeoJSON.FeatureCollection;
      return normalizeBuildingFeatures(geojson.features);
    } catch (e) {
      lastErr = e instanceof Error ? e : new Error(String(e));
    } finally {
      window.clearTimeout(timeout);
    }
  }
  throw lastErr ?? new Error("Overpass unavailable");
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

function mergeBuildingLists(lists: BuildingFeature[][]): BuildingFeature[] {
  const byId = new Map<string, BuildingFeature>();
  for (const list of lists) {
    for (const f of list) {
      const props = (f.properties ?? {}) as Record<string, unknown>;
      const id = featureKey(f);
      const existing = byId.get(id);
      if (!existing) {
        byId.set(id, f);
        continue;
      }
      const hNew = parseHeightMeters(props);
      const hOld = parseHeightMeters((existing.properties ?? {}) as Record<string, unknown>);
      if (hNew > hOld) byId.set(id, f);
    }
  }
  return toShadowBuildingFeatures([...byId.values()]);
}

export async function fetchBuildingsForMap(
  map: maplibregl.Map,
  mapboxToken?: string,
  options: { includeOverpass?: boolean } = {}
): Promise<BuildingFeature[]> {
  if (map.getZoom() < MIN_ZOOM) return [];

  const localTasks: Promise<BuildingFeature[]>[] = [
    fetchOpenFreeMapBuildings(map).catch(() => []),
    fetchRendered3dBuildings(map).catch(() => []),
  ];

  if (mapboxToken && map.getSource("composite")) {
    localTasks.push(
      fetchMapboxBuildings(map).catch(() => [])
    );
  }

  const localResults = await Promise.all(localTasks);
  const localMerged = mergeBuildingLists(localResults);
  if (localMerged.length > 0 && !options.includeOverpass) return localMerged;

  try {
    return mergeBuildingLists([localMerged, await fetchOverpassBuildings(map)]);
  } catch (e) {
    console.warn("Overpass building fetch failed:", e);
    return localMerged;
  }
}
